"""六级听力讲义 解析数据检查（讲义 build 前自动跑；有一处就不出 PDF）。
解析/<套>.json：每题 答案（= 答案裁定）、依据（本组原文句的逐字子串）、讲（先依据后结论，有因果说法）、
替换（正确选项的逐字片段 ↔ 依据句的逐字片段，类型在 TYPES 里）、错项（另外三个字母各一条，类别在 WRONG 里）、选项译。
python3 解析检查.py [套 …]；--自检 双向验证（埋雷必须全部报出，正常数据 0）。"""
import copy
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / 'tools'))
import 材料 as M  # noqa: E402
import 中文地道 as ZD  # noqa: E402

J = HERE.parent / '解析'
TYPES = ['同义改写', '词性句式转换', '正反转换', '概括归纳', '原词复现']
WRONG = ['没提到', '张冠李戴', '偷换', '说反了', '过度推断']
HAN = re.compile('[一-鿿]')
ZH_HALF = re.compile(r'[一-鿿][,;:?!]|[,;:?!][一-鿿]')
CAUSE = re.compile('因为|所以|因此|可见|说明|可知|既然|由此|这就是|也就是说|正对应|对应')
ANS = re.compile(r'答案(?:是|选|为)\s*([A-D])')


def zh_ok(where, s, lo, hi, E):
    if not isinstance(s, str) or not HAN.search(s):
        E.append(f'{where}：没有中文')
        return
    if not lo <= len(s) <= hi:
        E.append(f'{where}：长度 {len(s)} 不在 {lo}—{hi} 字')
    if ZH_HALF.search(s):
        E.append(f'{where}：中文里用了半角标点（{ZH_HALF.search(s).group(0)}）')
    if re.search(r'["\']', s):
        E.append(f'{where}：直引号')


def check(sid, data=None):
    d = M.load(sid)
    if data is None:
        f = J / f'{sid}.json'
        if not f.exists():
            return [f'{sid}：没有 {f.name}']
        data = json.loads(f.read_text('utf-8'))
    E = []
    T = data.get('题', {})
    want = {str(n) for n in d['questions']}
    if set(T) != want:
        E.append(f'{sid}：题号不全或多余：缺 {sorted(want - set(T), key=int)} 多 {sorted(set(T) - want)}')
    for g in d['groups']:
        sents = {s['sid']: s['en'] for s in g['sents']}
        for n in g['qs']:
            x, q, w = T.get(str(n)), d['questions'][n], f'{sid} 第{n}题'
            if not x:
                continue
            a = q['ans']
            right = q['opts']['ABCD'.index(a)]
            if x.get('答案') != a:
                E.append(f'{w}：答案 {x.get("答案")} ≠ 答案裁定 {a}')
            ev = x.get('依据') or []
            if not 1 <= len(ev) <= 3:
                E.append(f'{w}：依据要 1—3 条')
            evs = []
            for e in ev:
                en = sents.get(e.get('sid'))
                if en is None:
                    E.append(f'{w}：依据句号 {e.get("sid")} 不在本组原文里')
                elif e.get('句', '') not in en or len(e.get('句', '').split()) < 3:
                    E.append(f'{w}：依据“{e.get("句", "")[:40]}”不是第 {e["sid"]} 句的逐字片段（或少于 3 词）')
                else:
                    evs.append(en)
            jiang = x.get('讲', '')
            zh_ok(f'{w} 讲', jiang, 30, 220, E)
            m = ANS.findall(jiang)
            if not m or any(c != a for c in m):
                E.append(f'{w} 讲：要写明“答案选 {a}”（现在 {m}）')
            if not CAUSE.search(jiang):
                E.append(f'{w} 讲：没有因果 / 对应的说法（先依据、后结论）')
            rp = x.get('替换') or []
            if not 1 <= len(rp) <= 4:
                E.append(f'{w}：同义替换要 1—4 条')
            for r in rp:
                if r.get('类型') not in TYPES:
                    E.append(f'{w}：替换类型“{r.get("类型")}”不在 {TYPES}')
                if not r.get('选项') or r['选项'] not in right:
                    E.append(f'{w}：替换左边“{r.get("选项")}”不是正确选项 {a} 的逐字片段')
                if not r.get('原文') or not any(r['原文'] in en for en in evs):
                    E.append(f'{w}：替换右边“{r.get("原文")}”不是依据句的逐字片段')
                if r.get('类型') == '原词复现' and r.get('选项', '').lower() != r.get('原文', '').lower():
                    E.append(f'{w}：标“原词复现”的两边要相同')
            wr = x.get('错项') or {}
            if set(wr) != set('ABCD') - {a}:
                E.append(f'{w}：错项要正好是 {"".join(sorted(set("ABCD") - {a}))}（现在 {"".join(sorted(wr))}）')
            for L_, v in wr.items():
                if v.get('类') not in WRONG:
                    E.append(f'{w} {L_} 项：错因类别“{v.get("类")}”不在 {WRONG}')
                zh_ok(f'{w} {L_} 项说明', v.get('说', ''), 8, 70, E)
            if n not in g['qsent']:
                zh_ok(f'{w} 题译（录音里没有念题句，要自己译题干）', x.get('题译', ''), 4, 80, E)
            tr = x.get('选项译') or {}
            if set(tr) != set('ABCD'):
                E.append(f'{w}：选项译要 A—D 四条')
            for L_, v in tr.items():
                zh_ok(f'{w} {L_} 项译文', v, 2, 60, E)
            E += ZD.problems([(f'{w} 讲', jiang)] + [(f'{w} {k} 项', v.get('说', '')) for k, v in wr.items()] + [(f'{w} {k} 译', v) for k, v in tr.items() if isinstance(v, str)])
    return E


def selftest():
    sid = next((s for s in M.SETS if (J / f'{s}.json').exists()), None)
    if not sid:
        sys.exit('自检：还没有解析数据')
    good = json.loads((J / f'{sid}.json').read_text('utf-8'))
    if check(sid, good):
        sys.exit(f'自检：正常数据 {sid} 报了问题')
    d = M.load(sid)
    a1 = d['questions'][1]['ans']
    other = next(c for c in 'ABCD' if c != a1)
    mines = {
        '答案字母错': lambda t: t['1'].__setitem__('答案', other),
        '讲里答案字母错': lambda t: t['1'].__setitem__('讲', t['1']['讲'].replace(f'答案选 {a1}', f'答案选 {other}').replace(f'答案选{a1}', f'答案选{other}').replace(f'答案是 {a1}', f'答案是 {other}').replace(f'答案为 {a1}', f'答案为 {other}')),
        '依据不是原文': lambda t: t['2']['依据'][0].__setitem__('句', t['2']['依据'][0]['句'] + ' indeed'),
        '依据句号越组': lambda t: t['3']['依据'][0].__setitem__('sid', 1),
        '替换左边不是选项': lambda t: t['4']['替换'][0].__setitem__('选项', 'completely invented words'),
        '替换右边不是原文': lambda t: t['5']['替换'][0].__setitem__('原文', 'completely invented words'),
        '替换类型乱写': lambda t: t['6']['替换'][0].__setitem__('类型', '换说法'),
        '少一个错项': lambda t: t['7']['错项'].pop(next(iter(t['7']['错项']))),
        '错因类别乱写': lambda t: next(iter(t['8']['错项'].values())).__setitem__('类', '不对'),
        '缺一题': lambda t: t.pop('9'),
        '中文不地道': lambda t: t['10'].__setitem__('讲', t['10']['讲'] + '这里对原文进行了分析。'),
        '讲没有因果': lambda t: t['11'].__setitem__('讲', f'答案选 {d["questions"][11]["ans"]}。原文里有这句话，选项里也有这层意思，两者一致。'),
    }
    miss = []
    for name, f in mines.items():
        x = copy.deepcopy(good)
        f(x['题'])
        if not check(sid, x):
            miss.append(name)
    if miss:
        sys.exit(f'自检失败：这些雷没报出：{miss}')
    print(f'自检通过：{sid} 正常 0 处；{len(mines)} 颗雷全部报出')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--自检']:
        selftest()
    else:
        ids = sys.argv[1:] or [f.stem for f in sorted(J.glob('*.json'))]
        E = [e for s in ids for e in check(s)]
        print('\n'.join(E) if E else f'{len(ids)} 套解析检查全部通过')
        sys.exit(1 if E else 0)
