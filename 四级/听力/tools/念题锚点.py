"""念题校对材料：每套应有的锚点（News Report One…、Conversation、Passage、Questions x and/to y are based on、Question N）在定稿文字里有没有、各几处。
缺的、多的一次全部列出，附识别词下标窗口，供在 <套>/待核裁定.json 写 "改 a:b"（定稿.py 整段改写；下标是识别词下标，即定稿.json 的 改动 之前）。
用法：python3 念题锚点.py <套> … | ALL      退出码 1 = 有缺
"""
import json, re, sys
from pathlib import Path
H = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(H / 'tools'))
import 题目 as T
NUMW = 'one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split()
def nw(n): return NUMW[n - 1] if n <= 20 else 'twenty[- ]' + NUMW[n - 21]
def num(n): return rf'(?:{n}|{nw(n)})'


def need():
    out = []
    for b, (q1, q2) in enumerate(T.SEC):
        out.append((f'Questions {q1}–{q2}', rf'\bQuestions? {num(q1)},? (?:and|to) {num(q2)},? (?:are|is) based', 1))
        for q in range(q1, q2 + 1):
            out.append((f'Question {q}', rf'\b[Qq]uestion {num(q)}\b(?! (?:and|to) )' + (r'(?![- ](?:one|two|three|four|five)\b)' if q == 20 else ''), 1))
    return out


def run(sid, show=True):
    d = json.loads((H / sid / '定稿.json').read_text('utf-8'))
    W = [w[0] for w in d['词']]
    t = ' '.join(W)
    starts = [m.start() for m in re.finditer(r'\S+', t)]
    bad = []
    import bisect
    found = []
    for name, rx, k in need():
        hits = [m.start() for m in re.finditer(rx, t, re.I)]
        if len(hits) != k:
            bad.append((name, len(hits)))
        found.append((name, hits))
    if show:
        rid_w = [w[0] for w in json.loads((H / '识别' / d['录音'] / '识别.json').read_text('utf-8'))]
        for i, (name, hits) in enumerate(found):
            if len(hits) == 1: continue
            lo = next((h[0] for _, h in reversed(found[:i]) if len(h) == 1), 0)
            hi = next((h[0] for _, h in found[i + 1:] if len(h) == 1), len(t))
            a, b = bisect.bisect_right(starts, lo) - 1, bisect.bisect_right(starts, hi)
            # 定稿词下标 ≈ 识别词下标（改动少）；打印识别词下标窗口里像念题的地方
            txt = ' '.join(f'{k}:{rid_w[k]}' for k in range(max(0, a), min(b + 3, len(rid_w))) if re.match(r'(?i)question|\d|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|section|passage|conversation|news|based', rid_w[k]))
            print(f'  {name} 找到 {len(hits)} 处；窗口：{txt[:600]}')
    if show and bad:
        print(sid, '缺 / 多：', bad)
    return bad


if __name__ == '__main__':
    ids = sys.argv[1:]
    if ids == ['ALL']: ids = sorted(json.loads((H / '对照.json').read_text('utf-8'))['choice'])
    nb = sum(len(run(s)) for s in ids)
    print(f'合计 {nb} 处'); sys.exit(1 if nb else 0)
