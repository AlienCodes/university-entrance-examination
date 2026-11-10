#!/usr/bin/env python3
"""独立做题的材料包（答案第二来源）：每套 = 识别出的英文录音文字（只取第一遍朗读：按 数据/<套>/时间轴.json 切材料）+ 题目选项（不含任何答案）。
同一段录音（原音.sha256 相同）且题目相同的套只放一次（做题结果共用，抽取/做题共用.json）。
没有解析答案（或不齐 20 个）的套要两次独立做题：两个包各放一次，由不同子代理做。
用法：python3 -I 做题包.py <输出目录> [包数=2]"""
import difflib, json, re, sys
from pathlib import Path
P = Path(__file__).resolve().parents[1]
SETS = json.loads((P / '套.json').read_text('utf-8'))
Q = json.loads((P / '抽取/定稿题.json').read_text('utf-8'))
out = Path(sys.argv[1]); npk = int(sys.argv[2]) if len(sys.argv) > 2 else 2
out.mkdir(parents=True, exist_ok=True)
ZH = re.compile(r'[一-鿿]{2}')
NOISE = re.compile(r'\W*(yeah|i|the|oh|ah|uh|um|hmm|mm|我|嗯|啊|一|是)?\W*', re.I)


def material(sid, s):
    K = P / '识别' / s['识别']
    cut = json.loads((K / '锚点.json').read_text('utf-8'))['cut']
    T = json.loads((P / '数据' / sid / '时间轴.json').read_text('utf-8'))
    B = [[b[0] - cut, b[1] - cut, b[3]] for b in json.loads((K / '分块.json').read_text('utf-8'))
         if b[1] > cut and not ZH.search(b[3]) and not NOISE.fullmatch(b[3])]
    seg = lambda a, b: ' '.join(x[2] for x in B if a <= x[0] < b)
    q = Q[s['题目']]; G = q['组']; L = []
    for i, (a, b) in enumerate(T['dlg']):
        t = [x[2] for x in B if (a - 0.5 if i else -1e9) <= x[0] < b + 0.1]
        h = len(t) // 2                              # 第一节读两遍的卷（2026）：两半几乎相同就只留前一半
        if h and difflib.SequenceMatcher(None, ' '.join(t[:h]), ' '.join(t[h:])).ratio() > 0.6: t = t[:h]
        L.append(f'[第{G[i][0]}题] ' + ' '.join(t))
    off = len(T['dlg'])
    for j, g in enumerate(T['grp']):
        q1, q2 = G[off + j]
        if 'play' in g:                       # 全国类：读两遍，只取前一半
            a, b = g['play'], g['ans'][0]
            L.append(f'[第{q1}—{q2}题] ' + seg(a - 0.1, (a + b) / 2))
        else:                                 # 上海 B：短文 → “Now listen again” → 短文 → 念题；取第一遍 + 念题
            blk = [x for x in B if g['start'] <= x[0] < g['ans'][1] and not re.search(r'directions|you will hear two', x[2], re.I)]   # 通用说明不要
            k = next((i + (x[1] - x[0] > 15) for i, x in enumerate(blk) if re.search(r'listen\W+again', x[2], re.I)), len(blk) // 2)
            qs = [x for x in blk[k:] if re.match(r'^\W*(questions?\W+)?(1[1-9]|20)\b', x[2], re.I)]
            L.append(f'[第{q1}—{q2}题] ' + ' '.join(x[2] for x in blk[:k]) + ' || 念题：' + ' '.join(x[2] for x in qs))
    qs = '\n'.join(f'{k}. {v.get("干", "")} | ' + ' | '.join(f'{L_}. {o}' for L_, o in v['选项'].items())
                   for k, v in sorted(q['题'].items(), key=lambda x: int(x[0])))
    return f'######## 套={sid}\n【录音（识别，可能有错字）】\n' + '\n'.join(L) + f'\n【题目】\n{qs}\n'


seen, share, items = {}, {}, []
for sid, s in SETS.items():
    q = Q[s['题目']]
    key = ((P / '识别' / s['识别'] / '原音.sha256').read_text().split()[0], json.dumps(q['题'], sort_keys=True))
    if key in seen: share[sid] = seen[key]; continue
    seen[key] = sid
    items.append((sid, len(q.get('解析答案') or {}) == 20, material(sid, s)))
# 有解析答案的轮流分进各包；没有的每个包都放（各包由不同子代理做 → 两次独立做题）
packs = [[] for _ in range(npk)]
for i, (sid, has, txt) in enumerate(items):
    for k in ([i % npk] if has else range(npk)): packs[k].append(txt)
for k, pk in enumerate(packs):
    t = '\n'.join(pk)
    (out / f'做题{k + 1:02d}.txt').write_text(t, 'utf-8')
    print(f'做题{k + 1:02d}', len(pk), '套', len(t), '字')
(P / '抽取/做题共用.json').write_text(json.dumps(share, ensure_ascii=False, indent=1), 'utf-8')
print(len(items), '套要做，两次做：', [s for s, h, _ in items if not h], '共用', share)
