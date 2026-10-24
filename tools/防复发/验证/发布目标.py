"""踩坑 53：.github/check-release-target.py 的双向验证。7 种钉在触发提交上的写法必须全报，用分支名的写法必须不报；仓库里现有工作流必须通过。"""
import importlib.util
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('crt', R / '.github/check-release-target.py')
src = (R / '.github/check-release-target.py').read_text('utf-8')
ns = {}
exec(src.split('bad = []')[0], ns)
BAD = ns['BAD']
mines = ['gh release create "$TAG" --target "$GITHUB_SHA"', 'gh release create x --target ${GITHUB_SHA}', 'gh release create x --target ${{ github.sha }}',
         'gh release create x --target=$GITHUB_SHA', 'gh api -f target_commitish=$GITHUB_SHA', 'target_commitish: ${{ github.sha }}', "gh release create x --target '${{ github.sha }}'"]
safe = ['gh release create x --target "$GITHUB_REF_NAME"', 'target_commitish: ${{ github.ref_name }}', 'echo $GITHUB_SHA > sha.txt']
miss = [m for m in mines if not BAD.search(m)]
false = [m for m in safe if BAD.search(m)]
repo = subprocess.run([sys.executable, str(R / '.github/check-release-target.py')], cwd=R, capture_output=True, text=True)
print(f'埋雷 {len(mines)} 种，报出 {len(mines) - len(miss)}；正确写法误报 {len(false)}；仓库工作流：{"通过" if repo.returncode == 0 else "不通过"}')
for m in miss + false:
    print('  ', m)
ok = not miss and not false and repo.returncode == 0
print('发布目标：双向通过' if ok else '发布目标：不通过')
sys.exit(0 if ok else 1)
