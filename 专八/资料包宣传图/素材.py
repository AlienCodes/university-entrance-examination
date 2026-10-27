"""宣传图素材：从资料包里真实的 PDF 渲染、裁出局部（不做假图）。输出 work/素材/（不入库）。

    python3 专八/资料包宣传图/素材.py
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KA = REPO / '专八' / '听写卡'
S = HERE / 'work' / '素材'
TMP = HERE / 'work' / 'tmp'


def folder(n):
    return next(KA.glob(f'{n:02d} *'))


def pdf(n, k):
    return next(folder(n).glob(f'* - {k} *.pdf'))


def page(n, k, p, dpi=None, width=None):
    """渲染第 p 页，返回 PIL 图。"""
    TMP.mkdir(parents=True, exist_ok=True)
    out = TMP / f'{n:02d}_{k}_{p}'
    opt = ['-r', str(dpi)] if dpi else ['-scale-to-x', str(width), '-scale-to-y', '-1']
    subprocess.run(['pdftoppm', '-q', *opt, '-f', str(p), '-l', str(p), '-singlefile', '-png', str(pdf(n, k)), str(out)], check=True)
    return Image.open(f'{out}.png').convert('RGB')


def crop(im, x0, y0, x1, y1):
    w, h = im.size
    return im.crop((round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h)))


# (文件名, 篇目序号, 第几件, 页, 裁剪框（页面比例）或 None, dpi)
ITEMS = [
    ('jd_cover', 1, 0, 1, None, None),
    ('jd_01_2', 1, 0, 2, None, None),
    ('jd_01_3', 1, 0, 3, None, None),
    ('jd_06_4', 6, 0, 4, None, None),
    ('jd_17_3', 17, 0, 3, None, None),
    ('jd_25_2', 25, 0, 2, None, None),
    ('cs_card', 1, 4, 1, (0.075, 0.445, 0.925, 0.945), 300),
    ('cs_steps', 1, 4, 2, (0.095, 0.618, 0.92, 0.935), 300),
    ('cs_full1', 1, 4, 1, None, 150),
    ('cs_full2', 1, 4, 2, None, 150),
    ('dk1_full', 1, 1, 1, None, 150),
    ('dk2_full', 1, 2, 1, None, 150),
    ('dk3_full', 1, 3, 1, None, 150),
    ('dk1', 1, 1, 1, (0.05, 0.135, 0.78, 0.300), 300),
    ('dk2', 1, 2, 1, (0.05, 0.135, 0.78, 0.300), 300),
    ('dk3', 1, 3, 1, (0.06, 0.150, 0.96, 0.359), 300),
]

if __name__ == '__main__':
    S.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1:]
    for name, n, k, p, box, dpi in ITEMS:
        if only and name not in only:
            continue
        im = page(n, k, p, dpi=dpi, width=None if dpi else 1600)
        if box:
            im = crop(im, *box)
        im.save(S / f'{name}.png')
        print(name, im.size)
