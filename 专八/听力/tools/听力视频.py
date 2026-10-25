"""专八听力 2025 视频版真题考试：原音一刀不剪，画面跟着录音走。

  python 听力视频.py timeline            识别.json + 停顿.json → 时间轴.json（锚点都由程序在识别结果里找，找不到或不唯一就报错）
  python 听力视频.py stills [--sample]  时间轴 → 每个画面状态一张 4K 截图（--sample：每种屏型各一张）；每张都跑排版检查，有一处就停
  python 听力视频.py video 原音.wav      截图 + 原音（只做整体增益）→ 成品 mp4，生成后独立核查，不通过就删除成品

画面时刻 = 录音时刻 + LEAD（片头静音 1.5 秒，铁律 3）。录音结束后接参考答案（静音）。
"""
import hashlib, html, json, math, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
D = HERE.parent / '2025'
FL = HERE.parent / 'fonts_local'          # 原卷 PDF 里取出的字体（.gitignore，不进仓库）
import os
OUT = Path(os.environ.get('TEM8_OUT', '/tmp/tem8listen'))      # 截图、中间文件、成品（不进仓库）
FPS, LEAD = 30, 1.5
ANS_A, ANS_B = 40.0, 25.0          # 参考答案两屏停留秒数（录音结束后，静音）
NAME = '2025年 专八听力 视频版真题考试.mp4'
Q = json.loads((D / '题目.json').read_text('utf-8'))


def die(msg):
    print('停止：' + msg); sys.exit(1)


# ───────────────────────── 时间轴 ─────────────────────────
def norm(w):
    return re.sub(r"[^a-z0-9]", '', w.lower())


def timeline():
    W = json.loads((D / '识别.json').read_text('utf-8'))
    S = json.loads((D / '停顿.json').read_text('utf-8'))['静音']
    words = [(norm(w[0]), w[1], w[2]) for w in W]

    def find(seq, lo, hi, nth=None):
        """在 [lo, hi) 里找连续词序列 seq，必须恰好一处；返回第一个词的开始时刻"""
        seq = [norm(x) for x in seq.split()]
        hits = [words[i][1] for i in range(len(words) - len(seq) + 1)
                if lo <= words[i][1] < hi and [words[i + k][0] for k in range(len(seq))] == seq]
        if len(hits) != 1:
            die(f'锚点“{" ".join(seq)}”在 {lo}–{hi} 秒找到 {len(hits)} 处（必须恰好 1 处）')
        return hits[0]

    def sil(lo, hi, mn, mx):
        r = [s for s in S if lo <= s[0] < hi and mn <= s[1] - s[0] <= mx]
        # 静音终点按能量门限量出，可能比识别出的下一个词开头晚几十毫秒：取两者较早的（下一句一开口就换画面）
        return [[a, min(b, min(w[1] for w in words if w[1] > a + 0.5))] for a, b in r]

    T = {}
    T['secA'] = find('Section A Mini', 0, 20)
    T['instrA'] = []
    lo = T['secA']
    for k, sen in enumerate(Q['instrA'][:6]):
        t = find(' '.join(sen.split()[:4]), lo, 45)   # 每句前 4 个词
        T['instrA'].append(t); lo = t + 0.1
    pv = sil(40, 80, 25, 40)
    if len(pv) != 1: die(f'Section A 预览停顿应 1 段，找到 {pv}')
    T['previewA'] = pv[0]
    T['nowA'] = find('Now listen to the mini', 70, 80)
    T['lecture'] = find('Working Memory Good morning', 80, 90)
    T['checkSay'] = find('Now you have three minutes', 540, 560)
    ck = sil(550, 760, 170, 200)
    if len(ck) != 1: die(f'检查时间停顿应 1 段，找到 {ck}')
    T['check'] = ck[0]
    T['secB'] = find('Section B', ck[0][1], ck[0][1] + 10)
    T['instrB'] = []
    lo = T['secB']
    for k, sen in enumerate(Q['instrB']):
        t = find(' '.join(sen.split()[:4]), lo, 790)   # 每句前 4 个词
        T['instrB'].append(t); lo = t + 0.1
    pv = sil(780, 820, 25, 40)
    if len(pv) != 1: die(f'Section B 预览停顿应 1 段，找到 {pv}')
    T['previewB'] = pv[0]
    T['part1'] = find('Now listen to part one', 805, 820)
    T['int1'] = find('Good evening everybody', 815, 830)
    # “This is the end of Part One of the interview”：识别成 “…end. … end of Part One”，取 “end of Part One” 前两个词（This is）的开始
    i = [k for k, w in enumerate(words) if 1075 <= w[1] < 1085 and w[0] == 'end' and words[k + 1][0] == 'of' and words[k + 2][0] == 'part']
    if len(i) != 1: die('Part One 结束语找不到')
    T['part1End'] = words[i[0] - 2][1]
    T['q1'] = find('Question one', 1085, 1090)
    p1 = sil(T['q1'], 1170, 9.5, 11.5)
    if len(p1) != 5: die(f'Part One 题后停顿应 5 段，找到 {len(p1)}')
    T['part2'] = find('Now listen to Part 2', 1160, 1170)
    T['int2'] = find('Historically there have', 1170, 1180)
    i = [k for k, w in enumerate(words) if 1445 <= w[1] < 1455 and w[0] == 'end' and words[k + 1][0] == 'of' and words[k + 2][0] == 'part']
    if len(i) != 1: die('Part Two 结束语找不到')
    T['part2End'] = words[i[0] - 2][1]
    T['q6'] = find('Question six', 1455, 1462)
    p2 = sil(T['q6'], 1545, 9.5, 11.5)
    if len(p2) != 5: die(f'Part Two 题后停顿应 5 段，找到 {len(p2)}')
    T['pauses'] = p1 + p2
    T['endB'] = find('This is the end of Section B', 1535, 1545)
    import soundfile
    T['audioEnd'] = soundfile.info(sys.argv[2]).duration       # 原音时长（timeline 必须给原音路径）
    # 单调性：各锚点必须按考试顺序递增
    seq = [T['secA'], *T['instrA'], T['previewA'][0], T['previewA'][1], T['nowA'], T['lecture'], T['checkSay'],
           T['check'][0], T['check'][1], T['secB'], *T['instrB'], T['previewB'][0], T['previewB'][1], T['part1'], T['int1'],
           T['part1End'], T['q1']] + [x for p in p1 for x in p] + [T['part2'], T['int2'], T['part2End'], T['q6']] + \
          [x for p in p2 for x in p] + [T['endB'], T['audioEnd']]
    if any(b < a for a, b in zip(seq, seq[1:])): die('锚点不是按考试顺序递增：' + str([(i, a, b) for i, (a, b) in enumerate(zip(seq, seq[1:])) if b < a]))
    (D / '时间轴.json').write_text(json.dumps(T, ensure_ascii=False, indent=1), 'utf-8')
    print('时间轴：', {k: v for k, v in T.items() if k not in ('instrA', 'instrB', 'pauses')})
    print('停顿秒数：预览A %.2f 检查 %.2f 预览B %.2f 题后 %s' % (T['previewA'][1] - T['previewA'][0], T['check'][1] - T['check'][0],
          T['previewB'][1] - T['previewB'][0], [round(b - a, 2) for a, b in T['pauses']]))


# ───────────────────────── 画面状态 ─────────────────────────
def states():
    """返回 [(开始录音秒, 状态字典)]，按时间排；倒计时逐秒展开。录音前 LEAD 秒是片头（t<0）。"""
    T = json.loads((D / '时间轴.json').read_text('utf-8'))
    L = []

    def add(t, **s): L.append((t, s))

    def countdown(a, b, label, **s):
        """[a, b) 倒计时：显示 ceil(b - t)；在 b-k 处换数"""
        n = math.ceil(b - a - 1e-6)
        add(a, cd=n, cdl=label, **s)
        for k in range(n - 1, 0, -1):
            add(b - k, cd=k, cdl=label, **s)

    add(-LEAD, kind='title')
    add(T['secA'], kind='instr', sec='A', hi=-1)
    for k, t in enumerate(T['instrA']):
        add(t, kind='instr', sec='A', hi=k)
    countdown(*T['previewA'], '预览', kind='sheet', st='预览答题卡（30 秒）')
    add(T['nowA'], kind='sheet', st='Mini-lecture 即将开始，只放一遍')
    add(T['lecture'], kind='sheet', st='Mini-lecture 播放中，只放一遍')
    add(T['checkSay'], kind='sheet', st='Mini-lecture 结束，检查时间三分钟')
    countdown(*T['check'], '检查', kind='sheet', st='检查答案')
    add(T['check'][1], kind='instr', sec='B', hi=-1)
    for k, t in enumerate(T['instrB'][:6]):
        add(t, kind='instr', sec='B', hi=k)
    add(T['instrB'][6], kind='plist', part=1, st='预览 Part One 选项（30 秒）')
    countdown(*T['previewB'], '预览', kind='plist', part=1, st='预览 Part One 选项（30 秒）')
    add(T['part1'], kind='plist', part=1, st='Part One 即将开始，采访结束后念第 1—5 题')
    add(T['int1'], kind='plist', part=1, st='Part One 播放中，采访结束后念第 1—5 题')
    add(T['part1End'], kind='plist', part=1, st='Part One 结束，即将念题')
    starts = [T['q1']] + [p[1] for p in T['pauses'][:4]] + [T['q6']] + [p[1] for p in T['pauses'][5:9]]
    for k in range(10):
        a, b = T['pauses'][k]
        add(starts[k], kind='q', n=k + 1, st='念题')
        countdown(a, b, '作答', kind='q', n=k + 1, st='请在答题纸上作答')
        if k == 4:
            add(T['part2'], kind='plist', part=2, st='Part Two 即将开始，采访结束后念第 6—10 题')
            add(T['int2'], kind='plist', part=2, st='Part Two 播放中，采访结束后念第 6—10 题')
            add(T['part2End'], kind='plist', part=2, st='Part Two 结束，即将念题')
    add(T['endB'], kind='end')
    add(T['audioEnd'], kind='ansA')
    add(T['audioEnd'] + ANS_A, kind='ansB')
    L.sort(key=lambda x: x[0])
    total = T['audioEnd'] + ANS_A + ANS_B
    return L, total, T


# ───────────────────────── HTML ─────────────────────────
CSS = """
@font-face{font-family:'TNR';src:url('FL/TimesNewRoman.ttf');font-weight:400;font-style:normal}
@font-face{font-family:'TNR';src:url('FL/TimesNewRomanBold.ttf');font-weight:700;font-style:normal}
@font-face{font-family:'TNR';src:url('FL/TimesNewRomanItalic.ttf');font-weight:400;font-style:italic}
@font-face{font-family:'TNR';src:url('FL/TimesNewRomanBoldItalic.ttf');font-weight:700;font-style:italic}
@font-face{font-family:'WingX';src:url('FL/Wingdings.ttf')}
/* 考卷样式（用户 2026-10-25）：纯白底黑字，不用主题；字体就是原卷 PDF 里嵌入的 Times New Roman 四个字重 + SimSun + Wingdings（只在本机，不进仓库） */
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1920px;height:1080px;overflow:hidden;background:#fff;color:#000}
body{font-family:'TNR','Liberation Serif','Noto Serif SC';font-weight:400;position:relative;-webkit-font-smoothing:antialiased}
.top{position:absolute;left:90px;right:90px;top:0;height:118px;border-bottom:2px solid #000;display:flex;align-items:center}
.top b{font-weight:700;font-size:40px;white-space:nowrap}
.top b em{font-style:normal;margin-right:60px}
.st{font-family:'Noto Serif SC','TNR';font-size:36px;white-space:nowrap;margin-left:auto;margin-right:30px}
.cd{display:flex;align-items:baseline;gap:14px;border:3px solid #000;padding:2px 22px 4px;white-space:nowrap}
.cd i{font-style:normal;font-family:'Noto Serif SC';font-size:32px}
.cd span{font-weight:700;font-size:66px;line-height:80px;font-variant-numeric:tabular-nums;min-width:120px;text-align:right}
.main{position:absolute;left:90px;right:90px;top:156px;bottom:44px}
.foot{display:none}
.ttl{position:absolute;left:0;right:0;top:110px;display:flex;flex-direction:column;align-items:center;gap:22px;text-align:center}
.ttl h1{font-weight:700;font-size:80px;line-height:1.15}
.ttl h2{font-weight:700;font-size:80px;line-height:1.1}
.ttl .tl{font-weight:700;font-size:46px;align-self:flex-end;margin-right:220px}
.ttl .pt{font-weight:700;font-size:56px;width:1560px;display:flex;justify-content:space-between;margin-top:46px}
.ttl .zh{font-family:'Noto Serif SC';font-size:56px;margin-top:40px}
.ttl .note{font-family:'Noto Serif SC';font-size:36px;line-height:1.3}
.sec{font-weight:700;font-size:52px;margin-bottom:34px;white-space:nowrap}
.sec em{font-style:normal;margin-right:30px}
.instr{font-weight:700;font-style:italic;font-size:56px;line-height:1.55;text-wrap:pretty}
.instr s{text-decoration:none}
.instr s.on{text-decoration:underline;text-decoration-thickness:3px;text-underline-offset:8px}
.sheet{position:absolute;inset:0;border:2px solid #000;padding:16px 40px 0}
.sheet .t{text-align:center;font-weight:700;font-size:44px;margin-bottom:8px}
.cols{display:flex;gap:56px}
.col{flex:1;min-width:0}
.ln{font-size:37px;line-height:46px;position:relative}
.ln.h{font-weight:700;margin-top:18px}
.ln.h:first-child{margin-top:0}
.ln.b{padding-left:46px}.ln.b::before{content:'\\F06C';font-family:'WingX';position:absolute;left:8px;top:0;font-size:30px}
.ln.e{padding-left:80px}
.ln.d{padding-left:90px}.ln.d::before{content:'\\2014';position:absolute;left:46px}
.gap{white-space:nowrap}
.inst2{font-weight:700;font-style:italic;font-size:42px;line-height:1.35;margin:-8px 0 30px}
.pl .r{display:grid;grid-template-columns:80px 1fr 1fr;column-gap:30px;font-size:43px;line-height:58px;margin-bottom:8px}
.opt b{font-weight:400;margin-right:14px}
.qn{font-weight:700;font-size:52px;margin-bottom:26px}
.stem{font-weight:700;font-size:72px;line-height:1.25;margin-bottom:52px;text-wrap:balance;max-width:1700px}
.ql .opt{font-size:68px;line-height:112px;display:flex}
.ql .opt b{width:90px;flex:none}
.end{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:44px;text-align:center}
.end h1{font-weight:700;font-size:68px;line-height:1.3}.end p{font-family:'Noto Serif SC';font-size:46px}
.ans{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:repeat(8,auto);grid-auto-flow:column;column-gap:70px;row-gap:6px}
.ans div{font-size:46px;line-height:68px;border-bottom:1px solid #000;display:flex;flex-wrap:wrap;column-gap:18px}
.ans .n{font-weight:700;min-width:66px;flex:none}
.ans .a{flex:1 1 0;min-width:0}
.ans .zh{font-family:'Noto Serif SC';font-size:34px;white-space:nowrap;padding-left:84px;flex-basis:100%;line-height:46px;margin-top:-10px}
.ansb{display:grid;grid-template-columns:1fr 1fr;column-gap:56px}
.ansb div{font-size:43px;line-height:96px;border-bottom:1px solid #000;display:flex;gap:20px;white-space:nowrap}
.ansb .n{font-weight:700;min-width:56px}
.ansb b{font-weight:700;width:64px;line-height:62px;align-self:center;text-align:center;border:2px solid #000}
"""


def esc(s):
    return html.escape(s, quote=False)


def gaps(s):
    return re.sub(r'\{(\d+)\}', lambda m: f'<span class="gap">({m.group(1)}) _______</span>', esc(s))


def page(s):
    k = s['kind']
    top = '<div class="top"><b><em>PART I</em>LISTENING COMPREHENSION</b>'
    if s.get('st'):
        top += f'<span class="st">{esc(s["st"])}</span>'
    if 'cd' in s:
        top += f'<div class="cd"><i>{s["cdl"]}</i><span>{s["cd"] // 60}:{s["cd"] % 60:02d}</span></div>'
    top += '</div>'
    body = ''
    if k == 'title':
        top = ''
        body = ('<div class="ttl blk"><h1>TEST FOR ENGLISH MAJORS (2025)</h1><h2>-GRADE EIGHT-</h2>'
                '<div class="pt"><span>PART I</span><span>LISTENING COMPREHENSION</span><span>(25 MIN)</span></div>'
                '<div class="zh">2025 年专八听力  视频版真题考试</div>'
                '<div class="note">原题原音</div><div class="note">请备好纸笔作答，参考答案将在考试结束后给出。</div></div>')
    elif k == 'instr':
        sec = s['sec']
        head = '<em>SECTION A</em>MINI-LECTURE' if sec == 'A' else '<em>SECTION B</em>INTERVIEW'
        sents = Q['instrA'][:6] if sec == 'A' else Q['instrB']
        h = s['hi']
        sp = ' '.join(f'<s class="{"on" if i == h else ("done" if i < h else "")}">{esc(x)}</s>' for i, x in enumerate(sents))
        body = f'<div class="main"><div class="sec blk">{head}</div><div class="instr blk">{sp}</div></div>'
        top = top.replace('<div class="top">', '<div class="top">', 1)
    elif k == 'sheet':
        cols, cur = [], []
        for it in Q['sheet']:
            if it[0] == 'title':
                continue
            if it[0] == 'col':
                cols.append(cur); cur = []; continue
            cur.append(f'<div class="ln {it[0]}">{gaps(it[1])}</div>')
        cols.append(cur)
        body = ('<div class="main"><div class="sheet blk"><div class="t">Working Memory</div><div class="cols">' +
                ''.join(f'<div class="col">{"".join(c)}</div>' for c in cols) + '</div></div></div>')
    elif k == 'plist':
        p = s['part']
        rng = range(0, 5) if p == 1 else range(5, 10)
        rows = ''
        for i in rng:
            o = Q['questions'][i][1]
            rows += (f'<div class="r"><span class="n">{i + 1}.</span>' +
                     ''.join(f'<span class="opt"><b>{"ABCD"[j]}.</b>{esc(o[j])}</span>' for j in (0, 1)) +
                     '</div><div class="r"><span></span>' +
                     ''.join(f'<span class="opt"><b>{"ABCD"[j]}.</b>{esc(o[j])}</span>' for j in (2, 3)) + '</div>')
        name = 'Part One' if p == 1 else 'Part Two'
        body = (f'<div class="main pl"><div class="sec blk"><em>SECTION B</em>INTERVIEW: {name.upper()}</div>'
                f'<div class="inst2 blk">Now, listen to Part {"One" if p == 1 else "Two"} of the interview. Questions {"1 to 5" if p == 1 else "6 to 10"} are based on Part {"One" if p == 1 else "Two"} of the interview.</div><div class="blk">{rows}</div></div>')
    elif k == 'q':
        n = s['n']
        stem, o, _ = Q['questions'][n - 1]
        body = (f'<div class="main"><div class="qn blk">Question {n}</div><div class="stem blk">{esc(stem)}</div><div class="ql blk">' +
                ''.join(f'<div class="opt one"><b>{"ABCD"[j]}.</b><span>{esc(o[j])}</span></div>' for j in range(4)) + '</div></div>')
    elif k == 'end':
        body = ('<div class="main"><div class="end blk"><h1>This is the end of<br>PART I LISTENING COMPREHENSION.</h1>'
                '<p>听力考试结束，请放下笔。下面是参考答案。</p></div></div>')
    elif k == 'ansA':
        top = top.replace('</b>', '</b><span class="st">参考答案：Section A Mini-lecture</span>', 1)
        items = ''
        for i, a in enumerate(Q['gap_answers']):
            m = re.match(r'(.*?)(（.*）)?$', a)
            note = f'<span class="zh">{esc(m.group(2))}</span>' if m.group(2) else ''
            items += f'<div><span class="n">({i + 1})</span><span class="a">{esc(m.group(1))}</span>{note}</div>'
        body = f'<div class="main"><div class="sec blk"><em>KEY</em>SECTION A MINI-LECTURE</div><div class="ans blk">{items}</div></div>'
    elif k == 'ansB':
        top = top.replace('</b>', '</b><span class="st">参考答案：Section B Interview</span>', 1)
        items = ''
        for i in [0, 5, 1, 6, 2, 7, 3, 8, 4, 9]:
            st, o, a = Q['questions'][i]
            items += f'<div><span class="n">{i + 1}.</span><b>{a}</b><span>{esc(o["ABCD".index(a)])}</span></div>'
        body = f'<div class="main"><div class="sec blk"><em>KEY</em>SECTION B INTERVIEW</div><div class="ansb blk">{items}</div></div>'
    css = CSS.replace('FL/', FL.as_uri() + '/')
    css = "@import url('" + (ROOT / '四级' / 'tools' / 'fonts' / 'fonts.css').as_uri() + "');" + css
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{top}{body}<div class="foot">TEM-8 2025 LISTENING</div></body></html>'


# ───────────────────────── 排版检查（每张截图都跑） ─────────────────────────
CHECK_JS = r"""() => {
 const bad = [], W = 1920, H = 1080;
 const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
 for (const e of document.querySelectorAll('body *')) {
   if (!vis(e)) continue;
   const r = e.getBoundingClientRect();
   if (r.left < -0.5 || r.top < -0.5 || r.right > W + 0.5 || r.bottom > H + 0.5) bad.push('出画面 ' + e.className + ' ' + e.textContent.slice(0, 30));
   if (e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible') bad.push('溢出 ' + e.className);
 }
 // 主区域内容不能超出 main / sheet 边界
 for (const box of document.querySelectorAll('.main, .sheet, .ttl')) {
   const b = box.getBoundingClientRect();
   for (const e of box.querySelectorAll('*')) {
     if (!vis(e)) continue; const r = e.getBoundingClientRect();
     const m = box.classList.contains('sheet') ? 14 : -0.5;   // 答题卡内容离边框至少 14 像素
     if (r.bottom > b.bottom - m || r.right > b.right - m || r.left < b.left + m) bad.push('超出边框 ' + (e.className || e.tagName) + ' ' + e.textContent.slice(0, 30));
   }
 }
 // 块之间不重叠
 const blks = [...document.querySelectorAll('.blk, .top, .foot')].filter(vis).map(e => [e, e.getBoundingClientRect()]);
 for (let i = 0; i < blks.length; i++) for (let j = i + 1; j < blks.length; j++) {
   const [a, ra] = blks[i], [b, rb] = blks[j];
   if (a.contains(b) || b.contains(a)) continue;
   if (Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left) > 0.5 && Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top) > 0.5) bad.push('重叠 ' + a.className + ' / ' + b.className);
 }
 // 选项、一览行、答案行、状态、倒计时：必须一行
 for (const e of document.querySelectorAll('.opt, .pl .r > span, .ansb div, .ans .zh, .note, .inst2, .end p, .ttl .zh, .ttl h2, .ttl h1, .st, .cd i, .cd span, .gap, .sec, .qn, .top b')) {
   const lh = parseFloat(getComputedStyle(e).lineHeight) || parseFloat(getComputedStyle(e).fontSize) * 1.3;
   const rs = e.getClientRects(); if (rs.length > 1) { bad.push('折行 ' + e.textContent.slice(0, 40)); continue; }
   if (e.getBoundingClientRect().height > lh * 1.6 + 8) bad.push('折行 ' + e.textContent.slice(0, 40));
 }
 // 答题卡每一行：折行时空格编号不能和空格线拆开（.gap 一行），另外记下行数供核对
 // 英文单词不许被拆开（断字）
 for (const e of document.querySelectorAll('body *')) { const h = getComputedStyle(e).hyphens; if (h === 'auto') bad.push('断字 ' + e.className); }
 return bad;
}"""

ALLOWED_FONTS = {'Times New Roman', 'Liberation Serif', 'Noto Serif SC', 'Wingdings'}   # 原卷字体 + 原卷里没有轮廓的字的后备（度量兼容 / 思源宋体）


def font_check(page_, cdp):
    """CDP 取每个元素实际用到的字体：出现允许以外的字体（系统字体回退）就报错"""
    bad = []
    cdp.send('DOM.enable'); cdp.send('CSS.enable')
    root = cdp.send('DOM.getDocument', {'depth': -1})['root']
    ids = cdp.send('DOM.querySelectorAll', {'nodeId': root['nodeId'], 'selector': 'body, body *'})['nodeIds']
    for nid in ids:
        try:
            fs = cdp.send('CSS.getPlatformFontsForNode', {'nodeId': nid})['fonts']
        except Exception:
            continue
        for f in fs:
            if not any(f['familyName'] == a or f['familyName'].startswith(a + ' ') for a in ALLOWED_FONTS):   # “EB Garamond ExtraBold”是 800 字重的本名
                bad.append(f'字体回退 {f["familyName"]} ×{f["glyphCount"]}')
    return bad


ANSWER_WORDS = None


def leak_check(s, htm):
    """考试过程中的画面不许出现答案：填空答案短语、选择题“正确答案”标记"""
    if s['kind'] in ('ansA', 'ansB'):
        return []
    bad = []
    txt = re.sub(r'<[^>]+>', ' ', htm.split('</style>', 1)[1])
    txt = re.sub(r'\s+', ' ', html.unescape(txt)).lower()
    for a in Q['gap_answers']:
        for part in re.split(r'[/,（]', a):
            p = part.strip().lower().rstrip('）')
            if len(p.split()) >= 2 and p in txt:
                bad.append(f'答案泄露：{p}')
    if '参考答案 ·' in txt or 'key' in txt.split():
        bad.append('答案泄露：答案标题')
    return bad


def color_check(png):
    """考卷样式只许黑白灰：任何像素 R、G、B 相差超过 6 就算彩色"""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(png).convert('RGB')).astype(int)
    n = int(((a.max(2) - a.min(2)) > 6).sum())
    return f'画面里有 {n} 个彩色像素' if n else ''


def key(s):
    return hashlib.sha1(json.dumps(s, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def stills(sample=False):
    from playwright.sync_api import sync_playwright
    L, total, T = states()
    todo = {}
    for t, s in L:
        todo.setdefault(key(s), s)
    if sample:
        pick, seen = {}, set()
        for t, s in L:
            typ = s['kind'] + ('+cd' if 'cd' in s else '')
            if typ not in seen and not (s['kind'] == 'instr' and s['hi'] < 2):
                seen.add(typ); pick[key(s)] = s
        todo = pick
    shots = OUT / 'shots'; shots.mkdir(parents=True, exist_ok=True)
    errs = 0
    exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2)
        cdp = pg.context.new_cdp_session(pg)
        tmp = OUT / 'page.html'
        for i, (k, s) in enumerate(todo.items()):
            png = shots / f'{k}.png'
            htm = page(s)
            tmp.write_text(htm, 'utf-8')
            pg.goto(tmp.as_uri()); pg.evaluate('document.fonts.ready')
            pg.wait_for_function('document.fonts.status === "loaded"')
            bad = pg.evaluate(CHECK_JS) + font_check(pg, cdp) + leak_check(s, htm)
            if bad:
                errs += 1
                print('排版检查不通过', s, sorted(set(bad))[:8])
                pg.screenshot(path=str(png.with_suffix('.bad.png')))
                if not sample:
                    die(f'{len(bad)} 处')
                continue
            if not png.exists():
                pg.screenshot(path=str(png))
                c = color_check(png)
                if c:
                    png.unlink(); die(f'{c}：{s}')
            if sample:
                print('样张', s['kind'], 'cd' in s, png)
        br.close()
    if errs:
        die(f'{errs} 张截图排版检查不通过')
    print(f'截图 {len(todo)} 张，排版检查全部 0 处')


# ───────────────────────── 视频 ─────────────────────────
def video(wav):
    import numpy as np, soundfile as sf, pyloudnorm as pl
    L, total, T = states()
    a, sr = sf.read(wav, dtype='float64', always_2d=True)
    if abs(len(a) / sr - T['audioEnd']) > 0.01: die('原音时长与时间轴不符')
    gain_db = -16 - pl.Meter(sr).integrated_loudness(a)
    g = 10 ** (gain_db / 20)
    if 20 * np.log10(np.abs(a).max() * g) > -1: die('整体增益后峰值超过 −1 dBFS（只许整体增益，不许压缩限幅）')
    lead = np.zeros((int(round(LEAD * sr)), 2)); tail = np.zeros((int(round((ANS_A + ANS_B) * sr)), 2))
    y = np.concatenate([lead, a * g, tail])
    OUT.mkdir(parents=True, exist_ok=True)
    sf.write(OUT / 'audio.wav', y, sr, subtype='PCM_24')
    nfr = round((total + LEAD) * FPS)
    # 每个状态的开始帧（录音时刻 + LEAD，取整到帧）
    fr = [(round((t + LEAD) * FPS), key(s)) for t, s in L]
    fr = [(f, k) for f, k in fr]
    lst = []
    for (f, k), nxt in zip(fr, [x[0] for x in fr[1:]] + [nfr]):
        if nxt <= f: die(f'画面状态时长 ≤ 0 帧：{k}')
        png = OUT / 'shots' / f'{k}.png'
        if not png.exists(): die(f'缺截图 {k}（先跑 stills）')
        lst.append(f"file '{png}'\nduration {(nxt - f) / FPS:.6f}")
    lst.append(f"file '{OUT / 'shots' / (fr[-1][1] + '.png')}'")
    (OUT / 'list.txt').write_text('\n'.join(lst) + '\n')
    (OUT / '帧表.json').write_text(json.dumps(fr), 'utf-8')
    out = OUT / NAME
    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(OUT / 'list.txt'), '-i', str(OUT / 'audio.wav'),
           '-fps_mode', 'cfr', '-r', str(FPS), '-frames:v', str(nfr), '-c:v', 'libx264', '-preset', 'medium', '-tune', 'stillimage', '-crf', '18',
           '-pix_fmt', 'yuv420p', '-g', '300', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-af', 'aresample=48000',
           '-movflags', '+faststart', '-shortest', str(out)]
    subprocess.run(cmd, check=True)
    verify(out, T, total, fr)


def verify(out, T, total, fr):
    """成品独立核查：分辨率、帧率恒定、声画等长、开头/结尾静音、整体响度与峰值、画面切换时刻与时间轴一致"""
    import numpy as np, pyloudnorm as pl
    bad = []
    pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(out)],
                                   capture_output=True, text=True).stdout)
    v = [s for s in pr['streams'] if s['codec_type'] == 'video'][0]
    au = [s for s in pr['streams'] if s['codec_type'] == 'audio'][0]
    if (v['width'], v['height']) != (3840, 2160): bad.append('分辨率')
    if v['r_frame_rate'] != '30/1': bad.append('帧率')
    vd, ad = float(v['duration']), float(au['duration'])
    want = total + LEAD
    if abs(vd - want) > 1 / FPS + 1e-3 or abs(ad - vd) > 0.05: bad.append(f'时长 画面 {vd} 声音 {ad} 应 {want:.3f}')
    pts = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'packet=pts_time', '-of', 'csv=p=0', str(out)],
                         capture_output=True, text=True).stdout.split()
    p = sorted(float(x) for x in pts)
    d = np.diff(p)
    if len(p) != round(want * FPS) or d.max() - d.min() > 1e-3: bad.append(f'帧时间戳不恒定（{len(p)} 帧）')
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(out), '-f', 'f32le', '-ac', '2', '-ar', '48000', '-'], capture_output=True).stdout
    y = np.frombuffer(pcm, dtype=np.float32).reshape(-1, 2).astype(np.float64)
    sr = 48000
    seg = y[int(LEAD * sr):int((LEAD + T['audioEnd']) * sr)]
    L = pl.Meter(sr).integrated_loudness(seg)
    peak = 20 * np.log10(np.abs(seg).max())
    if abs(L + 16) > 0.7: bad.append(f'整体响度 {L:.2f} LUFS')
    if peak > -1: bad.append(f'峰值 {peak:.2f} dBFS')
    head = 20 * np.log10(np.abs(y[:int(LEAD * sr) - 480]).max() + 1e-9)
    tl = 20 * np.log10(np.abs(y[int((LEAD + T['audioEnd']) * sr) + 4800:]).max() + 1e-9)
    if head > -60: bad.append(f'开头静音 {head:.1f} dB')
    if tl > -60 or (len(y) / sr - LEAD - T['audioEnd']) < 2.0: bad.append(f'结尾静音 {tl:.1f} dB')
    # 画面切换时刻：抽取每个状态起点后 2 帧的画面，与对应截图比较（缩小后均方差），证明画面按时间轴切换
    from PIL import Image
    import io
    chk = fr[::max(1, len(fr) // 60)] + [fr[-1]]
    for f, k in chk:
        t = (f + 1.5) / FPS
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.4f}', '-i', str(out), '-frames:v', '1', '-vf', 'scale=480:270', '-f', 'image2', '-c:v', 'png', '-'],
                             capture_output=True).stdout
        a = np.asarray(Image.open(io.BytesIO(raw)).convert('L'), dtype=float)
        b = np.asarray(Image.open(OUT / 'shots' / f'{k}.png').convert('L').resize((480, 270)), dtype=float)
        if np.abs(a - b).mean() > 3: bad.append(f'画面与截图不符 帧{f} {k} 差 {np.abs(a - b).mean():.1f}')
    rep = {'时长秒': round(vd, 3), '整体响度LUFS': round(L, 2), '峰值dBFS': round(peak, 2), '画面状态': len(fr), '抽查切换点': len(chk),
           '问题': bad}
    (D / '核查报告.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), 'utf-8')
    print(rep)
    if bad:
        out.unlink(); die('成品核查不通过，已删除成品')
    print('成品核查全部通过：', out)


def selftest():
    """双向验证（踩坑 77）：正常画面 0 处；故意放进 ①答案 ②溢出 ③字体里没有的字，三项检查都必须报出"""
    from playwright.sync_api import sync_playwright
    ok = True
    exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
    good = {'kind': 'q', 'n': 9, 'st': '作答', 'cd': 7, 'cdl': '作答'}
    sheet = {'kind': 'sheet', 'st': '检查答案', 'cd': 125, 'cdl': '检查'}
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
        cdp = pg.context.new_cdp_session(pg)
        tmp = OUT / 'selftest.html'; OUT.mkdir(parents=True, exist_ok=True)

        def run(htm, s):
            tmp.write_text(htm, 'utf-8'); pg.goto(tmp.as_uri()); pg.wait_for_function('document.fonts.status === "loaded"')
            return pg.evaluate(CHECK_JS) + font_check(pg, cdp) + leak_check(s, htm)
        cases = [('正常（单题 + 答题卡）', page(good), good, False), ('正常', page(sheet), sheet, False),
                 ('答题卡里混进答案', page(sheet).replace('and knowledge', 'and knowledge long-term memory'), sheet, True),
                 ('选项太长溢出', page(good).replace('Creativity is irrational.', 'Creativity is irrational. ' * 4), good, True),
                 ('字体里没有的字', page(good).replace('QUESTION 9', 'QUESTION 9 ☃'), good, True)]
        for name, htm, s, want in cases:
            got = run(htm, s)
            print(('✅' if bool(got) == want else '❌'), name, '→', got[:2] or '0 处')
            ok &= bool(got) == want
        br.close()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    c = sys.argv[1]
    if c == '--自检': selftest()
    if c == 'timeline': timeline()  # python 听力视频.py timeline 原音.wav
    elif c == 'stills': stills('--sample' in sys.argv)
    elif c == 'video': video(sys.argv[2])
