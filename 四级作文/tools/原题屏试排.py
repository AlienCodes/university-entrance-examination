"""只排原题屏、跑全部检查（不画别的屏，几秒一篇）：/opt/ttsenv/bin/python 四级作文/tools/原题屏试排.py <输出目录> c32 c30 [--shot 出 4K 图]。项目在 set_project 那行改。"""
import sys, json, importlib.util, tempfile
from pathlib import Path
R = Path('/home/user/university-entrance-examination')
spec = importlib.util.spec_from_file_location('make_video', R / '专八/tools/make_video.py')
M = importlib.util.module_from_spec(spec); sys.modules['make_video'] = M; spec.loader.exec_module(M)
M.set_project('四级作文'); M.set_style(M.PJ['look']) if hasattr(M, 'set_style') else None
P = {p['id']: p for p in json.loads((M.C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
from playwright.sync_api import sync_playwright
out = Path(sys.argv[1]); shot = '--shot' in sys.argv
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(); pg = br.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2 if shot else 1)
    for pid in [a for a in sys.argv[2:] if not a.startswith('--')]:
        for i, label, fit, res in M.layout(pg, P[pid], Path(td) / 'x.html'):
            if label == '原题':
                pr = M.screen_checks(pg, label, fit, res)
                m = pg.evaluate("() => { const r = document.querySelector('.pq img').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)] }")
                print(pid, 'img', m, '问题', len(pr), *pr[:6], flush=True)
                if shot: pg.screenshot(path=str(out / f'{pid}_pq.png'))
                break
    br.close()
