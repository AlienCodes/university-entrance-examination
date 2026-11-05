"""四级听力：录音 ↔ 试卷对照（按内容，不看文件名），生成 四级/听力/对照表.md 和 对照.json。
录音文字：四级/听力/识别/<id>/识别.json（parakeet）；没有时用 otter/<id>.txt 并注明。
① 试卷 → 录音：试卷听力选项里有区分度的实词（按 35 份试卷算 IDF），在录音识别文字里出现的加权比例；取最高，并给与第二名的差距。
② 录音 ↔ 录音：识别文字的词 4 元组重合度（Jaccard）；≥ 0.5 判为同一份听力（不同剪辑 / 编码）。
③ 每段录音念到的题号（Question one … twenty-five）是否 1—25 齐全；开头有没有 “College English Test Band Four”。
用法：python3 对照表.py [合集解压目录]（给了就顺带列出每份试卷的解析 PDF 与文字层情况）"""
import json, math, re, subprocess, sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; H = ROOT / '四级/听力'
STOP = set('''about above after again against also although among another anyone because been before being below between both cannot
could does doing done down during each either else enough even ever every from further have having here hers herself himself
into itself just least less like made make many more most much must neither never none only other ought ours over same shall
should since some such than that their theirs them themselves then there these they this those though through thus very
were what when where which while whom whose will with within without would your yours yourself the and for are was not but
can did had has her him his its our out own she too who why you all any how may one two new now get got way use used
section directions conversation passage recording report news questions question based heard just choices choose best
answer sheet mark corresponding letter single line centre center spoken only once after hear four marked'''.split())
NUM = 'one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split()
def numword(n):
    return NUM[n - 1] if n <= 20 else 'twenty ' + NUM[n - 21]
def words(t):
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", t.lower().replace('’', "'"))
def otter_check(rid):
    """otter 转写与 parakeet 识别是不是同一段录音（词 4 元组 Jaccard）"""
    f, o = H / '识别' / rid / '识别.json', H / 'otter' / f'{rid}.txt'
    if not (f.exists() and o.exists()): return None
    a = words(' '.join(w[0] for w in json.loads(f.read_text()))); b = words(o.read_text('utf-8'))
    ga, gb = set(zip(a, a[1:], a[2:], a[3:])), set(zip(b, b[1:], b[2:], b[3:]))
    return round(len(ga & gb) / max(1, len(ga | gb)), 2)
def rec_text(rid):
    f = H / '识别' / rid / '识别.json'
    if f.exists():
        return ' '.join(w[0] for w in json.loads(f.read_text())), 'parakeet'
    o = H / 'otter' / f'{rid}.txt'
    if o.exists(): return o.read_text('utf-8'), 'otter'
    return None, None
papers = {f.stem: f.read_text('utf-8') for f in sorted((H / '试卷').glob('*.txt'))}
recs = json.loads((H / '原始材料/音频清单.json').read_text('utf-8'))
ptok = {k: set(w for w in words(re.sub(r'(?m)^#.*$', '', v)) if len(w) >= 4 and w.isalpha() and w not in STOP) for k, v in papers.items()}
df = Counter(w for s in ptok.values() for w in s)
idf = {w: math.log(len(ptok) / df[w]) for w in df}
R = {}
for r in recs:
    t, src = rec_text(r['id'])
    if t is None: continue
    ws = words(t)
    R[r['id']] = {'src': src, 'set': set(ws), 'grams': set(zip(ws, ws[1:], ws[2:], ws[3:])), 'text': ' '.join(ws), 'meta': r}
def score(p, rid):
    v = ptok[p]; tot = sum(idf[w] for w in v)
    return sum(idf[w] for w in v if w in R[rid]['set']) / tot
S = {p: sorted(((round(score(p, r), 3), r) for r in R), reverse=True) for p in papers}
same = {}
ids = sorted(R)
for i, a in enumerate(ids):
    for b in ids[i + 1:]:
        ga, gb = R[a]['grams'], R[b]['grams']
        j = len(ga & gb) / max(1, len(ga | gb))
        if j >= 0.5: same.setdefault(a, []).append((b, round(j, 2))); same.setdefault(b, []).append((a, round(j, 2)))
def qnums(rid):
    t = R[rid]['text']
    return [n for n in range(1, 26) if re.search(r'\bquestions? (number )?' + numword(n) + r'\b', t) or re.search(rf'\bquestions? {n}\b', t)]
# 每段录音归到得分最高的试卷
rec_best = {}
for rid in R:
    sc = sorted(((score(p, rid), p) for p in papers), reverse=True)
    rec_best[rid] = (sc[0][1], round(sc[0][0], 3), round(sc[0][0] - sc[1][0], 3))
res = {'papers': {}, 'recordings': {}}
prob = []
for p in papers:
    (s1, r1), (s2, r2) = S[p][0], S[p][1]
    members = sorted(r for r in R if rec_best[r][0] == p)
    res['papers'][p] = {'best': r1, 'score': s1, 'second': [r2, s2], 'recordings': members}
    if not members: prob.append(f'{p}：没有录音归到这份试卷')
for rid in R:
    q = qnums(rid); m = R[rid]['meta']
    res['recordings'][rid] = {'paper': rec_best[rid][0], 'score': rec_best[rid][1], 'margin': rec_best[rid][2],
        'same_text': same.get(rid, []), 'questions_missing': [n for n in range(1, 26) if n not in q],
        'otter_jaccard': otter_check(rid), 'intro': 'college english test' in R[rid]['text'][:400], 'src': R[rid]['src'], 'decoded_dur': m['decoded_dur']}
    oj = res['recordings'][rid]['otter_jaccard']
    if oj is not None and oj < 0.3: prob.append(f'{rid}：otter 转写与这段录音的识别对不上（{oj}）')
    if rec_best[rid][1] < 0.3 or rec_best[rid][2] < 0.15: prob.append(f'{rid}：配对不确定（得分 {rec_best[rid][1]}，领先 {rec_best[rid][2]}）')
(H / '对照.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), 'utf-8')
print('\n'.join(prob) or '0 处配对问题')
