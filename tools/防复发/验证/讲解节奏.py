"""双向验证：讲解配音的节奏（踩坑 93；用户 2026-10-30 看第 56 题样片：“hold，举办”后面紧接着说下去、几乎没停；
“是不是谓语呢？”尾音轻飘上扬）。要识别模型（SenseVoice）与 librosa，只在本机跑（needs tts）。
  ① 有问题的版本：旧第 56 题样片的音频（样本 节奏_旧q56.flac + timings），套上标了 ‖ 的旧稿 → 必须报出
     “举办‖给了词”停顿不够、“是不是谓语呢？”尾音上扬；
  ② 修好的版本：仓库里现在的第 56 题样片（timings 里的稿文字带 ‖）→ 0 处；
  ③ 入口：讲解音频.render、讲解视频.verify 调 讲解节奏.check；选段.candidates 对问句量 tail_rise；稿检查 自检通过。
    /opt/ttsenv/bin/python tools/防复发/验证/讲解节奏.py"""
import ast
import json
import subprocess
import sys
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / '高考语法填空/tools'), str(ROOT / 'tools/tts')]
import 讲解节奏 as NJ  # noqa: E402

bad = []
al = NJ.Aligner()
S = Path(__file__).parent / '样本'
a, sr = sf.read(str(S / '节奏_旧q56.flac'), dtype='float32')
tm = json.loads((S / '节奏_旧q56.timings.json').read_text('utf-8'))
marked = {'q56c': '括号里给了一个词，hold，举办。‖给了词，一般都要变形。‖hold 是个动词。',
          'q56d': '那它在这句话里是不是谓语呢？‖我们找一下主干。‖It is common for them，这里的 it 是个假主语，先占个位置，真正的主语在后面。'
                  '‖这是个固定句型：It is common for somebody to do something，对某人来说，做某事很常见。'}
rep, errs = NJ.check(a, sr, tm['items'], marked, al)
hit_pause = any('举办。‖给了词' in e and '停顿' in e for e in errs)
hit_rise = any('谓语呢？' in e and '上扬' in e for e in errs)
print(f'① 旧样片：{len(errs)} 处；“举办‖给了词”停顿 {"报出" if hit_pause else "漏查"}；“是不是谓语呢？”上扬 {"报出" if hit_rise else "漏查"}')
if not (hit_pause and hit_rise):
    bad.append('① 旧样片没报全')

mp3 = ROOT / '高考语法填空/audio/2026 新课标Ⅰ卷 语法填空 第56题样片（用户本人声音）.mp3'
tm2 = json.loads(mp3.with_suffix('.timings.json').read_text('utf-8'))
if not any('‖' in it['text'] for it in tm2['items']):
    bad.append('② 仓库里的第 56 题样片还是旧稿（没有 ‖）')
else:
    b, sr2 = sf.read(str(mp3), dtype='float32')
    rep2, errs2 = NJ.check(b if b.ndim == 1 else b.mean(1), sr2, tm2['items'], {it['id']: it['text'] for it in tm2['items']}, al)
    print(f'② 现在的样片：{len(errs2)} 处（应 0）', errs2[:3])
    bad += errs2


def calls(path, func, name):
    tree = ast.parse((ROOT / path).read_text('utf-8'))
    for f in ast.walk(tree):
        if isinstance(f, ast.FunctionDef) and f.name == func:
            return any(isinstance(c, ast.Call) and getattr(c.func, 'attr', getattr(c.func, 'id', None)) == name for c in ast.walk(f))
    return False


need = [('高考语法填空/tools/讲解音频.py', 'render', 'check'), ('高考语法填空/tools/讲解视频.py', 'verify', 'check'),
        ('高考语法填空/tools/选段.py', 'candidates', 'tail_rise')]
miss = [f'{p}:{f}→{n}' for p, f, n in need if not calls(p, f, n)]
r = subprocess.run([sys.executable, str(ROOT / '高考语法填空/tools/稿检查.py'), str(ROOT / '高考语法填空/稿/2026_新课标Ⅰ卷.json'), '--自检'],
                   capture_output=True, text=True)
if r.returncode:
    miss.append('稿检查 自检失败')
print('③ 入口：', '全部接上' if not miss else miss)
bad += miss
print('讲解节奏双向验证', '通过' if not bad else f'失败：{bad}')
sys.exit(1 if bad else 0)
