"""把 <年>.py 草稿（B = {id: [段落, …]}）写进 四级/作文/<年>.json，打印字数。
用法：python3 四级/tools/作文写入.py 草稿.py"""
import json, sys, pathlib, runpy
R = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(R / 'tools'))
import 作文规则 as r
B = runpy.run_path(sys.argv[1])['B']
for y in sorted({i[1:5] for i in B}):
    p = R / '四级/作文' / f'{y}.json'; d = json.loads(p.read_text())
    for e in d:
        if e['id'] in B:
            e['body'] = B[e['id']]
            n = r.wc(' '.join(e['body'])) - (r.wc(e['first']) if 'not including' in e['limit'] else 0)
            print(e['id'], n)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n')
