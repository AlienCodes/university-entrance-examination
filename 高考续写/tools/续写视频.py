"""读后续写讲解视频引擎（可复用：换一个讲解目录 = 题目.json + 范文.json + 稿.json 就是下一篇）。

只写画面（frames）；截图、排版检查、编码、成品核查全部复用 高考语法填空/tools/讲解视频.py（不改它，运行时换上本引擎的 frames / page / FIT）：
  截图 1920×1080 × 2 = 3840×2160；每张跑 讲解视频.CHECK_JS（出画面、卡片溢出、重叠、孤字、行首标点、英文单词断开、别的项目文字）
  + 本引擎的 EXTRA_JS（字号下限：中文 ≥ 40、原文英文 ≥ 36、范文句 ≥ 44、全文 ≥ 36；高亮必须落在字上）+ CDP 字体回退；有一处就停。
  成品：3840×2160、恒定 30 帧、声画等长、开头静音 ≥ 1.5 秒、结尾 ≥ 2.0 秒、视频音轨响度（含意群级）、合格证、电磁音、呼吸声、
  问句尾音与 ‖ 停顿、逐屏抽帧与截图一致——都由 讲解视频.verify 做。
画面（稿里每段一屏，开口前 0.25 秒切）：片头 → 题目要求（开头语带译文）→ 原文四段（高亮讲到的原文短语，旁边记笔记）→ 开头语分析
  → 情节提纲 / 伏笔与呼应 → 逐句讲范文（上：当前句，得分点短语下划线、正在讲的高亮；下：本段范文 / 意思与作用 / 得分点 / 怎么写·可替换）
  → 常见失分点 → 方法总结 → 完整范文（当前句高亮）。
用法：/opt/ttsenv/bin/python 续写视频.py --稿 讲解目录/稿.json --stills --out 截图目录
      /opt/ttsenv/bin/python 续写视频.py --稿 讲解目录/稿.json --音频 成品.mp3 --video --out 目录 --name 名.mp4
      /opt/ttsenv/bin/python 续写视频.py --自检        （双向验证：正常页 0 处，雷全部报出）
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '高考语法填空/tools')]
import 讲解视频 as V  # noqa: E402

MIN = {'zh': 40, 'pa': 36, 'en': 44, 'fu': 36}
START = {'zh': 44, 'pa': 40, 'en': 50, 'fu': 40}
SEC = {'task': '题目要求', 'p1': '读原文', 'p2': '读原文', 'p3': '读原文', 'p4': '读原文', 'open': '开头语分析', 'outline': '情节提纲',
       'echo': '伏笔与呼应', 'rubric': '评分标准', 'para1': '第一段连读', 'para2': '第二段连读', 'fail': '常见失分点', 'sum': '方法总结', 'full': '完整范文'}
CN = '一二三四五六七八九十'
STEP5 = [('zh', '① 中文构思'), ('v', '② 谓语'), ('s', '③ 主语'), ('r', '④ 其余'), ('pt', '⑤ 得分点')]
DANGN = {'①': '① 融洽衔接', '②': '② 内容丰富', '③': '③ 语法词汇', '④': '④ 连接紧凑'}

CSS = """
.tx, .ttl { line-break: strict; word-break: normal; text-wrap: pretty; }
.tx { font-size: var(--zh, 44px); line-height: 1.5; }
.en { font-size: var(--pa, 40px); line-height: 1.55; font-weight: 500; }
.es { font-size: var(--en, 50px); line-height: 1.5; font-weight: 600; }
.fu { font-size: var(--fu, 40px); line-height: 1.6; margin-bottom: 18px; }
.ttl { font-size: 54px; margin-bottom: 14px; }
.card.stk { padding: 26px 50px; }
.stk .ttl { font-size: 48px; margin-bottom: 8px; }
.nl { padding: 2px 16px; margin: 2px 0; }
.mk { background: var(--hl); border-radius: 6px; box-shadow: 0 0 0 3px var(--hl); }
.u { border-bottom: 5px solid #f0a35e; }
.dim { color: #a8a29e; }
.gv { color: var(--blue); }
.muted { color: var(--muted); }
.nl { padding: 4px 16px; border-radius: 12px; margin: 4px 0; }
.nl.new { background: var(--hl); }
.op { border: 3px solid var(--line); border-radius: 18px; padding: 14px 26px; margin-top: 18px; }
.op.on { border-color: var(--accent); background: #fff7ef; }
.op .lb { font-size: 34px; color: var(--muted); font-weight: 600; }
.cols { display: grid; grid-template-columns: 1fr 1fr; column-gap: 60px; }
.ch { font-size: 46px; font-weight: 700; color: var(--accent); margin-bottom: 6px; }
.rw { display: grid; grid-template-columns: 1fr 70px 1fr; align-items: center; padding: 12px 10px; border-bottom: 2px solid #ddd6c6; }
.rw .ar { text-align: center; color: var(--accent); font-weight: 800; font-size: 44px; }
.rw.hd2 .tx { color: var(--muted); font-weight: 700; }
.rw.new { background: var(--hl); border-radius: 12px; }
.note { white-space: nowrap; color: var(--muted); }
.s5 { display: flex; gap: 12px; margin-bottom: 14px; }
.s5 .st { font-size: 30px; padding: 6px 0; }
.hid { visibility: hidden; }
.bw { display: flex; flex-wrap: wrap; column-gap: 18px; }
.bw .bi { width: fit-content; max-width: 100%; }
.zhl { color: var(--muted); }
.zhl b { color: var(--ink); font-weight: 600; }
.dg { display: inline-block; white-space: nowrap; font-size: 30px; font-weight: 700; color: #fff; background: var(--blue); border-radius: 10px; padding: 0 12px; margin-right: 10px; }
.cols2 { display: grid; grid-template-columns: 1fr 1fr; column-gap: 46px; }
.srcb { border-left: 6px solid var(--line); padding-left: 24px; }
.srcb .lb { font-size: 32px; color: var(--muted); font-weight: 700; margin-bottom: 6px; }
.ptk { margin-bottom: 10px; }
.ptk.old .tx { color: var(--muted); }
"""

FIT_JS = r"""() => {
  // 卡片竖排（.stk 依次往下，最后一张撑到底边）；放不下按 原文英文 → 全文 → 范文句 → 中文 的顺序缩字号，不低于下限
  const cards = [...document.querySelectorAll('.card.stk')], B = document.body;
  const v = %(start)s, mins = %(min)s;
  const set = () => { for (const k in v) B.style.setProperty('--' + k, v[k] + 'px'); };
  const layout = () => { let top = 118;
    cards.forEach((c, i) => { c.style.top = top + 'px';
      c.style.height = i === cards.length - 1 ? (1030 - top) + 'px' : 'auto'; top += c.offsetHeight + 22; });
    return cards.every(c => c.scrollHeight <= c.clientHeight + 1) && (!cards.length || cards[cards.length - 1].clientHeight >= 120); };
  for (let i = 0; i < 80; i++) { set(); if (layout()) return v;
    const k = ['pa', 'fu', 'en', 'zh'].find(k => v[k] > mins[k]); if (!k) return v; v[k] -= 1; }
  return v;
}""" % {'start': json.dumps(START), 'min': json.dumps(MIN)}

EXTRA_JS = r"""(mins) => {
  const bad = [];
  const sel = {zh: '.tx', pa: '.en', en: '.es', fu: '.fu'};
  for (const k in sel) for (const e of document.querySelectorAll(sel[k])) {
    const fs = parseFloat(getComputedStyle(e).fontSize); if (fs < mins[k] - 0.01) bad.push('字号 ' + fs + ' < ' + mins[k] + '：' + e.textContent.slice(0, 16)); }
  for (const e of document.querySelectorAll('.mk, .u')) if (!e.textContent.trim()) bad.push('高亮是空的');
  for (const e of document.querySelectorAll('.tx, .en, .es, .fu, .ttl')) {
    const c = e.closest('.card'); if (!c) continue; const a = e.getBoundingClientRect(), b = c.getBoundingClientRect();
    if (a.right > b.right - 30 || a.bottom > b.bottom - 10) bad.push('文字贴出卡片内边距：' + e.textContent.slice(0, 16)); }
  return bad;
}"""


def esc(s):
    return html.escape(s, quote=False)


def hilite(text, cur=(), old=(), cls_cur='mk', cls_old='u'):
    """按字符标高亮：cur（正在讲）优先于 old（讲过的）；短语必须在文里（找不到就报错，不静默）。中文注释 (使绕道) 整体不断行。"""
    lab = [''] * len(text)
    for ph, c in [(p, cls_old) for p in old] + [(p, cls_cur) for p in cur]:
        i = text.find(ph)
        if i < 0:
            raise ValueError(f'高亮短语不在文里：{ph}')
        for j in range(i, i + len(ph)):
            lab[j] = c
    out, i = [], 0
    while i < len(text):
        j = i
        while j < len(text) and lab[j] == lab[i]:
            j += 1
        chunk = esc(text[i:j])
        chunk = chunk.replace('(', '<span class="note">(').replace(')', ')</span>') if '(' in chunk and ')' in chunk else chunk
        out.append(f'<span class="{lab[i]}">{chunk}</span>' if lab[i] else chunk)
        i = j
    return ''.join(out)


def load(doc):
    t = json.loads((ROOT / doc['题目']).read_text('utf-8'))
    fw = json.loads((ROOT / doc['范文']).read_text('utf-8'))
    return t, fw


def head(t, sec):
    return f'<div class="hd"><div class="src zh">{t["year"]} {esc(t["paper"])} · {esc(t["section"])}</div><div class="src zh">{esc(sec)}</div></div>'


def lines_html(ls, new_n):
    return ''.join(f'<div class="tx nl{" new" if i >= len(ls) - new_n else ""}">{esc(x)}</div>' for i, x in enumerate(ls))


def card(inner, extra=''):
    return f'<div class="card stk"{extra}>{inner}</div>'


def frames(doc):
    t, fw = load(doc)
    P = fw['paragraphs']
    own = [(pi, si) for pi, p in enumerate(P) for si, s in enumerate(p) if not s.get('given')]
    out = [('title', f'<div class="title"><div class="y">{t["year"]}</div><div class="p zh">{esc(t["paper"])}</div>'
                     f'<div class="s zh">{esc(t["section"])} · 思路与范文逐句讲解</div></div>')]
    notes, marks, cols, rows = {}, {}, {1: [], 2: []}, []
    sl = {}                                    # 逐句屏：每屏每阶段累加的行、讲过的得分点
    for s in doc['segments']:
        scr = s['screen']
        if s.get('note'):
            notes.setdefault(scr, []).append(s['note'])
        nn = 1 if s.get('note') else 0
        if scr == 'task' or scr == 'open':
            ops = ''.join(f'<div class="op{" on" if s.get("hi") == f"o{k + 1}" else ""}"><div class="lb">Paragraph {k + 1}:</div>'
                          f'<div class="en">{esc(g)}</div><div class="tx muted">{esc(t["开头语译文"][k])}</div></div>' for k, g in enumerate(t['开头语']))
            if scr == 'task':
                req = ''.join(f'<div class="tx">{esc(x)}</div>' for x in [t['要求'].split('. ', 1)[-1]] + t['注意'])
                body = head(t, SEC[scr]) + card(f'<div class="ttl zh">题目要求</div>{req}{ops}')
            else:
                body = head(t, SEC[scr]) + card(f'<div class="ttl zh">两句开头语</div>{ops}') + card(f'<div class="ttl zh">怎么接</div>{lines_html(notes.get(scr, []), nn)}')
        elif scr in ('p1', 'p2', 'p3', 'p4'):
            k = int(scr[1])
            old = marks.setdefault(scr, [])
            cur = s.get('mark', [])
            para = hilite(t['原文'][k - 1], cur, old)
            old += cur
            body = (head(t, SEC[scr]) + card(f'<div class="ttl zh">原文第 {CN[k - 1]} 段</div><div class="en">{para}</div>')
                    + card(f'<div class="ttl zh">笔记</div>{lines_html(notes.get(scr, []), nn)}'))
        elif scr == 'outline':
            if s.get('col'):
                cols[s['col']] += s['lines']
            new = s.get('lines', []) if s.get('col') else []
            ch = ''.join(f'<div><div class="ch zh">第{CN[c - 1]}段</div>' + ''.join(
                f'<div class="tx nl{" new" if (c == s.get("col") and i >= len(cols[c]) - len(new)) else ""}">{esc(x)}</div>' for i, x in enumerate(cols[c])) + '</div>' for c in (1, 2))
            body = head(t, SEC[scr]) + card(f'<div class="ttl zh">情节提纲（每段四步）</div><div class="cols">{ch}</div>')
        elif scr == 'echo':
            if s.get('row'):
                rows.append(s['row'])
            rs = ''.join(f'<div class="rw{" new" if (s.get("row") and i == len(rows) - 1) else ""}"><div class="en">{esc(a)}</div><div class="ar">→</div><div class="en">{esc(b)}</div></div>'
                         for i, (a, b) in enumerate(rows))
            body = head(t, SEC[scr]) + card('<div class="ttl zh">伏笔与呼应：原文的线，续写都要收住</div>'
                                            '<div class="rw hd2"><div class="tx">原文</div><div class="ar"></div><div class="tx">续写</div></div>' + rs)
        elif scr.startswith('s') and scr[1:].isdigit():
            k = int(scr[1:])
            pi, si = own[k - 1]
            sen = P[pi][si]
            st = sl.setdefault(scr, {'build': [], 'pts': []})
            ph = s['ph']
            shown = s['show'] if ph in ('v', 's', 'r') else (0 if ph == 'zh' else 99)
            if ph in ('v', 's', 'r'):
                st['build'] += s['ln']
            if ph == 'pt':
                st['pts'].append(s)
            stage = {'read': 'r', 'alt': 'pt'}.get(ph, ph)
            order = [x for x, _ in STEP5]
            bar = ''.join(f'<div class="st{" on" if x == stage else (" done" if order.index(x) < order.index(stage) else "")}">{lb}</div>' for x, lb in STEP5)
            if ph in ('pt', 'alt'):
                cur = [s['hl']] if ph == 'pt' else []
                old = [x['hl'] for x in st['pts'] if x is not s]
                es = hilite(sen['en'], cur, old)
            else:
                es = ''.join(f'<span class="{"hid" if n > shown else ("mk" if n == shown and ph != "read" else "")}">{esc(x)}</span>' for x, n in sen['块'])
            top = card(f'<div class="s5">{bar}</div>'
                       f'<div class="tx zhl">中文：<b>{esc(sen["zh"])}</b></div><div class="es">{es}</div>')
            if ph == 'zh':
                low = card(f'<div class="ttl zh">先想中文：为什么要写这一句</div>{lines_html(s["ln"], len(s["ln"]))}')
            elif ph in ('v', 's', 'r', 'read'):
                n_new = 0 if ph == 'read' else 1
                bl = ''.join(f'<div class="tx nl bi{" new" if i >= len(st["build"]) - n_new else ""}">{esc(x)}</div>' for i, x in enumerate(st['build']))
                low = card(f'<div class="ttl zh">汉译英：先谓语，再主语，再其余</div><div class="bw">{bl}</div>')
            elif ph == 'pt':
                pts = ('<div class="ptk">' + ''.join(f'<span class="dg">{DANGN[d]}</span>' for d in s['dang'])
                       + lines_html(s['ln'], len(s['ln'])) + '</div>')
                src = hilite(s['src'], s['mark'])
                low = card(f'<div class="ttl zh">得分点（对应第五档）</div><div class="cols2"><div>{pts}</div>'
                           f'<div class="srcb"><div class="lb zh">原文出处</div><div class="en">{src}</div></div></div>')
            else:
                low = card(f'<div class="ttl zh">可替换表达</div>{lines_html(s["ln"], len(s["ln"]))}')
            body = head(t, f'逐句讲范文 · 第{CN[pi]}段 · 第 {k} / {len(own)} 句') + top + low
        elif scr == 'rubric':
            body = head(t, SEC[scr]) + card(f'<div class="ttl zh">评分标准：最高一档</div>{lines_html(notes.get(scr, []), nn)}')
        elif scr in ('para1', 'para2'):
            pi = int(scr[-1]) - 1
            para = ' '.join(f'<span class="{"gv" if x.get("given") else ""}">{esc(x["en"])}</span>' for x in P[pi])
            zh = ''.join(esc(x['zh']) for x in P[pi])
            body = head(t, SEC[scr]) + card(f'<div class="ttl zh">第{CN[pi]}段范文（蓝色是题目给的开头语）</div><div class="fu">{para}</div>') + card(f'<div class="tx muted">{zh}</div>')
        elif scr in ('fail', 'sum'):
            ttl = '常见失分点' if scr == 'fail' else '方法总结：读后续写五步'
            body = head(t, SEC[scr]) + card(f'<div class="ttl zh">{ttl}</div>{lines_html(notes.get(scr, []), nn)}')
        elif scr == 'full':
            cur = s.get('cur')
            ps = ''.join('<div class="fu">' + ' '.join(
                f'<span class="{"mk" if cur == [pi, si] else ("gv" if x.get("given") else "")}">{esc(x["en"])}</span>' for si, x in enumerate(p)) + '</div>'
                for pi, p in enumerate(P))
            body = head(t, SEC[scr]) + card(f'<div class="ttl zh">完整范文（蓝色是题目给的开头语）</div>{ps}')
        else:
            raise ValueError(scr)
        out.append((s['id'], body))
    return out


def page(body):
    css = V.CSS % {'zk': ROOT / '中考/tools/fonts', 'inter': ROOT / '专八/tools/fonts/inter'}
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}{CSS}</style></head><body>{body}</body></html>'


def install():
    """把本引擎的画面装进 讲解视频（不改那个文件）：frames、page、FIT；CHECK_JS 的断行检查加上本引擎的文字块，再接上 EXTRA_JS。"""
    old = "'.ttl, .sent, .full, .title > div, .hd .src'"
    assert old in V.CHECK_JS, '讲解视频.CHECK_JS 的选择器变了，续写引擎要跟着改'
    core = V.CHECK_JS.replace(old, "'.ttl, .sent, .full, .title > div, .hd .src, .tx, .en, .es, .fu'")
    V.CHECK_JS = f'(args) => {{ const a = ({core})(args); return a.concat(({EXTRA_JS})({json.dumps(MIN)})); }}'
    V.frames, V.page, V.FIT_JS = frames, page, FIT_JS


def selftest():
    """双向验证：讲解视频 自带的雷 + 本引擎的雷（字号过小、贴边、选择器接上）都要报出；正常页 0 处。"""
    base = V.selftest()                 # 讲解视频 自己的雷，用它原来的页面（本引擎的样式会改字号、断行）
    install()
    from playwright.sync_api import sync_playwright
    import tempfile
    ok_body = head({'year': 2026, 'paper': '新课标Ⅰ卷', 'section': '读后续写'}, '题目要求') + card('<div class="ttl zh">笔记</div><div class="tx nl">人物与目的：赶去多伦多，和男朋友过圣诞</div>')
    mines = {
        '中文字号过小': card('<div class="tx" style="font-size:30px">小字</div>'),
        '范文句字号过小': card('<div class="es" style="font-size:36px">Small sentence.</div>'),
        '孤字（.tx 接上断行检查）': card('<div class="tx" style="width:560px;text-wrap:wrap">一二三四五六七八九十一二一二三四五六七八九十一二一二三四五六七八九十一二甲</div>', ' style="right:auto;width:700px"'),
        '卡片溢出': card(''.join('<div class="tx nl">很长的一行笔记很长的一行笔记</div>' for _ in range(30))),
    }
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': V.W, 'height': V.H})
        tmp = Path(tempfile.mkdtemp())
        for name, body in [('正常', ok_body)] + list(mines.items()):
            f = tmp / 'x.html'
            f.write_text(page(body), 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            pg.evaluate(FIT_JS)
            if name.startswith('中文') or name.startswith('范文'):
                pg.evaluate("() => document.querySelectorAll('[style*=font-size]').forEach(e => e.style.setProperty('font-size', e.style.fontSize, 'important'))")
            res[name] = pg.evaluate(V.CHECK_JS, [V.OTHER_PROJECTS, V.BOARD_MIN, V.EN_MIN])
        b.close()
    good = not res['正常'] and all(res[k] for k in mines)
    for k, v in res.items():
        print(f'  {k}：{len(v)} 处' + (f'（{v[0][:40]}）' if v else ''))
    print('续写引擎自检', '通过' if good else '失败')
    return good and base


if __name__ == '__main__':
    if '--自检' in sys.argv:
        sys.exit(0 if selftest() else 1)
    install()
    V.main()
