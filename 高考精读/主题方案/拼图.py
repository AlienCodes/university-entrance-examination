"""把 4 张同一屏（原版 + 3 个方案）拼成对比图，另出 320 宽缩略图。

    python 拼图.py <渲染输出目录>   # 目录里有 out_原版/ out_A_热气球/ …（中考/tools/样式设计/render.py 的输出）
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1])
FONTS = (HERE.parents[1] / '四级' / 'tools' / 'fonts' / 'fonts.css').as_uri()
NAMES = [('原版', '原版（绿色树苗）'), ('A_热气球', 'A 热气球'), ('B_叠书铅笔', 'B 叠书与铅笔'), ('C_彩虹云朵', 'C 彩虹与云朵')]
SCREEN = 's2.png'

cells = ''.join(f"<figure><figcaption>{t}</figcaption><img src='{(SRC / f'out_{n}' / SCREEN).as_uri()}'>"
                f"<div class=z style=\"background-image:url('{(SRC / f'out_{n}' / SCREEN).as_uri()}')\"></div></figure>" for n, t in NAMES)
html = f"""<!doctype html><meta charset=utf-8><link rel=stylesheet href='{FONTS}'><style>
body{{margin:0;background:#fff;font-family:'Noto Serif SC',serif;width:2340px}}
.g{{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:20px}}
figure{{margin:0;display:grid;grid-template-columns:950px 220px;gap:10px;align-items:end}} figcaption{{grid-column:1/3}} figcaption{{font-size:34px;font-weight:700;color:#2a2342;margin:0 0 8px}}
img{{width:950px;display:block;border:1px solid #ddd}}
.z{{width:210px;height:300px;border:3px solid #5a3dc4;border-radius:10px;
   background-size:1920px 1080px;background-position:0 -780px;background-color:#fff}}
</style><div class=g>{cells}</div>"""
tmp = HERE / '_拼图.html'
tmp.write_text(html, 'utf-8')
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 2420, 'height': 800})
    pg.goto(tmp.as_uri()); pg.wait_for_timeout(500)
    pg.screenshot(path=str(HERE / '对比_装饰方案.png'), full_page=True)
    # 320 宽缩略图（手机信息流里看整体感觉），4 张排一行
    th = ''.join(f"<figure><figcaption>{t}</figcaption><img src='{(SRC / f'out_{n}' / SCREEN).as_uri()}'></figure>" for n, t in NAMES)
    tmp.write_text(f"<!doctype html><meta charset=utf-8><link rel=stylesheet href='{FONTS}'><style>body{{margin:0;background:#fff;font-family:'Noto Serif SC',serif}}"
                   f".g{{display:flex;gap:12px;padding:12px}}figure{{margin:0;display:block}}figcaption{{font-size:16px;font-weight:700}}img{{width:320px;display:block;border:1px solid #ddd}}</style><div class=g>{th}</div>", 'utf-8')
    pg.set_viewport_size({'width': 1340, 'height': 240})
    pg.goto(tmp.as_uri()); pg.wait_for_timeout(500)
    pg.screenshot(path=str(HERE / '缩略_320宽.png'), full_page=True)
    b.close()
tmp.unlink()
print('写出 对比_装饰方案.png、缩略_320宽.png')
