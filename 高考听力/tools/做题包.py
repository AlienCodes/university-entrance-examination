#!/usr/bin/env python3
"""独立做题的材料包：每套 = 识别出的录音文字（剪切点之后；第二遍朗读与第一遍几乎相同的块去掉）+ 题目选项（不含任何答案）。
同录音且题目完全相同的套只放一次（做题结果两套共用）。用法：python3 -I 做题包.py <输出目录> <每包套数>"""
import difflib, json, sys
from pathlib import Path
P = Path(__file__).resolve().parents[1]
SETS = json.loads((P / '套.json').read_text('utf-8'))
Q = json.loads((P / '抽取/定稿题.json').read_text('utf-8'))
out, n = Path(sys.argv[1]), int(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
seen, items, share = {}, [], {}
for sid, s in SETS.items():
    q = Q[s['题目']]
    key = (s['识别'], json.dumps(q['题'], sort_keys=True))
    if key in seen: share[sid] = seen[key]; continue
    seen[key] = sid
    K = P / '识别' / s['识别']
    cut = json.loads((K / '锚点.json').read_text('utf-8'))['cut']
    txt, prev = [], []
    for b in json.loads((K / '分块.json').read_text('utf-8')):
        if b[1] <= cut or len(b[3]) <= 3: continue
        if len(b[3]) > 40 and any(difflib.SequenceMatcher(None, b[3], p).ratio() > 0.8 for p in prev[-12:]): continue
        prev.append(b[3]); txt.append(b[3])
    qs = '\n'.join(f'{k}. {v.get("干", "")}\n' + '\n'.join(f'   {L}. {o}' for L, o in v['选项'].items()) for k, v in sorted(q['题'].items(), key=lambda x: int(x[0])))
    items.append(f'######## 套={sid}\n【录音文字（语音识别，可能有错字；第二遍朗读已去掉）】\n' + '\n'.join(txt) + f'\n【题目】\n{qs}\n')
for i in range(0, len(items), n):
    (out / f'做题{i // n + 1:02d}.txt').write_text('\n'.join(items[i:i + n]), 'utf-8')
    print(f'做题{i // n + 1:02d}', len('\n'.join(items[i:i + n])), '字')
(P / '抽取/做题共用.json').write_text(json.dumps(share, ensure_ascii=False, indent=1), 'utf-8')
print(len(items), '套要做，共用', share)
