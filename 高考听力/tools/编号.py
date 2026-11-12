#!/usr/bin/env python3
"""套.json：ASCII 编号（工作流、资产名用）→ 中文卷名（片头、文件名）、题目（抽取/定稿题.json 的键）、录音（识别/ 的目录）。
同一套有两段录音的（2020 新课标Ⅰ卷：版本一 = 该卷题目，版本二与Ⅱ、Ⅲ卷录音相同；2020 山东第 1 / 2 次）按 选录音 的结果。
2023 上海卷（秋考）第 18—20 题已按老师授权、对照原声补齐，纳入全部 50 套。用法：python3 -I 编号.py"""
import json, re
from pathlib import Path
P = Path(__file__).resolve().parents[1]
CODE = [('上海卷（春考）', 'shc'), ('上海卷（秋考）', 'shq'), ('新课标Ⅰ卷', 'xkb1'), ('新课标Ⅱ卷', 'xkb2'), ('新课标Ⅲ卷', 'xkb3'),
        ('新高考Ⅰ卷', 'xgk1'), ('新高考Ⅱ卷', 'xgk2'), ('江苏卷', 'js'), ('浙江卷（1月）', 'zj1'), ('浙江卷（6月）', 'zj6'),
        ('浙江卷（7月）', 'zj7'), ('全国甲卷', 'jia'), ('全国乙卷', 'yi')]
SKIP = {'2020 新课标Ⅰ卷（版本二）': '与新课标Ⅱ卷同一份录音、同一套题'}
REC = {'2020 新课标Ⅰ卷': '2020 新课标Ⅰ卷（版本一）'}
REC.update(json.loads((P / '识别/选录音.json').read_text('utf-8')) if (P / '识别/选录音.json').exists() else {})
Q = json.loads((P / '抽取/定稿题.json').read_text('utf-8'))
out = {}
for k in sorted(Q):
    if k in SKIP: continue
    y, paper = k.split(' ', 1)
    code = next(c for n, c in CODE if paper.startswith(n))
    rec = REC.get(k, k)
    if not (P / '识别' / rec / '分块.json').exists(): print('缺录音识别', k, rec); continue
    out[f'{y}-{code}'] = {'名': k, '题目': k, '识别': rec}
(P / '套.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')
print(len(out), '套；不做', SKIP)
