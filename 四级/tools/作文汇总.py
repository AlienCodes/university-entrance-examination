"""四级作文范文：把 四级/作文/<年份>.json 汇总成一份可读的 Markdown（2026 → 2021），字数用 tools/作文规则.counted（与作文检查同一处）。"""
import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1] / '作文'
sys.path.insert(0, str(ROOT.parents[1] / 'tools'))
import 作文规则 as r
out = ['# 大学英语四级作文范文（2026—2021，共 31 套）', '',
       '字数：题目要求 150—200 词，范文一律写到 190—200 词（2023 年 12 月三套题目写明不含给定首句，字数不含首句）。', '']
n = 0
for y in sorted((p.stem for p in ROOT.glob('20??.json')), reverse=True):
    for e in json.loads((ROOT / f'{y}.json').read_text()):
        n += 1
        out += [f"## {e['paper']}　{e['type']}", '', f"**题目**（字数要求 {e['limit']}；范文 {r.counted(e)} 词）", '']
        out += ['> ' + l if l else '>' for l in e['prompt'].split('\n')] + ['', '**范文**', '']
        if e.get('title'): out += [f"**{e['title']}**", '']
        if e.get('salutation'): out += [e['salutation'], '']
        for p in e['body']: out += [p, '']
        if e.get('closing'): out += [e['closing'] + '  ', e['signature'], '']
        elif e.get('signature'): out += [e['signature'], '']
        out += ['---', '']
(ROOT / '四级作文范文.md').write_text('\n'.join(out))
print('ok', n, '篇', ROOT / '四级作文范文.md')
