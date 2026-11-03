"""读后续写讲解视频 v2 画面（用户 2026-11-03）：原文高亮短语第一次出现时 ① 高亮闪一下（亮 → 暗 → 亮保持），② 高亮下面显示中文意思。

不改 v1（续写视频.py、讲解视频.py 一个字不动）：运行时包住 v1 的 frames / FIT / CHECK_JS / stills / timeline / verify。
  范围：稿里每段的 mark（四个原文屏 a01—a08、得分点屏 s*p* 的原文出处），中文意思在讲解目录的 高亮中文.json（键 = mark 原样）。
  闪烁：有 mark 的段展开成 3 张静帧 id、id~d（高亮暗）、id~h（高亮保持），各 FLASH 秒，第一张从这段原来的切屏时刻开始。
  中文：排在高亮所在（最后一）行的下一行，左边对齐高亮；放不下往左挪；高亮在同一行的几处合成一行。
检查（有一处就停，都带双向验证 --自检）：
  预检：每个 mark 都有中文、非空、是中文、不含英文字母、没有多余条目；
  排版（每屏）：中文意思字号 ≥ 40、紧跟在高亮下面（0—60 像素）、不压任何英文字、不出卡片内边距；v1 的全部排版检查照跑（中文意思也查孤字）；
  时间：子屏按顺序、每张 = FLASH 秒（按帧）、后面那段的切屏不早于闪完；
  成品：v1 verify 全部 + 闪烁子屏逐张抽帧，只在亮 / 暗两张图不同的像素上比，必须更像自己那张。
用法同 v1：/opt/ttsenv/bin/python 续写视频_v2.py --稿 … --stills --out …   |   --音频 … --video …   |   --自检
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import 续写视频 as X  # noqa: E402

V = X.V
ROOT = X.ROOT
FLASH = 0.2          # 亮 / 暗 各 0.2 秒（= 6 帧），然后亮着保持
ZM_MIN = 40          # 中文意思字号下限（铁律 5：手机看得清）
SUB = ('~d', '~h')

CSS2 = """
.en { line-height: var(--plh, 1.55); }
.ck { display: grid; grid-template-columns: minmax(0, 0.8fr) 60px minmax(0, 1.2fr); align-items: baseline; padding: 4px 16px; border-radius: 12px; margin: 2px 0; }
.ck .ar, .rw2 .ar { text-align: center; color: var(--accent); font-weight: 800; font-size: 40px; }
.ck .nt { grid-column: 1 / -1; }
.nt { color: var(--muted); }
.jn { padding: 6px 16px; border-radius: 12px; margin-top: 12px; }
.jn .dg { vertical-align: 0.15em; margin-right: 14px; }
.cmp1 .ck:not(.new) > .tx, .cmp1 .ck:not(.new) > .ar { display: none; }
.cmp1 .ck:not(.new) { display: block; padding: 0 16px; }
.cmp2 .jn.old { display: none; }
.jn.old .en { color: var(--muted); }
.ck.new, .jn.new { background: var(--hl); }
.zhs { color: var(--muted); }
.rw2 { display: grid; grid-template-columns: 1fr 70px 1fr; align-items: center; padding: 2px 10px; border-bottom: 2px solid #ddd6c6; }
.rw2 .en, .rw2 .tx { line-height: 1.35; }
.fu[data-tr="cur"] { line-height: 1.5; margin-bottom: 8px; }
.rw2.new { background: var(--hl); border-radius: 12px; }
.rw2.hd2 .tx { color: var(--muted); font-weight: 700; }
.zhm { display: block; font-size: var(--zm, 40px); line-height: 1.25; margin: 0 0 2px; font-weight: 500; color: #b45309; }
.zhm .zq { white-space: nowrap; }
.zhm .zmi { display: inline-block; max-width: 100%; line-break: strict; word-break: normal; text-wrap: pretty;
  background: #fff7e0; border-left: 5px solid #f0b429; border-radius: 6px; padding: 0 14px; }
"""


def zh_table(doc):
    p = (ROOT / doc['题目']).parent / '高亮中文.json'
    return json.loads(p.read_text('utf-8'))['高亮中文']


def preflight(doc):
    """每个 mark 都有中文意思；中文非空、含汉字、不含英文字母；没有多余条目。返回问题列表。"""
    try:
        z = zh_table(doc)
    except FileNotFoundError:
        return ['没有 高亮中文.json']
    marks = [m for s in doc['segments'] for m in s.get('mark', [])]
    bad = [f'高亮没有中文意思：{m}' for m in dict.fromkeys(marks) if m not in z]
    bad += [f'多余的中文条目（不是任何 mark）：{k}' for k in z if k not in marks]
    try:
        fb = fb_table(doc)
    except FileNotFoundError:
        fb = {}
        bad.append('没有 伏笔中文.json')
    try:
        alt = alt_table(doc)
    except FileNotFoundError:
        alt = {}
        bad.append('没有 可替换中文.json')
    alts = [a for s in doc['segments'] for a in s.get('替换', [])]
    bad += [f'可替换表达没有中文（可替换中文.json）：{a}' for a in alts if a not in alt]
    bad += [f'多余的可替换中文条目：{k}' for k in alt if k not in alts]
    fb_alt = list(alt.items())
    rows = [s['row'] for s in doc['segments'] if s.get('row')]
    bad += [f'伏笔表原文一栏没有中文（高亮中文.json）：{a}' for a, _ in rows if a not in z]
    bad += [f'伏笔表续写一栏没有中文（伏笔中文.json）：{b}' for _, b in rows if b not in fb]
    bad += [f'多余的伏笔中文条目：{k}' for k in fb if k not in [b for _, b in rows]]
    for k, v in list(z.items()) + list(fb.items()) + fb_alt:
        if not v.strip() or not re.search(r'[一-鿿]', v) or re.search(r'[A-Za-z]', v):
            bad.append(f'中文意思不合格（空 / 没有汉字 / 有英文字母）：{k} → {v!r}')
    return bad


def frames(doc):
    """v1 的画面 + 当前 mark 带 data-zh；有 mark 的段后面跟两张闪烁子屏。"""
    bad = preflight(doc)
    if bad:
        raise ValueError('高亮中文预检：' + '；'.join(bad))
    z = zh_table(doc)
    t, _ = X.load(doc)
    hl0 = X.hilite

    def hilite(text, cur=(), old=(), **kw):
        out = hl0(text, cur, old, **kw)
        if not cur or not all(c in z for c in cur) or not any(text in p for p in t['原文'] + t['开头语']):   # 只给原文、开头语（含得分点屏的出处）的 mark 加中文
            return out
        order = sorted(cur, key=text.find)
        parts = out.split('<span class="mk">')
        assert len(parts) == len(order) + 1, ('高亮段数与 mark 数不一致（相邻或重叠的 mark？）', cur)
        return parts[0] + ''.join(f'<span class="mk" data-zh="{X.esc(z[m])}">' + p for m, p in zip(order, parts[1:]))

    X.hilite = hilite
    try:
        mine = SCREEN_RE.match
        base = dict(X.frames(dict(doc, segments=[s for s in doc['segments'] if not mine(s['screen'])])))
        base.update(own_frames(doc, t, z))
    finally:
        X.hilite = hl0
    marked = {s['id'] for s in doc['segments'] if s.get('mark')}
    flash = {s['id'] for s in doc['segments'] if s.get('ph') in ('chunk', 'join')}
    out = [('title', base['title'])]
    _, fw = X.load(doc)
    for s in doc['segments']:
        fid, body = s['id'], base[s['id']]
        if s['screen'] in ('para1', 'para2'):          # 英文段落下面那张卡片就是整段中文
            body = body.replace('<div class="fu">', '<div class="fu" data-tr="next">')
        elif s['screen'] == 'full' and s.get('cur'):   # 完整范文：当前句的中文排在高亮下面（同高亮中文的做法）
            pi, si = s['cur']
            assert body.count('<span class="mk">') == 1, fid
            body = body.replace('<span class="mk">', f'<span class="mk" data-zh="{X.esc(fw["paragraphs"][pi][si]["zh"])}">').replace('<div class="fu">', '<div class="fu" data-tr="cur">')
        elif s['screen'] == 'full':                     # 收尾一句（没有当前句）：整篇范文的中文
            body = X.head(t, X.SEC['full']) + X.card('<div class="ttl zh">完整范文（中文）</div>' + ''.join(
                f'<div class="tx">{"".join(X.esc(x["zh"]) for x in p)}</div>' for p in fw['paragraphs']))
        out.append((fid, body))
        if fid in marked or fid in flash:
            if fid in marked:
                assert body.count('data-zh=') == len(s['mark']), fid
            else:
                assert 'fl"' in body or 'fl ' in body, ('新块没有闪烁标记', fid)
            out.append((fid + '~d', body + '<style>.mk[data-zh], .fl { background: transparent !important; box-shadow: none !important; }</style>'))
            out.append((fid + '~h', body))
    return out


SCREEN_RE = re.compile(r's\d+$|echo$')
STEPN = [('zh', '① 中文构思'), ('chunk', '② 逐块翻'), ('join', '③ 连成一句'), ('pt', '④ 得分点')]


def alt_table(doc):
    return json.loads(((ROOT / doc['题目']).parent / '可替换中文.json').read_text('utf-8'))['可替换中文']


def fb_table(doc):
    return json.loads(((ROOT / doc['题目']).parent / '伏笔中文.json').read_text('utf-8'))['伏笔中文']


def word_marks(text, marks):
    """范文句里标出连接处：按整词找（and 取第一处，别的必须恰好一处，同 续写检查 ④）。"""
    lab = [''] * len(text)
    for m in marks:
        hits = [x.start() for x in re.finditer(rf'(?<![A-Za-z’]){re.escape(m)}(?![A-Za-z’])', text)]
        if not hits or (len(hits) > 1 and m != 'and'):
            raise ValueError(f'连接处“{m}”在范文句里出现 {len(hits)} 次')
        for j in range(hits[0], hits[0] + len(m)):
            lab[j] = 'mk'
    out, i = [], 0
    while i < len(text):
        j = i
        while j < len(text) and lab[j] == lab[i]:
            j += 1
        out.append(f'<span class="mk">{X.esc(text[i:j])}</span>' if lab[i] else X.esc(text[i:j]))
        i = j
    return ''.join(out)


def own_frames(doc, t, z):
    """v2 自己画的屏：伏笔与呼应（两栏英文下面都配中文）、逐句讲范文（中文构思 → 逐块翻 → 连成一句 → 读句 → 得分点 → 可替换）。"""
    _, fw = X.load(doc)
    P = fw['paragraphs']
    own = [(pi, si) for pi, p in enumerate(P) for si, s in enumerate(p) if not s.get('given')]
    fb = fb_table(doc)
    out, rows = {}, []
    by = {}
    for s in doc['segments']:
        by.setdefault(s['screen'], []).append(s)
    for s in doc['segments']:
        scr, ph = s['screen'], s.get('ph')
        if not SCREEN_RE.match(scr):
            continue
        if scr == 'echo':
            if s.get('row'):
                rows.append(s['row'])
            cell = lambda en, zh: f'<div><div class="en">{X.esc(en)}</div><div class="tx zhs">{X.esc(zh)}</div></div>'  # noqa: E731
            rs = ''.join(f'<div class="rw2{" new" if (s.get("row") and i == len(rows) - 1) else ""}">{cell(a, z[a])}<div class="ar">→</div>{cell(b, fb[b])}</div>'
                         for i, (a, b) in enumerate(rows))
            out[s['id']] = X.head(t, X.SEC[scr]) + X.card('<div class="ttl zh">伏笔与呼应：原文的线，续写都要收住</div>'
                                                          '<div class="rw2 hd2"><div class="tx">原文</div><div class="ar"></div><div class="tx">续写</div></div>' + rs)
            continue
        k = int(scr[1:])
        pi, si = own[k - 1]
        sen = P[pi][si]
        ss = by[scr]
        ck = [x for x in ss if x.get('ph') == 'chunk']
        jn = {x['step']: x for x in ss if x.get('ph') == 'join'}
        stage = {'read': 'join', 'alt': 'pt'}.get(ph, ph)
        order = [x for x, _ in STEPN]
        bar = ''.join(f'<div class="st{" on" if x == stage else (" done" if order.index(x) < order.index(stage) else "")}">{lb}</div>' for x, lb in STEPN)
        zh = X.hilite(sen['zh'], [s['hl']]).replace('<span class="mk">', '<span class="mk fl">') if ph == 'chunk' else X.esc(sen['zh'])
        es = ''
        if ph in ('pt', 'alt'):                  # 读句时下面就是连好的范文句，上面不再重复
            pts = [x for x in ss if x.get('ph') == 'pt']
            cur = [s['hl']] if ph == 'pt' else []
            old = [x['hl'] for x in pts[:pts.index(s)]] if ph == 'pt' else ([x['hl'] for x in pts] if ph == 'alt' else [])
            es = f'<div class="es">{X.hilite(sen["en"], cur, old)}</div>'
        top = X.card(f'<div class="s5">{bar}</div><div class="tx zhl">中文：<b>{zh}</b></div>{es}')
        if ph == 'zh':
            low = X.card(f'<div class="ttl zh">先想中文：为什么要写这一句</div>{X.lines_html(s["ln"], len(s["ln"]))}')
        elif ph in ('chunk', 'join', 'read'):
            J = s['show'] if ph == 'chunk' else len(ck)
            h = ''
            for i, c in enumerate(ck[:J], 1):
                new = ph == 'chunk' and i == J
                h += (f'<div class="ck{" new fl" if new else ""}"><div class="tx">{X.esc(c["zh"])}</div><div class="ar">→</div><div class="en" data-tr="zh">{X.esc(c["en"])}</div>'
                      + (f'<div class="tx nt">{X.esc(c["note"])}</div>' if new else '') + '</div>')
            step = s.get('step') if ph == 'join' else ('done' if ph == 'read' else None)
            if step and 'base' in jn:
                b = jn['base']
                now = step == 'base'                     # 讲到范文时，保底版留着（变灰、收起要点）；它就是顶上那句中文的直译
                tr = '' if now else ' data-tr="zh"'
                h += (f'<div class="jn{" new fl" if now else " old"}"><div class="en"{tr}><span class="dg">直接连（已经对了）</span>{X.esc(b["base"])}</div>'
                      + (''.join(f'<div class="tx nt">{X.esc(x)}</div>' for x in b['ln']) if now else '') + '</div>')
            if step in ('fan', 'done'):
                f = jn['fan']
                h += (f'<div class="jn{" new fl" if step == "fan" else ""}"><div class="es"><span class="dg">范文</span>{word_marks(sen["en"], f["marks"])}</div>'
                      + ''.join(f'<div class="tx nt">{X.esc(x)}</div>' for x in f['ln']) + '</div>')
            ttl = '逐块翻：按逗号切块，每块先翻成简单英文' if ph == 'chunk' else '连成一句：先写对，再写好'
            low = X.card(f'<div class="ttl zh">{ttl}</div>{h}')
        elif ph == 'pt':
            pts = ('<div class="ptk">' + ''.join(f'<span class="dg">{X.DANGN[d]}</span>' for d in s['dang'])
                   + X.lines_html(s['ln'], len(s['ln'])) + '</div>')
            low = X.card(f'<div class="ttl zh">得分点（对应第五档）</div><div class="cols2"><div>{pts}</div>'
                         f'<div class="srcb"><div class="lb zh">原文出处</div><div class="en">{X.hilite(s["src"], s["mark"])}</div></div></div>')
        elif ph == 'alt':
            alt = alt_table(doc)
            low = X.card('<div class="ttl zh">可替换表达</div>' + ''.join(
                f'<div class="nl new"><div class="tx">{X.esc(ln)}</div><div class="tx zhs">{X.esc(alt[a])}</div></div>' for ln, a in zip(s['ln'], s['替换'])))
        else:
            raise ValueError(f'{s["id"]}：v2 不认识的步骤 {ph}（旧讲法 v/s/r 已不用）')
        out[s['id']] = X.head(t, f'逐句讲范文 · 第{X.CN[pi]}段 · 第 {k} / {len(own)} 句') + top + low
    return out


def page(body):
    # 中文意思是排版时用脚本插进去的；先把这些字隐藏着放进页面，document.fonts.ready 才会等它们的字体子集（否则同一屏两次排版会不一样）
    import html as H
    zs = ''.join(H.unescape(x) for x in re.findall(r'data-zh="([^"]*)"', body))
    pre = f'<div class="zpre" style="position:absolute;left:0;top:0;visibility:hidden;font-size:40px;font-weight:500">{X.esc(zs)}</div>' if zs else ''
    return X.page(pre + body).replace('</style>', CSS2 + '</style>', 1)


ZH_PLACE = r"""() => {
  // 把每个 .mk[data-zh] 的中文排在它（最后一）行的下一行：在那一行行尾插一个块；同一行的几处合成一条
  for (const z of document.querySelectorAll('.zhm')) { const p = z.parentNode; z.remove(); p.normalize(); }
  for (const c of new Set([...document.querySelectorAll('.mk[data-zh]')].map(m => m.closest('.en, .fu, .es, .tx')))) {
    const marks = [...c.querySelectorAll('.mk[data-zh]')];
    const groups = [];
    for (const m of marks) { const rs = [...m.getClientRects()].filter(r => r.width > 0); const r = rs[rs.length - 1];
      let g = groups.find(g => Math.abs(g.top - r.top) < r.height * 0.5);
      if (!g) { g = {top: r.top, bottom: r.bottom, left: r.left, ms: []}; groups.push(g); } g.ms.push(m); g.left = Math.min(g.left, r.left); }
    groups.sort((a, b) => b.top - a.top);      // 从下往上插，插了下面的不影响上面的位置
    for (const g of groups) {
      // 找这一行之后的第一个字（换行处），块插在它前面
      const w = document.createTreeWalker(c, NodeFilter.SHOW_TEXT); let at = null;
      const last = g.ms[g.ms.length - 1];
      for (let n = w.nextNode(); n && !at; n = w.nextNode()) {
        if (!(last.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING) || last.contains(n) || n.parentElement.closest('.zhm')) continue;
        for (let i = 0; i < n.textContent.length; i++) { const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1);
          const b = r.getClientRects()[0]; if (b && b.width && b.top > g.top + (g.bottom - g.top) * 0.5) { at = [n, i]; break; } }
      }
      const blk = document.createElement('span'); blk.className = 'zhm';
      // 中文只在标点后换行（一个分句不拆开）
      const item = t => { const it = document.createElement('span'); it.className = 'zmi';
        for (const ch of t.split(/(?<=[，；、])/)) { const q = document.createElement('span'); q.className = 'zq'; q.textContent = ch; it.appendChild(q); } return it; };
      if (at) { const [n, i] = at; const rest = n.splitText(i); rest.parentNode.insertBefore(blk, rest); } else c.appendChild(blk);
      const cr = c.getBoundingClientRect(), W = cr.width - 2;
      const ms = g.ms.map(m => { const rs = [...m.getClientRects()].filter(r => r.width > 0); return [m, rs[rs.length - 1].left - cr.left]; });
      // 每处排在自己的高亮下面；挤不下就往左挪；还是放不下才合成一条
      const its = ms.map(([m]) => item(m.dataset.zh)); its.forEach(x => blk.appendChild(x));
      const ws = its.map(x => x.getBoundingClientRect().width);
      const xs = []; ms.forEach(([, L], k) => xs.push(k ? Math.max(L, xs[k - 1] + ws[k - 1] + 24) : L));
      const over = xs[xs.length - 1] + ws[ws.length - 1] - W; if (over > 0) for (let k = 0; k < xs.length; k++) xs[k] -= over;
      for (let k = xs.length - 2; k >= 0; k--) xs[k] = Math.min(xs[k], xs[k + 1] - ws[k] - 24);
      if (xs[0] < 0 && its.length > 1) { its.forEach(x => x.remove()); const one = item(g.ms.map(m => m.dataset.zh).join('；')); blk.appendChild(one);
        one.style.marginLeft = Math.max(0, Math.min(ms[0][1], W - one.getBoundingClientRect().width)) + 'px'; }
      else its.forEach((x, k) => { x.style.marginLeft = (k ? xs[k] - xs[k - 1] - ws[k - 1] : Math.max(0, xs[0])) + 'px'; });
    }
  }
}"""

ZH_CHECK_JS = r"""(mins) => {
  const bad = [], R = e => e.getBoundingClientRect();
  const marks = [...document.querySelectorAll('.mk[data-zh]')], zs = [...document.querySelectorAll('.zhm .zmi')];
  const want = marks.map(m => m.dataset.zh).join('|'), got = zs.map(z => z.textContent.split('；')).flat().join('|');
  if (marks.length && [...new Set(want.split('|'))].sort().join('|') !== [...new Set(got.split('|'))].sort().join('|')) bad.push('中文意思没排出来或不对：' + got);
  for (const z of zs) {
    { const w = document.createTreeWalker(z, NodeFilter.SHOW_TEXT); let prev = null;
      for (let n = w.nextNode(); n; n = w.nextNode()) for (let i = 0; i < n.textContent.length; i++) {
        const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1); const b = r.getClientRects()[0]; if (!b || !b.width) continue;
        if (prev && b.top > prev[1].top + prev[1].height * 0.5 && !/[，；、]/.test(prev[0])) bad.push('中文意思在词中间换行：' + prev[0] + ' / ' + n.textContent[i]);
        prev = [n.textContent[i], b]; } }
    const fs = parseFloat(getComputedStyle(z).fontSize); if (fs < mins - 0.01) bad.push('中文意思字号 ' + fs + ' < ' + mins);
    const zr = R(z), card = z.closest('.card'), cr = R(card), host = z.closest('.zhm').parentElement.closest('.en, .fu, .es, .tx');
    if (zr.width < 1 || zr.height < 1 || getComputedStyle(z).visibility !== 'visible') { bad.push('中文意思没排出来（看不见）：' + z.textContent.slice(0, 12)); continue; }
    if (zr.left < cr.left + 30 || zr.right > cr.right - 30 || zr.bottom > cr.bottom - 10 || zr.top < cr.top) bad.push('中文意思出卡片内边距：' + z.textContent.slice(0, 12));
    // 不压上面的高亮行、不压下面的英文：同一段英文里每个字都不能和中文块相交
    const w = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) { if (n.parentElement.closest('.zhm')) continue;
      for (let i = 0; i < n.textContent.length; i++) { if (!n.textContent[i].trim()) continue;
        const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1); const b = r.getClientRects()[0]; if (!b || !b.width) continue;
        if (b.left < zr.right && zr.left < b.right && b.top < zr.bottom - 1 && zr.top < b.bottom - 1) { bad.push('中文意思压住英文：' + z.textContent.slice(0, 12) + ' / ' + n.textContent.slice(Math.max(0, i - 6), i + 6)); break; } } }
    // 中文必须紧跟在它的高亮下面（高亮最后一行的下方 0—60 像素）
    const ms = marks.filter(m => z.textContent.split('；').includes(m.dataset.zh));
    for (const m of ms) { const rs = [...m.getClientRects()].filter(r => r.width > 0), r = rs[rs.length - 1];
      if (zr.top < r.bottom - 1 || zr.top > r.bottom + 60) bad.push('中文意思没有紧跟在高亮下面：' + m.dataset.zh); }
  }
  return bad;
}"""


ENZH_JS = r"""() => {
  // 全片英文配中文（用户 2026-11-03）：卡片里每个含英文（两个词以上）的文本块，本块、同一父元素里的兄弟文本块、或块里插的中文意思（.zhm）
  // 至少要有两个汉字（开头“可替换：”这类不超过 8 个字的标签不算）；data-tr="next" 的块由下一张卡片整体翻译（段落连读屏）
  const bad = [], BL = '.en, .es, .fu, .tx, .lb', HAN = /[\u4e00-\u9fff]/g;
  const han = e => ((e.textContent.replace(/^[^：]{0,8}：/, '')).match(HAN) || []).length;
  const own = e => { const c = e.cloneNode(true); c.querySelectorAll('.zhm').forEach(x => x.remove()); return c.textContent; };
  for (const e of document.querySelectorAll('.card :is(' + BL + ')')) {
    if (e.parentElement.closest(BL) || e.closest('.zpre')) continue;
    const txt = own(e);
    if (!/[A-Za-z]{2,}[^A-Za-z\u4e00-\u9fff]+[A-Za-z]{2,}/.test(txt)) continue;
    const zhOf = x => { if (getComputedStyle(x).display === 'none') return 0; const c = x.cloneNode(true); c.querySelectorAll('.zhm, .dg').forEach(y => y.remove()); c.textContent = c.textContent; return han(c); };
    let ok = zhOf(e) >= 2 || e.querySelector('.zhm .zmi');
    if (!ok) ok = [...e.parentElement.children].some(x => x !== e && x.matches(BL) && !x.matches('.ttl') && zhOf(x) >= 2);
    if (!ok && e.dataset.tr === 'zh') ok = [...document.querySelectorAll('.zhl')].some(x => han(x) >= 6);
    if (!ok && e.dataset.tr === 'cur') ok = !!e.closest('.card').querySelector('.zhm .zmi');
    if (!ok && e.dataset.tr === 'next') { const n = e.closest('.card').nextElementSibling; ok = !!n && n.matches('.card') && han(n) >= 10; }
    if (!ok) bad.push('英文没有中文：' + txt.trim().slice(0, 40));
  }
  return bad;
}"""

ORIG = {}
V0 = {k: getattr(V, k) for k in ('CHECK_JS', 'FIT_JS', 'frames', 'page', 'stills', 'timeline', 'verify')}   # 装之前的原样（可重复装）


def install():
    for k, v in V0.items():
        setattr(V, k, v)
    X.install()
    old = ".tx, .en, .es, .fu'"
    assert old in V.CHECK_JS, '续写引擎的断行选择器变了，v2 要跟着改'
    core = V.CHECK_JS.replace(old, ".tx, .en, .es, .fu, .zmi'")
    V.CHECK_JS = f'(args) => {{ const a = ({core})(args); return a.concat(({ZH_CHECK_JS})({ZM_MIN}), ({ENZH_JS})()); }}'
    hook = 'for (let i = 0; i < 80; i++) { set(); if (layout())'
    assert hook in X.FIT_JS, '续写引擎的 FIT 变了，v2 要跟着改'
    # v1 的 FIT 每改一次字号重排一次；中文块的位置跟着换行变，所以每一轮先重新插中文再量
    last = 'if (!k) return v;'
    assert last in X.FIT_JS, '续写引擎的 FIT 变了，v2 要跟着改'
    # 字号都到下限还放不下（中文意思多占了行）：原文行距 1.55 往下收，最低 1.4
    V.FIT_JS = (X.FIT_JS.replace('() => {', '() => { const place = ' + ZH_PLACE + '; let plh = 1.55;', 1)
                .replace(hook, hook.replace('set(); ', 'set(); place(); '))
                .replace(last, "if (!k) { if (plh > 1.4 + 1e-6) { plh = +(plh - 0.03).toFixed(2); B.style.setProperty('--plh', plh); continue; } "
                         # 字号、行距都到下限还放不下（逐句屏连成一句）：先把讲过的块收成只留英文（中文就在顶上那句），再收起变灰的保底版
                         "if (document.querySelector('.jn') && !B.classList.contains('cmp1')) { B.classList.add('cmp1'); continue; } "
                         "if (document.querySelector('.jn.old') && !B.classList.contains('cmp2')) { B.classList.add('cmp2'); continue; } return v; }"))
    ORIG.update(stills=V0['stills'], timeline=V0['timeline'], verify=V0['verify'])
    V.frames, V.page = frames, page
    V.stills, V.timeline, V.verify = stills, timeline, verify


def stills(doc, outdir, only=None):
    if only:
        only = set(only) | {i + s for i in only for s in SUB}
    return ORIG['stills'](doc, outdir, only)


def timeline(doc, tm, ids):
    base = [i for i in ids if not i.endswith(SUB)]
    c = ORIG['timeline'](doc, tm, base)
    out, j, t0 = [], 0, None
    for fid in ids:
        if fid.endswith(SUB):
            assert out and ids[len(out) - 1].split('~')[0] == fid.split('~')[0], ('闪烁子屏顺序不对', fid)
            out.append(t0 + FLASH * (1 if fid.endswith('~d') else 2))
        else:
            t0 = c[j]
            j += 1
            out.append(t0)
    out.append(c[-1])
    return timeline_check(ids, out)


def timeline_check(ids, cuts):
    fr = [round(x * V.FPS) for x in cuts]
    n = round(FLASH * V.FPS)
    for i, fid in enumerate(ids):
        if fid.endswith(SUB) or (i + 1 < len(ids) and ids[i + 1] == fid + '~d'):
            last = fid.endswith('~h')
            if not last and fr[i + 1] - fr[i] != n:
                raise ValueError(f'闪烁子屏 {fid} 长 {fr[i + 1] - fr[i]} 帧，应为 {n}')
            if last and fr[i + 1] - fr[i] < V.FPS // 2:
                raise ValueError(f'闪完后保持太短：{fid} 只有 {fr[i + 1] - fr[i]} 帧（下一段切屏太早）')
    if any(b <= a for a, b in zip(fr, fr[1:])):
        raise ValueError('切屏时刻不递增')
    return cuts


def flash_problem(frame, own, sib):
    """只在亮 / 暗两张截图不同的像素上比：视频这一帧必须明显更像自己那张。"""
    import numpy as np
    m = np.abs(own - sib).sum(-1) > 30
    if m.sum() < 200:
        return '亮 / 暗两张截图几乎一样（闪烁看不出来）'
    d_own, d_sib = float(np.abs(frame - own)[m].mean()), float(np.abs(frame - sib)[m].mean())
    return None if d_own < d_sib * 0.5 else f'抽帧不像自己（自己 {d_own:.1f}，另一张 {d_sib:.1f}）'


def verify(mp4, mp3, tm, pngdir, ids, fr):
    import shutil
    import subprocess
    import tempfile
    import numpy as np
    from PIL import Image
    errs, rep = ORIG['verify'](mp4, mp3, tm, pngdir, ids, fr)
    info = json.loads((Path(pngdir) / 'stills.json').read_text('utf-8'))
    tmp = Path(tempfile.mkdtemp(prefix='flash_'))
    load = lambda p: np.asarray(Image.open(p).convert('RGB'), np.float32)
    n = 0
    try:
        for i, fid in enumerate(ids):
            if not fid.endswith('~d'):
                continue
            base = fid[:-2]
            pairs = [(i - 1, base, fid), (i, fid, base), (i + 1, base + '~h', fid)]
            for k, me, other in pairs:
                o = tmp / f'{k}.png'
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{(fr[k] + fr[k + 1]) / 2 / V.FPS:.3f}', '-i', str(mp4), '-frames:v', '1', str(o)], check=True)
                p = flash_problem(load(o), load(Path(pngdir) / info[me]['png']), load(Path(pngdir) / info[other]['png']))
                if p:
                    errs.append(f'闪烁 {me}：{p}')
            n += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    rep['flash_groups'] = n
    return errs, rep


def selftest():
    """双向验证：正常 0 处；雷（中文压英文、出卡片、字号小、没排出来、数据缺 / 不是中文、子屏时长、抽帧错张）都要报出。"""
    import numpy as np
    import tempfile
    from playwright.sync_api import sync_playwright
    ok = X.selftest()
    install()
    t = {'year': 2026, 'paper': '新课标Ⅰ卷', 'section': '读后续写'}
    para = ('Emily Sanders, a 25-year-old from Detroit, Michigan, set out on December 23rd with high hopes of reaching Toronto to meet her boyfriend for Christmas. '
            'Although she had heard warnings about an approaching snowstorm, she didn’t give it much thought. As the snow came down more and more heavily, Emily was directed off the highway.')
    def body(extra_css='', zh=True):
        h = X.hilite(para, ['Emily Sanders, a 25-year-old from Detroit, Michigan', 'Emily was directed off the highway'])
        if zh:
            parts = h.split('<span class="mk">')
            h = parts[0] + '<span class="mk" data-zh="艾米丽·桑德斯，25 岁，来自密歇根州底特律">' + parts[1] + '<span class="mk" data-zh="艾米丽被引导驶离了高速公路">' + parts[2]
        return (X.head(t, '读原文') + X.card(f'<div class="ttl zh">原文第一段</div><div class="en">{h}</div>')
                + X.card('<div class="ttl zh">笔记</div><div class="tx nl">人物与目标：赶去多伦多，和男朋友过圣诞</div>') + (f'<style>{extra_css}</style>' if extra_css else ''))
    mines = {
        '中文压住下一行英文': body('.zhm{margin-bottom:-60px !important}'),
        '中文出卡片': body('.zhm .zmi{margin-left:1500px !important; white-space:nowrap}'),
        '中文字号过小': body('.zhm{font-size:30px !important}'),
        '中文没排出来': body('.zhm{display:none !important}'),
        '中文离高亮太远': body('.zhm{margin-top:90px !important}'),
        '中文在词中间换行': body('.zhm .zmi{max-width:300px !important} .zhm .zq{white-space:normal !important}'),
        '英文没有中文': X.head(t, '可替换') + X.card('<div class="ttl zh">可替换表达</div><div class="nl new"><div class="tx">可替换：The nearest station was just a short drive away.</div></div>'),
        '全文屏缺当前句中文': X.head(t, '完整范文') + X.card('<div class="ttl zh">完整范文</div><div class="fu" data-tr="cur">Three days later, Emily returned to get her car. The sky was clear now.</div>'),
    }
    ok_alt = X.head(t, '可替换') + X.card('<div class="ttl zh">可替换表达</div><div class="nl new"><div class="tx">可替换：The nearest station was just a short drive away.</div><div class="tx zhs">最近的火车站开车过去只要一小会儿。</div></div>')
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': V.W, 'height': V.H})
        tmp = Path(tempfile.mkdtemp())
        for name, bd in [('正常', body()), ('正常（可替换带中文）', ok_alt)] + list(mines.items()):
            f = tmp / 'x.html'
            f.write_text(page(bd), 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            pg.evaluate(V.FIT_JS)
            res[name] = pg.evaluate(V.CHECK_JS, [V.OTHER_PROJECTS, V.BOARD_MIN, V.EN_MIN])
        b.close()
    # 数据预检
    doc = {'题目': '高考续写/讲解/2026_新课标Ⅰ卷/题目.json', 'segments': [{'id': 'a', 'mark': ['her car slid into a ditch']}]}
    res['正常（数据）'] = [x for x in preflight(doc) if '多余' not in x]
    z = zh_table(doc)
    for name, val in [('数据：缺中文', None), ('数据：英文没翻', 'her car slid'), ('数据：空', ' ')]:
        zz = dict(z)
        if val is None:
            zz.pop('her car slid into a ditch')
        else:
            zz['her car slid into a ditch'] = val
        old = globals()['zh_table']
        globals()['zh_table'] = lambda d, zz=zz: zz
        try:
            res[name] = [x for x in preflight(doc) if '多余' not in x]
        finally:
            globals()['zh_table'] = old
    # 真实稿：伏笔表、可替换的中文齐全（0 处）；拿掉一条必须报出
    real = json.loads((ROOT / '高考续写/讲解/2026_新课标Ⅰ卷/稿.json').read_text('utf-8'))
    res['正常（真实稿预检）'] = preflight(real)
    for name, fn, key in [('数据：可替换缺中文', 'alt_table', 'free of snow'), ('数据：伏笔表缺中文', 'fb_table', 'lay quiet in the sunshine')]:
        old = globals()[fn]
        zz = dict(old(real))
        zz.pop(key)
        globals()[fn] = lambda d, zz=zz: zz
        try:
            res[name] = preflight(real)
        finally:
            globals()[fn] = old
    # 时间
    ids = ['title', 'a01', 'a01~d', 'a01~h', 'a02']
    try:
        res['正常（时间）'] = [] if timeline_check(ids, [0, 1.0, 1.2, 1.4, 5.0, 9.0]) else ['?']
    except ValueError as e:
        res['正常（时间）'] = [str(e)]
    for name, cuts in [('时间：暗屏太长', [0, 1.0, 1.2, 1.5, 5.0, 9.0]), ('时间：闪完马上切走', [0, 1.0, 1.2, 1.4, 1.5, 9.0])]:
        try:
            timeline_check(ids, cuts)
            res[name] = []
        except ValueError as e:
            res[name] = [str(e)]
    # 抽帧
    own = np.full((60, 60, 3), 255, np.float32)
    sib = own.copy()
    sib[10:40, 10:50] = [255, 241, 168]
    sib[10:40, 10:50, 2] = 100
    res['正常（抽帧）'] = [x for x in [flash_problem(own + 1.5, own, sib)] if x]
    res['抽帧：拿成了另一张'] = [x for x in [flash_problem(sib + 1.5, own, sib)] if x]
    res['抽帧：亮暗一样'] = [x for x in [flash_problem(own, own, own + 1)] if x]
    want = {'中文压住下一行英文': '压住英文', '中文出卡片': '出卡片内边距', '中文字号过小': '中文意思字号', '中文没排出来': '没排出来',
            '中文离高亮太远': '紧跟', '中文在词中间换行': '词中间换行', '数据：缺中文': '没有中文意思', '数据：英文没翻': '不合格', '数据：空': '不合格',
            '英文没有中文': '英文没有中文', '全文屏缺当前句中文': '英文没有中文', '数据：可替换缺中文': '可替换表达没有中文', '数据：伏笔表缺中文': '伏笔表续写一栏没有中文',
            '时间：暗屏太长': '应为', '时间：闪完马上切走': '保持太短', '抽帧：拿成了另一张': '不像自己', '抽帧：亮暗一样': '几乎一样'}
    miss = [k for k, w in want.items() if not any(w in x for x in res[k])]   # 每颗雷必须被它对应的那条检查报出（不是碰巧别的检查报了）
    if miss:
        print('  雷没被对应检查报出：', miss)
    good = not miss and all(not v for k, v in res.items() if k.startswith('正常')) and all(v for k, v in res.items() if not k.startswith('正常'))
    for k, v in res.items():
        print(f'  {k}：{len(v)} 处' + (f'（{v[0][:50]}）' if v else ''))
    print('v2 自检', '通过' if good else '失败')
    return good and ok


if __name__ == '__main__':
    if '--自检' in sys.argv:
        sys.exit(0 if selftest() else 1)
    install()
    V.main()
