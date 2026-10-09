"""把 58 篇六级仔细阅读切成句子，供翻译、标注、网页、视频使用。

    python3 六级/tools/split_sents.py

输入 六级/仔细阅读/passages.json（封版定稿），输出 六级/仔细阅读/sents.json：
[{id, year, month, set, passage, paper, part, words, sents: [[段1句1, 段1句2…], [段2…]]}]
切句规则与高考 tools/sent.py 相同（保护 Mr./Dr./U.S./e.g. 等缩写和人名首字母），
另加四、六级文章里出现的缩写。切完逐段校验：句子拼回去必须与原段落完全一致。
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ABBR = r'(?:Mr|Mrs|Ms|Dr|Prof|St|U\.S|U\.K|e\.g|i\.e|vs|etc|No|Inc|Nov|a\.m|p\.m|Jr|Ph\.D|E)'
NOSPLIT = []     # 个别需要人工指定不切开的位置：(篇号, 原文片段)


def split(p):
    q = re.sub(r'\b(' + ABBR + r')\.(?=\s+[a-z])|\b(' + ABBR + r')\.(?!\s*$)(?=\s+(?:[A-Z][a-z]+\s)?(?:[a-z]|coli))',
               lambda m: m.group(0).replace('.', '<DOT>'), p)
    q = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|St|Jr|vs|e\.g|i\.e|Ph\.D)\.', lambda m: m.group(0).replace('.', '<DOT>'), q)
    q = re.sub(r'(?<![A-Za-z])([A-HJ-Z])\.(?=\s+[A-Z])', r'\1<DOT>', q)     # 人名首字母 G. K. Chesterton
    # 引语以问号/叹号结束、后面紧跟“某人 said”：与引语是同一句（“…as kids?” Hall said.），不切开
    q = re.sub(r'(?<=[?!][”"]) (?=(?:[A-Z][\w’.-]*\s){1,3}(?:said|says|asked|asks|added|adds|explained|explains|noted|notes|wrote|writes)\b)', '<SP>', q)
    parts = re.split(r'(?<=[.!?])(["”’)]*)\s+(?=["“‘(]?[A-Z0-9])', q)
    out, buf = [], ''
    for i, x in enumerate(parts):
        if i % 2 == 0:
            buf += x
        else:
            out.append(buf + x)
            buf = ''
    if buf:
        out.append(buf)
    return [s.replace('<DOT>', '.').replace('<SP>', ' ').strip() for s in out if s.strip()]


def main():
    P = json.loads((ROOT / '仔细阅读' / 'passages.json').read_text('utf-8'))
    res = []
    for p in P:
        sents = []
        for para in p['paras']:
            ss = split(para)
            assert ' '.join(ss) == para, (p['id'], para[:80])
            sents.append(ss)
        res.append({k: p[k] for k in ('id', 'year', 'month', 'set', 'passage', 'paper', 'part', 'words')} | {'sents': sents})
    (ROOT / '仔细阅读' / 'sents.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), 'utf-8')
    n = sum(len(s) for r in res for s in r['sents'])
    print(f'{len(res)} 篇，{n} 句')


if __name__ == '__main__':
    main()
