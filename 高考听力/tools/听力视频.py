"""高考听力 视频版真题考试（白纸黑字考卷样式，照四六级听力视频版）：画面跟着原音走，按小节 / 材料分组显示题目。
照用专八引擎 专八/听力/tools/听力视频.py（导入为 base）：截图（stills）、排版检查 CHECK_JS、题间空隙 QGAP_JS（铁律 19）、
CDP 字体回退、彩色像素、编码（video）、成品核查（verify）、原音逐样本比对（orig_match）——规则只写一处。
这里只写高考自己的：开头剪切（老师要求 6）、时间轴、画面状态、画面、版式、答案泄露检查。

  python 听力视频.py <id> timeline 原音.mp3     识别/<套>/分块.json + 锚点.json → 时间轴.json（每个锚点恰好一处、按考试顺序递增）
  python 听力视频.py <id> layout                 每屏从大字号往下试，排版检查 + 题间空隙 0 处的第一个 → 版式.json（字号低于下限报错）
  python 听力视频.py <id> stills [--sample]
  python 听力视频.py <id> audio|video 原音.mp3 [--试跑]
  python 听力视频.py <id> --自检                 双向验证（正常 0 处；混进答案、溢出、题间没分开、缺字、片头年份卷名不对、组不对都报）
原音：开头剪到“第一节 / Section A”锚点（老师要求 6，原音不动的唯一例外：只剪开头，保留部分与原音逐样本相同），其余一点不动。
"""
import html, json, math, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / '专八/听力/tools'))
import importlib
base = importlib.import_module('听力视频')

SID = sys.argv[1]
SETS = json.loads((P / '套.json').read_text('utf-8'))
if SID not in SETS: base.die(f'套.json 里没有 {SID}')
S = SETS[SID]
NAMEK = S['名']                                   # 如“2025 新课标Ⅰ卷”
Y, PAPER = NAMEK.split(' ', 1)
SH = '上海' in PAPER
D = P / '数据' / SID
OUT = Path(os.environ.get('GK_OUT', f'/tmp/gklisten/{SID}'))
NAME_RE = r'^(20\d\d)年 (\S+) 高考英语听力 视频版真题考试\.mp4$'
NAME = f'{Y}年 {PAPER} 高考英语听力 视频版真题考试.mp4'
QD = json.loads((P / '抽取/定稿题.json').read_text('utf-8'))[S.get('题目', NAMEK)]
GROUPS = [tuple(g) for g in QD['组']]
QS = {int(k): v for k, v in QD['题'].items()}
NOPT = 4 if SH else 3
LET = 'ABCD'[:NOPT]
ANSF = P / '答案.json'
ANS = (json.loads(ANSF.read_text('utf-8')) if ANSF.exists() else {}).get(SID, {})
die = base.die
KEY_SEC = 20.0                                    # 每屏参考答案停留（静音）
MIN_FONT = {'q1': 40, 'grp': 40, 'sha': 44, 'ans': 32}   # 字高下限（按 1920×1080 量，老师要求 1）
STRUCT = [(i, i) for i in range(1, 11)] + [(11, 13), (14, 16), (17, 20)] if SH else \
         [(i, i) for i in range(1, 6)]


def check_data():
    """题目数据：20 题、每题 NOPT 个选项、组 = 卷面说明（全国类 1—5 各一题 + 第二节 5 组连续到 20；上海固定 13 组）"""
    bad = []
    if sorted(QS) != list(range(1, 21)): bad.append(f'题号 {sorted(QS)}')
    for n, q in QS.items():
        o = q.get('选项') or {}
        if sorted(o) != list(LET) or not all(str(x).strip() for x in o.values()): bad.append(f'第 {n} 题选项')
        if not SH and not str(q.get('干', '')).strip(): bad.append(f'第 {n} 题无题干')
    if SH and GROUPS != STRUCT: bad.append(f'组 {GROUPS}')
    if not SH and (GROUPS[:5] != STRUCT or len(GROUPS) != 10 or GROUPS[-1][1] != 20 or
                   any(GROUPS[i][0] != GROUPS[i - 1][1] + 1 for i in range(1, 10))): bad.append(f'组 {GROUPS}')
    if ANS and (sorted(map(int, ANS)) != list(range(1, 21)) or any(a not in LET for a in ANS.values())): bad.append('答案')
    if not re.fullmatch(r'20(19|2[0-6])', Y) or not PAPER or '未知' in PAPER: bad.append(f'年份卷名 {NAMEK}')
    if not re.match(NAME_RE, NAME): bad.append(f'文件名 {NAME}')
    if bad: die('题目数据：' + '；'.join(bad))


# ───────────────────────── 时间轴 ─────────────────────────
ZHN = {'两': 2, '二': 2, '三': 3, '四': 4, '2': 2, '3': 3, '4': 4}


def clusters(bl, gap):
    out = []
    for b in bl:
        if out and b[0] - out[-1][-1][1] < gap: out[-1].append(b)
        else: out.append([b])
    return out


def timeline(wav):
    import numpy as np, soundfile as sf
    K = P / '识别' / S['识别']
    B = json.loads((K / '分块.json').read_text('utf-8'))
    cut = json.loads((K / '锚点.json').read_text('utf-8'))['cut']
    a, sr = sf.read(wav, dtype='float32', always_2d=True)
    # 剪切点必须在静音里（独立量：剪切点前后 0.1 秒的能量低于底噪 + 12 dB）
    if cut > 0:
        m = a.mean(1); h = int(0.02 * sr); n = len(m) // h
        db = 10 * np.log10((m[:n * h].reshape(n, h) ** 2).mean(1) + 1e-12); thr = max(np.percentile(db, 10) + 12, -50.0)       # 低于 −50 dBFS 一律算静音（数字静音的录音底噪 + 12 dB 太严）
        i = int(cut / 0.02)
        if (db[max(0, i - 1):i + 2] > thr).any(): die(f'剪切点 {cut} 秒不在静音里（{db[max(0, i - 1):i + 2].round(1)} > {thr:.1f}）')
    B = [[max(0.0, s - cut), e - cut, l, t] for s, e, l, t in B if e > cut + 0.05]      # 锚点所在的块（上海：说明 + 第 1 段对话连在一起）从 0 起
    T = {'cut': cut, 'audioEnd': round(len(a) / sr - cut, 4), 'anchorAfterCut': round(json.loads((K / '锚点.json').read_text('utf-8')).get('anchor', cut) - cut, 3)}
    zh = lambda b: b[2] == 'zh' or re.search(r'[一-鿿]{3}', b[3])
    one = lambda xs, what: xs[0] if len(xs) == 1 else die(f'{what} 找到 {len(xs)} 处（必须恰好一处）')
    endb = [b for b in B if re.search(r'听力(部分|考试)?到此结束|end of (the )?listening', b[3], re.I)]
    if not SH:
        endb += [b for b in B if '第二节到此结束' in b[3]]
        s1e = one([b for b in B if re.search(r'第一节到此结束', b[3])] or [b for b in B if re.match(r'^第二节', b[3])][:1], '第一节结束')
        intro = [b for b in B if zh(b) and re.search(r'听下面一段|听第\s*\S{1,3}\s*段', b[3]) and b[0] > s1e[0]]
        icl = clusters(intro, 3.0)
        if len(icl) != 5: die(f'第二节材料说明找到 {len(icl)} 段（应为 5）：' + str([c[0][3] for c in icl]))
        s1 = [b for b in B if b[1] <= s1e[0]]
        zh1 = [b for b in s1 if zh(b)]
        rd = zh1[-1]                                        # 第一节最后一句中文说明 = “阅读第一小题”
        if not re.search(r'第(一|1)小题', rd[3]): die(f'第一节阅读提示没找到：{rd[3]}')
        chime = lambda c: sum(x[1] - x[0] for x in c) < 2.5 and len(''.join(x[3] for x in c)) <= 4     # 只有提示音的一簇
        dl = [c for c in clusters([b for b in s1 if b[0] > rd[1] and not zh(b)], 5.0) if not chime(c)]
        if len(dl) != 5: die(f'第一节对话找到 {len(dl)} 段（应为 5）')
        T['instr1'] = 0.0
        T['read1'] = [rd[1], dl[0][0][0]]
        T['dlg'] = [[c[0][0], c[-1][1]] for c in dl]
        T['dlgEnd'] = [T['dlg'][i + 1][0] for i in range(4)] + [next((b[0] for b in s1 if b[0] > T['dlg'][4][1] and chime([b])), s1e[0])]
        T['instr2'] = s1e[0]
        T['grp'] = []
        for g, c in enumerate(icl):
            q1, q2 = GROUPS[5 + g]
            zc = [b for b in B if c[0][0] <= b[0] and zh(b) and (b[0] - c[-1][1] < 3.0 or b in c)]
            zc = clusters([b for b in B if zh(b) and b[0] >= c[0][0]], 3.0)[0]
            m = re.search(r'阅读这(两|二|三|四|[234])个', ''.join(b[3] for b in zc))
            if not m or ZHN[m.group(1)] != q2 - q1 + 1: die(f'第 {q1}—{q2} 题说明的题数对不上：{"".join(b[3] for b in zc)}')
            nxt = icl[g + 1][0][0] if g < 4 else min([b[0] for b in endb if b[0] > c[0][0]] or [die('第二节结束说明没找到')])
            en = [b for b in B if zc[-1][1] < b[0] < nxt and not zh(b)]
            tail = nxt
            while en and chime([en[-1]]): tail = en.pop()[0]           # 下一段前的提示音：作答到提示音响为止
            if not en: die(f'第 {q1}—{q2} 题没有材料')
            T['grp'].append({'start': c[0][0], 'read': [zc[-1][1], en[0][0]], 'play': en[0][0], 'ans': [en[-1][1], tail]})
        T['end'] = T['grp'][-1]['ans'][1]
    else:
        en = [b for b in B if b[0] < (endb[0][0] if endb else 1e9)]
        sb = one([b for b in en if re.search(r'section\s*b', b[3], re.I)], 'Section B')
        A = [c for c in clusters([b for b in en if b[0] < sb[0]], 4.0) if not (sum(x[1] - x[0] for x in c) < 2.5 and len(''.join(x[3] for x in c)) <= 4)]
        if len(A) != 10: die(f'Section A 对话找到 {len(A)} 段（应为 10）')
        T['dlg'] = [[0.0 if i == 0 else c[0][0], c[-1][1]] for i, c in enumerate(A)]
        T['instrB'] = sb[0]
        W = {11: 'eleven', 14: 'fourteen', 17: 'seventeen'}
        T['grp'] = []
        for q1, q2 in GROUPS[10:]:
            if q1 == 11: T['grp'].append({'start': sb[0]}); continue      # 第一组在 Section B 说明里宣布
            hit = [b for b in en if b[0] >= sb[0] and re.search(rf'questions?\W+({q1}|{W[q1]})\W+(through|to|and)', b[3], re.I)]
            T['grp'].append({'start': one(hit, f'Questions {q1} through {q2}')[0]})
        T['grp'][0]['start'] = sb[0]
        ends = [g['start'] for g in T['grp'][1:]] + [one(endb, '听力结束')[0]]
        for g, e in zip(T['grp'], ends):
            blk = [b for b in en if g['start'] <= b[0] < e]
            g['ans'] = [blk[-1][1], e]
        T['end'] = ends[-1]
    seq = [0.0] + (T['read1'] + sum(T['dlg'], []) + [T['instr2']] if not SH else sum(T['dlg'], []) + [T['instrB']])
    for g in T['grp']: seq += [g['start']] + g.get('read', []) + ([g['play']] if 'play' in g else []) + g['ans']
    seq += [T['end'], T['audioEnd']]
    if any(y < x for x, y in zip(seq, seq[1:])):
        die('锚点不是按考试顺序递增：' + str([(i, x, y) for i, (x, y) in enumerate(zip(seq, seq[1:])) if y < x]))
    D.mkdir(parents=True, exist_ok=True)
    (D / '时间轴.json').write_text(json.dumps(T, ensure_ascii=False, indent=1), 'utf-8')
    print(SID, '时间轴：剪去开头', cut, '秒，结束', round(T['end'], 1), '作答停顿', [round(g['ans'][1] - g['ans'][0], 1) for g in T['grp']], '第一节', [round(b - a[1], 1) for a, b in zip(T.get('dlg', []), T.get('dlgEnd', []))])


# ───────────────────────── 画面状态 ─────────────────────────
def states():
    T = json.loads((D / '时间轴.json').read_text('utf-8'))
    L = []

    def add(t, **s): L.append((t, s))

    def countdown(a, b, label, **s):      # 同专八：显示 ceil(b - t)，开头不足半秒的一格并进下一格
        n = math.ceil(b - a - 1e-6)
        if (b - a) - (n - 1) < 0.5: n -= 1
        if n < 1: return
        add(a, cd=n, cdl=label, **s)
        for k in range(n - 1, 0, -1): add(b - k, cd=k, cdl=label, **s)

    add(-base.LEAD, kind='title')
    if not SH:
        add(0.0, kind='instr', sec=1)
        countdown(*T['read1'], '阅读', kind='q1', cur=1, st='阅读第 1 小题')
        for i, (s, e) in enumerate(T['dlg']):
            add(s, kind='q1', cur=i + 1, st=f'第 {i + 1} 段对话（只读一遍）')
            nx = T['dlg'][i + 1][0] if i < 4 else T['instr2']
            countdown(e, T['dlgEnd'][i], '作答', kind='q1', cur=i + 1, st=f'回答第 {i + 1} 小题' + (f'，阅读第 {i + 2} 小题' if i < 4 else ''))
        add(T['instr2'], kind='instr', sec=2)
        for g, G in enumerate(T['grp']):
            q1, q2 = GROUPS[5 + g]
            add(G['start'], kind='grp', g=g, st=f'第 {g + 6} 段材料')
            countdown(*G['read'], '阅读', kind='grp', g=g, st=f'阅读第 {q1}—{q2} 题')
            add(G['play'], kind='grp', g=g, st=f'第 {g + 6} 段材料（读两遍）')
            countdown(*G['ans'], '作答', kind='grp', g=g, st=f'回答第 {q1}—{q2} 题')
    else:
        for i, (s, e) in enumerate(T['dlg']):
            add(s, kind='sha', n=i + 1, st=f'Conversation {i + 1}')
            nx = T['dlg'][i + 1][0] if i < 9 else T['instrB']
            countdown(e, nx, '作答', kind='sha', n=i + 1, st=f'回答第 {i + 1} 题')
        for g, G in enumerate(T['grp']):
            q1, q2 = GROUPS[10 + g]
            add(G['start'], kind='grp', g=g, st=f'Questions {q1}—{q2}')
            countdown(*G['ans'], '作答', kind='grp', g=g, st=f'回答第 {q1}—{q2} 题')
    add(T['end'], kind='end')
    add(T['audioEnd'], kind='ansA')
    add(T['audioEnd'] + KEY_SEC, kind='ansB')
    total = T['audioEnd'] + 2 * KEY_SEC
    L.sort(key=lambda x: x[0])
    return L, total, T


# ───────────────────────── 画面 ─────────────────────────
INSTR = {1: ('第一节', '听下面5段对话。每段对话后有一个小题，从题中所给的A、B、C三个选项中选出最佳选项。听完每段对话后，你都有10秒钟的时间来回答有关小题和阅读下一小题。每段对话仅读一遍。'),
         2: ('第二节', '听下面5段对话或独白。每段对话或独白后有几个小题，从题中所给的A、B、C三个选项中选出最佳选项。听每段对话或独白前，你将有时间阅读各个小题，每小题5秒钟；听完后，各小题将给出5秒钟的作答时间。每段对话或独白读两遍。')}
CSSG = """
.top b{font-family:'TNR','Noto Serif SC'}
.zhs{font-family:'Noto Serif SC','TNR'}
.instr.zhs{font-style:normal;font-weight:700;line-height:1.7}
.ttl .yr{font-family:'Noto Serif SC';font-weight:700;font-size:120px;margin-top:40px}
.ttl .pp{font-family:'Noto Serif SC';font-weight:700;font-size:100px}
.qs .qg{padding:calc(var(--f) * 0.32) 0 calc(var(--f) * 0.34);border-bottom:2px solid #c8c8c8;font-size:var(--f);line-height:1.3}
.qs .qg:first-child{padding-top:0}
.qs .qg:last-child{border-bottom:none}
.qs .h{display:flex;font-weight:700}
.qs .h .n{flex:none;width:calc(var(--f) * 1.7)}
.qs .os{display:grid;padding-left:calc(var(--f) * 1.7);column-gap:calc(var(--f) * 1.0)}
.qs .os.row{grid-template-columns:repeat(NOPT,minmax(0,max-content))}
.qs .os.two{grid-template-columns:repeat(2,minmax(0,max-content))}
.qs .os.col{grid-template-columns:minmax(0,max-content)}
.qs .opt{white-space:nowrap}
.qs .opt b{font-weight:700;margin-right:calc(var(--f) * 0.35)}
.qs .qg.dim{color:#8a8a8a;border-bottom-color:#dcdcdc}
.qs .qg.cur .n span{border:3px solid #000;padding:0 calc(var(--f) * 0.12)}
.ans .qg{font-size:var(--af,40px);line-height:1.45}
.ans .n{min-width:calc(var(--af,40px) * 1.6)}
.ans b{font-weight:700;width:calc(var(--af,40px) * 1.37);text-align:center;border:2px solid #000;line-height:1.1;align-self:flex-start;margin:calc(var(--af,40px) * 0.11) 14px 0 0;flex:none}
.ans{grid-template-rows:repeat(5,auto)}
"""


def esc(s):
    return html.escape(str(s).strip(), quote=False)


def qblock(n, how, cls=''):
    q = QS[n]
    stem = esc(q.get('干', ''))
    os_ = ''.join(f'<span class="opt"><b>{L}.</b>{esc(q["选项"][L])}</span>' for L in LET)
    if how == 'two' and NOPT == 3:   # A B / C
        pass
    return (f'<div class="qg{cls}"><div class="h"><span class="n"><span>{n}.</span></span><span class="sm">{stem}</span></div>'
            f'<div class="os {how}">{os_}</div></div>')


TOPL = 'I. Listening Comprehension' if SH else '第一部分　听力（共两节，满分30分）'


def page(s):
    k = s['kind']
    top = f'<div class="top"><b>{TOPL}</b>'
    if s.get('st'): top += f'<span class="st">{esc(s["st"])}</span>'
    if 'cd' in s: top += f'<div class="cd"><i>{s["cdl"]}</i><span>{s["cd"] // 60}:{s["cd"] % 60:02d}</span></div>'
    top += '</div>'
    body, var = '', ''
    if k == 'title':
        top = ''
        body = (f'<div class="ttl blk"><div class="yr" data-y="{Y}">{Y}年</div><div class="pp" data-p="{esc(PAPER)}">{esc(PAPER)}</div>'
                f'<div class="zh">高考英语听力　视频版真题考试</div>'
                '<div class="note">原题原音</div><div class="note">请备好纸笔作答，参考答案将在考试结束后给出。</div></div>')
    elif k == 'instr':
        h, t = INSTR[s['sec']]
        body = f'<div class="main"><div class="sec blk zhs">{h}</div><div class="instr blk zhs">{esc(t)}</div></div>'
    elif k in ('q1', 'grp', 'sha'):
        if k == 'q1': ns, ttl = list(range(1, 6)), '第一节'
        elif k == 'sha': ns, ttl = [s['n']], 'Section A'
        else:
            q1, q2 = GROUPS[(10 if SH else 5) + s['g']]
            ns, ttl = list(range(q1, q2 + 1)), ('Section B' if SH else '第二节')
        f, hows = s.get('fit') or LAY[k + str(s.get('g', s.get('n', '')))]
        var = f'--f:{f}px'
        rows = ''.join(qblock(n, h, (' cur' if n == s['cur'] else ' dim') if k == 'q1' else '') for n, h in zip(ns, hows))
        body = (f'<div class="main"><div class="sec blk{" zhs" if not SH else ""}">{ttl}</div>'
                f'<div class="qs blk" data-min="{MIN_FONT[k]}" data-ns="{",".join(map(str, ns))}">{rows}</div></div>')
    elif k == 'end':
        body = ('<div class="main"><div class="end blk"><h1>' + ('That’s the end of listening comprehension.' if SH else '听力部分到此结束。') +
                '</h1><p>请放下笔。下面是参考答案。</p></div></div>')
    elif k in ('ansA', 'ansB'):
        rng = range(1, 11) if k == 'ansA' else range(11, 21)
        top = top.replace('</b>', f'</b><span class="st">参考答案（{rng[0]}—{rng[-1]}）</span>', 1)
        af = s.get('fit') or LAY[k]
        var = f'--af:{af}px'
        items = ''.join(f'<div class="qg"><span class="n">{i}.</span><b>{ANS.get(str(i), "?")}</b>'
                        f'<span class="a">{esc(QS[i]["选项"].get(ANS.get(str(i), "A"), ""))}</span></div>' for i in rng)
        body = f'<div class="main"><div class="sec blk zhs">参考答案</div><div class="ans blk" data-min="{MIN_FONT['ans']}">{items}</div></div>'
    css = base.CSS.replace('FL/', base.FL.as_uri() + '/') + CSSG.replace('NOPT', str(NOPT))
    css = "@import url('" + (ROOT / '四级' / 'tools' / 'fonts' / 'fonts.css').as_uri() + "');" + css
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body style="{var}">{top}{body}'
            f'<div class="foot">{esc(NAMEK)} LISTENING</div></body></html>')


LAYF = D / '版式.json'
LAY = json.loads(LAYF.read_text('utf-8')) if LAYF.exists() else {}

FIT_JS = r"""() => { const r = []; for (const e of document.querySelectorAll('.qs .opt, .ans .qg')) {
  const lh = parseFloat(getComputedStyle(e).lineHeight); if (e.getClientRects().length > 1 || e.getBoundingClientRect().height > lh * 1.6) r.push('折行 ' + e.textContent.slice(0, 30)); }
  return r; }"""
SIZE_JS = r"""() => { const r = []; for (const m of document.querySelectorAll('.qs, .ans')) { const lo = parseFloat(m.dataset.min || 0);
  for (const e of m.querySelectorAll('.opt, .sm, .a')) { const f = parseFloat(getComputedStyle(e).fontSize); if (e.textContent.trim() && f < lo) { r.push('字号 ' + f + ' < 下限 ' + lo); return r; } } }
  return r; }"""


def screens():
    L, _, _ = states()
    out = {}
    for _, s in L:
        if s['kind'] in ('q1', 'grp', 'sha'):
            out.setdefault(s['kind'] + str(s.get('g', s.get('n', ''))), s)
    return out


def checks(pg, htm, s, cdp=None):
    got = pg.evaluate(base.CHECK_JS) + pg.evaluate(base.QGAP_JS, base.MIN_GAP) + pg.evaluate(FIT_JS) + pg.evaluate(SIZE_JS) + leak_check(s, htm) + struct_check(s, htm)
    if cdp is not None: got += _font_check(pg, cdp)
    return got


def layout():
    """每屏从大字号往下试：每题先试选项一行（row），放不下试两栏（two）、一栏（col）；0 处的第一个写进 版式.json"""
    from playwright.sync_api import sync_playwright
    exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
    res = {}
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': 1920, 'height': 1080})
        tmp = OUT / 'layout.html'; OUT.mkdir(parents=True, exist_ok=True)

        def bad(st):
            h = page(st); tmp.write_text(h, 'utf-8'); pg.goto(tmp.as_uri()); pg.wait_for_function('document.fonts.status === "loaded"')
            return checks(pg, h, st)
        for key, s in screens().items():
            n = len(s.get('fit', [0, [0] * 5])[1]) if 'fit' in s else None
            ns = 5 if s['kind'] == 'q1' else (1 if s['kind'] == 'sha' else GROUPS[(10 if SH else 5) + s['g']][1] - GROUPS[(10 if SH else 5) + s['g']][0] + 1)
            s = dict(s, st='回答第 17—20 题', cd=20, cdl='作答')
            got = None
            for f in range(96, MIN_FONT[s['kind']] - 1, -2):
                hows = []
                for j in range(ns):          # 每题挑最紧凑的、不折行的选项排法（别的题先按一栏）
                    for h in ('row', 'two', 'col'):
                        trial = hows + [h] + ['col'] * (ns - j - 1)
                        if not [x for x in bad(dict(s, fit=[f, trial])) if x.startswith('折行')]:
                            hows.append(h); break
                    else: hows.append('col')
                if not bad(dict(s, fit=[f, hows])):
                    got = [f, hows]; break
            if not got: die(f'{key} 字号降到下限 {MIN_FONT[s["kind"]]} 还放不下')
            res[key] = got
        for k in ('ansA', 'ansB'):
            got = next((af for af in range(60, MIN_FONT['ans'] - 1, -2) if not bad({'kind': k, 'fit': af})), None)
            if not got: die(f'答案一览 {k} 字号降到下限还放不下')
            res[k] = got
        br.close()
    D.mkdir(parents=True, exist_ok=True)
    LAYF.write_text(json.dumps(res, ensure_ascii=False), 'utf-8')
    print(SID, '版式：', {k: v[0] if isinstance(v, list) else v for k, v in res.items()})


def leak_check(s, htm):
    """考试过程中的画面不许出现答案：答案标题、答案框（.ans）"""
    if s['kind'] in ('ansA', 'ansB'): return []
    body = htm.split('</style>', 1)[1]
    txt = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', body)))
    bad = []
    if '参考答案' in txt and s['kind'] != 'end' and s['kind'] != 'title': bad.append('答案泄露：答案标题')
    if s['kind'] != 'title' and re.search(r'class="(ans|ansb|ok|right|correct)\b', body): bad.append('答案泄露：答案样式')
    return bad


def struct_check(s, htm):
    """老师要求 3、7：每屏题号 = 该段材料说明里的题号范围；片头年份、卷名 = 数据"""
    bad = []
    if s['kind'] == 'title':
        if f'data-y="{Y}">{Y}年<' not in htm or f'data-p="{esc(PAPER)}">{esc(PAPER)}<' not in htm: bad.append('片头年份卷名与数据不符')
    m = re.search(r'data-ns="([\d,]+)"', htm)
    if s['kind'] in ('q1', 'grp', 'sha'):
        if not m: return bad + ['题目屏没有题号范围']
        ns = list(map(int, m.group(1).split(',')))
        want = list(range(1, 6)) if s['kind'] == 'q1' else ([s['n']] if s['kind'] == 'sha' else list(range(GROUPS[(10 if SH else 5) + s['g']][0], GROUPS[(10 if SH else 5) + s['g']][1] + 1)))
        shown = [int(x) for x in re.findall(r'<span class="n"><span>(\d+)\.</span>', htm)]
        if ns != want or shown != want: bad.append(f'题号 {shown} ≠ 材料说明 {want}')
    return bad


# 换上高考的部分，其余全用专八引擎
base.D, base.OUT, base.NAME, base.Q = D, OUT, NAME, {'gap_answers': []}
base.ORIGINAL = True
base.states, base.page = states, page
base.leak_check = lambda s, htm: leak_check(s, htm) + struct_check(s, htm)          # 截图时每张都跑（专八 stills 调用）
_font_check = base.font_check
base.font_check = lambda pg, cdp: _font_check(pg, cdp) + pg.evaluate(FIT_JS) + pg.evaluate(SIZE_JS)


def sha_ok(mp3):
    import hashlib
    sha = hashlib.sha256(Path(mp3).read_bytes()).hexdigest()
    want = (P / '识别' / S['识别'] / '原音.sha256').read_text('utf-8').split()[0]
    if sha != want: die(f'{mp3} 的 sha256 与 识别/{S["识别"]}/原音.sha256 不符')


def cut_wav(mp3):
    """原音解码（专八 decoded：不改采样率、声道）→ 剪掉开头到锚点（老师要求 6）→ 逐样本核对保留部分与原音相同"""
    import numpy as np, soundfile as sf
    w = base.decoded(mp3, OUT)
    T = json.loads((D / '时间轴.json').read_text('utf-8'))
    a, sr = sf.read(w, dtype='float32', always_2d=True)
    k = int(round(T['cut'] * sr))
    if not 0 <= T['cut'] < 600: die('剪切点不合理')
    c = OUT / 'cut.wav'
    sf.write(c, a[k:], sr, subtype='FLOAT')
    b, sr2 = sf.read(c, dtype='float32', always_2d=True)
    sys.path.insert(0, str(HERE)); import 剪开头
    bad = 剪开头.check(a, b, k, int(round((T['cut'] + T.get('anchorAfterCut', 0.0)) * sr))) + ([] if sr2 == sr else ['采样率变了'])
    if bad: die('剪开头：' + '；'.join(bad))
    print('剪开头：', T['cut'], '秒（保留部分与原音逐样本相同）')
    return str(c)


def selftest():
    from playwright.sync_api import sync_playwright
    exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
    if not LAY: die('先跑 layout')
    sc = screens()
    g0 = next(v for k, v in sc.items() if k.startswith('grp'))
    first = sc.get('q11') or sc.get('sha1')
    gs = dict(g0, st='回答', cd=9, cdl='作答')
    a3 = QS[GROUPS[-1][0]]['选项']['A']
    cases = [('正常（题组）', gs, page(gs), False), ('正常（首屏）', first, page(first), False),
             ('正常（片头）', {'kind': 'title'}, page({'kind': 'title'}), False),
             ('正常（答案一览）', {'kind': 'ansA'}, page({'kind': 'ansA'}), False),
             ('考试画面混进参考答案', gs, page(gs).replace('</span></div></div></body>', '参考答案</span></div></div></body>'), True),
             ('考试画面带答案样式', gs, page(gs).replace('class="qs blk"', 'class="qs blk"><i class="ans"></i><i', 1), True),
             ('选项太长溢出', gs, page(gs).replace(esc(a3), ' '.join([esc(a3)] * (200 // max(1, len(a3)) + 2)), 1), True),
             ('题与题之间没分开（铁律 19）', gs, page(gs).replace('class="qg', 'class="x'), True),
             ('少一题（组不对）', gs, re.sub(r'<div class="qg[^"]*"><div class="h"><span class="n"><span>\d+\.</span>.*?</div></div>', '', page(gs), count=1), True),
             ('片头卷名不对', {'kind': 'title'}, page({'kind': 'title'}).replace(f'>{esc(PAPER)}<', '>未知卷<'), True),
             ('字号低于下限', gs, page(gs).replace(f'--f:{LAY["grp0"][0]}px', '--f:20px'), True),
             ('字体里没有的字', gs, page(gs).replace('第二节' if not SH else 'Section B', '𝄞 ꙮ', 1), True)]
    ok = True
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': 1920, 'height': 1080}); cdp = pg.context.new_cdp_session(pg)
        tmp = OUT / 'selftest.html'; OUT.mkdir(parents=True, exist_ok=True)
        for name, s, htm, want in cases:
            tmp.write_text(htm, 'utf-8'); pg.goto(tmp.as_uri()); pg.wait_for_function('document.fonts.status === "loaded"')
            got = checks(pg, htm, s, cdp)
            print(('✅' if bool(got) == want else '❌'), name, '→', got[:2] or '0 处'); ok &= bool(got) == want
        br.close()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    c = sys.argv[2]
    check_data()
    if c == '--自检': selftest()
    elif c == 'timeline': sha_ok(sys.argv[3]); timeline(base.decoded(sys.argv[3], OUT))
    elif c == 'layout': layout()
    elif c == 'stills':
        if len(ANS) != 20: die('答案不齐 20 个（答案.json），不出图')
        base.stills('--sample' in sys.argv)
    elif c == 'audio': sha_ok(sys.argv[3]); base.audio_check(cut_wav(sys.argv[3]))
    elif c == 'video': sha_ok(sys.argv[3]); base.video(cut_wav(sys.argv[3]), '--试跑' in sys.argv)
    elif c == 'preview': base.preview()
