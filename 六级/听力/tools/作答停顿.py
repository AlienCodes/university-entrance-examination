"""作答停顿实测：没有 插停顿.json 的各套，每道题念完（题干问号那个词结束）到下一个词开口的时长；
写进 202606-1/插停顿.json 的 秒 = 全部题后停顿的中位数（不拍脑袋，协调会话 2026-11-04）。
用法：python3 作答停顿.py [--写 202606-1]"""
import json, re, statistics, sys
from pathlib import Path

D = Path(__file__).resolve().parent.parent
NUM = 'one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split()
nz = lambda w: re.sub(r'[^a-z0-9]', '', w.lower())


def pauses(sid):
    W = json.loads((D / sid / '定稿.json').read_text('utf-8'))['词']
    out, i = [], 0
    while i < len(W) - 1:
        n = nz(W[i + 1][0])
        if nz(W[i][0]) == 'question' and (n.isdigit() or n in NUM or n.startswith('twenty')):
            j = next((k for k in range(i + 2, min(i + 60, len(W))) if W[k][0].endswith('?')), None)
            nxt = next((k for k in range(j + 1, len(W)) if W[k][1] is not None), None) if j else None
            if j and W[j][2] is not None and nxt:
                e = min(W[j][2], W[j][1] + max(0.9, 0.12 * len(W[j][0])))      # 同 听力视频.timeline 的单词时长封顶
                out.append(round(W[nxt][1] - e, 2))
            i = j or i + 1
        i += 1
    return out


if __name__ == '__main__':
    sets = sorted(p.name for p in D.glob('2*') if not (p / '插停顿.json').exists() or '--写' not in sys.argv)
    sets = [s for s in sets if not (D / s / '插停顿.json').exists()]
    allp = {s: [x for x in pauses(s) if x >= 8] for s in sets}
    flat = [x for v in allp.values() for x in v]
    med = round(statistics.median(flat), 2)
    print(f'{len(sets)} 套、{len(flat)} 个题后停顿（≥ 8 秒）：中位数 {med} 秒，范围 {min(flat)}—{max(flat)}；每套题数',
          {s: len(v) for s, v in allp.items() if len(v) != 25} or '都是 25')
    if '--写' in sys.argv:
        t = D / sys.argv[sys.argv.index('--写') + 1] / '插停顿.json'
        d = json.loads(t.read_text('utf-8')) if t.exists() else {}
        d.update({'秒': med, '依据': f'作答停顿.py：另 {len(sets)} 套 {len(flat)} 个题后停顿的中位数（范围 {min(flat)}—{max(flat)} 秒）'})
        t.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', 'utf-8'); print('写入', t)
