"""六级写作讲义商品图素材：用讲义自己的排版程序（六级作文/tools/讲义.py）渲染真实内页元素，逐个高清截图（3 倍），买家看到的就是讲义里的样子。

    /opt/ttsenv/bin/python 六级作文/讲义/商品图/素材.py

输出 六级作文/讲义/商品图/work/素材/（不入库，随时重画）。另外从三份 PDF 渲染封面、目录页（“已读”框按 PDF 自己的勾选外观打勾）、
c01 一章的内页、默写卡和答案的第一页卡片。沿用 考研作文/讲义/商品图/素材.py 的做法。
"""
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]
OUT = HERE / 'work' / '素材'
spec = importlib.util.spec_from_file_location('jy6', C / 'tools' / '讲义.py')
J = importlib.util.module_from_spec(spec)
spec.loader.exec_module(J)
PDF = {'讲义': J.OUT_HANDOUT, '默写卡': J.OUT_CARDS, '答案': J.OUT_ANS}
PID = 'c01'                     # 展示用的一篇：2026 年 6 月第 1 套（最新一次考试）


def ppm(f, p, out, r=120):
    subprocess.run(['pdftoppm', '-r', str(r), '-f', str(p), '-l', str(p), '-png', '-singlefile', str(f), str(OUT / out)], check=True)


def checked_toc(n=3):
    """目录页：前 n 个“已读”框打勾（用 PDF 自己的“勾上”外观，不是画上去的），另存一份再渲染。"""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject
    w = PdfWriter(clone_from=str(J.OUT_HANDOUT))
    page = w.pages[1]
    boxes = [a.get_object() for a in page.get('/Annots', []) if a.get_object().get('/FT') == '/Btn' or a.get_object().get('/AP')]
    boxes = [b for b in boxes if '/AP' in b and '/N' in b['/AP'] and len(b['/AP']['/N']) == 2]
    boxes.sort(key=lambda b: -float(b['/Rect'][1]))
    assert len(boxes) >= n, len(boxes)
    for b in boxes[:n]:
        on = next(k for k in b['/AP']['/N'] if k != '/Off')
        b[NameObject('/V')] = NameObject(on)
        b[NameObject('/AS')] = NameObject(on)
    with tempfile.NamedTemporaryFile(suffix='.pdf') as t:
        w.write(t.name)
        ppm(t.name, 2, '目录_已勾', r=150)
    return len(boxes)


def pdf_pages():
    for k, f in PDF.items():
        ppm(f, 1, f'封面_{k}', r=110)
        ppm(f, 2, f'目录_{k}')
    got, _ = J.page_of(J.OUT_HANDOUT, {'a': 'MODEL ESSAY 01', 'b': 'MODEL ESSAY 02'})
    a, b = got['a'], got['b']
    for i, p in enumerate(range(a, b), 1):
        ppm(J.OUT_HANDOUT, p, f'内页_{i:02d}')
    for k in ('默写卡', '答案'):
        got, _ = J.page_of(PDF[k], {'a': f'DICTATION'})
        ppm(PDF[k], got['a'], f'卡页_{k}')
    nb = checked_toc()
    print(f'{PID} 一章 {b - a} 页（PDF 第 {a}—{b - 1} 页）；目录页“已读”框 {nb} 个')
    (OUT / '章页数.json').write_text(json.dumps({'pages': b - a, 'first': a}), 'utf-8')


def elements():
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(device_scale_factor=3, viewport={'width': 800, 'height': 1200})
        body = J.general_chapter() + J.essay_chapter(1, PID, tmp) + J.card_section(PID, False) + J.card_section(PID, True)
        f = Path(tmp) / 'x.html'
        f.write_text(J.page_html(body, '素材'), 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        pg.wait_for_timeout(400)
        ch = "section[data-mark='CH01'] "

        def shot(name, sel, i=0):
            el = pg.locator(sel).nth(i)
            el.scroll_into_view_if_needed()
            el.screenshot(path=str(OUT / f'{name}.png'))

        def span(name, sel, i, j, pad=6, sel2=None):
            """连续几个元素（sel 的第 i 个到 sel2 或 sel 的第 j 个）合成一张。"""
            pg.evaluate('scrollTo(0, 0)')
            a, b = pg.locator(sel).nth(i).bounding_box(), pg.locator(sel2 or sel).nth(j).bounding_box()
            x0, y0 = min(a['x'], b['x']) - pad, a['y'] - pad
            x1, y1 = max(a['x'] + a['width'], b['x'] + b['width']) + pad, b['y'] + b['height'] + pad
            pg.screenshot(path=str(OUT / f'{name}.png'), clip={'x': x0, 'y': y0, 'width': x1 - x0, 'height': y1 - y0}, full_page=True)

        shot('范文', ch + '.essay')
        shot('译文', ch + '.trans')
        shot('思路', ch + '.flow')
        span('步骤', ch + '.step', 0, 1)
        shot('审题', ch + '.warn')
        shot('要求', ch + '.rqs')
        span('得分', ch + '.sc', 0, 1)
        shot('升格1', ch + '.up', 0)
        shot('升格2', ch + '.up', 1)
        for i in range(len(pg.locator(ch + '.pat').all())):
            shot(f'句式{i + 1}', ch + '.pat', i)
        pos = pg.evaluate("""(sel) => { const p = document.querySelectorAll(sel)[2], R = p.getBoundingClientRect();
          const f = q => { const e = p.querySelector(q).getBoundingClientRect(); return [(e.top - R.top) / R.height, (e.bottom - R.top) / R.height]; };
          return {mean: f('.mean'), f: f('.f'), o: f('.o'), why: f('.why'), ex: f('.ex'), alt: f('.alt')}; }""", ch + '.pat')
        (OUT / '句式3位置.json').write_text(json.dumps(pos), 'utf-8')
        span('词汇', ch + '.vr', 0, 6)
        shot('黑名单', "section[data-mark='GEN'] .bad")
        shot('卡A', f"section[data-mark='C{PID}']:not(.ans) .card", 1)
        shot('卡B', f"section[data-mark='C{PID}']:not(.ans) .card", 7)
        shot('答案卡', f"section[data-mark='C{PID}'].ans .card", 1)
        br.close()


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    pdf_pages()
    elements()
    from PIL import Image
    for f in sorted(OUT.glob('*.png')):
        print(f.name, Image.open(f).size)
