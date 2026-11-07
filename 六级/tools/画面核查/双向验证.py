"""用法：/opt/ttsenv/bin/python 六级/tools/画面核查/双向验证.py（约 3 分钟；全部通过退出码 0）。
六级移植时引擎里加的每一处修正、检查放宽，双向验证：
   修正撤掉（只在内存里改一份引擎源码，不动仓库文件）→ 受影响的那几屏必须报出问题；现在的引擎 → 0。
   检查放宽（layoutcheck 例外、HBOX .pr）→ 在现在的画面上埋雷（JS 改页面），必须报出。"""
import json, sys, types, tempfile
from pathlib import Path
R = Path(__file__).resolve().parents[3]
ENGINE = R / '专八' / 'tools' / 'make_video.py'
SRC = ENGINE.read_text('utf-8')

def build(old=None, new=None):
    src = SRC
    if old is not None:
        assert src.count(old) == 1, ('撤修正的片段不唯一或找不到', old[:80])
        src = src.replace(old, new)
    m = types.ModuleType('mv_variant'); m.__file__ = str(ENGINE)
    exec(compile(src, str(ENGINE), 'exec'), m.__dict__)
    m.set_project('六级')
    return m

P = {p['id']: p for p in json.loads((R / '六级/data/vocab.json').read_text('utf-8'))['passages']}

def run(pg, f, m, pid, ks, mine=None, want=None):
    orig = m.screens
    m.screens = lambda p: [x for x in orig(p) if x[3] in ks]
    m._SPLIT_SIZES.clear()
    out = []
    for i, label, fit, r in m.layout(pg, P[pid], f):
        if mine:
            pg.evaluate(mine)
        probs = m.screen_checks(pg, label, fit, r)
        if want:
            probs = [x for x in probs if want in x]
        out += probs
    m.screens = orig
    return out

CASES = [  # 名称, 篇目, 句号（0 = 片头）, 撤掉的修正 (现在的源码片段, 撤掉后的样子)
 ('片头长标题在冒号后换行 TITLE_JS', 's06', {0}, ('            pg.evaluate(TITLE_JS)\n', '')),
 ('释义以省略号/破折号开头的块前加 <wbr>', 's04', {17}, ("('<wbr>' if a and s[lo + a] in '…—' else '') +", '')),
 ('释义以省略号/破折号开头的块前加 <wbr>（s21；原 s05 第 9 句在 2026-10-17 审阅修正后不再触发）', 's21', {4}, ("('<wbr>' if a and s[lo + a] in '…—' else '') +", '')),
 ('悬空连字符与 or/and 不断开', 's20', {14}, ("return re.sub(r'(?<![\\w’-])([A-Za-z]+-) ((?:or|and|nor|to)\\b)', r'<nobr>\\1 \\2</nobr>', h)", 'return h')),
# 2026-10-23 起由 zh_bind.en_spans ③（数字 + 小写词整体不断开，专八书卷水墨截图盲审）统一覆盖：撤掉下面这条旧修正后 s11 第 16 句仍 0 处是预期，不再单独验证；
 # ③ 本身的双向验证见 踩坑 71（旧引擎 + 新检查报“in 26 / countries”“20 / barrels”等，新引擎 0）
 # ('高亮单位 percent 前不换行空格', 's11', {16}, ("    out = re.sub(rf'(\\d) (<span class=\"(?:w|ph)\">(?:<nobr>)?(?:{UNITS})(?![A-Za-z]))', '\\\\1\\u00a0\\\\2', out)\n", '')),
 ('超宽连字符词条在连字符处断开 wide()', 's10', {21}, ("for (const n of b.querySelectorAll('nobr')) if (n.getBoundingClientRect().right > R + 0.5) n.style.whiteSpace = 'normal'; };", '};')),
 ('括注片段按词汇栏内边距量 notes()（2026-10-23 起量片段宽度与 R − 左边界，撤掉 = 只比网格列宽）', 's39', {16}, ("if (e.getBoundingClientRect().width > Math.min(dv.clientWidth, R - L) + 0.5) e.style.whiteSpace = 'normal'; }", "if (e.getBoundingClientRect().width > dv.clientWidth + 0.5) e.style.whiteSpace = 'normal'; }")),
 ('末尾短语连续接号放不下时断开 phr()', 's26', {19}, ("if (c && c.classList.contains('cont') && ps.length && c.getBoundingClientRect().right > R + 0.5) ps[ps.length - 1].style.whiteSpace = 'normal';", '')),
 ('书名号整体不断行 note_breaks', 's29', {14}, ("        elif (t[i] == '《' or t[i - 1] == '》') and 0 < i < len(t) - 1:      # 书名号整体不断行、前后可以断（六级 s29：“（宫城先生是电影《龙威小子》中的空手道师父）”）\n            out.add(i)\n", '')),
 ('画面 1–6 译文弯引号照常挤压 zh_html', 's01', {10}, ("if gloss or not wenkai else", 'if gloss else')),
 ('横向出界 .pr 放宽（撤掉 = 误报，s55；原 s38 第 8 句在正文加粗、审阅修正后不再触发）', 's55', {6}, ('pg.evaluate(HBOX)', 'pg.evaluate(TH.HBOX)')),
 ('横向出界 .pr 放宽（撤掉 = 误报，s54）', 's54', {21}, ('pg.evaluate(HBOX)', 'pg.evaluate(TH.HBOX)')),
]
MINES = [  # 名称, 篇目, 句号, 埋雷 JS, 必须报出的检查
 ('短语断开例外：去掉续接号后同一短语必须报', 's26', {19}, "() => { const c = document.querySelector('.en > .cont:last-child'); if (c) c.remove(); }", '短语断开'),
 ('标题：普通换行（不是 br.tb）必须报', 's06', {0}, "() => { const b = document.querySelector('.ttl h1 br.tb'); if (b) b.className = ''; }", '标题'),
 ('标题：br.tb 之外又换行（三行）必须报', 's06', {0}, "() => { const h = document.querySelector('.ttl h1'); h.append(document.createElement('br'), '多一行'); }", '标题'),
 ('连字符例外：放得下的连字符词在连字符处断开必须报', 's20', {14}, "() => { const w = document.createTreeWalker(document.querySelector('.en'), NodeFilter.SHOW_TEXT); for (let n; (n = w.nextNode());) { const i = n.data.indexOf('left-'); if (i >= 0) { n.splitText(i + 5).before(document.createElement('br')); return; } } }", '连字符'),
 ('连字符例外：词条里的短连字符词断开必须报', 's10', {21}, "() => { const w = document.createTreeWalker(document.querySelector('.en'), NodeFilter.SHOW_TEXT); for (let n; (n = w.nextNode());) { const i = n.data.indexOf('you-'); if (i >= 0) { n.splitText(i + 4).before(document.createElement('br')); return; } } }", ''),
 ('.pr 放宽：标点真伸出去（右移 60px）必须报', 's38', {8}, "() => { for (const e of document.querySelectorAll('.pr')) e.style.cssText += ';position:relative;left:60px'; }", '横向出界'),
 ('.pr 放宽：标点真伸出去（右移 60px，s54）必须报', 's54', {21}, "() => { for (const e of document.querySelectorAll('.pr')) e.style.cssText += ';position:relative;left:60px'; }", '横向出界'),
]

from playwright.sync_api import sync_playwright
cur = build()
fails = []
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': cur.W, 'height': cur.H}, device_scale_factor=2)
    f = Path(td) / 'x.html'
    for name, pid, ks, (old, new) in CASES:
        a = run(pg, f, build(old, new), pid, ks)
        b = run(pg, f, cur, pid, ks)
        ok = len(a) > 0 and len(b) == 0
        print(f'{"OK " if ok else "BAD"} {name}：撤掉修正 {len(a)} 处，现在 {len(b)} 处', flush=True)
        for x in a[:3]: print('     撤掉：', x[:200])
        for x in b[:3]: print('     现在：', x[:200])
        ok or fails.append(name)
    for name, pid, ks, js, want in MINES:
        a = run(pg, f, cur, pid, ks, mine=js, want=want or None)
        ok = len(a) > 0
        print(f'{"OK " if ok else "BAD"} 埋雷 {name}：报出 {len(a)} 处', flush=True)
        for x in a[:2]: print('     ', x[:200])
        ok or fails.append(name)
    br.close()
print('全部双向通过' if not fails else f'没通过：{fails}')
sys.exit(1 if fails else 0)
