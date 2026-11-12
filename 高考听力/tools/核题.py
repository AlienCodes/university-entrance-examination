#!/usr/bin/env python3
"""核子代理抽出的题：题数 20、选项数（上海 4，其余 3）、分组 = 标准结构、答案 A—D；两个来源逐字比；
只有一个来源时，题干 / 选项必须能在另一来源的原文字里找到（规范化后子串）。
用法：python3 -I 核题.py <抽取目录> <文字目录>  → 打印每套问题，写 <抽取目录>/定稿题.json（每套一个版本 + 答案）"""
import json, re, sys
from pathlib import Path

STD = [[i, i] for i in range(1, 6)]
SH = [[i, i] for i in range(1, 11)] + [[11, 13], [14, 16], [17, 20]]


def nz(t):
    t = (t or '').replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').replace('　', ' ')
    return re.sub(r'[^a-z0-9£$%]', '', t.lower())


def problems(k, v):
    p = []
    sh = '上海' in k
    qs = v.get('题') or {}
    if sorted(map(int, qs)) != list(range(1, 21)):
        p.append(f'题号 {sorted(map(int, qs))}')
    for n, q in qs.items():
        o = q.get('选项') or {}
        want = list('ABCD') if sh else list('ABC')
        if sorted(o) != want or not all(str(x).strip() for x in o.values()):
            p.append(f'第{n}题选项 {list(o)}')
        if not sh and not str(q.get('干', '')).strip():
            p.append(f'第{n}题无题干')
    g = v.get('组') or []
    if sh:
        if g != SH: p.append(f'组 {g}')
    else:
        if g[:5] != STD or sum(b - a + 1 for a, b in g[5:]) != 15 or len(g) != 10 or \
           any(g[i][0] != g[i - 1][1] + 1 for i in range(1, len(g))) or g[-1][1] != 20:
            p.append(f'组 {g}')
    a = v.get('答案') or {}
    if a and (sorted(map(int, a)) != list(range(1, 21)) or any(x not in 'ABCD' for x in a.values())):
        p.append(f'答案 {a}')
    return p


def main():
    src, txt = Path(sys.argv[1]), Path(sys.argv[2])
    allv = {}
    for f in sorted(src.glob('包*.json')):
        for k, srcs in json.loads(f.read_text('utf-8')).items():
            for s, v in (srcs or {}).items():
                if v: allv.setdefault(k, {})[s] = v
            allv.setdefault(k, {})
    out, bad = {}, 0
    for k, srcs in allv.items():
        vs = {s: v for s, v in srcs.items() if v}
        if not vs:
            print(f'{k}: 无听力题'); bad += 1; continue
        pr = {s: problems(k, v) for s, v in vs.items()}
        good = [s for s in vs if not pr[s]]
        msg = [f'{s}: {"; ".join(x[:3])}' for s, x in pr.items() if x]
        base = good[0] if good else next(iter(vs))
        B = vs[base]
        diff = []
        for s, v in vs.items():
            if s == base: continue
            for n, q in (B.get('题') or {}).items():
                q2 = (v.get('题') or {}).get(n) or {}
                if q.get('干') and q2.get('干') and nz(q['干']) != nz(q2['干']): diff.append(f'{n}干')
                for L, x in (q.get('选项') or {}).items():
                    if (q2.get("选项") or {}).get(L) and nz(x) != nz((q2.get("选项") or {}).get(L)): diff.append(f'{n}{L}')
        if len(vs) == 1:                       # 另一份原文字里找
            others = [p for p in txt.glob(f'{k}__*.txt') if not p.stem.endswith(base)]
            body = nz(' '.join(p.read_text('utf-8') for p in others))
            miss = []
            if body:
                for n, q in (B.get('题') or {}).items():
                    for L, x in [('干', q.get('干'))] + list((q.get('选项') or {}).items()):
                        if x and nz(x) not in body: miss.append(f'{n}{L}?')
            tot = sum(1 + len(q.get('选项') or {}) for q in (B.get('题') or {}).values())
            if len(miss) * 2 < tot: diff += miss          # 另一来源大半都找不到 = 它没印题目，不算不一致
        ans = {}
        for s, v in vs.items():
            for n, x in (v.get('答案') or {}).items():
                if ans.get(n, x) != x: diff.append(f'答案{n}')
                ans[n] = x
        if len(ans) < 20:                          # 程序补：答案表“1~5. CBAAB 6~10. …”
            for p in txt.glob(f'{k}__*.txt'):
                for a, b, L in re.findall(r'(?<!\d)(\d{1,2})\s*[~`\-—–至]\s*(\d{1,2})\s*[\.．:：、]?\s*([A-D]{2,10})(?![A-Za-z])', p.read_text('utf-8')):
                    a, b = int(a), int(b)
                    if 1 <= a < b <= 20 and b - a + 1 == len(L):
                        for i, x in enumerate(L):
                            if ans.get(str(a + i), x) != x: diff.append(f'答案{a + i}')
                            ans.setdefault(str(a + i), x)
        out[k] = {'来源': base, '组': B.get('组'), '题': B.get('题'), '解析答案': ans, '备注': [v.get('备注') for v in vs.values() if v.get('备注')]}
        if msg or diff:
            bad += 1
        print(f'{k}: {"OK" if not (msg or diff) else ""} {" | ".join(msg)} {"不一致:" + ",".join(diff[:12]) if diff else ""} 答案{len(ans)}')
    (src / '定稿题.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')
    print('有问题', bad, '/', len(allv))


main()
