"""踩坑 78：.github/check-browser-match.py 的双向验证。工作流用 141、本机 153 → 必须报；两边都是 153 → 不报；不写 browser（默认 141）、本机 141 → 不报；
仓库里 render-cet6-writing.yml 对 Chrome 153 必须通过。"""
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
ns = {}
exec((R / '.github/check-browser-match.py').read_text('utf-8').split("if __name__ == '__main__':")[0], ns)
check = ns['check']
C141, C153 = 'Chromium 141.0.7390.37', 'Google Chrome for Testing 153.0.8010.12'
wf_default = "      - uses: ./.github/actions/cet6-chalk-env\n      - name: x\n"
wf_153 = "      - uses: ./.github/actions/cet6-chalk-env\n        with:\n          browser: '153'\n      - name: x\n"
cases = [('默认 141 + 本机 153', wf_default, C153, True), ('153 + 本机 153', wf_153, C153, False),
         ('默认 141 + 本机 141', wf_default, C141, False), ('153 + 本机 141', wf_153, C141, True)]
bad = [n for n, wf, loc, want in cases if bool(check(wf, loc)) != want]
repo = subprocess.run([sys.executable, str(R / '.github/check-browser-match.py'), str(R / '.github/workflows/render-cet6-writing.yml'), '--local', C153],
                      capture_output=True, text=True)
print(f'{len(cases)} 种情况，判错 {len(bad)} 种 {bad}；仓库 render-cet6-writing.yml 对 Chrome 153：{"通过" if repo.returncode == 0 else "不通过"}')
ok = not bad and repo.returncode == 0
print('浏览器一致：双向通过' if ok else '浏览器一致：不通过')
sys.exit(0 if ok else 1)
