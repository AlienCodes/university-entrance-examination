"""证明画面字形与原卷“一模一样”：从原卷 PDF 渲染几个词，与浏览器用同一字体、同一字号排出的同一个词逐像素比对。
换成别的字体（如度量兼容的 Liberation Serif）必须报出（双向验证）。
用法：/opt/ttsenv/bin/python 字形比对.py [--字体 'Liberation Serif']   退出码 0 = 全部一致"""
import sys
from pathlib import Path
import numpy as np, pymupdf
from PIL import Image
HERE = Path(__file__).resolve().parent
PDF = HERE.parents[1] / '真题' / '2025年 英语专业八级真题.pdf'
FL = HERE.parent / 'fonts_local'
Z = 8                                            # PDF 1 pt = 8 像素
WORDS = [(0, 'professional', 400, 'normal', 11), (0, 'Ambivalent.', 400, 'normal', 11), (0, 'COMPREHENSION', 700, 'normal', 14),
         (0, 'semantically', 700, 'italic', 10), (8, 'consciousness', 400, 'normal', 11), (8, 'Functions', 700, 'normal', 11)]
TH = 0.045                                       # 墨迹差（0—1，对齐、模糊后）：原卷字体实测 0.021—0.040，Liberation Serif 0.054—0.085


def ink(a):
    a = 1 - a.astype(float) / 255
    ys, xs = np.where(a > 0.25)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def main():
    fam = sys.argv[sys.argv.index('--字体') + 1] if '--字体' in sys.argv else 'TNR'
    doc = pymupdf.open(str(PDF))
    from playwright.sync_api import sync_playwright
    css = ''.join(f"@font-face{{font-family:'TNR';src:url('{(FL / f).as_uri()}');font-weight:{w};font-style:{s}}}"
                  for f, w, s in (('TimesNewRoman.ttf', 400, 'normal'), ('TimesNewRomanBold.ttf', 700, 'normal'),
                                  ('TimesNewRomanItalic.ttf', 400, 'italic'), ('TimesNewRomanBoldItalic.ttf', 700, 'italic')))
    bad = []
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': 1600, 'height': 300})
        for pn, w, wt, st, pt in WORDS:
            r = doc[pn].search_for(w)[0]
            pix = doc[pn].get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=r + (-0.3, -1, 0.3, 1), colorspace=pymupdf.csGRAY)
            a = ink(np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width))
            tmp = Path('/tmp/zx.html')       # 用文件打开：内联页面加载不了本机字体文件（第一版两种字体结果一模一样，就是没加载上）
            tmp.write_text(f"<meta charset=utf-8><style>{css}body{{margin:40px;background:#fff}}span{{font-family:'{fam}',monospace;font-weight:{wt};font-style:{st};font-size:{pt * Z}px;color:#000}}</style><span>{w}</span>", 'utf-8')
            pg.goto(tmp.as_uri())
            pg.wait_for_function('document.fonts.status === "loaded"')
            pg.screenshot(path='/tmp/zx.png')
            b = ink(np.asarray(Image.open('/tmp/zx.png').convert('L')))
            wr = b.shape[1] / a.shape[1]
            bb = np.asarray(Image.fromarray((b * 255).astype(np.uint8)).resize(a.shape[::-1], Image.LANCZOS)).astype(float) / 255
            # 两种光栅化（MuPDF / Chrome）的抗锯齿、亚像素位置不同：先在 ±3 像素内对齐，再各自轻微模糊后比
            from PIL import ImageFilter
            blur = lambda x: np.asarray(Image.fromarray((x * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))).astype(float) / 255
            A = blur(a); d = 9
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    d = min(d, float(np.abs(A - blur(np.roll(np.roll(bb, dy, 0), dx, 1))).mean()))
            ok = d <= TH and abs(wr - 1) < 0.02
            print(f"{'✅' if ok else '❌'} {w:15s} 墨迹差 {d:.4f}  宽度比 {wr:.3f}")
            if not ok: bad.append(w)
        br.close()
    print('字形比对：' + ('全部一致' if not bad else f'{len(bad)} 个词不一致 {bad}'))
    sys.exit(1 if bad else 0)


main()
