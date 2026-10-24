"""生成翻译标注用的英文输入（每篇一个 kNN.txt：段落标记 + 每句一行 “[n] EN: …”，n 与标注文件的句号一致）。

    /opt/ttsenv/bin/python 考研/tools/gen_en.py <输出目录>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
for r in json.loads((ROOT / '阅读' / 'sents.json').read_text('utf-8')):
    L, n = [f"# {r['id']} {r['paper']} {r['passage']}（英文已精校封版，不要改）"], 0
    for k, para in enumerate(r['sents'], 1):
        L.append(f'¶{k}')
        for s in para:
            n += 1
            L.append(f'[{n}] EN: {s}')
    (out / f"{r['id']}.txt").write_text('\n'.join(L) + '\n', 'utf-8')
print('→', out)
