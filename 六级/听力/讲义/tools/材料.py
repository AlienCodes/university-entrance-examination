"""六级听力讲义的数据层：从已复核的精读数据（vocab.json：逐句原文 + 译文 + 生词）和题目、答案裁定拼出每套的结构。
load(套) → {id, year, month, set, groups: [{sec, name, qs: [题号…], sents: [{sid, en, zh}]}], questions: {题号: {q, opts, ans}}}
python3 材料.py 套 … → 写给解析作者的材料（scratch 里），python3 材料.py --统计 → 各套句数 / 词数。"""
import json
import re
import sys
from pathlib import Path

L = Path(__file__).resolve().parents[2]          # 六级/听力
V = {p['id']: p for p in json.loads((L / '精读' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
SETS = sorted(V, reverse=True)                   # 新的在前（老师定）
QB = re.compile(r'^Questions? .{1,30}? (?:are|is) based on', re.I)
QS = re.compile(r'^Question \w+[:.]', re.I)
NUM = 'one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split()
HEAD = re.compile(r'^(Conversation|Passage|Recording) (one|two|three|1|2|3)\b[.:]?\s*', re.I)


def load(sid):
    p = V[sid]
    t = json.loads((L / sid / '题目.json').read_text('utf-8'))
    ans = json.loads((L / sid / '答案裁定.json').read_text('utf-8'))
    qs = {}
    for i, (q, opts, a) in enumerate(t['questions'], 1):
        if ans[str(i)] != a:
            raise SystemExit(f'{sid} 第 {i} 题：题目.json 答案 {a} ≠ 答案裁定 {ans[str(i)]}')
        qs[i] = {'q': q, 'opts': opts, 'ans': ans[str(i)]}
    paras = p['paras']
    flat, k = [], 0
    for pi, para in enumerate(paras):
        for s in para:
            k += 1
            flat.append((pi, k, s))
    groups, gi = [], 0
    secs = t['sections']
    for pi, para in enumerate(paras):
        if len(para) == 1 and QB.match(para[0]['en']):
            prev = paras[pi - 1]
            base = sum(len(x) for x in paras[:pi - 1])
            sents = [{'sid': base + j + 1, 'en': s['en'], 'zh': s['zh'], 'w': s['w']} for j, s in enumerate(prev)]
            m = HEAD.match(sents[0]['en'])
            if not m:
                raise SystemExit(f'{sid}：第 {pi} 段之前找不到 Conversation/Passage/Recording 开头：{sents[0]["en"][:60]}')
            name = m.group(0).strip()
            if m.end() >= len(sents[0]['en']):
                sents = sents[1:]              # “Conversation one.” 单独一句：不算正文
            a, b = secs[gi]
            kind = m.group(1).lower()
            qsent, j = {}, pi + 1
            while j < len(paras) and len(paras[j]) == 1 and QS.match(paras[j][0]['en']):
                w = paras[j][0]['en'].split()[1].rstrip(':.').lower()
                n = int(w) if w.isdigit() else NUM.index(w) + 1
                if not a <= n <= b:
                    raise SystemExit(f'{sid}：念题句题号 {n} 不在第 {a}—{b} 题')
                qsent[n] = paras[j][0]
                j += 1
            groups.append({'kind': kind, 'name': name, 'qs': list(range(a, b + 1)), 'sents': sents, 'qsent': qsent})
            gi += 1
    if gi != len(secs) or sum(len(g['qs']) for g in groups) != len(qs):
        raise SystemExit(f'{sid}：找到 {gi} 组，题目.json 有 {len(secs)} 组')
    return {'id': sid, 'year': p['year'], 'month': p['month'], 'set': p['set'], 'groups': groups, 'questions': qs, 'summary': p.get('summary', ''), 'paras': paras}


def material(sid):
    d = load(sid)
    out = [f'# {sid}（{d["year"]}年{d["month"]}月 第{d["set"]}套）']
    for g in d['groups']:
        out.append(f'\n## {g["name"]}（第 {g["qs"][0]}—{g["qs"][-1]} 题）')
        for s in g['sents']:
            out.append(f'[{s["sid"]}] {s["en"]}')
        for n in g['qs']:
            q = d['questions'][n]
            out.append(f'\nQ{n}. {q["q"]}  （答案 {q["ans"]}）' + ('' if n in g['qsent'] else '（缺念题句）'))
            for L_, o in zip('ABCD', q['opts']):
                out.append(f'  {L_}) {o}')
    return '\n'.join(out)


if __name__ == '__main__':
    if sys.argv[1] == '--统计':
        for s in SETS:
            d = load(s)
            w = sum(len(x['en'].split()) for g in d['groups'] for x in g['sents'])
            ls = max(len(x['en'].split()) for g in d['groups'] for x in g['sents'])
            print(s, len(d['groups']), len(d['questions']), w, ls)
    else:
        outdir = Path(sys.argv[1])
        for s in sys.argv[2:] or SETS:
            (outdir / f'{s}.txt').write_text(material(s), 'utf-8')
