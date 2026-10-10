"""Render the cover of t01-t10 with a design CSS -> covers.png grid.  python covers.py design.css outdir"""
import sys, runpy, tempfile
from pathlib import Path
from PIL import Image
T = Path(__file__).resolve().parent
sys.argv = [str(T / 'render.py'), sys.argv[1], sys.argv[2], '--quick']
# reuse harness definitions (page / title_slide / P) without running its main part
src = (T / 'render.py').read_text()
ns = {'__file__': str(T / 'render.py'), '__name__': 'h'}
exec(compile(src[:src.index('SAMPLES = [')], 'render_head', 'exec'), ns)
from playwright.sync_api import sync_playwright
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
ids = [f't{i:02d}' for i in range(1, 11)]
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': 1920, 'height': 1080})
    f = Path(td) / 'x.html'
    for pid in ids:
        f.write_text(ns['title_slide'](ns['P'][pid]), 'utf-8')
        pg.goto(f.as_uri()); pg.evaluate('document.fonts.ready')
        pg.screenshot(path=str(out / f'cover_{pid}.png'))
    br.close()
ims = [Image.open(out / f'cover_{p}.png').resize((640, 360), Image.LANCZOS) for p in ids]
g = Image.new('RGB', (640 * 2 + 30, 370 * 5 + 10), '#808080')
for i, im in enumerate(ims):
    g.paste(im, (10 + (i % 2) * 650, 10 + (i // 2) * 370))
g.save(out / 'covers.png')
print('ok')
