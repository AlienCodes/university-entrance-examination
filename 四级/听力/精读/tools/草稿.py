"""标注草稿（零 token）：与已复核套（复核通过）里一字不差的句子，直接带上复核过的译文和词条；其余句子列出预填候选，标注员只补这些。

    python3 四级/听力/精读/tools/草稿.py 202206-1 …（自动复用四级、六级精读已复核套里一字不差的句子）   → /tmp/claude-0/草稿/<套>.txt

草稿格式：已复用的句子写成正式两行（“k 中文” + “= 词条”），行首不加记号；待补的句子写 “k ??? 英文” + “? 候选…”。
标注员把 ??? 行改成正式两行即可；复用的两行按本套上下文确认（专名、人称不同时改）。
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
C6 = HERE.parents[3] / '六级' / '听力' / '精读'      # 六级精读（已复核，可复用）
sys.path.insert(0, str(HERE))
import 预填 as P  # noqa: E402


def sents(sid, base=None):
    t = ((base or C4) / '原文.txt').read_text('utf-8')
    sec = t.split(f'## {sid}\n', 1)[1].split('\n## ', 1)[0]
    return [s for s in sec.split('\n') if s.strip()]


def ann(sid, base=None):
    A, k = {}, None
    for line in ((base or C4) / 'ann' / f'{sid}.txt').read_text('utf-8').split('\n'):
        m = re.match(r'^(\d+) (.*)$', line)
        if m:
            k = int(m[1])
            A[k] = [m[2], '']
        elif line.startswith('= ') and k:
            A[k][1] = line[2:]
    return A


def main():
    a = sys.argv[1:]
    ids = [x for x in a if not x.startswith('--')]
    known = {}
    for base in (C4, C6):           # 先本项目（四级）已复核的套，再六级精读已复核的套（说明、过渡句一字不差的直接复用）
        rf = base / 'ann' / '复核通过.json'
        sealed = json.loads(rf.read_text('utf-8'))['指纹'] if rf.exists() else {}
        for s in sorted(sealed):
            A = ann(s, base)
            for k, en in enumerate(sents(s, base), 1):
                if k in A:
                    known.setdefault(en, A[k])
    lex = P.lexicon()
    out = Path('/tmp/claude-0/草稿')
    out.mkdir(parents=True, exist_ok=True)
    for sid in ids:
        L = ['T: 听力原文精读', 'G: 长对话 · 短文 · 讲座', 'S: ???']
        reuse = 0
        for k, en in enumerate(sents(sid), 1):
            if en in known:
                reuse += 1
                L += [f'{k} {known[en][0]}', f'= {known[en][1]}']
            else:
                low = en.lower().replace('’', "'")
                cand = [x for t in sorted(set(re.findall(r"[a-z][a-z'-]*", low))) if t in lex and len(t) > 3 for x, _ in lex[t].most_common(1)]
                L += [f'{k} ??? {en}', '? ' + ' | '.join(cand)]
        (out / f'{sid}.txt').write_text('\n'.join(L) + '\n', 'utf-8')
        print(f'{sid}：{len(sents(sid))} 句，复用 {reuse} 句')


if __name__ == '__main__':
    main()
