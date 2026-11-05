"""四级听力关卡 2—4 双向验证（故意放错，必须报出；正常 0 处）。
  关卡 2 定稿：识别里放一个错词（官方原文与 otter 都对）→ 必须按原文改回；官方原文改成另一个真词（识别与 otter 都对）→ 必须进待核
  关卡 3 题目：换成别的套的选项 → 内容配对报；选项里放 OCR 残损（secunty）→ 报；念题少一道（Question 5 改掉）→ 念题锚点报
  关卡 4 答案：做题结果改一个字母 → 答案.py 报不一致
用法：python3 tools/防复发/验证/四级听力关卡.py"""
import copy, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '四级/听力/tools'))
import 定稿 as G, 题目 as T, 答案 as A
ok = True


def check(name, cond):
    global ok
    print(('✅' if cond else '❌'), name); ok &= bool(cond)


S = '201806-1'
rid, P, O, R, layer = G.sources(S)
base = G.run(S, quiet=True, P_override=copy.deepcopy(P))
check('关卡 2 正常：0 待核', not base['待核'])
# 识别里放错词：找一个三方都相同的实词
W = [x[0] for x in P]
k = next(i for i in range(200, len(W)) if W[i].lower() == 'students')
P2 = copy.deepcopy(P); P2[k][0] = 'stewards'
r = G.run(S, quiet=True, P_override=P2)
check(f'关卡 2 识别错词 students→stewards 按原文改回', any(c['位置'] == f'{k}:{k + 1}' and 'students' in c['改为'] for c in r['改动']))
R2 = list(R); j = next(i for i, w in enumerate(R2) if w.lower().strip('.,') == 'students'); R2[j] = 'studies'
r = G.run(S, quiet=True, R_override=R2, P_override=copy.deepcopy(P))
check('关卡 2 原文换成另一个真词 → 待核', len(r['待核']) >= 1)

words = [w[0] for w in json.loads((ROOT / f'四级/听力/{S}/定稿.json').read_text('utf-8'))['词']]
b, _ = T.run(S, quiet=True, words=words)
check('关卡 3 正常：0 处（除答案未裁定）', not [x for x in b if '答案没有裁定' not in x])
Q, _ = T.parse_options(T.paper_txt('202306-2'))
b, _ = T.run(S, quiet=True, words=words, Qover=Q)
check('关卡 3 换成别的套的选项 → 内容配对报', any('内容配对' in x or '中位数' in x for x in b))
Q, _ = T.parse_options(T.paper_txt(S)); Q[3]['C'] = 'Identify the suspect on the secunty video.'
b, _ = T.run(S, quiet=True, words=words, Qover=Q)
check('关卡 3 选项 OCR 残损 → 报', any('不认识' in x for x in b))
import 念题锚点 as N, re
w2 = ' '.join(words).replace('Question five', 'Question fife', 1).replace('Question 5', 'Question fife', 1)
d = json.loads((ROOT / f'四级/听力/{S}/定稿.json').read_text('utf-8'))
t = w2
miss = [name for name, rx, k in N.need() if len(re.findall(rx, t, re.I)) != k]
check('关卡 3 念题少一道 → 念题锚点报', 'Question 5' in miss)

o, b = A.run(S)
check('关卡 4 正常：两来源一致 25 题', len(o) == 25 and not b)
f = ROOT / f'四级/听力/{S}/做题.json'; old = f.read_text('utf-8')
try:
    d = json.loads(old); d['答案']['7'] = {'A': 'B', 'B': 'C', 'C': 'D', 'D': 'A'}[d['答案']['7']]; f.write_text(json.dumps(d, ensure_ascii=False), 'utf-8')
    o, b = A.run(S)
    check('关卡 4 做题改一个答案 → 报不一致', any(n == '7' for n, _, _ in b))
finally:
    f.write_text(old, 'utf-8')
sys.exit(0 if ok else 1)
