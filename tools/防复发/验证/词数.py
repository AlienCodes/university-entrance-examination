"""踩坑 30 / 41 / 60a / 74：片头词数规则（tools/text_rules.word_count）的双向验证 + 各项目 vocab.json 与定稿句子一致。
旧规则 len(split()) 在埋雷句子上必须算错，新规则必须算对；正在做的项目（专八、考研）vocab.json 的词数必须等于从定稿句子重算的数。"""
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / 'tools'))
import text_rules as TR  # noqa: E402

CASES = [('He crossed the tarpaulin (防水布) quickly.', 5), ('the villages—just three of them', 6),
         ('It cost $5 … or 6 dollars – roughly.', 7), ('from 1756–1791 in Vienna', 5)]
bad = []
for t, n in CASES:
    if TR.word_count(t) != n:
        bad.append(f'新规则算错：{t!r} 得 {TR.word_count(t)}，应为 {n}')
if all(len(t.split()) == n for t, n in CASES):
    bad.append('埋雷无效：旧规则 len(split()) 在全部用例上都算对了，测不出区别')
for proj in ('专八', '考研'):
    for p in json.loads((R / proj / 'data' / 'vocab.json').read_text('utf-8'))['passages']:
        n = TR.word_count(' '.join(s['en'] for pa in p['paras'] for s in pa))
        if n != p['words']:
            bad.append(f'{proj} {p["id"]} 片头词数 {p["words"]} ≠ 定稿句子重算 {n}（重跑 build_vocab.py）')
print('\n'.join(bad) or '词数：全部通过')
sys.exit(1 if bad else 0)
