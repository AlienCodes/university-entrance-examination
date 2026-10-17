"""比较同一篇视频两次生成的截屏，列出画面有变化的屏（不花 token）。用于修改程序后重新生成：没变的屏已经按最终状态复核过，
排版审阅员只需重点看变了的屏（zk-frame-qa.js 的 only 参数）。屏数不同就整篇都算变了。

    /opt/ttsenv/bin/python 中考/tools/画面核查/changed.py <旧截图目录> <新截图目录> z01 z02 …   → 打印 JSON {篇目: [屏号…]}
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

old, new = Path(sys.argv[1]), Path(sys.argv[2])
B, LIM = 8, 12          # 8 像素块平均灰度差超过 12 算变了（同一程序同一内容两次编码，块差为 0；一个字的变化在 8 像素块上远超 12）
res = {}
for vid in sys.argv[3:]:
    a, b = sorted((old / vid).glob('screen*.png')), sorted((new / vid).glob('screen*.png'))
    if len(a) != len(b):
        res[vid] = list(range(1, len(b) + 1))
        continue
    ch = []
    for i, (x, y) in enumerate(zip(a, b), 1):
        d = np.abs(np.asarray(Image.open(x).convert('L'), np.int16) - np.asarray(Image.open(y).convert('L'), np.int16)).astype(np.float32)
        h, w = d.shape[0] // B * B, d.shape[1] // B * B
        if d[:h, :w].reshape(h // B, B, w // B, B).mean(axis=(1, 3)).max() > LIM:
            ch.append(i)
    res[vid] = ch
    print(vid, f'{len(ch)}/{len(b)} 屏有变化：', ch, file=sys.stderr, flush=True)
print(json.dumps(res))
