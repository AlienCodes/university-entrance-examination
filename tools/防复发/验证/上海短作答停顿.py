"""短作答停顿不能把上海相邻两题合并；编号不唯一或倒序必须停。

纯 Python：真实 10 套上海数据逐套回归；旧停顿分组须在 2023 秋考报 9 段。
"""
import ast
import copy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
ENG = ROOT / '高考听力/tools/听力视频.py'
tree = ast.parse(ENG.read_text('utf-8'))
ns = {'re': re}
for name in ['clusters', 'shanghai_a']:
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(ENG), 'exec'), ns)


def inputs(row):
    base = ROOT / '高考听力/识别' / row['识别']
    cut = json.loads((base / '锚点.json').read_text())['cut']
    blocks = [[max(0, a-cut), b-cut, lang, text] for a, b, lang, text in
              json.loads((base / '分块.json').read_text()) if b > cut + .05]
    end = [b for b in blocks if re.search(r'听力(部分|考试)?到此结束|end of (the )?listening', b[3], re.I)]
    en = [b for b in blocks if b[0] < (end[0][0] if end else 1e9) and re.search(r'[A-Za-z0-9]', b[3])]
    sb = next(b[0] for b in en if re.search(r'section\s*b', b[3], re.I))
    return [b for b in en if b[0] < sb and not
            (b[1]-b[0] <= 1.3 and re.fullmatch(r'\W*(yeah|i|the|oh|ah|uh|um|hmm|mm|我|嗯|啊|一|是)?\W*', b[3], re.I))]


def old(blocks):
    return [c for c in ns['clusters'](blocks, 4.0) if not
            (sum(x[1]-x[0] for x in c) < 2.5 and len(''.join(x[3] for x in c)) <= 4)]


papers = json.loads((ROOT / '高考听力/套.json').read_text())
checked = 0
for sid, row in papers.items():
    if '上海' not in row['名']:
        continue
    blocks = inputs(row)
    groups = ns['shanghai_a'](blocks)
    assert len(groups) == 10 and sum(map(len, groups)) == len(blocks), sid
    if sid == '2023-shq':
        assert len(old(blocks)) == 9
        assert abs(groups[4][0][0] - 129.47) < 1e-8 and abs(groups[3][-1][1] - 125.77) < 1e-8
    else:
        assert groups == old(blocks), f'{sid} 原有分组发生变化'
    checked += 1

blocks = inputs(papers['2023-shq'])
i = next(i for i, b in enumerate(blocks) if re.match(r'^5\W', b[3]))
mutations = []
b = copy.deepcopy(blocks); b[i][3] = 'no number here'; mutations.append(b)
b = copy.deepcopy(blocks); b.insert(i+1, [b[i][0]+.01, b[i][1], 'en', '5, duplicate']); mutations.append(b)
b = copy.deepcopy(blocks)
j = next(j for j, x in enumerate(b) if re.match(r'^6\W', x[3]))
b[i][3], b[j][3] = b[j][3], b[i][3]; mutations.append(b)
for b in mutations:
    try:
        ns['shanghai_a'](b)
    except ValueError:
        continue
    raise AssertionError('缺失、重复或倒序编号没有被拦住')
print(f'通过：{checked}套上海真实数据；旧规则2023秋考9段、新规则10段；3种错误均拦截。')
