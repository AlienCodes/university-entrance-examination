"""排版预检：逐句（含分屏）渲染，找出一屏放不下或字号低于下限的句子，生成视频前先在 分屏.json 里拆屏。  /opt/ttsenv/bin/python 专八/tools/fitcheck.py t01 t02 …"""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, '/home/user/university-entrance-examination/专八/tools')
import make_video as M
from playwright.sync_api import sync_playwright
data = json.loads((M.C4 / 'data' / 'vocab.json').read_text('utf-8'))
ids = sys.argv[1:]
bad = []
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': M.W, 'height': M.H})
    for p in data['passages']:
        if p['id'] not in ids: continue
        S = [s for para in p['paras'] for s in para]
        for k, s in enumerate(S, 1):
            for part in M.split_parts(p['id'], k, s):
                f = Path(td) / 'x.html'; f.write_text(M.sentence_slide(p, s, k, len(S), part), 'utf-8')
                pg.goto(f.as_uri()); pg.evaluate('document.fonts.ready')
                fs, vs, fits = pg.evaluate(M.FIT)
                if not fits or fs < M.MIN_FS or vs < M.MIN_VS:
                    bad.append((p['id'], k, fs, vs, len(s['w']), len(s['en'])))
    br.close()
for b in bad: print(*b)
print('total bad', len(bad))
