"""原题屏的图表截图（用户 2026-10-26：原题的字要尽量大）：Directions 改成排版文字（专八/tools/make_video.py prompt_zh_html），
只有图表题的图表部分保留原卷截图。从 原题截图.py 出的 600 dpi 原题图（<篇目>.png）里按行找出文字带，从图表标题那一带起裁到底，
存成 <篇目>_图.png（不缩放，原像素）。

FIRST：图表标题是第几个文字带（0 起：Part I 页眉 = 0，Directions 三行 = 1—3）。裁之前核对：文字带数、图表带的高度都要像图表，否则报错。
用法：python3 六级作文/tools/原题图表.py"""
from pathlib import Path
import numpy as np
from PIL import Image

C = Path(__file__).resolve().parents[1]
FIRST = {'c30': 4, 'c31': 4}
PAD = 36


def bands(a):
    rows = (a < 128).sum(1) > 2
    out, s = [], None
    for y, v in enumerate(list(rows) + [False]):
        if v and s is None:
            s = y
        elif not v and s is not None:
            out.append([s, y]); s = None
    m = [out[0]]
    for b in out[1:]:
        if b[0] - m[-1][1] < 15:
            m[-1][1] = b[1]
        else:
            m.append(b)
    return m


def main():
    for pid, k in FIRST.items():
        im = Image.open(C / '原题' / f'{pid}.png').convert('RGB')
        a = np.asarray(im.convert('L'))
        b = bands(a)
        if len(b) <= k + 1 or max(y1 - y0 for y0, y1 in b[k + 1:]) < 1000 or any(y1 - y0 > 150 for y0, y1 in b[:k]):
            raise SystemExit(f'{pid} 文字带不像“页眉 + Directions + 图表”：{b}')
        y0, y1 = b[k][0] - PAD, min(a.shape[0], b[-1][1] + PAD)
        cols = np.where((a[y0:y1] < 128).sum(0) > 0)[0]
        x0, x1 = max(0, cols[0] - PAD), min(a.shape[1], cols[-1] + PAD)
        im.crop((x0, y0, x1, y1)).save(C / '原题' / f'{pid}_图.png', optimize=True)
        print(pid, '图表', (x0, y0, x1, y1), f'{x1 - x0}×{y1 - y0}')


if __name__ == '__main__':
    main()
