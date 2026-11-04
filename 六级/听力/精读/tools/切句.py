"""六级听力原文精读：定稿.json（练习会话的权威文字，0 待核才能用）→ 原文.txt 的一节（## <套>，逐句一行、空行分段）。

    python3 六级/听力/精读/tools/切句.py 202512-1 [202512-2 …]

- 只收 定稿.json 待核为 0 的套（不是 0 就停）；文字一字不改，只做排版统一（直撇号 / 直引号 → 弯的，带空格的破折号 → 不带空格），
  人工订正写在 原文订正.json（{套: [[原, 改为, 理由], …]}），每条必须恰好匹配一次（第 4 项写了次数就恰好那么多次，踩坑 17）。
- 切句：. ? ! 结尾（引号、括号跟着走）；Mr. Mrs. Ms. Dr. St.（不分大小写，转写有小写 mr.，统一成大写）和单个大写字母缩写、U.S. 句中不切（踩坑 6）。
- 分段：说明、Conversation / Passage / Recording、“Questions … are based on …”、每道念题各起一段；对话里换说话人靠停顿，不在这里分。
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent                       # 六级/听力/精读
SRC = C4.parent                        # 六级/听力/<套>/定稿.json
ABBR = re.compile(r"(?:\b(?i:Mr|Mrs|Ms|Dr|St|Prof|vs|etc|e\.g|i\.e)\.|\b[A-Z]\.|\bU\.S\.|\bU\.K\.|\ba\.m\.|\bp\.m\.)$")
HEAD = re.compile(r"^(?:Part (?:I|II|III|Two)|Section [ABC]|Directions|Conversation (?:One|Two)|Passage (?:One|Two)|Recording (?:One|Two|Three)|"
                  r"Questions? \w+(?: to| and) \w+ (?:are|is) based|Question \w+[:.]|Now,? listen|This is the end)", re.I)


def typo(s):
    s = re.sub(r"(\w)'(\w)", r'\1’\2', s)
    s = re.sub(r"(\s|^)'(\d0s)", r'\1’\2', s)
    s = re.sub(r"\s*(?:--|[—–])\s*", '—', s)
    s = re.sub(r'"(?=\w)', '“', s).replace('"', '”')
    s = re.sub(r"'(?=\w)", '‘', s).replace("'", '’')
    s = re.sub(r"\b(mr|mrs|ms|dr)\.", lambda m: m.group(1).capitalize() + '.', s)     # 转写里的小写称谓（mr. Sanchez）
    return s


def split(words):
    out, cur = [], []
    for w in words:
        cur.append(w)
        t = w.rstrip('”’")')
        letter_list = re.fullmatch(r'[A-D]\.', t) and len(cur) > 1 and cur[-2].lower() in ('and', 'or')      # “A, B, C, and D.” 是句末
        if re.search(r'[.?!]$', t) and (letter_list or not ABBR.search(t)):
            out.append(' '.join(cur))
            cur = []
    if cur:
        out.append(' '.join(cur))
    return out


def paras(sents):
    P = []
    for s in sents:
        if not P or HEAD.match(s) or (P[-1] and HEAD.match(P[-1][-1]) and not HEAD.match(s) and len(P[-1]) == 1 and P[-1][-1].lower().startswith('question ')):
            P.append([])
        P[-1].append(s)
    return P


def one(sid, fixes):
    d = json.loads((SRC / sid / '定稿.json').read_text('utf-8'))
    if d.get('待核'):
        raise SystemExit(f'{sid}：定稿.json 还有 {len(d["待核"])} 处待核（练习会话裁定后再做）')
    text = typo(' '.join(w[0] for w in d['词']))
    for fx in fixes.get(sid, []):
        old, new, why = fx[:3]
        want = fx[3] if len(fx) > 3 else 1          # 第 4 项：应匹配的次数（同一个人名全文统一，默认 1）
        n = text.count(old)
        if n == want and want > 1:
            text = text.replace(old, new)
            continue
        if n == 0 and text.count(new) == 1 and old not in new:     # 练习会话已在 定稿.json 里改好（念题校对等）：跳过，打印出来
            print(f'{sid}：订正“{old[:30]}”定稿里已改好，跳过')
            continue
        if n != 1:
            raise SystemExit(f'{sid}：原文订正“{old}”匹配 {n} 次（必须恰好 1 次）')
        text = text.replace(old, new)
    P = paras(split(text.split()))
    bad = [s for p in P for s in p if re.search(r' [—–] |\s--\s|"|\'', s)]
    if bad:
        raise SystemExit(f'{sid}：排版没统一：{bad[:3]}')
    return P


def main():
    ids = sys.argv[1:]
    ff = C4 / '原文订正.json'
    fixes = json.loads(ff.read_text('utf-8')) if ff.exists() else {}
    f = C4 / '原文.txt'
    old = f.read_text('utf-8') if f.exists() else '# 六级听力原文（逐句一行，空行分段）：由 tools/切句.py 从 六级/听力/<套>/定稿.json 生成，不手改（订正写 原文订正.json）。\n'
    sec = {}
    head, *rest = re.split(r'\n(?=## )', old)
    for r in rest:
        sec[r.split('\n', 1)[0][3:].strip()] = r
    for sid in ids:
        P = one(sid, fixes)
        sec[sid] = f'## {sid}\n' + '\n\n'.join('\n'.join(p) for p in P) + '\n'
        print(f'{sid}：{sum(map(len, P))} 句，{len(P)} 段')
    f.write_text(head.rstrip('\n') + '\n\n' + '\n'.join(sec[k].rstrip('\n') + '\n' for k in sorted(sec)), 'utf-8')


if __name__ == '__main__':
    main()
