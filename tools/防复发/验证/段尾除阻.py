"""踩坑 110：段尾 /k/ 除阻被呼吸声检查判成换气（高考续写精读 x20 knock.、x21 more work,、x27 out to work,）——检查不放宽，登记的段从闭塞起点剪断（make_audio.trim_release）。

双向验证（样本：x21:17 第 2 段、x27:10 第 2 段的 Kokoro 原始合成，前后补 0.5 秒静音、峰值归一）：
  ① 剪前 breath_check 报出（把错误放回去 = 不剪）；② trim_release 剪后 0 处，剪掉 0.1—0.25 秒（只剪除阻，不伤元音）；
  ③ 剪过的再剪一次找不到“闭塞静音 → 除阻鼓包”，返回剪掉 0（make_audio 对登记的段遇到这种情况报错，不静默放过）；
  ④ make_audio 里登记了却剪不到就 raise 的那一行还在。
    python3 tools/防复发/验证/段尾除阻.py
"""
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

H = Path(__file__).resolve().parent
R = H.parents[2]
sys.path[:0] = [str(R / 'tools' / 'tts'), str(H)]
import _抽取  # noqa: E402
import 去呼吸 as D  # noqa: E402

SR = 24000
tr = _抽取.load('高考续写/精读/tools/make_audio.py', ['trim_release'], {'np': np, 'G': type('G', (), {'SR': SR})})['trim_release']
bad = []


def pad(x):
    return np.concatenate([np.zeros(SR // 2, np.float32), x / np.abs(x).max() * 0.7, np.zeros(SR // 2, np.float32)]).astype(np.float32)


for k in ['x21_17', 'x27_10']:
    a, sr = sf.read(H / '样本' / f'段尾除阻_{k}原始段.flac', dtype='float32')
    assert sr == SR
    before = D.breath_check(pad(a), SR)
    t, cut = tr(a)
    after = D.breath_check(pad(t), SR)
    _, cut2 = tr(t)
    ok = bool(before) and not after and 0.1 <= cut <= 0.25 and cut2 == 0
    print(f"  {'✅' if ok else '❌'} {k}：剪前 {len(before)} 处（应 ≥ 1），剪后 {len(after)} 处（应 0），剪掉 {cut * 1000:.0f} ms（应 100—250），再剪 {cut2 * 1000:.0f} ms（应 0）")
    if not ok:
        bad.append(k)
src = (R / '高考续写/精读/tools/make_audio.py').read_text('utf-8')
ok = bool(re.search(r"raw, cut = trim_release\(raw\)\s+if not cut:\s+raise RuntimeError", src))
print(f"  {'✅' if ok else '❌'} make_audio：登记了 tail_release 却剪不到就报错")
if not ok:
    bad.append('raise')
print('段尾除阻 双向验证：' + ('全部通过' if not bad else f'失败：{bad}'))
sys.exit(1 if bad else 0)
