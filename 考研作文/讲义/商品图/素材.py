"""商品图素材：用讲义自己的排版程序（考研作文/tools/讲义.py）渲染真实内页元素，逐个高清截图（3 倍），保证买家看到的就是讲义里的样子。

    /opt/ttsenv/bin/python 考研作文/讲义/商品图/素材.py

输出 考研作文/讲义/商品图/work/素材/（不入库，随时重画）。另外从三份 PDF 渲染封面和 w02 一章的内页缩略图。
"""
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]
OUT = HERE / 'work' / '素材'
spec = importlib.util.spec_from_file_location('jy', C / 'tools' / '讲义.py')
J = importlib.util.module_from_spec(spec)
spec.loader.exec_module(J)
PDF = {'讲义': J.OUT_HANDOUT, '默写卡': J.OUT_CARDS, '答案': J.OUT_ANS}


def pdf_pages():
    """三份 PDF 的封面 + 讲义 w02 一章全部内页（按章首标记找页码，不写死）。"""
    for k, f in PDF.items():
        subprocess.run(['pdftoppm', '-r', '110', '-f', '1', '-l', '1', '-png', '-singlefile', str(f), str(OUT / f'封面_{k}')], check=True)
    got, n = J.page_of(J.OUT_HANDOUT, {'a': 'MODEL ESSAY 02', 'b': 'MODEL ESSAY 03'})
    a, b = got['a'], got['b']              # 直接量的是合并后的 PDF（含封面），页码就是 PDF 页码
    for i, p in enumerate(range(a, b), 1):
        subprocess.run(['pdftoppm', '-r', '120', '-f', str(p), '-l', str(p), '-png', '-singlefile', str(J.OUT_HANDOUT), str(OUT / f'内页_{i:02d}')], check=True)
    print('w02 一章', b - a, '页（PDF 第', a, '—', b - 1, '页）')


def elements():
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(device_scale_factor=3, viewport={'width': 800, 'height': 1200})
        body = J.general_chapter() + J.essay_chapter(2, 'w02', tmp) + J.card_section('w02', False) + J.card_section('w01', True)
        f = Path(tmp) / 'x.html'
        f.write_text(J.page_html(body, '素材'), 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        pg.wait_for_timeout(400)
        ch = "section[data-mark='CH02'] "

        def shot(name, sel, i=0):
            el = pg.locator(sel).nth(i)
            el.scroll_into_view_if_needed()
            el.screenshot(path=str(OUT / f'{name}.png'))

        def span(name, sel, i, j, pad=6):
            """连续几个元素（第 i 到第 j 个）合成一张。"""
            pg.evaluate('scrollTo(0, 0)')          # bounding_box 是视口坐标，整页截图的 clip 是页面坐标：先滚回顶部两者才一致
            a, b = pg.locator(sel).nth(i).bounding_box(), pg.locator(sel).nth(j).bounding_box()
            x0, y0 = min(a['x'], b['x']) - pad, a['y'] - pad
            x1, y1 = max(a['x'] + a['width'], b['x'] + b['width']) + pad, b['y'] + b['height'] + pad
            pg.screenshot(path=str(OUT / f'{name}.png'), clip={'x': x0, 'y': y0, 'width': x1 - x0, 'height': y1 - y0}, full_page=True)

        shot('范文', ch + '.essay')
        shot('译文', ch + '.trans')
        shot('思路', ch + '.flow')
        span('步骤', ch + '.step', 0, 1)
        shot('审题', ch + '.warn')
        for i in range(6):
            shot(f'句式{i + 1}', ch + '.pat', i)
        # 第 6 个句式卡里各部分的位置（占整张卡高度的比例），商品图上的标注按它对齐
        pos = pg.evaluate("""(sel) => { const p = document.querySelectorAll(sel)[5], R = p.getBoundingClientRect();
          const f = q => { const e = p.querySelector(q).getBoundingClientRect(); return [(e.top - R.top) / R.height, (e.bottom - R.top) / R.height]; };
          return {mean: f('.mean'), f: f('.f'), o: f('.o'), why: f('.why'), ex: f('.ex'), alt: f('.alt')}; }""", ch + '.pat')
        (OUT / '句式6位置.json').write_text(json.dumps(pos), 'utf-8')
        span('词汇', ch + '.vr', 0, 7)
        shot('黑名单', "section[data-mark='GEN'] .bad")
        shot('书信格式', "section[data-mark='GEN'] .box", 1)
        shot('卡A', "section[data-mark='Cw02'] .card", 0)
        shot('卡B', "section[data-mark='Cw02'] .card", 6)
        shot('答案卡', "section[data-mark='Cw01'] .card", 0)
        br.close()


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    pdf_pages()
    elements()
    for f in sorted(OUT.glob('*.png')):
        from PIL import Image
        print(f.name, Image.open(f).size)
