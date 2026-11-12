"""双向验证（踩坑 119）：六级听力答案一览屏（ansA / ansB）由 layout 实测挑字号。
旧引擎（e5151b1：答案 nowrap + overflow:hidden、字号写死 38）在 201812-1 必须报出出画面；
新引擎按 layout 同一套规则挑出字号后 0 处，且字号不低于下限 28。
    /opt/ttsenv/bin/python tools/防复发/验证/答案一览字号.py"""
import importlib.util, subprocess, sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
TOOLS = R / '六级/听力/tools'
SID, OLD = '201812-1', 'e5151b1'
if not (R / '专八/听力/fonts_local/TimesNewRoman.ttf').exists():
    subprocess.run([sys.executable, str(R / '专八/听力/tools/取字体.py')], check=True, capture_output=True)


def load(path, name):
    sys.argv = ['x', SID, 'none']
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


old_src = subprocess.run(['git', '-C', str(R), 'show', f'{OLD}:六级/听力/tools/听力视频.py'], capture_output=True, text=True, check=True).stdout
tmp_old = TOOLS / '_旧引擎_答案一览.py'
tmp_old.write_text(old_src, 'utf-8')
try:
    old = load(tmp_old, 'old6')
finally:
    tmp_old.unlink()
new = load(TOOLS / '听力视频.py', 'new6')

from playwright.sync_api import sync_playwright
exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
bad = []
with sync_playwright() as pw:
    br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
    pg = br.new_page(viewport={'width': 1920, 'height': 1080})
    t = Path(new.OUT); t.mkdir(parents=True, exist_ok=True); t = t / 'ans_selftest.html'

    def check(m, s):
        t.write_text(m.page(s), 'utf-8'); pg.goto(t.as_uri()); pg.wait_for_function('document.fonts.status === "loaded"')
        return pg.evaluate(m.base.CHECK_JS) + pg.evaluate(m.base.QGAP_JS, m.base.MIN_GAP)
    for k in ('ansA', 'ansB'):
        got = check(old, {'kind': k})
        ok = len(got) > 0
        print(('✅' if ok else '❌'), '旧引擎', k, '→', f'{len(got)} 处' if got else '0 处（应报出）', got[:1])
        if not ok: bad.append(f'旧 {k}')
        af = next((f for f in range(46, 27, -1) if not check(new, {'kind': k, 'fit': f})), None)
        ok = af is not None and af >= 28
        print(('✅' if ok else '❌'), '新引擎', k, '→', f'字号 {af}，0 处' if ok else '降到 28 还放不下')
        if not ok: bad.append(f'新 {k}')
    br.close()
print('答案一览字号双向验证', '通过' if not bad else f'失败 {bad}'); sys.exit(1 if bad else 0)
