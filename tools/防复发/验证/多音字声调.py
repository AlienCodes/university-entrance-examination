"""双向验证：配音发音（含多音字声调），铁律 23（用户 2026-11-03：“空格”被读成 kōng，应为 kòng gé）。要识别模型与 librosa（needs tts）。
  ① 预检：现在的讲解稿 0 处；从登记表里拿掉“带着”→ 必须报出；
  ② 读音修正：送进模型的“空格”变成“控格”，画面 / 稿文字不变；
  ③ 声调核查：第 3 轮 r2icl（“所以空格这里”的“空”读成一声，降幅 0.0）必须报出；第 2 版样片（读对了，降幅 8.3）0 处；
  ④ 入口：qwen_synth 送模型前走 model_text；讲解音频.render 调 check_items；选段 调 tone_problems。
    /opt/ttsenv/bin/python tools/防复发/验证/多音字声调.py"""
import json
import sys
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tools/tts'), str(ROOT / '高考语法填空/tools')]
import 多音字 as D  # noqa: E402
import 讲解节奏 as NJ  # noqa: E402

bad = []
doc = json.loads((ROOT / '高考语法填空/稿/2026_新课标Ⅰ卷.json').read_text('utf-8'))
texts = [(s['id'], s['text'].replace('‖', '')) for s in doc['segments'] if s['lang'] == 'Chinese']
e0 = D.preflight(texts)[1]
tb = D._table()
orig = D._table
D._table = lambda: {k: v for k, v in tb.items() if k != '带着'}
e1 = D.preflight(texts)[1]
D._table = orig
print(f'① 预检：现在 {len(e0)} 处（应 0）；拿掉“带着” {len(e1)} 处（应 > 0）')
if e0 or not any('带着' in x for x in e1):
    bad.append('①')
mt = D.model_text('所以空格这里，要用不定式。')
print(f'② 读音修正：{mt}')
if '控格' not in mt:
    bad.append('②')
al = NJ.Aligner()


def run(p):
    a, sr = sf.read(str(p), dtype='float32')
    a = a.mean(1) if a.ndim > 1 else a
    return D.check_items(a, sr, json.loads(Path(p).with_suffix('.timings.json').read_text('utf-8'))['items'], al)[1]


S = ROOT / '高考语法填空'
e_bad = run(S / '样音/第3轮_q56_r2icl.mp3')
e_ok = run(S / 'audio/2026 新课标Ⅰ卷 语法填空 第56题样片（用户本人声音）.mp3')
print(f'③ r2icl {len(e_bad)} 处 {e_bad}；第 2 版样片 {len(e_ok)} 处（应 0）')
if not any('空格' in x and '“空”' in x for x in e_bad) or e_ok:
    bad.append('③')
src = {n: (S / f'tools/{n}.py').read_text('utf-8') for n in ('qwen_synth', '讲解音频', '选段')}
if 'PY.model_text' not in src['qwen_synth'] or 'PY.check_items' not in src['讲解音频'] or 'PY.tone_problems' not in src['选段']:
    bad.append('④ 入口没接上')
print('多音字声调双向验证', '通过' if not bad else '失败：' + '、'.join(bad))
sys.exit(1 if bad else 0)
