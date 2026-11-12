"""踩坑 129 双向验证：四级听力 定稿.py 补的题号（只补 Question）要留给引擎贴着后一个词插值，原识别词保留时刻；词时刻不许倒序。
  旧定稿（f31f309 的 202306-1）：time_problems 必须报出 Question twenty four 倒序；现在重算的 35 套：0 处；
  202306-1 重算后 “twenty four.” 保留识别时刻 1381.19（作答停顿之后）；run() 里必须调用 time_problems。
用法：python3 tools/防复发/验证/补词时刻.py"""
import copy, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '四级/听力/tools'))
import 定稿 as G
ok = True


def check(name, cond):
    global ok
    print(('✅' if cond else '❌'), name); ok &= bool(cond)


# f31f309 的 202306-1 定稿第 2479—2483 个词（原样）
old = [['Americans', 1364.63, 1365.27, 0], ['Question', 1365.47, 1365.41, 0], ['twenty', 1365.41, 1365.36, 0], ['four.', 1365.36, 1365.32, 0], ['What', 1382.55, 1382.63, 0]]
check('旧定稿 202306-1 报倒序（Question twenty four）', any(w[1] == 'Question' for w in G.time_problems(old)))
rid, P, O, R, layer = G.sources('202306-1')
new = G.run('202306-1', quiet=True, P_override=copy.deepcopy(P))['词']
i = next(k for k in range(len(new) - 2) if [w[0] for w in new[k:k + 3]] == ['Question', 'twenty', 'four.'])
check('202306-1 重算：Question 留空、twenty four. 保留识别时刻（停顿之后）', new[i][1] is None and new[i + 1][1] == 1381.19)
bad = [p.parent.name for p in sorted((ROOT / '四级/听力').glob('*/定稿.json')) if G.time_problems(json.loads(p.read_text('utf-8'))['词'])]
check(f'35 套现在的定稿 0 处倒序 {bad}', not bad)
check('run() 调用 time_problems', 'tp = time_problems(words)' in (ROOT / '四级/听力/tools/定稿.py').read_text('utf-8'))
sys.exit(0 if ok else 1)
