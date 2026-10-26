"""一次性：由 作文题截取.py 的输出生成 四级/作文/<年>.json 骨架（body 留空；已存在的篇目保留 body）。
OCR 订正逐条写在 FIX（每条必须恰好匹配一次）；2021-06 三套截不到，按 PDF 原页手录。"""
import json, re, pathlib, subprocess, sys
D = pathlib.Path(__file__).resolve().parents[1]
raw = subprocess.run([sys.executable, str(D / 'tools/作文题截取.py')], capture_output=True, text=True).stdout
FIX = {('2022-06', 1): [('fo r ', 'for ')], ('2022-06', 2): [('fo r ', 'for '), ("students'", 'students’')],
       ('2021-12', 3): [('have丿ust', 'have just'), ('report. ou should', 'report. You should')],
       ('2021-12', 2): [('aim , ', 'aim, ')], ('2021-12', 1): [('the f reshmen', 'the freshmen')]}
# 2021-06 三套 txt 是乱码 OCR，按 PDF 原页手录（标题 + 参考陈述）
MANUAL = {
 ('2021-06', 1): "Directions: For this part, you are allowed 30 minutes to write an essay titled “Are people becoming addicted to technology?”. The statement given below is for your reference. You should write at least 120 words but no more than 180 words.\n\nNumerous studies claim that addiction to technology is real and it has the same effect on the brain as drug addiction.",
 ('2021-06', 2): "Directions: For this part, you are allowed 30 minutes to write an essay titled “Is technology making people lazy?”. The statement given below is for your reference. You should write at least 120 words but no more than 180 words.\n\nMany studies claim that computers distract people, make them lazy thinkers and even lower their work efficiency.",
 ('2021-06', 3): "Directions: For this part, you are allowed 30 minutes to write an essay titled “Do violent video games lead to violence?”. The statement given below is for your reference. You should write at least 120 words but no more than 180 words.\n\nA growing body of research finds that violent video games can make kids act aggressively in their real world relationships, causing an increase in violence.",
}
items = {}
for blk in re.split(r'^=== ', raw, flags=re.M)[1:]:
    head, _, txt = blk.partition('\n')
    m = re.match(r'(\d{4}-\d\d) 第(\d)套', head); k = (m[1], int(m[2]))
    txt = MANUAL.get(k) or txt.strip()
    assert txt != '截取失败', k
    for a, b in FIX.get(k, []):
        assert txt.count(a) == 1, (k, a); txt = txt.replace(a, b)
    assert '"' not in txt and "'" not in txt.replace('’', ''), k
    items[k] = txt
for y in sorted({k[0][:4] for k in items}):
    p = D / '作文' / f'{y}.json'
    old = {e['id']: e for e in json.loads(p.read_text())} if p.exists() else {}
    out = []
    for (ym, n), txt in sorted(items.items(), key=lambda kv: (kv[0][0], kv[0][1]), reverse=True):
        if ym[:4] != y: continue
        i = f'c{ym}-{n}'
        t = re.search(r'essay titled “([^”]+)”', txt)
        lim = re.search(r'at least \d+ words but (?:no|not) more than \d+ words', txt)[0]
        typ = ('命题作文（给定标题 + 参考陈述）' if t else '应用文（报告）' if 'write a report' in txt
               else '应用文（建议书）' if 'write a proposal' in txt else '情景作文' if 'Suppose' in txt else '议论文')
        e = {'id': i, 'paper': f'{ym[:4]}年{int(ym[5:])}月大学英语四级 第{n}套', 'part': 'Part I Writing', 'type': typ,
             'limit': lim, 'prompt': txt}
        if t: e['title'] = t[1]
        e['body'] = old.get(i, {}).get('body', [])
        out.append(e)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(y, len(out))
