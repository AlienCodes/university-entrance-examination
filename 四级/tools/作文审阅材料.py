"""生成范文审阅材料（只含文字）：题目 + 范文，按埋雷清单在副本里埋雷（每条必须恰好匹配一次）。
用法：python3 四级/tools/作文审阅材料.py 输出.md 年份或id前缀… [--雷 雷.py]   （雷.py 定义 M = [(id, 原文, 雷), …]）"""
import json, sys, pathlib, runpy
R = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(R / 'tools'))
import 作文规则 as r
a = sys.argv[1:]; mines = []
if '--雷' in a: i = a.index('--雷'); mines = runpy.run_path(a[i + 1])['M']; a = a[:i] + a[i + 2:]
out, pre = a[0], a[1:]
es = [e for p in sorted((R / '四级/作文').glob('20??.json'), reverse=True) for e in json.loads(p.read_text())
      if any(e['id'].startswith(x) or e['id'][1:5] == x for x in pre) and e['body']]
idx = {e['id']: e for e in es}
for i, x, y in mines:
    n = sum(p.count(x) for p in idx[i]['body'])
    if n != 1: sys.exit(f'雷匹配 {n} 次：{i} {x!r}')
    idx[i]['body'] = [p.replace(x, y) for p in idx[i]['body']]
L = []
for e in es:
    L += [f"## {e['id']}　{e['paper']}　{e['type']}", '', '**题目**', '', e['prompt'], '', f"**范文**（{r.counted(e)} 词）", '']
    if e.get('title'): L += [f"Title: {e['title']}", '']
    if e.get('salutation'): L += [e['salutation'], '']
    L += [p + '\n' for p in e['body']]
    if e.get('closing'): L += [e['closing'], e.get('signature', ''), '']
pathlib.Path(out).write_text('\n'.join(L))
print(len(es), '篇', len(mines), '雷 →', out)
