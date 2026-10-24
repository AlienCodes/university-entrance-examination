"""双向验证：仓库检查（踩坑 42、43、52、68 工作流；47 软链接）。埋雷必须报出，现在的仓库与正常写法必须为 0。
    python3 tools/防复发/验证/仓库检查.py"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

H = Path(__file__).resolve().parents[1] / '仓库检查.py'
spec = importlib.util.spec_from_file_location('ck', H)
ck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ck)
bad = []


def case(name, errs, want, has=''):
    ok = bool(errs) == want and (not want or not has or any(has in e for e in errs))
    print(f"  {'✅' if ok else '❌'} {name}（{len(errs)} 处）")
    if not ok:
        bad.append(f'{name}：{errs[:2]}')


GOOD = """name: t
on: push
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          sparse-checkout: |
            tools/
            !/考研/真题/
      - name: build
        run: python3 x.py
"""
case('正常工作流 → 0', ck.check_workflow('new.yml', GOOD), False)
# 踩坑 68 原样重现：用字符串替换删掉“!/考研/真题/”这一行，只删了文字、留下缩进和换行之外的部分
broken = GOOD.replace('!/考研/真题/\n', '')
case('删行留缩进，下一步被并进字符串 → 报（踩坑 68）', ck.check_workflow('new.yml', broken), True, '踩坑 68')
case('YAML 坏了 → 报', ck.check_workflow('new.yml', GOOD + '  bad: [\n'), True, 'YAML')
case('新工作流用 softprops → 报（踩坑 42）', ck.check_workflow('new.yml', GOOD.replace('python3 x.py', 'echo') + '      - uses: softprops/action-gh-release@v2\n'), True, '踩坑 42')
case('新工作流用 zip -0 → 报（踩坑 52）', ck.check_workflow('new.yml', GOOD.replace('python3 x.py', 'zip -0 -r a.zip d')), True, '踩坑 52')
case('新工作流用 unzip -l → 报（踩坑 43）', ck.check_workflow('new.yml', GOOD.replace('python3 x.py', 'unzip -l a.zip | grep x')), True, '踩坑 43')
legacy = sorted(ck.LEGACY)[0]
case('登记的旧流程用 zip -0 → 放', ck.check_workflow(legacy, GOOD.replace('python3 x.py', 'zip -0 -r a.zip d')), False)
case('登记的旧流程已改好却还在 LEGACY → 报（只许减少）', ck.check_workflow(legacy, GOOD), True, 'LEGACY')
case('现在仓库里的全部工作流 → 0', ck.check_workflows(), False)

with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as out:
    root = Path(d)
    (root / 'tools').mkdir()
    (root / 'tools' / 'real.onnx').write_text('x')
    (root / 'tools' / 'inner').symlink_to(root / 'tools' / 'real.onnx')
    case('仓库内的软链接 → 0', ck.check_symlinks(root), False)
    Path(out, 'm.onnx').write_text('x')
    (root / 'tools' / 'outer').symlink_to(Path(out, 'm.onnx'))
    case('软链接指向临时目录 → 报（踩坑 47）', ck.check_symlinks(root), True, '仓库外')
    os.remove(Path(out, 'm.onnx'))
    case('临时目录删了、软链接断了 → 报（踩坑 47）', ck.check_symlinks(root), True, '断掉')
case('现在仓库里的软链接 → 0', ck.check_symlinks(), False)

print('仓库检查双向验证：' + ('全部通过' if not bad else f'{len(bad)} 处失败\n  ' + '\n  '.join(bad)))
sys.exit(1 if bad else 0)
