"""对 六级/作文/<年>.json 的正文做逐条替换：每条 (id, 原文, 新文) 必须恰好匹配一次，否则报错、一处不改。
用法：python3 六级/tools/作文改句.py 改动.py   （改动.py 里定义 R = [(id, a, b), …]）"""
import json, sys, pathlib, runpy
D = pathlib.Path(__file__).resolve().parents[1] / '作文'
R = runpy.run_path(sys.argv[1])['R']
files = {p: json.loads(p.read_text()) for p in D.glob('20??.json')}
idx = {e['id']: e for d in files.values() for e in d}
for i, a, b in R:
    n = sum(x.count(a) for x in idx[i]['body'])
    if n != 1: sys.exit(f'{i} 匹配 {n} 次：{a!r}')
for i, a, b in R: idx[i]['body'] = [x.replace(a, b) for x in idx[i]['body']]
for p, d in files.items(): p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n')
print('改了', len(R), '处')
