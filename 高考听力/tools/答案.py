#!/usr/bin/env python3
"""答案两源一致才写（总协调要求）：解析答案（定稿题.json 的 解析答案）× 独立做题（抽取/做题01、做题02.json，子代理只看识别文字 + 选项）。
没有解析答案（或不齐 20 个）的套：两个包各做一次，两次独立做题一致才写；共用录音且题目相同的套（做题共用.json）共用结果。
有一题不一致就不写那一套，列出来交人裁定（裁定写进 抽取/答案裁定.json：{套: {题: 字母, "理由": …}}）。
  python3 -I 答案.py            → 答案.json + 打印不一致"""
import json
from pathlib import Path
P = Path(__file__).resolve().parents[1]
S = json.loads((P / '套.json').read_text('utf-8'))
Q = json.loads((P / '抽取/定稿题.json').read_text('utf-8'))
share = json.loads((P / '抽取/做题共用.json').read_text('utf-8'))
W = [json.loads((P / f'抽取/做题0{k}.json').read_text('utf-8')) for k in (1, 2)]
RF = P / '抽取/答案裁定.json'
R = json.loads(RF.read_text('utf-8')) if RF.exists() else {}
out, bad = {}, {}
for sid, s in S.items():
    src = share.get(sid, sid)
    pa = Q[s['题目']].get('解析答案') or {}
    sols = [w[src] for w in W if src in w]
    if len(pa) == 20: refs = [('解析', pa)] + [('做题', x) for x in sols[:1]]
    else: refs = [(f'做题{i + 1}', x) for i, x in enumerate(sols)]
    if len(refs) < 2: bad[sid] = f'来源不够 {len(refs)}'; continue
    a, diff = {}, []
    for n in map(str, range(1, 21)):
        v = {k: x.get(n) for k, x in refs}
        if n in R.get(sid, {}): a[n] = R[sid][n]
        elif len(set(v.values())) == 1 and None not in v.values(): a[n] = v[refs[0][0]]
        else: diff.append(f'{n}:' + '/'.join(f'{k}{x}' for k, x in v.items()))
    if diff: bad[sid] = diff
    else: out[sid] = a
(P / '答案.json').write_text(json.dumps(out, ensure_ascii=False, indent=0), 'utf-8')
print(f'答案.json：{len(out)} 套两源一致；不一致 {len(bad)} 套')
for k, v in bad.items(): print(' ', k, v)
