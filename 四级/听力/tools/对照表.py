"""四级听力：录音 ↔ 试卷对照（按内容，不看文件名），生成 四级/听力/对照表.md 和 对照.json。
录音文字：四级/听力/识别/<id>/识别.json（parakeet）；没有时用 otter/<id>.txt 并注明。
① 试卷 → 录音：试卷听力选项里有区分度的实词（按 35 份试卷算 IDF），在录音识别文字里出现的加权比例；取最高，并给与第二名的差距。
② 录音 ↔ 录音：识别文字的词 4 元组重合度（Jaccard）；≥ 0.5 判为同一份听力（不同剪辑 / 编码）。
③ 每段录音念到的题号（Question one … twenty-five）是否 1—25 齐全；开头有没有 “College English Test Band Four”。
关卡（任何一处退出码 1）：每份试卷都有录音、得分 ≥ 0.3 且领先第二名 ≥ 0.15；每段录音同样；
归到同一份试卷的几段录音文字必须相同（4 元组 Jaccard ≥ 0.5）；只认第 1、2 套试卷（第 3 套只是选项顺序不同，绝不能用）；otter 与识别一致度 ≥ 0.3。
双向验证：CET4_SWAP=a:b 把两段录音的识别文字对调，必须报出（tools/防复发/验证/四级听力配对.py）。
用法：python3 对照表.py"""
import json, math, os, re, subprocess, sys
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
if os.environ.get('CET4_DUP'):
    a, b = os.environ['CET4_DUP'].split(':'); papers[b] = papers[a]
recs = json.loads((H / '原始材料/音频清单.json').read_text('utf-8'))
ptok = {k: set(w for w in words(re.sub(r'(?m)^#.*$', '', v)) if len(w) >= 4 and w.isalpha() and w not in STOP) for k, v in papers.items()}
df = Counter(w for s in ptok.values() for w in s)
idf = {w: math.log(len(ptok) / df[w]) for w in df}
SWAP = dict([os.environ['CET4_SWAP'].split(':')]) if os.environ.get('CET4_SWAP') else {}
SWAP.update({v: k for k, v in SWAP.items()})
DROP = os.environ.get('CET4_DROP')          # 测试：去掉一段录音
DUP = os.environ.get('CET4_DUP')            # 测试：a:b 让试卷 a 的文字冒充试卷 b
R = {}
for r in recs:
    if r['id'] == DROP: continue
    t, src = rec_text(SWAP.get(r['id'], r['id']))
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
    if p[-1] not in '12': prob.append(f'{p}：用了第 3 套试卷（只是选项顺序不同，不能用）')
    for a in members:
        for b in members:
            if a < b and not any(x[0] == b for x in same.get(a, [])): prob.append(f'{p}：{a} 与 {b} 都归到这份试卷，文字却不同')
note = []
def lab(rid): return rid[1:]
for rid in R:
    if rec_best[rid][0] != lab(rid): note.append(f'{rid}：文件名标的是 {lab(rid)}，内容是 {rec_best[rid][0]}（以内容为准）')
for rid in R:
    q = qnums(rid); m = R[rid]['meta']
    res['recordings'][rid] = {'paper': rec_best[rid][0], 'score': rec_best[rid][1], 'margin': rec_best[rid][2],
        'same_text': same.get(rid, []), 'questions_missing': [n for n in range(1, 26) if n not in q],
        'otter_jaccard': otter_check(rid), 'intro': 'college english test' in R[rid]['text'][:400], 'src': R[rid]['src'], 'decoded_dur': m['decoded_dur']}
    oj = res['recordings'][rid]['otter_jaccard']
    if oj is not None and oj < 0.3: prob.append(f'{rid}：otter 转写与这段录音的识别对不上（{oj}）')
    if rec_best[rid][1] < 0.3 or rec_best[rid][2] < 0.15: prob.append(f'{rid}：配对不确定（得分 {rec_best[rid][1]}，领先 {rec_best[rid][2]}）')
print('\n'.join(prob) or '0 处配对问题')
print('\n'.join('注意 ' + x for x in note))

# ---------- 对照表.md ----------
JX = json.loads((H / '原始材料/解析清单.json').read_text('utf-8'))
def fmt_t(s): return f'{int(s // 60)}:{s % 60:04.1f}'
def ym(p): return f'{p[:4]}年{int(p[4:6])}月 第{p[-1]}套'
L = ['# 四级听力：录音 ↔ 试卷对照表（程序生成：`四级/听力/tools/对照表.py`，不要手改）', '',
     f'- 老师上传的 default.zip：顶层 `audio files/` **30 个 mp3** + `Transcripts/` 30 个 otter 转写 + 合集 `解析 听力原文对照.zip`（2018-06—2026-06 每次考试的真题 PDF / Word、答案解析、听力音频 35 个）。',
     f'- 65 个 mp3 按能量包络去重后是 **{len(recs)} 段不同的录音**（`原始材料/音频清单.json`）；按识别文字归到试卷后，**实际不同的听力 = {sum(1 for p in res["papers"].values() if p["recordings"])} 份**（第 3 套试卷都写明“听力与前两套相同，只是选项顺序不同”，不单独算）。',
     '- 配对只看内容：试卷听力选项里有区分度的实词在录音识别文字里出现的加权比例（得分），括号里是第二名；文件名只当标签。', '']
JN = json.loads((H / '原始材料/解析内容.json').read_text('utf-8')) if (H / '原始材料/解析内容.json').exists() else {}
L += ['## 一、每份试卷用哪段录音', '', '| 试卷 | 采用的录音 | 解码时长 | 得分（第二名） | 同内容的其他录音 | 题号 1—25 | 试卷文字 | 解析 PDF | 解析里的官方听力原文（录音转写覆盖率） |', '|---|---|---|---|---|---|---|---|---|']
def yw(p):
    j = JN.get(p)
    if not j: return '未查'
    return ('有' if j['原文覆盖率'] >= 0.4 else '**没有**（解析只有答案与讲解）') + f'（{j["原文覆盖率"]}）'
choice = {}
for p, v in sorted(res['papers'].items()):
    ms = v['recordings']
    if not ms:
        L.append(f'| {ym(p)} | **没有录音** | | {v["second"][1]}（{v["second"][0]}） | | | | | |'); continue
    good = [r for r in ms if not res['recordings'][r]['questions_missing']]
    pick = sorted(good or ms, key=lambda r: (r[0] != 't', r))[0]; choice[p] = pick
    rr = res['recordings'][pick]
    others = '、'.join(f'{r}（{"同文字" if any(x[0] == r for x in rr["same_text"]) else "文字不同"}）' for r in ms if r != pick) or '—'
    qm = '齐' if not rr['questions_missing'] else '缺 ' + ','.join(map(str, rr['questions_missing']))
    src = papers[p].splitlines()[0].replace('# 来源：', '')
    src = '仓库 .txt' if src.startswith('四级/真题') else ('合集 Word' if src.endswith('.docx') else '合集 PDF 文字层')
    j = JX.get(p); jx = f'{j["pages"]} 页，' + ('有文字层' if j['text_chars'] > 5000 else '扫描版（要 OCR）') if j else '**没有**'
    L.append(f'| {ym(p)} | `{pick}`{"（老师给的 30 个）" if pick[0] == "t" else "（合集）"} | {fmt_t(rr["decoded_dur"])} | {rr["score"]}（{v["second"][1]}） | {others} | {qm} | {src} | {jx} | {yw(p)} |')
L += ['', '## 二、45 段录音逐个', '', '| 录音 | 原文件 | 解码时长 | 采样率 / 声道 | 归到试卷 | 得分 / 领先 | 开头有考试说明 | otter 与识别一致度 | 识别来源 |', '|---|---|---|---|---|---|---|---|---|']
for r in recs:
    x = res['recordings'].get(r['id'])
    nm_ = r['原名'].split('/')[-1]
    if not x: L.append(f'| `{r["id"]}` | {nm_} | {fmt_t(r["decoded_dur"])} | {r["sr"]} / {r["channels"]} | 还没识别 | | | | |'); continue
    L.append(f'| `{r["id"]}` | {nm_} | {fmt_t(r["decoded_dur"])} | {r["sr"]} / {r["channels"]} | {x["paper"]} | {x["score"]} / {x["margin"]} | {"是" if x["intro"] else "**否**"} | {x["otter_jaccard"] if x["otter_jaccard"] is not None else "—"} | {x["src"]} |')
L += ['', '## 三、关卡结果', ''] + [f'- **{x}**' for x in prob] + ([] if prob else ['- 0 处（每份试卷都有录音、配对得分与领先都过门槛、同一试卷的录音文字相同、otter 都对得上）'])
L += ['', '## 四、文件名标签与内容不一致的（以内容为准，下游一律按 对照.json 的 choice 取录音）', ''] + [f'- {x}' for x in note] + ([] if note else ['- 无'])
if not SWAP:
    (H / '对照表.md').write_text('\n'.join(L) + '\n', 'utf-8')
    (H / '对照.json').write_text(json.dumps({**res, 'choice': choice}, ensure_ascii=False, indent=1), 'utf-8')
sys.exit(1 if prob else 0)
