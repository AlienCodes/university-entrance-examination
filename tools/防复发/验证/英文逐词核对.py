"""踩坑 107 双向验证：英文逐词核对.judge——同一个词出现几次，每一处都要读对。
用整片 v2 实测的识别结果（不重跑识别）：s3b1 take1 两处 towed 识别成 ['told Yung', 'towed out of']，旧规则（任一处对）锁定、新规则必须报出；
s11b1 take2 drove 只一处 ['Drove away.']，新旧规则都放行；一处都没对上（'（对不上）'）两种都不放行。"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
src = (ROOT / '高考续写/tools/英文逐词核对.py').read_text('utf-8')
tree = ast.parse(src)
ns = {'re': re}
exec(compile(ast.Module([n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'judge'], []), 'judge', 'exec'), ns)
judge = ns['judge']


def old(got, words):
    return all(any(re.search(rf'\b{re.escape(wd)}\b', r, re.I) for r in got.get(wd, [])) for wd in words)


cases = [('s3b1 take1 两处 towed 一处读成 told', {'towed': ['told Yung', 'towed out of']}, ['towed'], True, False),
         ('s11b1 take2 drove 一处读对', {'drove': ['Drove away.']}, ['drove'], True, True),
         ('s11b1 take1 对不上', {'drove': ['（对不上）']}, ['drove'], False, False),
         ('两处都读对', {'towed': ['towed it', 'have it towed out']}, ['towed'], True, True)]
bad = []
for name, got, ws, want_old, want_new in cases:
    o, n = old(got, ws), bool(judge(got, ws))
    print(f'  {"✅" if (o, n) == (want_old, want_new) else "❌"} {name}：旧规则 {o}（应 {want_old}），新规则 {n}（应 {want_new}）')
    if (o, n) != (want_old, want_new):
        bad.append(name)
print('英文逐词核对双向验证：' + ('全部通过' if not bad else f'失效 {bad}'))
sys.exit(1 if bad else 0)
