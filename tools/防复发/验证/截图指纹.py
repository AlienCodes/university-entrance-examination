"""踩坑 36：截图审阅指纹必须覆盖生成画面要用的每一个文件（引擎、排版检查、共用断行规则 zh_bind、分词补充、字号、人名、样式字体、该篇数据与分屏）。
逐个把这些文件的内容改一个字节，指纹都必须变；原样必须不变。"""
import os
import sys
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[3]
os.environ.setdefault('DZB_VARIANT', '水墨')
sys.path.insert(0, str(R / '专八' / 'tools'))
import make_video as M  # noqa: E402

look = 'C'
base = M.fingerprint('t01', look)
must = [Path(M.__file__).resolve(), M.QA / 'layoutcheck.py', M.QA / '分词补充.txt', M.QA / 'zh_bind.py', M.HERE / '字号.json', M.T / '人名.json', *M.look_files(look)]
orig = Path.read_bytes
bad = []
for f in must:
    def rb(self, f=f):
        b = orig(self)
        return b + b' ' if Path(self).resolve() == Path(f).resolve() else b
    with mock.patch.object(Path, 'read_bytes', rb):
        if M.fingerprint('t01', look) == base:
            bad.append(f'{Path(f).relative_to(R)} 改了，指纹不变')
same = M.fingerprint('t01', look) == base
print(f'检查 {len(must)} 个文件：{len(must) - len(bad)} 个改动会让指纹变；原样重算{"不变" if same else "变了"}')
for x in bad:
    print('  ❌', x)
ok = not bad and same
print('截图指纹：双向通过' if ok else '截图指纹：不通过')
sys.exit(0 if ok else 1)
