"""生词预填（零 token）：把六级阅读等已复核标注里的词条，按词形（原文里一模一样的词）列到每一句下面，标注员挑、改、补。

    python3 六级/听力/精读/tools/预填.py 202512-1 > 预填.txt

来源：六级/ann、专八/听力/原文/ann（说明文字常用词）、考研/ann、专八/ann（已复核）。每个词形列出现最多的两种释义（词性不同时标注员按本句定）。
输出每句：“k 英文” + “? 候选1 | 候选2 …”。不是标注结果，标注员按本句词性、词义逐条判断。
"""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRCS = ['六级/ann', '专八/听力/原文/ann', '考研/ann', '专八/ann']


def lexicon():
    lex = collections.defaultdict(collections.Counter)
    for d in SRCS:
        for f in sorted((ROOT / d).glob('*.txt')):
            for line in f.read_text('utf-8').split('\n'):
                if not line.startswith('= '):
                    continue
                for e in line[2:].split(' | '):
                    if '=' not in e:
                        continue
                    k, v = e.split('=', 1)
                    k = k.strip()
                    if k.startswith('~'):
                        head = re.sub(r'\{.*\}', '', k[1:]).strip()
                        lex['~' + head.lower()][f'{k.split("{")[0]}={v.strip()}'] += 1
                    else:
                        lex[k.lower()][f'{k}={v.strip()}'] += 1
    return lex


def main():
    sid = sys.argv[1]
    txt = (ROOT / '六级/听力/精读/原文.txt').read_text('utf-8')
    sec = txt.split(f'## {sid}\n', 1)[1].split('\n## ', 1)[0]
    sents = [s for s in sec.split('\n') if s.strip()]
    lex = lexicon()
    phr = [k for k in lex if k.startswith('~')]
    for k, s in enumerate(sents, 1):
        low = s.lower().replace('’', "'")
        toks = set(re.findall(r"[a-z][a-z'-]*", low))
        cand = []
        for t in sorted(toks):
            if t in lex:
                cand += [x for x, _ in lex[t].most_common(2)]
        for p in phr:
            body = p[1:]
            if '…' not in body and len(body.split()) > 1 and re.search(r'\b' + re.escape(body) + r'\b', low):
                cand += [x for x, _ in lex[p].most_common(1)]
        print(f'{k} {s}')
        print('? ' + ' | '.join(cand))
    print(f'# {len(sents)} 句；词库 {len(lex)} 个词形', file=sys.stderr)


if __name__ == '__main__':
    main()
