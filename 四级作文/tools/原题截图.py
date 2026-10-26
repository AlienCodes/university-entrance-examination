"""四级作文原题截图（照 考研作文/tools/原题截图.py：Part I Writing 标题裁到 Part II 标题之前）。

原：考研作文原题截图（用户 2026-10-22：视频开头展示原题，截图必须高清）。

    /opt/ttsenv/bin/python 考研作文/tools/原题截图.py            # 24 篇全部
    /opt/ttsenv/bin/python 考研作文/tools/原题截图.py w02 w05    # 指定篇目

做法：原卷 PDF（考研/真题/<试卷>.pdf，文字和图表都是矢量）按 600 dpi 渲染，用 pdftotext -bbox 找到 Section III/IV Writing 之后的
“Part A”“Part B”标题，从本题标题裁到下一题标题（或页脚网址）之前；本题跨页时（标题在前一页、图表在后一页）把后一页页首到页脚的内容接在下面。
裁好后去掉四周空白、留 8 磅边，存 考研作文/原题/<篇目>.png（灰度）。
检查：按视频里原题卡片能放图的区域（约 1670 × 860，4K 下 × 2）等比放到最大，原图像素必须不少于画面上要的像素（只缩小、不放大），不够就报错；
make_video 的原题屏另按实际显示尺寸逐屏核对（原题截图不够高清）。
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
C = HERE.parent
ROOT = C.parent
PAPERS = ROOT / '四级' / '真题'
DPI = 600
K = DPI / 72
BOX = (1670 * 2, 860 * 2)      # 原题卡片放图区域（4K 像素，近似；精确值由 make_video 原题屏检查实测）


def words(pdf, page):
    h = subprocess.run(['pdftotext', '-f', str(page), '-l', str(page), '-bbox', str(pdf), '-'], capture_output=True, text=True, check=True).stdout
    return [(float(a), float(b), float(c), float(d), html_unescape(t)) for a, b, c, d, t in
            re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', h)]


def html_unescape(t):
    import html
    return html.unescape(t)


def npages(pdf):
    return int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True, check=True).stdout).group(1))


def pdf_of(rec):
    y, m, s = rec['year'], rec['month'], rec['set']
    return PAPERS / str(y) / f'{y}年{m:02d}月' / f'{y}年{m}月 英语四级真题 第{s}套.pdf'


def headings(pdf):
    """每页左边距的 Part 标题（Part I / II …）位置与页脚：[(页, 'I'/'II'…, y)]，{页: 页脚 y}。"""
    out, foot = [], {}
    for pg in range(1, npages(pdf) + 1):
        ws = words(pdf, pg)
        foot[pg] = min([w[1] for w in ws if 'burningvocabulary' in w[4] or (w[4].isdigit() and w[1] > 790)] or [820])
        for i, w in enumerate(ws):
            if w[4] == 'Part' and i + 1 < len(ws) and (re.fullmatch(r'I|II|III|IV', ws[i + 1][4]) or ws[i + 1][4] in ('n:', 'II:', '][', 'Il', 'll')) and w[0] < 80 and abs(ws[i + 1][1] - w[1]) < 8:  # 2021-06 原卷 Part II 的“II”文字层是“n:”
                out.append((pg, ws[i + 1][4], w[1]))
    return out, foot


def render(pdf, pg, top, bot, tmp):
    ws = words(pdf, pg)        # 左右边界按本页文字实际范围（2021-06 扫描件整页偏左，固定的 30—565 磅会切掉 Part / Directions 的首字母）
    x0, x1 = max(min(w[0] for w in ws) - 8, 0), max(w[2] for w in ws) + 8
    x, y, w, h = round(x0 * K), round(top * K), round((x1 - x0) * K), round((bot - top) * K)
    f = Path(tmp) / f'p{pg}_{round(top)}'
    subprocess.run(['pdftoppm', '-f', str(pg), '-l', str(pg), '-r', str(DPI), '-x', str(x), '-y', str(y), '-W', str(w), '-H', str(h),
                    '-gray', '-png', '-singlefile', str(pdf), str(f)], check=True)
    return np.array(Image.open(f.with_suffix('.png')).convert('L'))


def trim(a, pad):
    ink = a < 200
    r, c = np.where(ink.any(1))[0], np.where(ink.any(0))[0]
    if not len(r):
        return a[:0]
    return a[max(r[0] - pad, 0):min(r[-1] + pad + 1, a.shape[0]), max(c[0] - pad, 0):min(c[-1] + pad + 1, a.shape[1])]


def cut_above(a):
    """从“Part I”这一行（裁剪起点下 14 磅处，一定落在标题字里）往上找第一条全白行，切掉它上面的东西
    （2026-06 第 1 套：页眉试卷标题紧贴 Part I 上方，旧裁法带进了标题的下半截）。"""
    r = round(14 * K)
    while r > 0 and (a[r] < 200).any():
        r -= 1
    return a[r:]


def crop(rec, tmp):
    pdf = pdf_of(rec)
    hs, foot = headings(pdf)
    me = [h for h in hs if h[1] == 'I']
    if len(me) == 2 and me[0][0] == me[1][0] and pdf.name.startswith('2021年6月'):
        me = me[:1]       # 2021-06 第 3 套：Part II（听力说明）的文字层识别成“Part I”；Writing 永远是试卷第一个 Part
    if len(me) != 1:
        raise SystemExit(f"{rec['id']}：{pdf.name} 里 Part I 标题找到 {len(me)} 个：{hs}")
    pg, _, y0 = me[0]
    nxt = [h for h in hs if (h[0], h[2]) > (pg, y0)]
    pieces = []
    if nxt and nxt[0][0] == pg:                       # 下一题在同一页：裁到下一题标题之前
        pieces.append(cut_above(render(pdf, pg, y0 - 6, nxt[0][2] - 4, tmp)))
    else:                                              # 裁到页脚；本题跨页（下一页还有本题内容）时接上
        pieces.append(cut_above(render(pdf, pg, y0 - 6, foot[pg] - 4, tmp)))
        if pg + 1 in foot and not (nxt and nxt[0][0] == pg + 1 and nxt[0][2] < 120):
            end = nxt[0][2] - 4 if nxt and nxt[0][0] == pg + 1 else foot[pg + 1] - 4
            nb = render(pdf, pg + 1, 40, end, tmp)
            if (nb < 200).any():
                pieces.append(nb)
    pad = round(8 * K)
    pieces = [trim(p, pad) for p in pieces]
    pieces = [p for p in pieces if p.size]
    w = max(p.shape[1] for p in pieces)
    a = np.vstack([np.pad(p, ((0, 0), (0, w - p.shape[1])), constant_values=255) for p in pieces])
    a = trim(a, pad)
    need = min(BOX[0] / a.shape[1], BOX[1] / a.shape[0])
    if need > 1:
        raise SystemExit(f"{rec['id']}：原题截图 {a.shape[1]}×{a.shape[0]} 不够高清（画面上要放大 {need:.2f} 倍）")
    return a, len(pieces)


def main(ids):
    P = json.loads((C / '作文' / 'sents.json').read_text('utf-8'))
    P = [p for p in P if not ids or p['id'] in ids]
    (C / '原题').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for p in P:
            a, n = crop(p, tmp)
            Image.fromarray(a).save(C / '原题' / p['prompt_img'], optimize=True)
            print(f"{p['id']} {p['paper']}：{a.shape[1]}×{a.shape[0]}" + ('（跨页拼接）' if n > 1 else ''))


if __name__ == '__main__':
    main(sys.argv[1:])
