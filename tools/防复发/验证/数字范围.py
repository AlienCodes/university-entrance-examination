"""专八 t15 年份“1756— / 1791”断开（新情况检测 2026-10-23）：zh_bind.zh_spans ⑦ 数字范围整体不断开的双向验证。
现在的 zh_bind：每个数字范围都在某个不断开的片段里；改之前的版本（git 提交 ca9f2f8）：不在。"""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

R = Path(__file__).resolve().parents[3]
import jieba  # noqa: E402

CASES = ['沃尔夫冈·阿马德乌斯·莫扎特（1756—1791），由汤姆', '萨列里（1750—1825）在病重时', '公元前2000—1800年间']


def covered(mod):
    res = []
    for t in CASES:
        i = t.index('—')
        res.append(any(a < i < b and a < i + 1 < b for a, b in mod.zh_spans(t, jieba)))
    return res


def load(path):
    spec = importlib.util.spec_from_file_location('zb', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


now = covered(load(R / '中考/tools/画面核查/zh_bind.py'))
old_src = subprocess.run(['git', '-C', str(R), 'show', 'ca9f2f8:中考/tools/画面核查/zh_bind.py'], capture_output=True, text=True).stdout
with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, dir=R / '中考/tools/画面核查') as f:
    f.write(old_src)
try:
    old = covered(load(f.name))
finally:
    Path(f.name).unlink()
ok = all(now) and not any(old)
print(f'现在：{now}；改之前：{old}')
print('数字范围：双向通过' if ok else '数字范围：不通过')
sys.exit(0 if ok else 1)
