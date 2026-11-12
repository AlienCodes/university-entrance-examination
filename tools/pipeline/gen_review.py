"""从 data/vocab.json 生成复核用的文本文件（每篇一个），格式与 annreview3 相同。
    python3 gen_review.py <输出目录>
"""
import json
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
D = json.load(open(Path(__file__).resolve().parents[2] / 'data' / 'vocab.json'))
TIER = {'core': '高中核心', 'ext': '超纲拓展', 'phr': '短语'}
RECALL = {'f34', 'f35'}   # 2026 天津卷两次均为回忆版
n = 0
for p in D['passages']:
    if not p.get('done'):
        continue
    L = [f"# {p['id']} {p['name']}" + ('（回忆版试卷，原文更可能有抄录错误）' if p['file'] in RECALL else ''),
         f"标题: {p['title']}", f"体裁: {p['genre']}", f"概要: {p['summary']}", '']
    k = 0
    for para in p['paras']:
        for s in para:
            k += 1
            L.append(f"[{k}] EN: {s['en']}")
            L.append(f"    ZH: {s['zh']}")
            for w in s['w']:
                surf = ' … '.join(s['en'][a:b] for a, b in w['sp'])
                L.append(f"    - {w['h']}  ({TIER[w['t']]})  {w['m']}   ← 高亮原文: \"{surf}\"")
        L.append('')
    (OUT / f"{p['id']}.txt").write_text('\n'.join(L), 'utf-8')
    n += 1
print('written', n)
