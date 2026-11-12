"""复核埋雷（程序造雷，零 token）：给审阅员的标注副本里每套放 5 颗确定的错误——数字、时间、否定、词性、释义各一，答案另存，审阅员看不到。

    python3 六级/听力/精读/tools/埋雷.py <输出目录> 201812-1 [201812-2 …]
        → <输出目录>/<套>.txt（带雷副本）、<输出目录>/../雷_<组>.json（答案：套、句、类型、原、改成）
    python3 六级/听力/精读/tools/埋雷.py --判 <雷.json> <意见.json>   每颗雷都被报出（同套同句）才算通过，退出码 1 = 漏雷

雷按句子挑，分散在全文前中后（种子 = 套名，可重现），每句最多一颗。
"""
import json
import random
import re
import sys
from pathlib import Path

C4 = Path(__file__).resolve().parents[1]
TIME = [('昨天', '明天'), ('今天', '昨天'), ('明天', '昨天'), ('上周', '下周'), ('下周', '上周'), ('去年', '明年'), ('明年', '去年'),
        ('早上', '晚上'), ('晚上', '早上'), ('上午', '下午'), ('下午', '上午'), ('冬天', '夏天'), ('夏天', '冬天'), ('星期一', '星期五'), ('周末', '周一'),
        ('之前', '之后'), ('之后', '之前'), ('以前', '以后'), ('以后', '以前'), ('最近', '很久以前'), ('年前', '年后')]
NEG = [('不是', '是'), ('不会', '会'), ('不能', '能'), ('没有', '有'), ('不要', '要'), ('从不', '总是'), ('不太', '很'), ('不想', '想')]
NUMS = {'一': '三', '两': '五', '三': '七', '四': '六', '五': '八', '六': '九', '七': '四', '八': '二', '九': '六', '十': '二十'}


def blocks(sid):
    lines = (C4 / 'ann' / f'{sid}.txt').read_text('utf-8').split('\n')
    out = {}
    for i, l in enumerate(lines):
        m = re.match(r'^(\d+) ', l)
        if m:
            out[int(m.group(1))] = (i, i + 1)
    return lines, out


def plant(sid, rnd):
    lines, B = blocks(sid)
    n = max(B)
    used, mines = set(), []

    def pick(cond):
        ks = [k for k in B if k > 10 and k not in used and all(abs(k - u) > 3 for u in used) and cond(k)]
        if not ks:
            raise SystemExit(f'{sid}：找不到能埋雷的句子')
        k = rnd.choice(ks)
        used.add(k)
        return k

    zh = lambda k: lines[B[k][0]]                     # noqa: E731
    ent = lambda k: lines[B[k][1]]                    # noqa: E731
    # 1 数字
    k = pick(lambda k: re.search(r'\d', zh(k).split(' ', 1)[1]) or re.search(r'(?<![第上这那一])[两三四五六七八九十][个年天岁次位种名月%小周分]', zh(k)))
    s = zh(k)
    m = re.search(r'\d+', s.split(' ', 1)[1])
    if m:
        a = len(str(k)) + 1 + m.start()
        v = m.group()
        new = s[:a] + str(int(v) + (10 if int(v) >= 10 else 3)) + s[a + len(v):]
    else:
        m = re.search(r'(?<![第上这那一])[两三四五六七八九十](?=[个年天岁次位种名月%小周分])', s)
        new = s[:m.start()] + NUMS[m.group()] + s[m.end():]
    mines.append((k, '数字', s, new, B[k][0]))
    # 2 时间
    k = pick(lambda k: any(a in zh(k) for a, _ in TIME))
    s = zh(k)
    a, b = next((a, b) for a, b in TIME if a in s)
    mines.append((k, '时间', s, s.replace(a, b, 1), B[k][0]))
    # 3 否定
    k = pick(lambda k: any(a in zh(k).split(' ', 1)[1] for a, _ in NEG))
    s = zh(k)
    a, b = next((a, b) for a, b in NEG if a in s.split(' ', 1)[1])
    i = s.index(a, len(str(k)) + 1)
    mines.append((k, '否定', s, s[:i] + b + s[i + len(a):], B[k][0]))
    # 4 词性：adj. → adv. / n. → v.
    k = pick(lambda k: re.search(r'=(adj|n)\. ', ent(k)))
    s = ent(k)
    m = re.search(r'=(adj|n)\. ', s)
    mines.append((k, '词性', s, s[:m.start()] + ('=adv. ' if m.group(1) == 'adj' else '=v. ') + s[m.end():], B[k][1]))
    # 5 释义：换成远处另一个词条的释义
    k = pick(lambda k: ' | ' in ent(k) or re.search(r'^= \w+=', ent(k)))
    s = ent(k)
    items = s[2:].split(' | ')
    j = rnd.randrange(len(items))
    w, g = items[j].split('=', 1)
    far = [x for kk in B if abs(kk - k) > 40 for x in ent(kk)[2:].split(' | ') if '=' in x and x.split('=', 1)[0] != w]
    far = [x for x in far if x.split('=', 1)[1].split('. ', 1)[0] == g.split('. ', 1)[0] and x.split('=', 1)[1] != g] or far
    items[j] = w + '=' + rnd.choice(far).split('=', 1)[1]
    mines.append((k, '释义', s, '= ' + ' | '.join(items), B[k][1]))
    for k, t, old, new, li in mines:
        assert lines[li] == old and new != old
        lines[li] = new
    return '\n'.join(lines), [{'套': sid, '句': k, '类型': t, '原': o, '改成': nw} for k, t, o, nw, _ in mines]


def judge(mf, rf):
    mines = json.loads(Path(mf).read_text('utf-8'))
    rep = json.loads(Path(rf).read_text('utf-8'))
    got = {(r['套'], int(r['句'])) for r in rep if str(r.get('句', '')).isdigit()}
    miss = [m for m in mines if (m['套'], m['句']) not in got]
    for m in miss:
        print(f'漏雷：{m["套"]} 第{m["句"]}句（{m["类型"]}）')
    mk = {(m['套'], m['句']) for m in mines}
    extra = [r for r in rep if (r['套'], int(r['句'])) not in mk]
    print(f'雷 {len(mines) - len(miss)}/{len(mines)} 查出；雷之外的意见 {len(extra)} 条')
    return 1 if miss else 0


def main():
    if sys.argv[1] == '--判':
        sys.exit(judge(sys.argv[2], sys.argv[3]))
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    allm = []
    for sid in sys.argv[2:]:
        txt, ms = plant(sid, random.Random(sid))
        (out / f'{sid}.txt').write_text(txt, 'utf-8')
        allm += ms
    (out.parent / f'雷_{out.name}.json').write_text(json.dumps(allm, ensure_ascii=False, indent=1), 'utf-8')
    print(f'{len(sys.argv) - 2} 套，雷 {len(allm)} 颗 → {out}')


if __name__ == '__main__':
    main()
