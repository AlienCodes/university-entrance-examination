"""定稿标点切错（一句被句号从中间切断、句号点错位置）的收尾：先在 原文订正.json 写订正（“词. 下词” → “词 下词”），再

    python3 六级/听力/精读/tools/合并句.py 201812-1 [201812-2 …]

按订正重新切句（切句.one），把旧 原文.txt 的句子按词序（difflib，大小写、标点不计）对到新句子：
- 几句并成一句：中文直接相连（去掉衔接处的“……”，前一半句末的“。”改“，”），词条合并去重；
- 句界挪动（billion. years, if → billion years. If）：句数不变，中文照旧（标注员已按正确断句译），词条不在本句的挪到它所在的句；
然后写回 原文.txt、ann/<套>.txt，句号自动重排，最后跑 标注检查.py。没有任何变化的套不动。
只做文字结构，不出音频；202512-1（已出截图）不在这里改。
"""
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
sys.path.insert(0, str(HERE))
import 切句  # noqa: E402

NORM = re.compile(r"[^\w’]+")


def toks(sents):
    out = []
    for i, s in enumerate(sents):
        for w in s.split():
            w = NORM.sub('', w.lower())
            if w:
                out.append((w, i))
    return out


def old_sents(sid):
    for blk in (C4 / '原文.txt').read_text('utf-8').split('\n## ')[1:]:
        h, body = blk.split('\n', 1)
        if h.strip() == sid:
            return [s for s in body.split('\n') if s.strip()]
    raise SystemExit(f'{sid}：原文.txt 里没有')


def parse_ann(f):
    head, blocks = [], []
    for line in f.read_text('utf-8').split('\n'):
        m = re.match(r'^(\d+) (.*)$', line)
        if m:
            blocks.append([int(m.group(1)), m.group(2), []])
        elif line.startswith('= ') and blocks:
            blocks[-1][2] += [x.strip() for x in line[2:].split(' | ') if x.strip()]
        elif not blocks:
            head.append(line)
        elif line.strip():
            raise SystemExit(f'{f.name}：认不出的行 {line[:40]}')
    return head, blocks


def join_zh(a, b):
    a, b = a.rstrip(), b.lstrip()
    a2 = re.sub(r'(……|…)$', '', a)
    b2 = re.sub(r'^(……|…)', '', b)
    if a2 != a or b2 != b:
        return a2 + b2
    if a.endswith('。'):
        a = a[:-1] + '，'
    return a + b


def surf(e):
    k = e.split('=', 1)[0].strip()
    m = re.search(r'\{(.+?)\}', k)
    k = m.group(1) if m else k.lstrip('~')
    return [w for w in re.split(r'…|\s+', k.lower()) if w]


def has(sent, e):
    ts = NORM.sub(' ', sent.lower()).split()
    def hit(w):
        w = NORM.sub('', w)
        stem = w[:-2] if len(w) > 5 else w[:-1] if len(w) > 3 else w      # 词形宽松：conversation / conversations、wander / wandered
        return any(t.startswith(stem) for t in ts)
    return all(hit(w) for w in surf(e))


def one(sid, fixes):
    old = old_sents(sid)
    P = 切句.one(sid, fixes)
    new = [s for p in P for s in p]
    if new == old:
        print(f'{sid}：没有变化')
        return False
    a, b = toks(old), toks(new)
    sm = difflib.SequenceMatcher(None, [w for w, _ in a], [w for w, _ in b], autojunk=False)
    votes = [dict() for _ in old]
    for blk in sm.get_matching_blocks():
        for t in range(blk.size):
            i, j = a[blk.a + t][1], b[blk.b + t][1]
            votes[i][j] = votes[i].get(j, 0) + 1
    if sm.ratio() < 0.995:
        raise SystemExit(f'{sid}：新旧词序差太多（{sm.ratio():.4f}），不是切句订正，停')
    owner = [max(v, key=lambda j: (v[j], -j)) if v else None for v in votes]
    f = C4 / 'ann' / f'{sid}.txt'
    head, blocks = parse_ann(f)
    if [k for k, _, _ in blocks] != list(range(1, len(old) + 1)):
        raise SystemExit(f'{sid}：标注句号与 原文.txt 句数（{len(old)}）对不上')
    nb = [[j + 1, None, []] for j in range(len(new))]
    for i, (k, zh, es) in enumerate(blocks):
        j = owner[i]
        if j is None:
            raise SystemExit(f'{sid}：第 {k} 句在新切句里找不到')
        nb[j][1] = zh if nb[j][1] is None else join_zh(nb[j][1], zh)
        for e in es:
            if e not in nb[j][2]:
                nb[j][2].append(e)
    moved = 0
    touched = {j for j in range(len(new)) if [i for i, o in enumerate(owner) if o == j] != [] and
               (sum(o == j for o in owner) > 1 or new[j] != old[owner.index(j)])}
    for j in range(len(nb)):
        _, zh, es = nb[j]
        if zh is None:                    # 一句拆成两句：后一半先写“（待译）”，词条按所在句挪过来，中文人工补（标注检查会拦）
            nb[j][1] = zh = '（待译）'
            touched |= {j, j - 1, j + 1}
            print(f'{sid}：新第 {j + 1} 句是拆出来的，中文待补：{new[j][:60]}')
        if j not in touched:
            continue
        for e in list(es):
            if not has(new[j], e):
                for jj in (j - 1, j + 1):
                    if jj in touched and has(new[jj], e):
                        es.remove(e)
                        if e not in nb[jj][2]:
                            nb[jj][2].append(e)
                        moved += 1
                        break
    changes = [(j + 1, sorted(k + 1 for k, o in enumerate(owner) if o == j)) for j in range(len(new))]
    for j, ks in changes:
        if len(ks) != 1 or new[j - 1] != old[ks[0] - 1]:
            print(f'{sid}：新 {j} ← 旧 {ks}：{new[j - 1][:70]}')
    txt = '\n'.join(head).rstrip('\n') + '\n' + ''.join(f'{k} {zh}\n= {" | ".join(es)}\n' for k, zh, es in nb)
    f.write_text(txt, 'utf-8')
    sys.argv = ['切句.py', sid]
    切句.main()
    print(f'{sid}：{len(old)} → {len(new)} 句，挪动词条 {moved} 个')
    return True


def main():
    fixes = json.loads((C4 / '原文订正.json').read_text('utf-8'))
    ids = [s for s in sys.argv[1:] if s != '202512-1']
    done = [s for s in ids if one(s, fixes)]
    if done:
        r = subprocess.run([sys.executable, str(HERE / '标注检查.py'), *done])
        sys.exit(r.returncode)


if __name__ == '__main__':
    main()
