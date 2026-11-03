"""双向验证：拼接衔接（用户 2026-11-03：要流畅、丝滑）。门限取自用户本人录音的自然停顿（拼接检查.py --录音）。needs tts。
  ① 第 2 版样片（0.55 秒插静音、‖ 拆小段）必须报出：停顿偏长 + 相邻段语速突变；第 3 轮 r2icl 必须报出相邻段语速突变（“答案就是：｜to be held”）；
  ② 本人录音一段（样本 语速_用户录音.flac，按自然停顿切开当作“小段”）0 处；
  ③ 入口：讲解音频.render 调 拼接检查。
    /opt/ttsenv/bin/python tools/防复发/验证/拼接衔接.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / '高考语法填空/tools'), str(ROOT / 'tools/tts')]
import 拼接检查 as PJ  # noqa: E402

bad = []
tgt = json.loads(PJ.TARGET.read_text('utf-8'))
S = ROOT / '高考语法填空'
e2 = PJ.problems(PJ.product_boundaries(S / 'audio/2026 新课标Ⅰ卷 语法填空 第56题样片（用户本人声音）.mp3'), tgt)
e3 = PJ.problems(PJ.product_boundaries(S / '样音/第3轮_q56_r2icl.mp3'), tgt)
print(f'① 第 2 版 {len(e2)} 处；r2icl {len(e3)} 处')
if not (any('停顿偏长' in x for x in e2) and any('语速差' in x for x in e2) and any('答案就是' in x for x in e3)):
    bad.append('① 旧版本没报全')
import 挑参考 as PR  # noqa: E402
x = PR.decode(Path(__file__).parent / '样本/语速_用户录音.flac')
asr = PR.ASR()
sp = [(s, e) for s, e in PR.utterances(x)[0] if (e - s) / PR.SR >= 1.0]
pieces = [(x[s:e], asr(x[s:e])[0], ((sp[k + 1][0] - e) / PR.SR) if k + 1 < len(sp) else 0) for k, (s, e) in enumerate(sp)]
B = [b for b, p in zip(PJ.boundaries(pieces, PR.SR), pieces) if p[2] <= 1.5]
for b in B:
    b.setdefault('at', 0)
    b.setdefault('between', '')
e4 = PJ.problems(B, tgt)
print(f'② 本人录音一段：{len(B)} 个边界，{len(e4)} 处 {e4}')
if e4:
    bad.append('② 本人录音被判不合格')
if 'PJ.problems' not in (S / 'tools/讲解音频.py').read_text('utf-8'):
    bad.append('③ render 没接拼接检查')
print('拼接衔接双向验证', '通过' if not bad else '失败：' + '、'.join(bad))
sys.exit(1 if bad else 0)
