"""翻译复核埋雷：把某篇的复核文件复制成新编号，按埋雷文件逐条替换（每条必须恰好匹配一次），检验复核员是否认真（必须全部查出）。

    /opt/ttsenv/bin/python 考研/tools/plant_review.py <复核文件目录> <埋雷位置.json>
埋雷文件格式与专八 翻译复核/第一轮埋雷位置.json 相同：{新编号: {"from": 原编号, "errors": [[原文, 改成, 说明], …]}}
"""
import json
import sys
from pathlib import Path

d, spec = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text('utf-8'))
for cid, s in spec.items():
    t = (d / f"{s['from']}.txt").read_text('utf-8')
    for old, new, _ in s['errors']:
        assert t.count(old) == 1, (cid, old, t.count(old))
        t = t.replace(old, new)
    t = t.replace(f"# {s['from']} ", f"# {cid} ", 1)
    (d / f'{cid}.txt').write_text(t, 'utf-8')
    print(cid, '←', s['from'], len(s['errors']), '处')
