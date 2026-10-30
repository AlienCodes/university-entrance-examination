"""只排原题屏、跑全部检查（不画别的屏，几秒一篇）：
/opt/ttsenv/bin/python 四级作文/tools/原题屏试排.py <项目> <输出目录> [c32 c30 …（不写 = 全部）] [--shot 出 4K 图]
项目：四级作文 / 六级作文。每篇打印选中的版式、英文 / 译文字号和问题数；有问题退出码 1。"""
import sys, json, importlib.util, tempfile
from pathlib import Path
R = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('make_video', R / '专八/tools/make_video.py')
M = importlib.util.module_from_spec(spec); sys.modules['make_video'] = M; spec.loader.exec_module(M)
args = [a for a in sys.argv[1:] if not a.startswith('--')]
M.set_project(args[0]); M.set_style(M.PJ['look'])
P = {p['id']: p for p in json.loads((M.C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
from playwright.sync_api import sync_playwright
out = Path(args[1]); out.mkdir(parents=True, exist_ok=True); shot = '--shot' in sys.argv
pids = args[2:] or sorted(P)
total = 0
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(); pg = br.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2 if shot else 1)
    for pid in pids:
        for i, label, fit, res in M.layout(pg, P[pid], Path(td) / 'x.html'):
            if label == '原题':
                pr = M.screen_checks(pg, label, fit, res)
                m = pg.evaluate("""() => { const g = document.querySelector('.pgrid'), f = s => parseFloat(getComputedStyle(document.querySelector(s)).fontSize);
                    return [g.className.replace('pgrid ', ''), g.style.getPropertyValue('--ca'), f('.pen'), f('.pzh .zh')] }""")
                print(pid, *m, '问题', len(pr), *pr[:6], flush=True)
                total += len(pr)
                if shot:
                    pg.screenshot(path=str(out / f'{pid}_原题屏.png'))
                break
    br.close()
print('合计', total, '处')
sys.exit(1 if total else 0)
