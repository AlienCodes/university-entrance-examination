"""从 六级/data/vocab.json 生成复核用的文本文件（每篇一个）。  python3 六级/tools/gen_review.py <输出目录>"""
import json
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
D = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'vocab.json').read_text('utf-8'))
TIER = {'core': '单词', 'ext': '单词', 'phr': '短语'}
n = 0
for p in D['passages']:
    if not p.get('done'):
        continue
    L = [f"# {p['id']} 大学英语六级 {p['name']}", f"标题: {p['title']}", f"体裁: {p['genre']}", f"概要: {p['summary']}", '']
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
