"""六级英语写作讲义 B 站小店商品图（1:1，2000×2000，主图 + 12 张介绍图）。

    python3 六级作文/讲义/商品图/素材.py            # 先画素材（真实内页元素、封面、目录、内页）
    python3 六级作文/讲义/商品图/商品图.py 草稿     # 主图 3 个方向 M1/M2/M3，只出 400×400 缩略图到 work/ 挑定稿
    python3 六级作文/讲义/商品图/商品图.py          # 全部成品（主图用 MAIN 指定的方向；没选上的方向出到 成品/备选/）
    python3 六级作文/讲义/商品图/商品图.py --自检   # 双向验证：主图字号×0.5 时每个 data-min 元素都要报，正常字号 0 处

用户要求（2026-10-26）：讲义要上 B 站小店卖；封面让人看了就想买；第一张主图要非常吸引人，展示讲义里最吸引人的东西；
介绍图至少六七张，说明这套讲义能帮学生搞定写作。沿用 考研作文/讲义/商品图/ 的做法和原则：
· 图上全部是讲义里的真实内容（用讲义自己的排版程序渲染的元素和 PDF 内页），不做假图；
· 每个数字都从数据现算（篇数、页数、句式、例句、升格、默写……），并断言，数据一改就停下核对图上的说法；
· 不印“02 / 09”这类编号（踩坑 70）；图上中文走讲义的 esc（末两字不分开、数字与单位不分开），并跑讲义的 WRAP_JS 断行检查；
· 合规：不用绝对化用语（最、第一、100%、保过、必过……），不写纸质版、价格、销量（程序检查 BANNED）；
· 主图在小店列表里会缩到 400×400：data-min 元素缩小后最小字号不低于下限（主标题 24、钩子 13、卖点 10 像素，同 专八/封面/系列封面.py）。
渲染后程序自查：文字不出画、互不重叠、截图不出画、图片和字体全部加载。
"""
import glob
import importlib.util
import json
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]                      # 六级作文/
REPO = C.parent
S = HERE / 'work' / '素材'
WORK = HERE / 'work'
OUT = HERE / '成品'
ALT_DIR = OUT / '备选'
MAIN = 'M2'                              # 定稿的主图方向（草稿缩略图挑定后写在这里）
sys.path.insert(0, str(REPO / 'tools'))
import 作文规则  # noqa: E402


def load(name, f):
    spec = importlib.util.spec_from_file_location(name, f)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


J = load('jy6', C / 'tools' / '讲义.py')          # 讲义排版程序：esc、WRAP_JS
L = load('cet6_cover', REPO / '六级/封面/系列封面.py')   # 黑板主题（与 B 站封面同一系列）
zx = J.esc
WRAP_JS = J.WRAP_JS

# ---------------------------------------------------------------- 数字（从讲义数据现算）
D = [json.loads(open(f, encoding='utf-8').read()) for f in sorted(glob.glob(str(C / '讲义/data/c*.json')))]
SP = {p['id']: p for p in json.loads((C / '作文/sents.json').read_text('utf-8'))}
VP = {p['id']: p for p in json.loads((C / 'data/vocab.json').read_text('utf-8'))['passages']}
G = json.loads((C / '讲义/data/总论.json').read_text('utf-8'))
N = len(D)
PAT = sum(len(d['句式']) for d in D)
EX = sum(len(x['例句']) for d in D for x in d['句式'])
ALT = sum(len(x['替换']) for d in D for x in d['句式'])
VOC = sum(len(d['词汇']) for d in D)
DIC = sum(len(d['默写']) for d in D)
STEP = sum(len(d['步骤']) for d in D)
REQ = sum(len(d['要求']) for d in D)
UP = sum(len(d['升格']) for d in D)
BAD = sum(len(b['行']) for s in G['小节'] for b in s['内容'] if b['类'] == '对照')
ES = [e for y in range(2015, 2100) if (REPO / f'六级/作文/{y}.json').exists() for e in json.loads((REPO / f'六级/作文/{y}.json').read_text('utf-8'))]
WC = [作文规则.counted(e) for e in ES]
EXAMS = OrderedDict()
for p in sorted(SP.values(), key=lambda p: (-int(p['year']), -int(p['month']), int(p['set']))):
    EXAMS.setdefault((int(p['year']), int(p['month'])), []).append(p)
Y0, Y1 = min(y for y, _ in EXAMS), max(y for y, _ in EXAMS)
NEWEST = '{}.{}'.format(*max(EXAMS))


def pages(f):
    return int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', str(f)], capture_output=True, text=True).stdout).group(1))


PG = {'讲义': pages(J.OUT_HANDOUT), '默写卡': pages(J.OUT_CARDS), '答案': pages(J.OUT_ANS)}
TOTAL = sum(PG.values())
SEC = 10                                                  # 每篇的小节数（讲义.py essay_chapter 的 sec(1…10)）
assert len(re.findall(r"sec\((\d+), '", (C / 'tools/讲义.py').read_text('utf-8'))) == SEC
assert (N, PAT, EX, ALT, VOC, DIC, STEP, REQ, UP, BAD) == (31, 201, 402, 403, 310, 212, 212, 205, 93, 7), (N, PAT, EX, ALT, VOC, DIC, STEP, REQ, UP, BAD)
assert all(len(x['例句']) == 2 for d in D for x in d['句式'])           # “每个句式 2 个仿写例句”
assert all(len(d['升格']) == 3 for d in D)                             # “每篇 3 组升格”
assert (min(WC), max(WC), len(EXAMS), Y0, Y1, NEWEST) == (190, 200, 11, 2021, 2026, '2026.6'), (min(WC), max(WC), len(EXAMS), Y0, Y1, NEWEST)
assert PG == {'讲义': 361, '默写卡': 96, '答案': 49}, PG                # 数据或排版一改就停下，先核对图上的说法
CHAP = json.loads((S / '章页数.json').read_text('utf-8'))['pages']     # c01 一章的页数（素材.py 量的）

INK, INK2, MUTE, BLUE, BERRY, GREEN = '#1f2537', '#3d4458', '#6b7287', '#2456a6', '#c0185a', '#2e7d4f'
HY, HP, PAPER, KY = '#ffe46b', '#ffc4d8', '#faf8f3', '#ff4a12'
YEL, RED, CHALK, HOT = L.YEL, '#ff6b6b', L.CHALK, L.HOT
MIN_TITLE, MIN_HOOK, MIN_SELL = 24, 13, 10      # 缩到 400×400 后的最小字高（像素）
K = 1.0                                         # 字号系数：只给 --自检 用
# 广告法绝对化用语 + 讲义没有的东西（纸质版、价格、销量）：图上、标题、描述里一律不许出现
BANNED = ['最', '第一', '顶级', '100%', '百分百', '保过', '必过', '包过', '提分保证', '保证提分', '纸质', '包邮', '销量', '好评', '¥', '元/']


def img(name):
    return (S / name).as_uri()


def fs(n):
    return f'{n * K:.0f}px'


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
.hp{{box-shadow:inset 0 -.44em 0 {HP};border-radius:.06em;padding:0 .04em}}
.h1{{font:900 56px/1.18 Black;color:{INK}}}
.sub{{font:700 26px/1.4 Bold;color:{INK2}}}
.top{{font:900 21px/1 Black;color:#fff;background:{BLUE};padding:9px 20px 10px;border-radius:999px;letter-spacing:.06em}}
.shot{{position:absolute;background:#fff;border-radius:14px;box-shadow:0 2px 0 rgba(31,37,55,.06),0 14px 34px rgba(31,37,55,.16);overflow:hidden}}
.shot img{{display:block;width:100%}}
.tag{{position:absolute;white-space:nowrap;font:900 22px/1 Black;color:#fff;padding:9px 16px 10px;border-radius:12px;box-shadow:0 5px 14px rgba(31,37,55,.22)}}
.tb{{background:{BLUE}}}.tr{{background:{BERRY}}}.tg{{background:{GREEN}}}.tk{{background:{KY}}}
.dot{{display:inline-block;width:34px;height:34px;border-radius:50%;background:{BERRY};color:#fff;font:800 20px/34px Inter;text-align:center}}
.page{{position:absolute;background:#fff;box-shadow:0 3px 0 rgba(31,37,55,.06),0 18px 40px rgba(31,37,55,.24);border-radius:4px}}
.page img{{display:block;width:100%;border-radius:4px}}
"""

BOARD_CSS = L.css(1000, 1000) + """
x-nb{white-space:nowrap}
.page{position:absolute;background:#fff;box-shadow:10px 14px 0 rgba(0,0,0,.40),0 0 36px rgba(0,0,0,.35);border-radius:3px}
.page img{display:block;width:100%;border-radius:3px}
.shot{position:absolute;background:#fff;border-radius:10px;border:8px solid #fbf8ef;box-shadow:10px 14px 0 rgba(0,0,0,.42),0 0 36px rgba(0,0,0,.3);overflow:hidden}
.shot img{display:block;width:100%}
.tag{position:absolute;white-space:nowrap;font:900 26px/1 Black;padding:10px 18px 12px;border-radius:12px;box-shadow:0 6px 0 rgba(0,0,0,.3)}
"""


def head(title, sub, y=46):
    # 不加“02 / 09”这类编号（踩坑 70）
    return (f'<div class="ab" style="left:50px;top:{y}px"><span class="top">六级英语写作满分范文精讲</span></div>'
            f'<div class="ab h1" data-k="h1" style="left:48px;top:{y + 52}px">{title}</div>'
            + (f'<div class="ab sub" data-k="sub" style="left:50px;top:{y + 126}px">{sub}</div>' if sub else ''))


def y_(t):
    return f'<span style="color:{YEL}">{t}</span>'


# ---------------------------------------------------------------- 主图（黑板主题，与 B 站封面同一系列）
def seal(x, y, d, rot=8):
    return (f'<div class="ab" data-k="seal" data-min="{MIN_SELL}" style="left:{x}px;top:{y}px;width:{d}px;height:{d}px;transform:rotate({rot}deg);'
            f'display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.05;color:#fff">'
            f'<i style="position:absolute;inset:0;border-radius:50%;background:{RED};filter:url(#rough);box-shadow:0 8px 0 rgba(0,0,0,.3)"></i>'
            f'<i style="position:absolute;inset:{d * .06:.0f}px;border-radius:50%;border:4px dashed rgba(255,255,255,.75)"></i>'
            f'<span class="lat ck" style="position:relative;font-size:{fs(d * .25)}">{NEWEST}</span>'
            f'<span class="ck" style="position:relative;font:900 {fs(d * .24)}/1.15 Black">已更新</span></div>')


def underline(w, col=YEL):
    return (f'<svg width="{w}" height="22" viewBox="0 0 {w} 22" style="display:block;overflow:visible" filter="url(#line)">'
            f'<path d="M6 14 C {w * .3} 5, {w * .65} 19, {w - 6} 8" fill="none" stroke="{col}" stroke-width="8" stroke-linecap="round"/></svg>')


def title_block(x, y, six=96, zt=132, fan=86):
    """六级写作 / 真题 满分 范文：“真题”黄块、“满分”红块，与 B 站封面 A1 一致。"""
    return (f'<div class="ab ck" data-k="six" data-min="{MIN_TITLE}" style="left:{x}px;top:{y}px;font:900 {fs(six)}/1 Black">'
            f'<span style="color:{HOT}">六级</span>写作</div>'
            f'<div class="ab" data-k="zt" data-min="{MIN_TITLE}" style="left:{x + 14}px;top:{y + six + 26}px;font:900 {fs(zt)}/1.12 Black">'
            f'{L.hl("真题", YEL, px=14, extra=f"font-size:{fs(zt)}")}'
            f'{L.hl("满分", RED, ink="#fff", px=14, extra=f"font-size:{fs(zt)};margin-left:{zt * .22:.0f}px")}'
            f'<span class="ck" style="font-size:{fs(fan)};margin-left:{zt * .16:.0f}px">范文</span></div>')


def hook(x, y, size=44, text=('彻底搞定', '六级写作')):
    return (f'<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="left:{x}px;top:{y}px;font:900 {fs(size)}/1.1 Black">'
            f'<span class="ck">{text[0]}</span><span class="ck" style="color:{YEL}">{text[1]}</span>'
            f'<div style="margin-top:-2px">{underline(round(size * 8.3))}</div></div>')


def board(inner):
    return f'<body>{L.SVG_DEFS}<div class="board"></div><div class="grain"></div>{L.dust(1000, 1000)}{inner}{L.frame(1000, 1000)}</body>'


def sell(y, size=30):
    return (f'<div class="ab ck" data-k="sell" data-min="{MIN_SELL}" style="left:50%;transform:translateX(-50%);top:{y}px;font:900 {fs(size)}/1.2 Black">'
            f'{y_(f"{Y0}—{Y1}")} 全部真题 {y_(N)} 篇 · {y_(PG["讲义"])} 页精讲 + 默写卡</div>')


def M1():
    """标题 + 三份真实封面扇形摊开 + 一页真实内页（满分范文页）。"""
    return board(f"""
{hook(54, 40)}
{seal(800, 36, 160, rot=8)}
{title_block(50, 118)}
<div class="page" style="left:660px;top:452px;width:240px;transform:rotate(9deg)"><img src="{img('内页_05.png')}"></div>
<div class="page" style="left:470px;top:468px;width:226px;transform:rotate(4deg)"><img src="{img('封面_答案.png')}"></div>
<div class="page" style="left:280px;top:470px;width:226px;transform:rotate(-2deg)"><img src="{img('封面_默写卡.png')}"></div>
<div class="page" style="left:80px;top:456px;width:240px;transform:rotate(-7deg)"><img src="{img('封面_讲义.png')}"></div>
<div class="tag" data-k="g1" style="left:70px;top:416px;transform:rotate(-5deg);background:{YEL};color:{INK}">讲义 {PG['讲义']} 页</div>
<div class="tag" data-k="g2" style="left:300px;top:420px;transform:rotate(-2deg);background:#fff;color:{INK}">默写卡 {PG['默写卡']} 页 + 答案 {PG['答案']} 页</div>
<div class="tag" data-k="g3" style="left:740px;top:404px;transform:rotate(6deg);background:{RED};color:#fff">真实内页</div>
{sell(858)}""")


def M2():
    """标题 + 一大张满分范文（荧光笔 + 圆圈编号）特写，三份真实封面叠在右侧。用户要求主图展示讲义里最吸引人的东西：定稿。"""
    return board(f"""
{hook(54, 40)}
{seal(800, 36, 160, rot=8)}
{title_block(50, 118)}
<div class="shot" style="left:60px;top:450px;width:700px;height:370px;transform:rotate(-1.5deg)"><img src="{img('范文.png')}"></div>
<div class="page" style="left:790px;top:420px;width:160px;transform:rotate(9deg)"><img src="{img('封面_答案.png')}"></div>
<div class="page" style="left:770px;top:500px;width:170px;transform:rotate(4deg)"><img src="{img('封面_默写卡.png')}"></div>
<div class="page" style="left:745px;top:584px;width:180px;transform:rotate(-2deg)"><img src="{img('封面_讲义.png')}"></div>
<div class="tag" data-k="g1" style="left:70px;top:410px;transform:rotate(-3deg);background:{YEL};color:{INK}">满分范文 · 高分句式全标出</div>
{sell(858)}""")


def M3():
    """标题 + 升格示范（普通句一步步改成满分句）：讲义里最能看出“怎么变成满分”的一页。"""
    return board(f"""
{hook(54, 40)}
{seal(800, 36, 160, rot=8)}
{title_block(50, 118)}
<div class="shot" style="left:60px;top:452px;width:880px;transform:rotate(-1.2deg)"><img src="{img('升格1.png')}"></div>
<div class="tag" data-k="g1" style="left:70px;top:412px;transform:rotate(-3deg);background:{RED};color:#fff">普通句 → 满分句，一步一步改</div>
{sell(858)}""")


MAINS = {'M1': M1, 'M2': M2, 'M3': M3}


# ---------------------------------------------------------------- 商品总图：一套 3 份
def p_set():
    items = [('满分范文精讲', '讲义', ['写作总攻略 + 31 篇精讲', f'{PAT} 个高分句式', f'{UP} 组升格示范', '书末附句式总表']),
             ('作文默写卡', '默写卡', [f'{DIC} 道句式填空', f'{DIC} 句看中文默整句', '每题提醒练什么句式']),
             ('默写卡答案', '答案', ['填空答案粉色标出', '整句对照范文原句', '默完马上自己批改'])]
    cols = ''
    for i, (name, key, pts) in enumerate(items):
        x = 40 + i * 315
        li = ''.join(f'<div style="display:flex;align-items:flex-start;margin-bottom:6px"><span style="flex:none;color:{GREEN};font:900 20px/1.45 Black;margin-right:7px">✓</span><span>{zx(t)}</span></div>' for t in pts)
        inner = '内页_05.png' if key == '讲义' else f'卡页_{key}.png'
        cols += (f'<div class="page" style="left:{x + 92}px;top:262px;width:190px;transform:rotate(6deg)"><img src="{img(inner)}"></div>'
                 f'<div class="page" style="left:{x + 18}px;top:242px;width:220px;transform:rotate(-3deg)"><img src="{img(f"封面_{key}.png")}"></div>'
                 f'<div class="ab" data-k="n{i}" style="left:{x}px;top:600px;width:290px;text-align:center">'
                 f'<div style="font:900 32px/1.2 Black"><span style="color:{KY}">{"①②③"[i]}</span> {name}</div>'
                 f'<div style="margin-top:8px"><span style="display:inline-block;font:900 24px/1 Black;color:#fff;background:{KY};padding:8px 18px 9px;border-radius:999px">'
                 f'<span class="lat">{PG[key]}</span> 页</span></div></div>'
                 f'<div class="ab" data-k="l{i}" style="left:{x + 22}px;top:704px;width:270px;white-space:normal;font:700 21px/1.45 Bold;color:{INK2}">{li}</div>')
    return f"""<body><div class="dots"></div>{head('这套资料一共 <span class="hy">3 份</span>', f'PDF 电子讲义，共 {TOTAL} 页：学、练、查一次备齐')}
{cols}
<div class="ab" data-k="band" style="left:40px;top:900px;width:920px;text-align:center;font:900 27px/1 Black;color:#fff;background:{BLUE};padding:18px 0 20px;border-radius:16px">
<span class="lat">{Y0}—{Y1}</span> · {len(EXAMS)} 次考试 · 六级写作真题 {N} 篇全收录</div>
</body>"""


# ---------------------------------------------------------------- 痛点 → 解决
def p_pain():
    pain = [('拿到题目没思路', '不知道每段该写什么、写多少'), ('背了模板，分数还是上不去', '句子平平，拿不到高分档'), ('句子写不地道', '满篇中式英语，自己还看不出来')]
    fix = [('审题 + 题目要求逐条落实', '每条要求对应范文哪一句，一目了然'), (f'升格示范 {UP} 组', '普通句一步一步改成满分句，看懂差距在哪'), (f'{PAT} 个高分句式 + 中式英语黑名单', '公式、讲解、仿写例句，写出地道句子')]
    p = ''.join(f'<div style="display:flex;align-items:center;background:#fff;border-radius:18px;padding:14px 24px;margin-bottom:12px;box-shadow:0 8px 24px rgba(31,37,55,.10)">'
                f'<span style="flex:none;width:46px;height:46px;border-radius:50%;background:#ffe3ea;color:{BERRY};font:900 30px/46px Black;text-align:center;margin-right:20px">✕</span>'
                f'<div><div style="font:900 33px/1.25 Black">{a}</div><div style="font:700 24px/1.4 Bold;color:{MUTE}">{b}</div></div></div>' for a, b in pain)
    f = ''.join(f'<div style="display:flex;align-items:center;margin-bottom:22px">'
                f'<span style="flex:none;width:46px;height:46px;border-radius:50%;background:{GREEN};color:#fff;font:900 30px/46px Black;text-align:center;margin-right:20px">✓</span>'
                f'<div><div style="font:900 32px/1.25 Black"><span class="hy">{a}</span></div><div style="font:700 24px/1.4 Bold;color:{INK2}">{b}</div></div></div>' for a, b in fix)
    return f"""<body><div class="dots"></div>{head('六级作文，你是不是也这样？', '')}
<div class="ab" data-k="pain" style="left:50px;top:196px;width:900px">{p}</div>
<div class="ab" data-k="arrow" style="left:50px;top:556px;width:900px;text-align:center;font:900 34px/1 Black;color:#fff;background:{BLUE};padding:20px 0 22px;border-radius:18px">这套讲义，一篇一篇帮你练到位 ↓</div>
<div class="ab" data-k="fix" style="left:60px;top:664px">{f}</div>
</body>"""


# ---------------------------------------------------------------- 每篇 10 块
def p_steps():
    steps = [('原题', '真题原题高清截图'), ('审题', '要写什么、哪里容易失分'), ('题目要求逐条落实', '每条要求 → 范文哪一句'), ('写作思路', '先列提纲，每段一个任务'),
             ('满分范文', '荧光笔标出高分句式 + 译文'), ('一步一步写', '每一句话是怎么写出来的'), ('为什么是满分档', '切题 · 结构与连贯 · 语言'),
             ('升格示范', '普通句一步一步改成满分句'), ('高分句式', '公式 + 讲解 + 两个仿写例句'), ('亮点词汇', '把普通说法换成高分说法')]
    assert len(steps) == SEC
    li = ''.join(f'<div style="display:flex;align-items:center;margin-bottom:11px"><span class="lat" style="flex:none;width:46px;height:46px;border-radius:12px;background:{BLUE};color:#fff;font-size:24px;line-height:46px;text-align:center;margin-right:14px">{i}</span>'
                 f'<div><div style="font:900 27px/1.2 Black">{a}</div><div style="font:700 19px/1.3 Bold;color:{MUTE}">{b}</div></div></div>' for i, (a, b) in enumerate(steps, 1))
    return f"""<body><div class="dots"></div>{head(f'每一篇都讲透：<span class="hy">{SEC} 个板块</span>', f'以 {NEWEST.replace(".", " 年 ")} 月第 1 套为例，这一篇就讲了 {CHAP} 页')}
<div class="ab" data-k="steps" style="left:50px;top:240px">{li}</div>
<div class="page" style="left:660px;top:250px;width:300px;transform:rotate(6deg)"><img src="{img('内页_08.png')}"></div>
<div class="page" style="left:585px;top:300px;width:300px;transform:rotate(0deg)"><img src="{img('内页_05.png')}"></div>
<div class="page" style="left:500px;top:360px;width:310px;transform:rotate(-6deg)"><img src="{img('内页_02.png')}"></div>
<div class="tag tr" data-k="t1" style="left:560px;top:880px;transform:rotate(-4deg)">真实内页 · 不是样板</div>
</body>"""


# ---------------------------------------------------------------- 题目要求 + 为什么是满分档
def p_req():
    return f"""<body><div class="dots"></div>{head('题目每条要求，<span class="hy">都落到范文的句子上</span>', '不只给范文：告诉你它为什么能拿满分档')}
<div class="tag tb" data-k="t1" style="left:60px;top:238px">题目要求逐条落实：全书 {REQ} 条</div>
<div class="shot" style="left:60px;top:286px;width:520px"><img src="{img('要求.png')}"></div>
<div class="tag tr" data-k="t2" style="left:610px;top:238px">为什么是满分档</div>
<div class="shot" style="left:610px;top:286px;width:330px"><img src="{img('得分.png')}"></div>
<div class="ab" data-k="note" style="left:610px;top:560px;width:330px;white-space:normal;font:700 22px/1.55 Bold;color:{INK2}">
{zx('从切题、结构与连贯、语言三个方面，逐条说明范文得分点，并引用范文原句。')}</div>
</body>"""


# ---------------------------------------------------------------- 满分范文
def p_essay():
    return f"""<body><div class="dots"></div>{head('满分范文：<span class="hy">荧光笔</span> + 圆圈编号', f'每篇 {min(WC)}—{max(WC)} 词，高分句式全部标出，后面逐个讲；附参考译文')}
<div class="shot" style="left:50px;top:256px;width:900px"><img src="{img('范文.png')}"></div>
<div class="tag tr" data-k="t1" style="left:660px;top:230px;transform:rotate(3deg)">① 编号 = 后面讲的高分句式</div>
<div class="ab" data-k="t2" style="left:50px;top:924px;width:900px;text-align:center;font:900 26px/1 Black;color:#fff;background:{BLUE};padding:14px 0 16px;border-radius:14px">每段都附参考译文 · 每句标序号，一句一句对照</div>
</body>"""


# ---------------------------------------------------------------- 一步一步写
def p_write():
    return f"""<body><div class="dots"></div>{head('一步一步写：<span class="hy">每句话怎么来的</span>', '先列提纲，再一句一句讲：这句要做什么、怎么写、范文原句 + 中文')}
<div class="tag tb" data-k="t1" style="left:80px;top:236px">写作思路：每段一个任务</div>
<div class="shot" style="left:80px;top:284px;width:840px"><img src="{img('思路.png')}"></div>
<div class="tag tr" data-k="t2" style="left:80px;top:510px">一步一步写：全书共 {STEP} 步，覆盖每一句</div>
<div class="shot" style="left:80px;top:558px;width:840px;height:400px"><img src="{img('步骤.png')}"></div>
</body>"""


# ---------------------------------------------------------------- 升格示范
def p_up():
    return f"""<body><div class="dots"></div>{head('升格示范：<span class="hy">普通句 → 满分句</span>', f'每篇 3 组，全书 {UP} 组：每一步改了什么、为什么更好，全写清楚')}
<div class="shot" style="left:60px;top:250px;width:880px"><img src="{img('升格1.png')}"></div>
<div class="shot" style="left:60px;top:620px;width:880px"><img src="{img('升格2.png')}"></div>
<div class="tag tk" data-k="t1" style="left:700px;top:226px;transform:rotate(3deg)">看懂差距在哪里</div>
</body>"""


# ---------------------------------------------------------------- 高分句式
def p_pat():
    pos = json.loads((S / '句式3位置.json').read_text('utf-8'))
    w, x0, y0 = 760, 150, 270
    im = Image.open(S / '句式3.png')
    h = w * im.height / im.width
    lab = [('mean', '这个句式表达什么'), ('f', '公式：照着套'), ('o', '范文原句 + 中文'), ('why', '讲解：为什么高分'), ('ex', '两个仿写例句 + 中文'), ('alt', '也可以这样说')]
    marks = ''.join(f'<div class="ab" style="left:{x0 - 50}px;top:{y0 + (pos[k][0] + pos[k][1]) / 2 * h - 17:.0f}px"><span class="dot">{i}</span></div>' for i, (k, _) in enumerate(lab, 1))
    legend = ''.join(f'<span style="margin-right:22px;white-space:nowrap"><span class="dot" style="width:28px;height:28px;font-size:17px;line-height:28px;vertical-align:2px;margin-right:6px">{i}</span>{t}</span>' for i, (_, t) in enumerate(lab, 1))
    return f"""<body><div class="dots"></div>{head(f'<span class="lat" style="color:{KY}">{PAT}</span> 个<span class="hy">高分句式</span>，个个讲透', f'每个句式：公式、范文原句、讲解、{EX // PAT} 个仿写例句、替换说法，全附中文')}
<div class="shot" style="left:{x0}px;top:{y0}px;width:{w}px"><img src="{img('句式3.png')}"></div>
{marks}
<div class="ab" data-k="legend" style="left:50px;top:{y0 + h + 20:.0f}px;width:900px;white-space:normal;font:700 22px/1.9 Bold;color:{INK}">{legend}</div>
<div class="tag tk" data-k="t1" style="left:680px;top:236px;transform:rotate(3deg)">共 {EX} 个仿写例句</div>
</body>"""


# ---------------------------------------------------------------- 写作总攻略
def p_guide():
    chips = [s['标题'].split('（')[0] for s in G['小节']]
    c = ''.join(f'<span style="display:inline-block;margin:0 10px 12px 0;padding:8px 16px 9px;border-radius:999px;background:#fff;border:3px solid {BLUE};font:900 22px/1 Black;color:{BLUE}">{zx(t)}</span>' for t in chips)
    return f"""<body><div class="dots"></div>{head('开篇写作总攻略：<span class="hy">先学会怎么拿分</span>', '评分标准、三种常考题型、30 分钟写作流程、字数控制，考前过一遍')}
<div class="ab" data-k="chips" style="left:50px;top:236px;width:900px;white-space:normal">{c}</div>
<div class="tag tr" data-k="t1" style="left:50px;top:372px">中式英语黑名单：都来自范文复核时真实改掉的说法</div>
<div class="shot" style="left:50px;top:422px;width:900px"><img src="{img('黑名单.png')}"></div>
</body>"""


# ---------------------------------------------------------------- 默写卡
def p_cards():
    return f"""<body><div class="dots"></div>{head('配套默写卡：<span class="hy">默句子</span>，不只是默单词', f'{DIC} 道句式填空 + {DIC} 句看中文默整句 + 答案，右侧提醒这句练什么句式')}
<div class="tag tb" data-k="t1" style="left:140px;top:226px">A 句式填空：补全关键表达</div>
<div class="shot" style="left:140px;top:270px;width:720px"><img src="{img('卡A.png')}"></div>
<div class="tag tb" data-k="t2" style="left:140px;top:490px">B 看中文，默写整句</div>
<div class="shot" style="left:140px;top:534px;width:720px"><img src="{img('卡B.png')}"></div>
<div class="tag tr" data-k="t3" style="left:140px;top:722px">答案：粉色就是填空的部分</div>
<div class="shot" style="left:140px;top:766px;width:720px"><img src="{img('答案卡.png')}"></div>
</body>"""


# ---------------------------------------------------------------- 学习体验：目录可点 + 书签 + 已读打勾
def p_toc():
    from pypdf import PdfReader
    outs = {k: [o.title for o in PdfReader(str(f)).outline] for k, f in (('讲义', J.OUT_HANDOUT), ('默写卡', J.OUT_CARDS), ('答案', J.OUT_ANS))}
    nh = len(outs['讲义'])
    assert nh == N + 2 and all(len(v) == N for k, v in outs.items() if k != '讲义'), {k: len(v) for k, v in outs.items()}
    bm = ''.join(f'<div style="padding:7px 12px;border-bottom:1px solid #e6e2d8;font:700 17px/1.3 Bold;color:{INK2}">{zx(t.replace(chr(12288), " "))}</div>' for t in outs['讲义'][:6])
    pts = [('点目录，直接跳到那一篇', f'{nh} 个目录项，点一下就到'), ('侧边栏书签', '三份 PDF 都有，随时跳转'), ('读完打勾 ✓', '“已读”框勾上、保存，进度一眼看到'), ('A4 排版', '屏幕上看、打印出来都清楚')]
    li = ''.join(f'<div style="margin-bottom:20px"><div style="font:900 27px/1.25 Black"><span class="hy">{a}</span></div><div style="font:700 20px/1.4 Bold;color:{INK2}">{zx(b)}</div></div>' for a, b in pts)
    return f"""<body><div class="dots"></div>{head('翻得快，<span class="hy">记得住读到哪</span>', '可点击目录 · 侧边栏书签 · 每篇“已读”勾选框')}
<div class="page" style="left:50px;top:262px;width:500px;transform:rotate(-1.5deg)"><img src="{img('目录_已勾.png')}"></div>
<div class="tag tr" data-k="t1" style="left:66px;top:234px;transform:rotate(-3deg)">真实目录页 · 打勾后的样子</div>
<div class="ab" data-k="pts" style="left:600px;top:250px;width:360px;white-space:normal">{li}</div>
<div class="ab" data-k="bm" style="left:600px;top:620px;width:350px;white-space:normal;background:#fff;border-radius:12px;box-shadow:0 10px 26px rgba(31,37,55,.14);overflow:hidden">
<div style="background:{INK};color:#fff;font:900 18px/1 Black;padding:10px 12px">书签（讲义 PDF 自带，前 6 条）</div>{bm}</div>
</body>"""


# ---------------------------------------------------------------- 31 篇全收录
def p_all():
    rows = ''
    for (yy, mm), ps in EXAMS.items():
        cells = ''.join(f'<div style="background:#fff;border-radius:10px;padding:6px 12px;box-shadow:0 3px 10px rgba(31,37,55,.08);white-space:normal;display:flex;align-items:center">'
                        f'<span style="flex:none;font:900 16px/1 Black;color:{BERRY};margin-right:8px">第{p["set"]}套</span>'
                        f'<span style="font:900 20px/1.22 Black;color:{INK}">{zx(VP[p["id"]]["title"])}</span></div>' for p in ps)
        cells += '<div></div>' * (3 - len(ps))
        rows += (f'<div style="display:grid;grid-template-columns:108px repeat(3,1fr);grid-auto-rows:56px;gap:6px;margin-bottom:6px">'
                 f'<div class="lat" style="display:flex;align-items:center;justify-content:center;font-size:24px;color:{KY}">{yy}.{mm}</div>{cells}</div>')
    return f"""<body><div class="dots"></div>{head(f'{Y0}—{Y1} 真题 <span class="lat" style="color:{KY}">{N}</span> 篇，<span class="hy">一篇不落</span>', f'{len(EXAMS)} 次考试全部收录，{NEWEST.replace(".", " 年 ")} 月已更新；每篇都按 10 个板块讲透')}
<div class="ab" data-k="grid" style="left:40px;top:230px;width:920px;white-space:normal">{rows}</div>
<div class="ab" data-k="band" style="left:40px;top:912px;width:920px;text-align:center;font:900 28px/1 Black;color:#fff;background:{BLUE};padding:18px 0 20px;border-radius:16px">
书末附 <span class="lat" style="color:{HY}">{PAT}</span> 个高分句式总表 · 考前一页过一遍</div>
</body>"""


# ---------------------------------------------------------------- 检查
CHECK_JS = r"""
(board) => {
  const W = innerWidth, H = innerHeight, out = [], M = board ? 24 : 8, MB = board ? 52 : 8;
  const els = [...document.querySelectorAll('[data-k]')];
  const r = els.map(e => { const b = e.getBoundingClientRect(); return {k: e.dataset.k, x0: b.left, y0: b.top, x1: b.right, y1: b.bottom}; });
  for (const a of r) if (a.x0 < M || a.y0 < M || a.x1 > W - M || a.y1 > H - MB) out.push(`${a.k} 出画 ${JSON.stringify(a)}`);
  for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) {
    if (els[i].contains(els[j]) || els[j].contains(els[i])) continue;
    if (els[i].dataset.k === 'band' || els[j].dataset.k === 'band') continue;      // 底衬条本来就垫在卖点下面
    const a = r[i], b = r[j], ox = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), oy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
    if (ox > 0 && oy > 0) out.push(`${a.k} 与 ${b.k} 重叠 ${ox.toFixed(0)}×${oy.toFixed(0)}`);
  }
  for (const im of document.images) if (!im.complete || !im.naturalWidth) out.push('图片没加载: ' + im.src.slice(-30));
  for (const e of document.querySelectorAll('.shot,.page')) { const b = e.getBoundingClientRect();
    if (b.left < 0 || b.top < 0 || b.right > W || b.bottom > H - (board ? 46 : 6)) out.push('截图出画: ' + (e.querySelector('img') || {src: '空'}).src.split('/').pop() + ' ' + JSON.stringify([b.left, b.top, b.right, b.bottom].map(Math.round))); }
  // 文字不许压到截图 / 内页上（标签 tag 除外：它本来就贴在截图角上）
  const pics = [...document.querySelectorAll('.shot,.page')].map(e => e.getBoundingClientRect());
  for (const e of document.querySelectorAll('[data-k]:not(.tag)')) {
    const tw = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
    for (let t; (t = tw.nextNode());) if (t.textContent.trim()) {
      const rg = document.createRange(); rg.selectNodeContents(t);
      for (const q of rg.getClientRects()) for (const c of pics)
        if (q.right > c.left + 2 && q.left < c.right - 2 && q.bottom > c.top + 2 && q.top < c.bottom - 2) { out.push(`${e.dataset.k} 文字压到截图「${t.textContent.trim()}」`); break; }
    }
  }
  for (const e of document.querySelectorAll('body *')) { const t = [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
    if (/^\d{1,2}\s*\/\s*\d{1,2}$/.test(t)) out.push('出现页码式编号（用户不要）: ' + t); }
  // 小店列表缩略图（400×400）：data-min 元素里最小的字不得低于下限
  for (const e of document.querySelectorAll('[data-min]')) {
    const tw = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
    let m = 1e9;
    for (let t; (t = tw.nextNode());) if (t.textContent.trim()) m = Math.min(m, parseFloat(getComputedStyle(t.parentElement).fontSize));
    const px = m * 400 / H;
    if (px < +e.dataset.min) out.push(`${e.dataset.k} 缩略图字高 ${px.toFixed(1)}px < 下限 ${e.dataset.min}px（400×400）`);
  }
  const fonts = [...document.fonts].filter(f => f.status !== 'loaded').map(f => f.family);
  if (fonts.length) out.push('字体未加载: ' + fonts.join(','));
  return out;
}"""


def banned(text):
    t = re.sub(r'<[^>]+>', '', text)
    return [w for w in BANNED if w in t]


def render(br, name, body, out_dir, board_=False):
    html = WORK / f'{name}.html'
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{BOARD_CSS if board_ else PAPER_CSS}</style></head>{body}</html>', 'utf-8')
    pg = br.new_page(viewport={'width': 1000, 'height': 1000}, device_scale_factor=2)
    pg.goto(html.as_uri())
    pg.evaluate('document.fonts.ready.then(() => [...document.fonts].forEach(f => f.load()))')
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(500)
    bad = pg.evaluate(CHECK_JS, board_) + pg.evaluate(WRAP_JS) + [f'禁用词「{w}」' for w in banned(body)]
    png = WORK / f'{name}.png'
    pg.screenshot(path=str(png))
    pg.close()
    im = Image.open(png).convert('RGB')
    assert im.size == (2000, 2000), im.size
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        im.save(out_dir / f'{name}.jpg', quality=92, optimize=True, progressive=True)
    im.resize((400, 400), Image.LANCZOS).save(WORK / f'{name}_400.png')
    return [f'{name}: {x}' for x in bad]


PAGES = [('02_商品总图', p_set), ('03_痛点与解决', p_pain), ('04_每篇10个板块', p_steps), ('05_题目要求与满分档', p_req),
         ('06_满分范文', p_essay), ('07_一步一步写', p_write), ('08_升格示范', p_up), ('09_高分句式', p_pat),
         ('10_写作总攻略', p_guide), ('11_默写卡', p_cards), ('12_目录书签已读', p_toc), ('13_31篇全收录', p_all)]


def selftest(br):
    """双向验证：主图字号×0.5 时每个 data-min 元素都要报出“缩略图字高”，正常字号一个都不报。"""
    global K
    bad = []
    for k, f in MAINS.items():
        for kk in (1.0, 0.5):
            K = kk
            body = f()
            res = render(br, f'自检_{k}', body, None, True)
            hit = {x.split(': ')[1].split()[0] for x in res if '缩略图字高' in x}
            need = set(re.findall(r'data-k="(\w+)" data-min=', body)) if kk < 1 else set()
            if kk < 1 and not {'hook', 'six', 'zt', 'sell', 'seal'} <= need:
                bad.append(f'{k} 缺少 data-min 元素：{sorted(need)}')
            if hit != need:
                bad.append(f'{k} 字号×{kk}：报出 {sorted(hit)}，应为 {sorted(need)}')
    K = 1.0
    if not banned('考前保过，全网第一') == ['第一', '保过'] or banned('满分范文 真题'):
        bad.append('禁用词检查失效')
    return bad


def main(args):
    from playwright.sync_api import sync_playwright
    WORK.mkdir(exist_ok=True)
    bad = []
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        if args and args[0] == '--自检':
            bad = selftest(br)
            print('\n'.join(bad) or '自检通过：字号×0.5 时主图每个 data-min 元素全部报出，正常字号不报；禁用词检查有效')
            return 1 if bad else 0
        if args and args[0] == '草稿':
            for k, f in MAINS.items():
                bad += render(br, f'草稿_{k}', f(), None, True)
        else:
            for old in list(OUT.glob('*.jpg')) + list(ALT_DIR.glob('*.jpg')):
                old.unlink()
            bad += render(br, '01_主图', MAINS[MAIN](), OUT, True)
            for k, f in MAINS.items():
                if k != MAIN:
                    bad += render(br, f'主图备选_{k}', f(), ALT_DIR, True)
            for name, fn in PAGES:
                bad += render(br, name, fn(), OUT)
            for f in sorted(OUT.glob('*.jpg')):
                print(f'{f.name} {f.stat().st_size / 1e6:.2f} MB')
        br.close()
    if bad:
        print('自查不通过：\n  ' + '\n  '.join(bad))
        return 1
    print('自查通过：文字不出画、互不重叠、不压截图、图片和字体全部加载、断行规则、缩略图字号、禁用词')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
