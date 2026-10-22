"""考研作文范文：把 考研/作文/<年份>.json 汇总成一份可读的 Markdown（2026 → 2021），并统计字数。"""
import json, re, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1] / '作文'
WRE = re.compile(r"[A-Za-z0-9]+(?:[’'\-.][A-Za-z0-9]+)*%?")
def wc(e): return sum(len(WRE.findall(p)) for p in e['body'])
out = ['# 考研英语作文范文（2026—2021，英语一 / 英语二，Part A + Part B）', '']
for y in sorted((p.stem for p in ROOT.glob('20??.json')), reverse=True):
    for e in json.loads((ROOT / f'{y}.json').read_text()):
        out += [f"## {e['paper']} {e['part']}　{e['type']}", '', f"**题目**（字数要求 {e['limit']}；范文 {wc(e)} 词）", '']
        out += ['> ' + l if l else '>' for l in e['prompt'].split('\n')] + ['', '**范文**', '']
        if e.get('title'): out += [f"**{e['title']}**", '']
        if e.get('salutation'): out += [e['salutation'], '']
        for p in e['body']: out += [p, '']
        if e.get('closing'): out += [e['closing'] + '  ', e['signature'], '']
        elif e.get('signature'): out += [e['signature'], '']
        out += ['---', '']
(ROOT / '考研作文范文.md').write_text('\n'.join(out))
print('ok', ROOT / '考研作文范文.md')
