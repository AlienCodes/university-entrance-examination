"""六级听力 视频版真题考试（白底黑字考卷样式，与专八 2025 一模一样）：原音一刀不剪，画面跟着录音走。

照用专八引擎 专八/听力/tools/听力视频.py（导入为 base）：截图（stills）、排版检查 CHECK_JS、题间空隙 QGAP_JS（铁律 19）、
CDP 字体回退、彩色像素、编码（video）、成品核查（verify）、试跑——一行不改，规则只写一处。
这里只写六级自己的：时间轴锚点（timeline）、画面状态（states）、画面（page）、答案泄露检查（六级答案是字母）。

  python 听力视频.py <套> timeline 原音.mp3      定稿.json + 题目.json → 时间轴.json（锚点在定稿文字里找，必须恰好一处、按考试顺序递增）
  python 听力视频.py <套> stills [--sample]
  python 听力视频.py <套> video 原音.mp3 [--试跑]
  python 听力视频.py <套> --自检                 双向验证（正常 0 处；混进答案、溢出、题间没分开、缺字都报）
样片：环境变量 CET6_CUT=<题号> 只做到第 N 题作答结束（音频同样截断），其余流程不变。
原音不适用 TTS 那几条检查（句间 0.8 秒、逐句响度、电磁音、合格证）：声音是考试原音，只做整体增益，峰值 ≤ −1 dBFS（同专八听力）。
"""
import html, json, math, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / '专八/听力/tools'))
import importlib
base = importlib.import_module('听力视频')        # 专八引擎（同名模块，路径在前）

SID = sys.argv[1]
D = HERE.parent / SID
OUT = Path(os.environ.get('CET6_OUT', f'/tmp/cet6listen/{SID}'))
Y, M, K = SID[:4], int(SID[4:6]), SID[-1]
NAME = f'{Y}年{M}月 六级听力 第{K}套 视频版真题考试.mp4'
Q = json.loads((D / '题目.json').read_text('utf-8'))
SEC = Q['sections']
CUT = int(os.environ.get('CET6_CUT', '0'))
ANS_A, ANS_B = 30.0, 25.0
die = base.die


def norm(w):
    return re.sub(r'[^a-z0-9]', '', w.lower())


NUMW = 'one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split()


def numtok(n):
    return {str(n), NUMW[n - 1] if n <= 20 else ''} - {''}


# ───────────────────────── 时间轴 ─────────────────────────
def timeline(wav):
    Wd = json.loads((D / '定稿.json').read_text('utf-8'))['词']
    # 识别漏掉的一小段（几个词到一两句：念题号“Q”、Section B 说明）没有时间：在前后已知时刻之间按字数线性插值；
    # 只补两头都有时间、≤ 40 词的段，补了多少打印出来（锚点落在插值段里，换屏误差在这一段的时长以内）
    filled, i = 0, 0
    while i < len(Wd):
        if Wd[i][1] is not None: i += 1; continue
        j = i
        while j < len(Wd) and Wd[j][1] is None: j += 1
        if 0 < i and j < len(Wd) and j - i <= 40:
            t0, t1 = Wd[i - 1][2], Wd[j][1]
            L = [len(x[0]) + 1 for x in Wd[i:j]]; tot = sum(L); acc = 0
            need = 0.065 * tot                        # 约 0.065 秒 / 字母（念题语速）
            if t1 - t0 > 1.5 * need:                  # 中间有停顿：念题号、Section 说明贴着后一个词，其余接着前一个词
                if re.match(r'(Questions?|Section|Directions|Conversation|Passage|Recording)\b', Wd[i][0]): t0 = t1 - need
                else: t1 = t0 + need
            for k in range(i, j):
                a0 = t0 + (t1 - t0) * acc / tot; acc += L[k - i]
                Wd[k] = [Wd[k][0], round(a0, 2), round(t0 + (t1 - t0) * acc / tot, 2)] + Wd[k][3:]
            filled += j - i
        i = j
    if filled: print(f'{SID} 插值补时间 {filled} 个词')
    # 识别有时把停顿前最后一个词的结束拉进停顿里（202306-1 apartment? 4.96 秒）：单个词时长封顶，停顿从实际念完算起
    capped = 0
    for w in Wd:
        if w[1] is not None and w[2] - w[1] > max(0.9, 0.12 * len(w[0])):
            w[2] = round(w[1] + max(0.9, 0.12 * len(w[0])), 2); capped += 1
    if capped: print(f'{SID} 词时长封顶 {capped} 个')
    ins = gap_points(Wd)
    if ins:                              # 录音没有作答停顿（202606-1）：每题念完插静音，补到总停顿 = GAP（另 29 套实测中位数），之后的词整体后移
        for w in Wd:
            if w[1] is not None:
                sh = sum(L for t, L in ins if t <= w[1] - 1e-6)
                w[1], w[2] = round(w[1] + sh, 2), round(w[2] + sh, 2)
        print(f'{SID} 插停顿 {len(ins)} 处，补到 {GAP} 秒，共插 {sum(L for _, L in ins):.2f} 秒')
    words = [(norm(w[0]), w[1], w[2]) for w in Wd]

    def t_at(i):
        """第 i 个词的开始时刻；没对上时间的取后面最近有时间的词"""
        for k in range(i, min(i + 4, len(words))):
            if words[k][1] is not None: return words[k][1]
        die(f'第 {i} 个词“{Wd[i][0]}”附近没有时间')

    def find(seqs, lo, hi, what):
        """在词下标 [lo, hi) 里找连续词序列（seqs 里任一种写法），必须恰好一处；返回词下标"""
        hits = sorted({i for seq in seqs for i in range(lo, hi - len(seq) + 1)
                       if all(words[i + k][0] in (seq[k] if isinstance(seq[k], set) else {seq[k]}) for k in range(len(seq)))})
        if len(hits) != 1:
            die(f'锚点“{what}”在第 {lo}—{hi} 个词里找到 {len(hits)} 处（必须恰好 1 处）')
        return hits[0]

    N = len(words)
    T = {'q': {}, 'pause': {}, 'blk': {}}
    a = find([['section', 'a']], 0, 80, 'Section A')
    T['secA'] = t_at(a)
    T['title0'] = t_at(0)
    labels = [('conversation', 'one'), ('conversation', 'two'), ('passage', 'one'), ('passage', 'two'),
              ('recording', 'one'), ('recording', 'two'), ('recording', 'three')]
    pos = a
    for b, ((q1, q2), (kind, nth)) in enumerate(zip(SEC, labels)):
        if b == 2:
            s = find([['section', 'b']], pos, N, 'Section B'); T['secB'] = t_at(s); pos = s
        if b == 4:
            s = find([['section', 'c']], pos, N, 'Section C'); T['secC'] = t_at(s); pos = s
        nn = {'one': 1, 'two': 2, 'three': 3}[nth]
        i = find([[kind, numtok(nn)]], pos, N, f'{kind} {nth}')
        # Questions q1 to q2 are based on …
        j = find([['questions', numtok(q1), 'to', numtok(q2)]], i, N, f'Questions {q1} to {q2}')
        T['blk'][b] = {'start': t_at(i), 'qintro': t_at(j)}
        pos = j
        for q in range(q1, q2 + 1):
            k = find([['question', numtok(q)]], pos, N, f'Question {q}')
            T['q'][q] = t_at(k)
            # 题后停顿：念完这题之后第一个 ≥ 8 秒的词间空隙（念题本身不会停这么久）
            g = next((m for m in range(k + 2, N - 1) if words[m][2] is not None and t_at(m + 1) - words[m][2] >= 8), None)
            if g is None: die(f'第 {q} 题后找不到 ≥ 8 秒的停顿')
            T['pause'][q] = [round(words[g][2], 2), round(t_at(g + 1), 2)]
            if not 8 <= T['pause'][q][1] - T['pause'][q][0] <= 25: die(f'第 {q} 题后停顿 {T["pause"][q]} 不在 8—25 秒')
            pos = g + 1
    e = find([['thats', 'the', 'end'], ['this', 'is', 'the', 'end']], pos, N, "That's the end")
    T['end'] = t_at(e)
    import soundfile
    a_, sr_ = soundfile.read(wav, dtype='float32', always_2d=True)          # mp3 头里的时长不准（实测多 3—7 秒），按解码长度
    T['audioEnd'] = len(a_) / sr_ + sum(L for _, L in ins)
    if ins: T['插停顿'] = {'秒': GAP, '原音时刻': [t for t, _ in ins], '插入秒': [L for _, L in ins]}
    if CUT:
        T['audioEnd'] = T['pause'][CUT][1]
    seq = [T['title0'], T['secA']]
    for b, (q1, q2) in enumerate(SEC):
        if b == 2: seq.append(T['secB'])
        if b == 4: seq.append(T['secC'])
        seq += [T['blk'][b]['start'], T['blk'][b]['qintro']]
        for q in range(q1, q2 + 1): seq += [T['q'][q], *T['pause'][q]]
    seq += [T['end']]
    if not CUT: seq += [T['audioEnd']]
    if any(y < x for x, y in zip(seq, seq[1:])):
        die('锚点不是按考试顺序递增：' + str([(i, x, y) for i, (x, y) in enumerate(zip(seq, seq[1:])) if y < x]))
    (D / '时间轴.json').write_text(json.dumps(T, ensure_ascii=False, indent=1), 'utf-8')
    print(SID, '时间轴：Section A', T['secA'], '结束', T['end'], '题后停顿', [round(b - a, 1) for a, b in T['pause'].values()])


# ───────────────────────── 画面状态 ─────────────────────────
BLKNAME = ['Conversation One', 'Conversation Two', 'Passage One', 'Passage Two', 'Recording One', 'Recording Two', 'Recording Three']
SECOF = lambda b: 'A' if b < 2 else ('B' if b < 4 else 'C')


def states():
    T = json.loads((D / '时间轴.json').read_text('utf-8'))
    T['q'] = {int(k): v for k, v in T['q'].items()}; T['pause'] = {int(k): v for k, v in T['pause'].items()}
    L = []

    def add(t, **s): L.append((t, s))

    def countdown(a, b, label, **s):      # 同专八：显示 ceil(b - t)，开头不足半秒的一格并进下一格
        n = math.ceil(b - a - 1e-6)
        if (b - a) - (n - 1) < 0.5: n -= 1
        add(a, cd=n, cdl=label, **s)
        for k in range(n - 1, 0, -1): add(b - k, cd=k, cdl=label, **s)

    add(-base.LEAD, kind='title')
    add(T['title0'] + 0.01, kind='instr', sec='A')
    for b, (q1, q2) in enumerate(SEC):
        if CUT and q1 > CUT: break
        if b == 2: add(T['secB'], kind='instr', sec='B')
        if b == 4: add(T['secC'], kind='instr', sec='C')
        add(T['blk'][str(b)]['start'], kind='plist', b=b, st=f'{BLKNAME[b]} 播放中，只放一遍')
        add(T['blk'][str(b)]['qintro'], kind='plist', b=b, st=f'即将念第 {q1}—{q2} 题')
        for q in range(q1, q2 + 1):
            if CUT and q > CUT: break
            add(T['q'][q], kind='q', n=q, st='念题')
            countdown(*T['pause'][q], '作答', kind='q', n=q, st='请在答题卡上作答')
    if not CUT:
        add(T['end'], kind='end')
        add(T['audioEnd'], kind='ansA')
        add(T['audioEnd'] + ANS_A, kind='ansB')
        total = T['audioEnd'] + ANS_A + ANS_B
    else:                                  # 样片：最后一题作答结束后接结束屏 3 秒（静音，满足结尾静音 ≥ 2 秒）
        add(T['audioEnd'], kind='end')
        total = T['audioEnd'] + 3.0
    L.sort(key=lambda x: x[0])
    return L, total, T


# ───────────────────────── 画面 ─────────────────────────
CSS6 = """
.pl .r{grid-template-columns:70px 1fr 1fr}
.pl .r1{display:grid;grid-template-columns:70px 1fr;column-gap:24px;font-size:var(--pf,40px);line-height:calc(var(--pf,40px) * 1.32)}
.pl .r{font-size:var(--pf,40px);line-height:calc(var(--pf,40px) * 1.32)}
.ql .opt{font-size:var(--of,64px);line-height:calc(var(--of,64px) * 1.62)}
.stem{font-size:var(--sf,66px)}
.ans .qg{font-size:38px;line-height:50px;padding:4px 0 5px;flex-wrap:nowrap}
.ans .n{min-width:64px}
.ans .a{white-space:nowrap;overflow:hidden}
.ans b{font-weight:700;width:52px;text-align:center;border:2px solid #000;line-height:42px;align-self:center;margin-right:14px;flex:none}
.ans{grid-template-rows:repeat(8,auto)}
.ans.c10{grid-template-rows:repeat(5,auto)}
.instr{font-size:var(--if,52px)}
"""


def esc(s):
    return html.escape(s, quote=False)


def opt_cells(o, j):
    return f'<span class="opt"><b>{"ABCD"[j]})</b>{esc(o[j])}</span>'


def page(s):
    k = s['kind']
    top = '<div class="top"><b><em>PART II</em>LISTENING COMPREHENSION</b>'
    if s.get('st'): top += f'<span class="st">{esc(s["st"])}</span>'
    if 'cd' in s: top += f'<div class="cd"><i>{s["cdl"]}</i><span>{s["cd"] // 60}:{s["cd"] % 60:02d}</span></div>'
    top += '</div>'
    body, var = '', ''
    if k == 'title':
        top = ''
        body = (f'<div class="ttl blk"><h1>COLLEGE ENGLISH TEST</h1><h2>-BAND SIX-</h2>'
                f'<div class="pt"><span>PART II</span><span>LISTENING COMPREHENSION</span><span>(30 MIN)</span></div>'
                f'<div class="zh">{Y} 年 {M} 月六级听力（第 {K} 套）  视频版真题考试</div>'
                '<div class="note">原题原音</div><div class="note">请备好纸笔作答，参考答案将在考试结束后给出。</div></div>')
    elif k == 'instr':
        sec = s['sec']
        txt = Q['说明'][sec]
        var = '--if:52px' if len(txt) < 520 else '--if:46px'
        body = f'<div class="main"><div class="sec blk"><em>SECTION {sec}</em></div><div class="instr blk">{esc(txt)}</div></div>'
    elif k == 'plist':
        b = s['b']
        q1, q2 = SEC[b]
        qs = [Q['questions'][i - 1][1] for i in range(q1, q2 + 1)]
        pf, two = s.get('fit') or LAY['plist'][str(b)]        # 版式由 layout 在浏览器里实测选定（版式.json）
        rows = ''
        for i, o, t in zip(range(q1, q2 + 1), qs, two):
            if t:
                rows += (f'<div class="qg"><div class="r"><span class="n">{i}.</span>{opt_cells(o, 0)}{opt_cells(o, 2)}</div>'
                         f'<div class="r"><span></span>{opt_cells(o, 1)}{opt_cells(o, 3)}</div></div>')
            else:
                rows += '<div class="qg">' + ''.join(f'<div class="r1"><span class="n">{f"{i}." if j == 0 else ""}</span>{opt_cells(o, j)}</div>' for j in range(4)) + '</div>'
        var = f'--pf:{pf}px'
        body = (f'<div class="main pl"><div class="sec blk"><em>SECTION {SECOF(b)}</em>{BLKNAME[b].upper()}</div>'
                f'<div class="inst2 blk">Questions {q1} to {q2} are based on the {BLKNAME[b].split()[0].lower()} you have just heard.</div><div class="blk">{rows}</div></div>')
    elif k == 'q':
        n = s['n']
        stem, o, _ = Q['questions'][n - 1]
        of, sf = s.get('fit') or LAY['q'][str(n)]
        var = f'--of:{of}px;--sf:{sf}px'
        body = (f'<div class="main"><div class="qn blk">Question {n}</div><div class="stem blk">{esc(stem)}</div><div class="ql blk">' +
                ''.join(f'<div class="opt one"><b>{"ABCD"[j]})</b><span>{esc(o[j])}</span></div>' for j in range(4)) + '</div></div>')
    elif k == 'end':
        body = ('<div class="main"><div class="end blk"><h1>This is the end of<br>PART II LISTENING COMPREHENSION.</h1>'
                '<p>听力考试结束，请放下笔。下面是参考答案。</p></div></div>')
    elif k in ('ansA', 'ansB'):
        rng = range(1, 16) if k == 'ansA' else range(16, 26)
        lab = 'Section A · B（1—15）' if k == 'ansA' else 'Section C（16—25）'
        top = top.replace('</b>', f'</b><span class="st">参考答案：{lab}</span>', 1)
        items = ''
        for i in rng:
            st, o, a = Q['questions'][i - 1]
            items += f'<div class="qg"><span class="n">{i}.</span><b>{a}</b><span class="a">{esc(o["ABCD".index(a)])}</span></div>'
        body = f'<div class="main"><div class="sec blk"><em>KEY</em>PART II LISTENING</div><div class="ans blk{" c10" if k == "ansB" else ""}">{items}</div></div>'
    css = base.CSS.replace('FL/', base.FL.as_uri() + '/') + CSS6
    css = "@import url('" + (ROOT / '四级' / 'tools' / 'fonts' / 'fonts.css').as_uri() + "');" + css
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body style="{var}">{top}{body}'
            f'<div class="foot">CET-6 {Y}.{M:02d} LISTENING</div></body></html>')


LAYF = D / '版式.json'
LAY = json.loads(LAYF.read_text('utf-8')) if LAYF.exists() else {'plist': {}, 'q': {}}


def layout():
    """每段选项一览、每道题：从大字号往下试（选项一览每题先试两栏），专八排版检查 + 题间空隙 0 处的第一个方案写进 版式.json"""
    from playwright.sync_api import sync_playwright
    exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
    res = {'plist': {}, 'q': {}}
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': 1920, 'height': 1080})
        tmp = OUT / 'layout.html'; OUT.mkdir(parents=True, exist_ok=True)

        def bad(st):
            tmp.write_text(page(st), 'utf-8'); pg.goto(tmp.as_uri()); pg.wait_for_function('document.fonts.status === "loaded"')
            return pg.evaluate(base.CHECK_JS) + pg.evaluate(base.QGAP_JS, base.MIN_GAP)
        for b, (q1, q2) in enumerate(SEC):
            nq, got = q2 - q1 + 1, None
            for pf in range(40, 27, -1):
                two = [not any(re.match(r'折行 [A-D]\)', x) for x in bad({'kind': 'plist', 'b': b, 'st': 'x', 'fit': [pf, [k == j for k in range(nq)]]})) for j in range(nq)]
                if not bad({'kind': 'plist', 'b': b, 'st': 'Recording Three 播放中，只放一遍', 'fit': [pf, two]}):
                    got = [pf, two]; break
            if not got: die(f'选项一览 {BLKNAME[b]} 字号降到 28 还放不下')
            res['plist'][str(b)] = got
        for n in range(1, 26):
            got = next(([of, sf] for of in range(64, 39, -2) for sf in (66, 58, 52)
                        if not bad({'kind': 'q', 'n': n, 'st': '请在答题卡上作答', 'cd': 13, 'cdl': '作答', 'fit': [of, sf]})), None)
            if not got: die(f'第 {n} 题字号降到 40 还放不下')
            res['q'][str(n)] = got
        br.close()
    LAYF.write_text(json.dumps(res, ensure_ascii=False), 'utf-8')
    print(SID, '版式：选项一览字号', {k: v[0] for k, v in res['plist'].items()}, '单题选项字号', sorted({v[0] for v in res['q'].values()}))


def leak_check(s, htm):
    """考试过程中的画面不许出现答案：参考答案标题、KEY、任何带答案字母的标记（六级答案是字母，看结构不看文字）"""
    if s['kind'] in ('ansA', 'ansB'): return []
    body = htm.split('</style>', 1)[1]
    txt = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', body)))
    bad = []
    if '参考答案：' in txt or re.search(r'\bKEY\b', txt): bad.append('答案泄露：答案标题')
    if re.search(r'class="(ans|ansb|ok|right|correct)\b', body): bad.append('答案泄露：答案样式')
    return bad


# 换上六级的部分，其余全用专八引擎
base.D, base.OUT, base.NAME, base.Q = D, OUT, NAME, {'gap_answers': []}
base.LIMIT = True                       # 六级原音约 −20 LUFS：整体增益到 −16 + 前瞻限幅（专八引擎里的通用功能）


GAPF = D / '插停顿.json'
GAP = json.loads(GAPF.read_text('utf-8'))['秒'] if GAPF.exists() else 0


def gap_points(Wd):
    """插停顿的原音时刻：每道题（Question N: …?）念完那一刻；只有 <套>/插停顿.json 存在才插，要正好 25 处"""
    if not GAP: return []
    pts, i = [], 0
    while i < len(Wd) - 1:
        if norm(Wd[i][0]) == 'question' and (norm(Wd[i + 1][0]).isdigit() or norm(Wd[i + 1][0]) in NUMW + ['twentyone', 'twentytwo', 'twentythree', 'twentyfour', 'twentyfive']):
            j = next((k for k in range(i + 2, min(i + 60, len(Wd))) if Wd[k][0].endswith('?')), None)
            if j is None or Wd[j][2] is None: die(f'插停顿：第 {i} 个词起的题干找不到带时间的问号结尾')
            nxt = next((k for k in range(j + 1, len(Wd)) if Wd[k][1] is not None), None)
            if nxt is None: die('插停顿：题干后面没有带时间的词')
            pts.append((Wd[j][2], round(max(0.0, GAP - (Wd[nxt][1] - Wd[j][2])), 2))); i = j
        i += 1
    if len(pts) != 25: die(f'插停顿：找到 {len(pts)} 道题（应 25）')
    return pts


def gap_identical(a, y, cuts):
    """插静音后的音频 y 与原音 a 比对：插入段全是数字 0，去掉插入段后与原音逐样本相同；有一处不符返回说明"""
    import numpy as np
    keep, pos, prev = [], 0, 0
    for k, z in cuts:
        seg = y[pos + (k - prev):pos + (k - prev) + z]
        if len(seg) != z or np.any(seg != 0): return f'原音 {k} 处插入的不是数字静音'
        keep.append(y[pos:pos + (k - prev)]); pos += (k - prev) + z; prev = k
    keep.append(y[pos:])
    b = np.concatenate(keep)
    if b.shape != a.shape: return f'去掉插入段后长度 {len(b)} ≠ 原音 {len(a)}'
    d = np.flatnonzero(np.any(b != a, axis=1))
    return f'去掉插入段后有 {len(d)} 个样本与原音不同（第一个在 {d[0]}）' if len(d) else ''


def gapped(mp3):
    """有 插停顿.json 的套：把插入点交给专八引擎，在内存里插（本文件不写音频）"""
    if GAP:
        T = json.loads((D / '时间轴.json').read_text('utf-8'))
        base.INSERTS = list(zip(T['插停顿']['原音时刻'], T['插停顿']['插入秒']))
        base.INSERT_CHECK = gap_identical
    return mp3


def sha_ok(mp3):
    """原音只认老师那份（协调会话审 5）：sha256 必须在 原始材料/SHA256SUMS 里"""
    import hashlib
    sha = hashlib.sha256(Path(mp3).read_bytes()).hexdigest()
    if sha not in {l.split()[0] for l in (HERE.parent / '原始材料/SHA256SUMS').read_text().splitlines() if l.strip()}:
        die(f'{mp3} 的 sha256 不在 原始材料/SHA256SUMS 里')
    return sha
base.states, base.page, base.leak_check = states, page, leak_check


def selftest():
    from playwright.sync_api import sync_playwright
    if not (base.FL / 'TimesNewRoman.ttf').exists(): die('缺原卷字体：先跑 专八/听力/tools/取字体.py')
    exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
    if not LAY['q']: die('先跑 layout')
    good = {'kind': 'q', 'n': 3, 'st': '请在答题卡上作答', 'cd': 9, 'cdl': '作答'}
    pl = {'kind': 'plist', 'b': 0, 'st': 'Conversation One 播放中，只放一遍'}
    a3 = Q['questions'][2][1][0]
    cases = [('正常（单题）', page(good), good, False), ('正常（选项一览）', page(pl), pl, False),
             ('正常（说明）', page({'kind': 'instr', 'sec': 'C'}), {'kind': 'instr', 'sec': 'C'}, False),
             ('考试画面混进参考答案标题', page(good).replace('Question 3', 'Question 3 参考答案：'), good, True),
             ('考试画面带答案样式', page(pl).replace('class="opt"', 'class="ok"', 1), pl, True),
             ('选项太长溢出', page(good).replace(esc(a3), ' '.join([esc(a3)] * (200 // len(a3) + 2)), 1), good, True),      # 按长度造（≥ 200 字母），短选项（The food.）重复 4 遍放得下
             ('选项一览题与题之间没分开（铁律 19）', page(pl).replace('class="qg"', 'class="x"'), pl, True),
             ('字体里没有的字', page(good).replace('Question 3', 'Question 3 𝄞 ꙮ'), good, True)]
    ok = True
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': 1920, 'height': 1080}); cdp = pg.context.new_cdp_session(pg)
        tmp = OUT / 'selftest.html'; OUT.mkdir(parents=True, exist_ok=True)
        for name, htm, s, want in cases:
            tmp.write_text(htm, 'utf-8'); pg.goto(tmp.as_uri()); pg.wait_for_function('document.fonts.status === "loaded"')
            got = pg.evaluate(base.CHECK_JS) + pg.evaluate(base.QGAP_JS, base.MIN_GAP) + base.font_check(pg, cdp) + leak_check(s, htm)
            print(('✅' if bool(got) == want else '❌'), name, '→', got[:2] or '0 处'); ok &= bool(got) == want
        br.close()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    c = sys.argv[2]
    if c == '--自检': selftest()
    elif c == 'timeline': timeline(sys.argv[3])
    elif c == 'layout': layout()
    elif c == 'stills': base.stills('--sample' in sys.argv)
    elif c == 'video':
        sha_ok(sys.argv[3])
        if CUT: base.CUT_END = json.loads((D / '时间轴.json').read_text('utf-8'))['audioEnd']
        base.video(gapped(sys.argv[3]), '--试跑' in sys.argv)
    elif c == 'preview': base.preview()
