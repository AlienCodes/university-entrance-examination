"""比较新旧两版生成程序对同一篇的排版，列出有实质变化的屏（不花 token）。直接用两版程序各渲染一遍比较（不经过视频编码，没有噪声），
可以给旧版加一段 CSS，抵消已知的、无关紧要的整体变化（如间距差 2 像素造成的整体平移），只留下真正需要审阅员看的屏。

    /opt/ttsenv/bin/python 中考/tools/画面核查/progdiff.py <旧版 make_video.py> [--css "<追加到旧版的 CSS>"] z01 z02 …   → 打印 JSON {篇目: [屏号…]}
屏数不同的篇目整篇都算变了。
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
sys.path.insert(0, str(R / '中考' / 'tools'))
from playwright.sync_api import sync_playwright  # noqa: E402

argv = sys.argv[1:]
css = ''
if '--css' in argv:
    j = argv.index('--css')
    css = argv[j + 1]
    argv = argv[:j] + argv[j + 2:]
spec = importlib.util.spec_from_file_location('old_make_video', argv[0])
OLD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OLD)
import make_video as NEW  # noqa: E402
from 画面核查.layoutcheck import screens  # noqa: E402

P = {p['id']: p for p in json.loads((R / '中考' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
res = {}
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': NEW.W, 'height': NEW.H})
    f = Path(td) / 'x.html'

    def shot(M, h, fit, extra=''):
        f.write_text(h.replace('</head>', f'<style>{extra}</style></head>') if extra else h, 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        if fit:
            pg.evaluate(M.FIT)
        pg.screenshot(path=str(Path(td) / 's.png'))
        return np.asarray(Image.open(Path(td) / 's.png').convert('L'), np.int16)

    for pid in argv[1:]:
        a, b = screens(OLD, P[pid]), screens(NEW, P[pid])
        if len(a) != len(b):
            res[pid] = list(range(1, len(b) + 1))
            continue
        ch = [i for i, ((_, ha, fa), (_, hb, fb)) in enumerate(zip(a, b), 1) if np.abs(shot(OLD, ha, fa, css) - shot(NEW, hb, fb)).max() > 40]
        res[pid] = ch
        print(pid, f'{len(ch)}/{len(b)} 屏有实质变化：', ch, file=sys.stderr, flush=True)
    br.close()
print(json.dumps(res))
