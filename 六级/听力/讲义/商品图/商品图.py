"""六级听力讲义套装 小店商品图（1:1，2000×2000）。老师 2026-11-04：第 1 张 = 商品总图，展示卖的所有文件（含六级历年真题原卷）。

    python3 六级/听力/讲义/商品图/商品图.py           # 先 build 讲义（成品/ 里 6 个 PDF），再出图到 成品/
    python3 六级/听力/讲义/商品图/商品图.py --自检    # 双向验证：字号×0.5 报缩略图字高、禁用词、编号都要报

沿用 六级作文/讲义/商品图/ 的做法：图上全是讲义真实页面（从成品 PDF 渲染）；数字（套数、题数、页数、组数、词数）程序现算；
不印“02 / 09”编号（踩坑 70）；不用绝对化用语、不写价格销量纸质（BANNED）；检查 CHECK_JS（出画、重叠、文字压图、编号、缩略图字号、字体）
直接从 六级作文 商品图.py 读出来用（规则只写一处）；中文走讲义 esc + WRAP_JS 断行检查。
历年真题原卷：老师手里有，商品总图上只列这一项（卡片 + 文字，不放扫描页、不编页数）。"""
import ast
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
T = HERE.parent / 'tools'
PDF = HERE.parent / '成品'
WORK = HERE / 'work'
OUT = HERE / '成品'
sys.path.insert(0, str(T))
import 讲义 as K  # noqa: E402
M, J = K.M, K.J


def _load(name, f):
    s = importlib.util.spec_from_file_location(name, f)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


L = _load('cet6_cover', REPO / '六级/封面/系列封面.py')
_src = (REPO / '六级作文/讲义/商品图/商品图.py').read_text('utf-8')
_lit = {t.id: n.value.value for n in ast.parse(_src).body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
        for t in n.targets if isinstance(t, ast.Name)}
CHECK_JS = _lit['CHECK_JS']
# 书名等 .fit 元素的文字不许超出所在的书（封面）边框（2026-11-04：书名溢出封面，原检查没管）
FIT_JS = r'''() => { const out = [];
  document.querySelectorAll('.fit').forEach(e => { const p = e.parentElement.getBoundingClientRect(), r = document.createRange();
    r.selectNodeContents(e); for (const b of r.getClientRects()) if (b.width && (b.left < p.left - 0.5 || b.right > p.right + 0.5 || b.top < p.top - 0.5 || b.bottom > p.bottom + 0.5)) {
      out.push('文字超出封面：' + e.textContent.slice(0, 12)); break; } });
  return out; }'''
BANNED = ast.literal_eval(re.search(r'^BANNED = (\[.*\])$', _src, re.M).group(1))
esc = J.esc

INK, INK2, MUTE, BLUE, BERRY, GREEN = '#1f2537', '#3d4458', '#6b7287', '#2456a6', '#c0185a', '#2e7d4f'
HY, PAPER, KY = '#ffe46b', '#faf8f3', '#ff4a12'
YEL, RED, HOT = L.YEL, '#ff6b6b', L.HOT
MIN_TITLE, MIN_HOOK, MIN_SELL = 24, 13, 10
KK = 1.0

# ---------------------------------------------------------------- 数字（现算）
SETS = M.SETS
NS = len(SETS)
NQ = sum(len(M.load(s)['questions']) for s in SETS)
Y0, Y1 = M.V[SETS[-1]]['year'], M.V[SETS[0]]['year']
NEWEST = f"{M.V[SETS[0]]['year']}"
EXAMS = len({(M.V[s]['year'], M.V[s]['month']) for s in SETS})
SYN = K.syn_rows(SETS) if all((K.JC.J / f'{s}.json').exists() for s in SETS) else {}
NSYN = sum(len(v) for v in SYN.values())
VS = K.vocab_stats()
NV = sum(1 for e in VS.values() if len(e['sets']) >= 3)
TIER = [sum(1 for e in VS.values() if lo <= len(e['sets']) <= hi) for _, lo, hi in K.TIERS]
NB = sum(1 for s in SETS for g in M.load(s)['groups'] for b in K.blanks(g['sents'], K._zipf()) if b)
BOOK = ['#ffe46b', '#ffb4cf', '#a8e6c8', '#bcd4ff', '#ffd2a8', '#f4f1e8']
BOOKT = [('听力真题', f'{NS}套精讲'), ('同义替换', '手册'), ('高频词', '手册'), ('听写本',), ('听写本', '答案'), ('30天', '刷题计划')]  # 封面书名分行，放进书里（FIT_JS 查）
FILES = [('main', '真题 30 套精讲'), ('syn', '同义替换手册'), ('vocab', '高频词手册'), ('dict', '听写本'), ('dans', '听写本答案'), ('plan', '30 天刷题计划')]


def npages(key):
    f = PDF / f'{K.NAMES[key]}.pdf'
    return int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', str(f)], capture_output=True, text=True).stdout).group(1))


PG = {k: npages(k) for k, _ in FILES}
TOTAL = sum(PG.values())


def find_page(key, text, start=1):
    """PDF 里第一个含这段文字的页（素材按内容找页，不写死页码）。"""
    f = PDF / f'{K.NAMES[key]}.pdf'
    for i in range(start, PG[key] + 1):
        t = subprocess.run(['pdftotext', '-f', str(i), '-l', str(i), str(f), '-'], capture_output=True, text=True).stdout
        if re.sub(r'\s+', '', text) in re.sub(r'\s+', '', t):
            return i
    raise SystemExit(f'{f.name} 里找不到“{text}”')


def shot(key, page, name, r=110):
    WORK.mkdir(exist_ok=True)
    out = WORK / name
    subprocess.run(['pdftoppm', '-r', str(r), '-f', str(page), '-l', str(page), '-png', '-singlefile', str(PDF / f'{K.NAMES[key]}.pdf'), str(out)], check=True)
    return (WORK / f'{name}.png').as_uri()


def fs(n):
    return f'{n * KK:.0f}px'


PAPER_CSS = f"""
@font-face{{font-family:Black;src:url({L.F_BLACK.as_uri()})}}
@font-face{{font-family:Bold;src:url({L.F_BOLD.as_uri()})}}
@font-face{{font-family:Inter;font-weight:800;src:url({L.F_INTER.as_uri()})}}
*{{margin:0;padding:0;box-sizing:border-box}}
x-nb{{white-space:nowrap}}
html,body{{width:1000px;height:1000px;overflow:hidden}}
body{{position:relative;font-family:Bold,sans-serif;color:{INK};background:{PAPER}}}
.dots{{position:absolute;inset:0;background:radial-gradient(circle at 1.5px 1.5px,rgba(70,92,128,.16) 1.3px,transparent 1.8px) 12px 12px/26px 26px}}
.ab{{position:absolute;white-space:nowrap}}
.lat{{font-family:Inter,Black,sans-serif;font-weight:800}}
.hy{{box-shadow:inset 0 -.44em 0 {HY};border-radius:.06em;padding:0 .04em}}
.h1{{font:900 54px/1.18 Black;color:{INK}}}
.sub{{font:700 26px/1.4 Bold;color:{INK2}}}
.top{{font:900 21px/1 Black;color:#fff;background:{BLUE};padding:9px 20px 10px;border-radius:999px;letter-spacing:.06em}}
.page{{position:absolute;background:#fff;box-shadow:0 3px 0 rgba(31,37,55,.06),0 18px 40px rgba(31,37,55,.24);border-radius:4px;overflow:hidden}}
.page img{{display:block;width:100%}}
.tag{{position:absolute;white-space:nowrap;font:900 22px/1 Black;color:#fff;padding:9px 16px 10px;border-radius:12px;box-shadow:0 5px 14px rgba(31,37,55,.22)}}
.pt{{font:700 23px/1.5 Bold;color:{INK2};white-space:normal}}.pt b{{color:{BLUE}}}
.pt div{{display:flex;margin-bottom:8px}}.pt div::before{{content:'✓';flex:none;color:{GREEN};font:900 22px/1.5 Black;margin-right:9px}}
"""
BOARD_CSS = L.css(1000, 1000) + """
x-nb{white-space:nowrap}
.page{position:absolute;background:#fff;box-shadow:8px 10px 0 rgba(0,0,0,.40),0 0 30px rgba(0,0,0,.35);border-radius:3px;overflow:hidden}
.page img{display:block;width:100%}
"""


def head(title, sub, y=44):
    return (f'<div class="ab" style="left:50px;top:{y}px"><span class="top">朋克英语 出品 · 六级听力真题 30 套精讲 · 全套讲义</span></div>'
            f'<div class="ab h1" data-k="h1" style="left:48px;top:{y + 50}px">{title}</div>'
            + (f'<div class="ab sub" data-k="sub" style="left:50px;top:{y + 122}px">{sub}</div>' if sub else ''))


def pts(x, y, w, items, k='pts'):
    return f'<div class="ab pt" data-k="{k}" style="left:{x}px;top:{y}px;width:{w}px">' + ''.join(f'<div><span>{t if "<" in t else esc(t)}</span></div>' for t in items) + '</div>'


def page(src, x, y, w, rot=0, crop=None):
    """crop=(上, 高) 按页面宽度的比例裁一段（只看页面的一部分）。"""
    if crop:
        top, h = crop
        return (f'<div class="page" style="left:{x}px;top:{y}px;width:{w}px;height:{w * h:.0f}px;transform:rotate({rot}deg)">'
                f'<img src="{src}" style="margin-top:-{w * top:.0f}px"></div>')
    return f'<div class="page" style="left:{x}px;top:{y}px;width:{w}px;transform:rotate({rot}deg)"><img src="{src}"></div>'


def tag(k, x, y, text, bg, ink='#fff', rot=0):
    return f'<div class="tag" data-k="{k}" style="left:{x}px;top:{y}px;background:{bg};color:{ink};transform:rotate({rot}deg)">{text}</div>'


def band(y, text):
    return (f'<div class="ab" data-k="band" style="left:40px;top:{y}px;width:920px;text-align:center;font:900 27px/1 Black;color:#fff;'
            f'background:{BLUE};padding:18px 0 20px;border-radius:16px">{text}</div>')


# ---------------------------------------------------------------- 01 商品总图（黑板）
def p_all():
    cards = ''
    for i, (k, name) in enumerate(FILES + [('paper', '六级历年真题原卷')]):
        col, row = i % 4, i // 4
        x, y = 44 + col * 232, 278 + row * 306
        if k == 'paper':
            pic = (f'<div class="ab" style="left:{x + 34}px;top:{y}px;width:150px;height:212px;background:#fbf8ef;border-radius:3px;'
                   f'box-shadow:8px 10px 0 rgba(0,0,0,.4);display:flex;flex-direction:column;align-items:center;justify-content:center;color:{INK}">'
                   f'<div data-k="pp" style="font:900 30px/1.25 Black;text-align:center">历年<br>真题<br>原卷</div>'
                   f'<div class="lat" style="font-size:18px;margin-top:10px;color:{BERRY}">CET-6</div></div>')
            sub = '原卷 PDF'
        else:
            pic = (f'<div class="ab" style="left:{x + 24}px;top:{y}px;width:170px;height:212px;background:{BOOK[i]};border-radius:4px 10px 10px 4px;'
                   f'box-shadow:8px 10px 0 rgba(0,0,0,.4);transform:rotate({(-3, 2, -2, 3, -2, 2)[i]}deg);border-left:12px solid rgba(0,0,0,.22);'
                   f'display:flex;flex-direction:column;justify-content:center;padding:0 12px;color:{INK}">'
                   f'<div class="lat" style="font-size:15px;letter-spacing:.12em;color:{INK2}">CET-6</div>'
                   f'<div class="fit" style="font:900 31px/1.2 Black;margin-top:6px;white-space:nowrap">{"<br>".join(esc(t) for t in BOOKT[i])}</div></div>')
            sub = f'<span class="lat">{PG[k]}</span> 页'
        cards += (pic + f'<div class="ab ck" data-k="c{i}" style="left:{x}px;top:{y + 226}px;width:218px;text-align:center;font:900 24px/1.25 Black">{esc(name)}</div>'
                  f'<div class="ab" data-k="s{i}" style="left:{x}px;top:{y + 262}px;width:218px;text-align:center;font:700 20px/1 Bold;color:{YEL}">{sub}</div>')
    return f"""<body>{L.SVG_DEFS}<div class="board"></div><div class="grain"></div>{L.dust(1000, 1000)}
<div class="ab ck" data-k="six" data-min="{MIN_TITLE}" style="left:50px;top:52px;font:900 {fs(74)}/1.1 Black"><span style="color:{HOT}">六级</span>听力 真题<span style="color:{YEL}">{NS}</span>套</div>
<div class="ab ck" data-k="hook" data-min="{MIN_HOOK}" style="left:54px;top:148px;font:900 {fs(40)}/1.2 Black">全套讲义 · 每道题都讲透</div>
<div class="ab ck" data-k="list" data-min="{MIN_SELL}" style="left:54px;top:214px;font:700 {fs(25)}/1.2 Bold;color:#e9efe9">这一套里有 <span style="color:{YEL}">{len(FILES) + 1}</span> 样东西：</div>
<div class="ab ck" data-k="brand" data-min="{MIN_SELL}" style="right:56px;top:214px;font:900 {fs(25)}/1.2 Black;color:{YEL}">朋克英语 出品</div>
<div class="ab" data-k="seal" data-min="{MIN_SELL}" style="left:790px;top:40px;width:160px;height:160px;transform:rotate(8deg);display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.05;color:#fff">
<i style="position:absolute;inset:0;border-radius:50%;background:{RED};filter:url(#rough);box-shadow:0 8px 0 rgba(0,0,0,.3)"></i>
<i style="position:absolute;inset:10px;border-radius:50%;border:4px dashed rgba(255,255,255,.75)"></i>
<span class="lat ck" style="position:relative;font-size:{fs(40)}">{NEWEST}</span><span class="ck" style="position:relative;font:900 {fs(38)}/1.15 Black">已更新</span></div>
{cards}
<div class="ab ck" data-k="sell" data-min="{MIN_SELL}" style="left:50%;transform:translateX(-50%);top:902px;font:900 {fs(28)}/1.2 Black">
<span style="color:{YEL}">{Y1}—{Y0}</span> · {EXAMS} 次考试 · {NQ} 道题 · PDF 讲义共 <span style="color:{YEL}">{TOTAL}</span> 页</div>
{L.frame(1000, 1000)}</body>"""


# ---------------------------------------------------------------- 介绍图（纸面）
def p_q():
    src = shot('main', find_page('main', '思路'), '精讲页')
    return f"""<body><div class="dots"></div>{head('每道题都讲透：<span class="hy">从哪句来、为什么</span>', f'{NQ} 道题，每题四个板块，基础弱也跟得上')}
{page(src, 52, 250, 500, rot=-1.5, crop=(0.02, 0.98))}
{tag('t1', 520, 300, '答案依据：原文哪一句', BLUE)}{tag('t2', 520, 360, '思路：先依据、后结论', GREEN)}
{tag('t3', 520, 420, '同义替换：换了什么说法', '#b7791f')}{tag('t4', 520, 480, '错项排除：属于哪种陷阱', BERRY)}
{pts(600, 560, 360, [f'答案依据<b>逐字</b>引用原文，在原文里黄色标出', '四个选项都配中文翻译', '每个错误选项都点明错在哪', '答案逐题双重核对'])}
</body>"""


def p_text():
    src = shot('main', find_page('main', 'LISTENING SET 01'), '原文页')
    return f"""<body><div class="dots"></div>{head('原文<span class="hy">逐句英汉对照</span>', '黄色 = 答案出处，右上角就是题号')}
{page(src, 330, 230, 600, rot=1.2, crop=(0, 1.2))}
{pts(52, 280, 260, ['长对话、短文、讲座全部原文', '每句英文下面一句中文', '本套 25 题答案速查', '本套内容一段话概括', '本套高频词，标出 30 套里考过几套'])}
</body>"""


def p_syn():
    src = shot('syn', find_page('syn', 'SYNONYM 01'), '替换页')
    rows = ''.join(f'<div><span>{esc(t)}：<b class="lat">{len(SYN.get(t, []))}</b> 组</span></div>' for t in K.JC.TYPES)
    return f"""<body><div class="dots"></div>{head(f'同义替换手册：<span class="hy">{NSYN} 组</span>', '听懂“换说法”，就听懂了六级听力的出题规律')}
{page(src, 420, 240, 520, rot=1.5, crop=(0, 1.15))}
<div class="ab pt" data-k="pts" style="left:52px;top:290px;width:340px">{rows}</div>
<div class="ab pt" data-k="note" style="left:52px;top:600px;width:340px;font-size:21px;color:{MUTE}">正确选项的说法 ⇄ 原文的说法，按五种类型分组，每组标出处（哪一年、哪一套、第几题）</div>
</body>"""


def p_vocab():
    src = shot('vocab', find_page('vocab', 'WORDS · TIER 1'), '词页')
    t = ''.join(f'<div><span>{n}词：<b class="lat">{c}</b> 个</span></div>' for (n, _, _), c in zip(K.TIERS, TIER))
    return f"""<body><div class="dots"></div>{head(f'高频词手册：<span class="hy">{NV} 个</span>词条', f'{NS} 套真题原文逐词统计，按考到的套数排序')}
{page(src, 420, 240, 520, rot=1.5, crop=(0, 1.15))}
<div class="ab pt" data-k="pts" style="left:52px;top:290px;width:340px">{t}</div>
<div class="ab pt" data-k="note" style="left:52px;top:520px;width:340px;font-size:21px;color:{MUTE}">每个词标出 30 套里考到几套、出现在哪几篇，回到原文就能听到它</div>
</body>"""


def p_dict():
    a = shot('dict', find_page('dict', 'DICTATION'), '听写页')
    b = shot('dans', find_page('dans', 'DICTATION'), '答案页')
    return f"""<body><div class="dots"></div>{head(f'听写本 + 答案：<span class="hy">{NB} 个空</span>', '每句挖出一个关键词，边听边写，写完马上对答案')}
{page(a, 60, 250, 470, rot=-2, crop=(0, 1.2))}{page(b, 520, 300, 420, rot=2.5, crop=(0, 1.2))}
{tag('t1', 70, 228, '听写本', BLUE, rot=-3)}{tag('t2', 760, 276, '答案本', BERRY, rot=3)}
</body>"""


def p_plan():
    src = shot('plan', 1, '计划页')
    return f"""<body><div class="dots"></div>{head('<span class="hy">30 天</span>刷题计划', '每天一套，五项任务做完一项勾一项')}
{page(src, 330, 230, 600, rot=1, crop=(0, 1.25))}
{pts(52, 290, 250, ['完整做一遍', '看精讲', '听写', '背高频词', '复听错题', '写下每天做对几题', '页码直接对到精讲'])}
</body>"""


def p_toc():
    src = shot('main', 2, '目录页')
    return f"""<body><div class="dots"></div>{head('目录<span class="hy">一点就跳</span>', '书签随时跳转，读完一套打个勾')}
{page(src, 330, 230, 600, rot=1, crop=(0, 1.2))}
{pts(52, 290, 250, ['点目录里任意一套，直接跳到那一页', '阅读器侧边栏有书签', '“已读”方框可以打勾保存，下次打开知道读到哪'])}
</body>"""


def p_sets():
    by = {}
    for s in SETS:
        by.setdefault(M.V[s]['year'], []).append(s)
    rows = ''.join(f'<div class="ab" data-k="y{y}" style="left:{60 + (i % 2) * 450}px;top:{250 + (i // 2) * 128}px;width:420px;font:900 30px/1.2 Black">'
                   f'<span class="lat" style="color:{BLUE}">{y}</span> 年 <span style="font:700 22px/1.4 Bold;color:{INK2};display:block">'
                   + ' · '.join(f'{"上半年" if m <= 6 else "下半年"} {n} 套' for m, n in sorted({M.V[s]['month']: sum(M.V[t]['month'] == M.V[s]['month'] for t in by[y]) for s in by[y]}.items(), reverse=True)) + '</span></div>'
                   for i, y in enumerate(sorted(by, reverse=True)))
    return f"""<body><div class="dots"></div>{head(f'{Y1}—{Y0} 共 <span class="hy">{NS} 套</span>真题', f'{EXAMS} 次考试，{NQ} 道题，新的在前')}
{rows}{band(900, f'{NS} 套 · {NQ} 题 · 每一题都有答案依据、思路、同义替换、错项排除')}
</body>"""


PAGES = [('01_商品总图', p_all, True), ('02_每题讲透', p_q, False), ('03_原文逐句对照', p_text, False), ('04_同义替换手册', p_syn, False),
         ('05_高频词手册', p_vocab, False), ('06_听写本', p_dict, False), ('07_30天刷题计划', p_plan, False), ('08_目录书签已读', p_toc, False),
         ('09_30套全收录', p_sets, False)]


YEAR_BAD = re.compile(r'(20\d\d)\s*[—-]\s*(20\d\d)|20\d\d\.\d{1,2}(?!\d)|20\d\d\s*年\s*\d{1,2}\s*月')


def year_problems(t):
    """老师定：年份写 2026—2018（新的在前），不写月份（“2026.6”“2026年6月”都不行）。"""
    out = []
    for m in YEAR_BAD.finditer(t):
        if m.group(1) and int(m.group(1)) > int(m.group(2)):
            continue
        out.append(f'年份写法「{m.group(0)}」：要写 2026—2018、不写月份')
    return out


def banned(text):
    t = re.sub(r'<[^>]+>', '', text)
    return [w for w in BANNED if w in t] + year_problems(t)


def render(br, name, body, board, out=True):
    WORK.mkdir(exist_ok=True)
    f = WORK / f'{name}.html'
    f.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{BOARD_CSS if board else PAPER_CSS}</style></head>{body}</html>', 'utf-8')
    pg = br.new_page(viewport={'width': 1000, 'height': 1000}, device_scale_factor=2)
    pg.goto(f.as_uri())
    pg.evaluate('document.fonts.ready.then(() => [...document.fonts].forEach(f => f.load()))')
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(500)
    bad = pg.evaluate(CHECK_JS, board) + pg.evaluate(FIT_JS) + pg.evaluate(J.WRAP_JS) + [f'禁用词「{w}」' for w in banned(body)]
    png = WORK / f'{name}.png'
    pg.screenshot(path=str(png))
    pg.close()
    im = Image.open(png).convert('RGB')
    assert im.size == (2000, 2000), im.size
    if out:
        OUT.mkdir(exist_ok=True)
        im.save(OUT / f'{name}.jpg', quality=92, optimize=True, progressive=True)
    im.resize((400, 400), Image.LANCZOS).save(WORK / f'{name}_400.png')
    return [f'{name}: {x}' for x in bad]


def selftest(br):
    global KK
    bad = []
    for kk in (1.0, 0.5):
        KK = kk
        body = p_all()
        res = render(br, f'自检_{kk}', body, True, out=False)
        hit = {x.split(': ')[1].split()[0] for x in res if '缩略图字高' in x}
        need = set(re.findall(r'data-k="(\w+)" data-min=', body)) if kk < 1 else set()
        if hit != need:
            bad.append(f'字号×{kk}：报出 {sorted(hit)}，应为 {sorted(need)}')
    KK = 1.0
    res = render(br, '自检_编号', p_sets().replace('</body>', '<div class="ab" data-k="zz" style="left:400px;top:960px">02 / 09</div></body>'), False, out=False)
    if not any('页码式编号' in x for x in res):
        bad.append('“02 / 09”编号没报出')
    res = render(br, '自检_溢出', p_all().replace('white-space:nowrap">', 'white-space:nowrap">很长很长很长的书名', 1), True, out=False)
    if not any('文字超出封面' in x for x in res):
        bad.append('书名溢出封面没报出')
    if not year_problems('2018—2026') or not year_problems('2026.6 已更新') or year_problems('2026—2018 · 2026 已更新'):
        bad.append('年份写法检查失效')
    if banned('全网第一 保过') != ['第一', '保过']:
        bad.append('禁用词检查失效')
    return bad


def main(a):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        if a[:1] == ['--自检']:
            bad = selftest(br)
            print('\n'.join(bad) or '自检通过：字号×0.5 时 data-min 元素全部报出、正常不报；编号、禁用词都报出')
            return 1 if bad else 0
        for old in OUT.glob('*.jpg'):
            old.unlink()
        bad = []
        for name, fn, board in PAGES:
            bad += render(br, name, fn(), board)
        br.close()
    if bad:
        print('自查不通过：\n  ' + '\n  '.join(bad))
        return 1
    print(f'{len(PAGES)} 张商品图自查通过 → {OUT}；套装共 {TOTAL} 页：' + '，'.join(f'{n} {PG[k]} 页' for k, n in FILES))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
