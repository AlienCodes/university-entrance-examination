"""合并句.py 之后的收尾（零 token）：订正把一句拆成两句时，词条都留在了前一句（标注检查报“找不到”，后一句“没有标注”）。
本句找不到、相邻 ±2 句里能找到（ann_lib.find，与标注检查同一个匹配）的词条挪过去；找不到的原样留下，打印出来交人工。

    python3 四级/听力/精读/tools/词条挪句.py 201806-1 [… ] [--dry]
"""
import os
import sys
import tempfile
from pathlib import Path

C4 = Path(__file__).resolve().parents[1]
os.environ['ZB_ROOT'] = str(C4)
sys.path.insert(0, str(C4.parents[2] / '专八' / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ann_lib as A  # noqa: E402
import 标注检查 as K  # noqa: E402


def entry(raw):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(f'T: x\nG: x\nS: x\n1 x\n= {raw}\n')
    try:
        return A.parse(f.name)[1][1]['w'][0]
    finally:
        os.unlink(f.name)


def main():
    a = sys.argv[1:]
    R = K.text_R()
    for sid in [x for x in a if not x.startswith('--')]:
        sents = A.flat(R[sid])
        f = C4 / 'ann' / f'{sid}.txt'
        L = f.read_text('utf-8').split('\n')
        eq = {}                                   # 句号 → “= …”行的下标
        k = None
        for i, l in enumerate(L):
            if l[:1].isdigit() and ' ' in l:
                k = int(l.split(' ', 1)[0])
            elif l.startswith('= ') and k:
                eq[k] = i
        items = {k: [x.strip() for x in L[i][2:].split(' | ') if x.strip()] for k, i in eq.items()}
        moved, left = 0, []
        for k in sorted(items):
            keep = []
            for raw in items[k]:
                e = entry(raw)
                if A.find(e, sents[k - 1], []) is not None:
                    keep.append(raw)
                    continue
                to = next((j for d in (1, -1, 2, -2) if 1 <= (j := k + d) <= len(sents) and A.find(e, sents[j - 1], []) is not None), None)
                if to is None:
                    keep.append(raw)
                    left.append((k, raw))
                    continue
                if raw not in items[to]:
                    items[to].append(raw)
                moved += 1
            items[k] = keep
        for k, i in eq.items():
            L[i] = '= ' + ' | '.join(items[k])
        if '--dry' not in a:
            f.write_text('\n'.join(L), 'utf-8')
        print(f'{sid}：挪动 {moved} 个，仍找不到 {len(left)} 个' + ''.join(f'\n  第{k}句 {r}' for k, r in left))


if __name__ == '__main__':
    main()
