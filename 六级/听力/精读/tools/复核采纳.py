"""复核意见（雷之外）按“原 → 建议”替换进 ann/<套>.txt：只在报的句号前后 2 句里找，原文恰好出现一处才换；对不上的、“英文”类打印出来人工处理。

    python3 六级/听力/精读/tools/复核采纳.py <雷.json> <意见.json> [--dry]
"""
import json
import re
import sys
from pathlib import Path

C4 = Path(__file__).resolve().parents[1]


def main():
    mines = {(m['套'], m['句']) for m in json.loads(Path(sys.argv[1]).read_text('utf-8'))}
    mt = {(m['套'], m['改成'].split(' ', 1)[-1][:12]) for m in json.loads(Path(sys.argv[1]).read_text('utf-8'))}
    dry = '--dry' in sys.argv
    files, left, ok = {}, [], 0
    for r in json.loads(Path(sys.argv[2]).read_text('utf-8')):
        sid, k = r['套'], int(r['句'])
        if (sid, k) in mines or any((sid, k + d) in mines and r['原'].strip('= ')[:12] in {x[1] for x in mt if x[0] == sid} for d in (-1, 1)):
            continue
        if r['类型'] == '英文':
            left.append(('英文', r))
            continue
        L = files.setdefault(sid, (C4 / 'ann' / f'{sid}.txt').read_text('utf-8').split('\n'))
        idx = [i for i, l in enumerate(L) if (m := re.match(r'^(\d+) ', l)) and abs(int(m.group(1)) - k) <= 2]
        cand = [j for i in idx for j in (i, i + 1) if r['原'].strip() and r['原'].strip() in L[j]]
        if len(cand) != 1:
            left.append((f'原文找到 {len(cand)} 处', r))
            continue
        j = cand[0]
        L[j] = L[j].replace(r['原'].strip(), r['建议'].strip(), 1)
        ok += 1
    if not dry:
        for sid, L in files.items():
            (C4 / 'ann' / f'{sid}.txt').write_text('\n'.join(L), 'utf-8')
    print(f'采纳 {ok} 条；待人工 {len(left)} 条')
    for why, r in left:
        print(f'[{why}] {r["套"]} {r["句"]} {r["类型"]}｜原：{r["原"][:80]}｜建议：{r["建议"][:120]}｜{r["理由"][:60]}')


if __name__ == '__main__':
    main()
