"""解析复核（审阅员 + 埋雷，铁律 17：不整屏看图，只看文字）。
python3 复核埋雷.py 准备 <目录> 套 …   → 每套 <套>.材料.txt + <套>.解析.json（副本，埋了雷），埋雷位置写进 埋雷.json（不给审阅员看）
python3 复核埋雷.py 对照 <目录> 意见.json → 雷查出几颗；其余意见列出来给协调人逐条看（真问题改原文件）
雷都是程序检查查不出、只有看懂内容才看得出的：依据换成别题的句子、两个选项译文对调、错因类别改错、讲解里“男士 / 女士”对换、两题的替换对调。"""
import copy
import json
import os
import random
import sys
from pathlib import Path

HERE = Path(os.path.abspath(__file__)).parent   # 不解析软链接：四级 tools 是指向这里的软链接，按所在目录取项目
sys.path.insert(0, str(HERE))
import 材料 as M  # noqa: E402
import 解析检查 as JC  # noqa: E402


def plant(sid, data, rnd):
    d, T, mines = M.load(sid), data['题'], []
    g = rnd.choice([g for g in d['groups'] if len(g['qs']) >= 3])
    a, b = rnd.sample(g['qs'], 2)
    T[str(a)]['依据'] = copy.deepcopy(T[str(b)]['依据'])
    mines.append((a, '依据换成了第 %d 题的出处' % b))
    n = rnd.choice([q for q in d['questions'] if q not in (a, b)])
    x, y = rnd.sample([c for c in 'ABCD'], 2)
    T[str(n)]['选项译'][x], T[str(n)]['选项译'][y] = T[str(n)]['选项译'][y], T[str(n)]['选项译'][x]
    mines.append((n, f'{x}、{y} 两项译文对调'))
    m = rnd.choice([q for q in d['questions'] if q not in (a, b, n)])
    L = next(iter(T[str(m)]['错项']))
    old = T[str(m)]['错项'][L]['类']
    T[str(m)]['错项'][L]['类'] = next(w for w in ('说反了', '没提到', '张冠李戴') if w != old)
    mines.append((m, f'{L} 项错因类别 {old} 改成了 {T[str(m)]["错项"][L]["类"]}'))
    for k in sorted(d['questions'], key=lambda _: rnd.random()):
        s = T[str(k)]['讲']
        if k not in (a, b, n, m) and ('男士' in s) != ('女士' in s):
            T[str(k)]['讲'] = s.replace('男士', '\0').replace('女士', '男士').replace('\0', '女士')
            mines.append((k, '讲解里说话人男女对换'))
            break
    return mines


def main():
    cmd, out = sys.argv[1], Path(sys.argv[2])
    if cmd == '准备':
        out.mkdir(parents=True, exist_ok=True)
        rnd, lei = random.Random(20261104), {}
        for sid in sys.argv[3:]:
            data = json.loads((JC.J / f'{sid}.json').read_text('utf-8'))
            lei[sid] = plant(sid, data, rnd)
            (out / f'{sid}.材料.txt').write_text(M.material(sid), 'utf-8')
            (out / f'{sid}.解析.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), 'utf-8')
        (out.parent / f'{out.name}_埋雷.json').write_text(json.dumps(lei, ensure_ascii=False, indent=1), 'utf-8')
        print(f'{len(lei)} 套，埋雷 {sum(map(len, lei.values()))} 颗（埋雷表在 {out.name}_埋雷.json，不放进审阅目录）')
    else:
        lei = json.loads((out.parent / f'{out.name}_埋雷.json').read_text('utf-8'))
        op = json.loads(Path(sys.argv[3]).read_text('utf-8'))
        hit, rest = set(), []
        for o in op:
            key = (o['套'], int(o['题']))
            if any((s, q) == key for s in lei for q, _ in lei[s]):
                hit.add(key)
            else:
                rest.append(o)
        allm = [(s, q, w) for s in lei for q, w in lei[s]]
        miss = [m for m in allm if (m[0], m[1]) not in hit]
        print(f'雷 {len(allm)} 颗，查出 {len(allm) - len(miss)} 颗；漏：{miss}')
        print(f'其余意见 {len(rest)} 条：')
        for o in rest:
            print(' ', o['套'], o['题'], o.get('字段', ''), o.get('问题', ''), '→', o.get('建议', ''))


if __name__ == '__main__':
    main()
