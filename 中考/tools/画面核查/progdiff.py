"""比较新旧两版生成程序对同一篇的排版，列出有实质变化的屏（不花 token）。直接用两版程序各渲染一遍比较（不经过视频编码，没有噪声），
可以给旧版加一段 CSS，抵消已知的、无关紧要的整体变化（如间距差 2 像素造成的整体平移），只留下真正需要审阅员看的屏。

    /opt/ttsenv/bin/python 中考/tools/画面核查/progdiff.py <旧版 make_video.py> [--css "<追加到旧版的 CSS>"] [--lines] z01 z02 …   → 打印 JSON {篇目: [屏号…]}
屏数不同的篇目整篇都算变了。
--lines：只比“每一块（英文、译文、每个词条、片头标题）每一行的文字”是否相同——换行位置变了才算变化（同一行里整体平移几个像素不算）。
同一行内的平移只会带来徽章贴字、右边溢出两类问题，都由 layoutcheck.py 逐屏实测；换行变了的屏必须交给排版审阅员（CLAUDE.md 踩坑 35、36）。
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

LINES = """() => { const out = []; const blocks = [...document.querySelectorAll('.ttl h1, .en, .zh, .v > div')];
  for (const k of blocks) { const L = []; let prev = null; const w = document.createTreeWalker(k, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) for (let i = 0; i < n.data.length; i++) { if (/\\s/.test(n.data[i])) continue;
      const rg = document.createRange(); rg.setStart(n, i); rg.setEnd(n, i + 1); const rs = rg.getClientRects(); if (!rs.length) continue;
      const l = rs[rs.length - 1].left; if (!L.length || l < prev - 2) L.push(''); L[L.length - 1] += n.data[i]; prev = l; }
    out.push(L.join('|')); }
  return out; }"""
argv = sys.argv[1:]
lines = '--lines' in argv
argv = [a for a in argv if a != '--lines']
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
        if lines:
            return pg.evaluate(LINES)
        pg.screenshot(path=str(Path(td) / 's.png'))
        return np.asarray(Image.open(Path(td) / 's.png').convert('L'), np.int16)

    for pid in argv[1:]:
        a, b = screens(OLD, P[pid]), screens(NEW, P[pid])
        if len(a) != len(b):
            res[pid] = list(range(1, len(b) + 1))
            continue
        diff = (lambda x, y: x != y) if lines else (lambda x, y: np.abs(x - y).max() > 40)
        ch = [i for i, ((_, ha, fa), (_, hb, fb)) in enumerate(zip(a, b), 1) if diff(shot(OLD, ha, fa, css), shot(NEW, hb, fb))]
        res[pid] = ch
        print(pid, f'{len(ch)}/{len(b)} 屏有{"换行" if lines else "实质"}变化：', ch, file=sys.stderr, flush=True)
    br.close()
print(json.dumps(res))
