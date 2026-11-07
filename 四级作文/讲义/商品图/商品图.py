"""四级英语写作讲义 B 站小店商品图（1:1，2000×2000，7 张）。

    python3 四级作文/讲义/商品图/素材.py            # 先画素材（真实内页元素、封面、目录、内页）
    python3 四级作文/讲义/商品图/商品图.py 草稿     # 主图 2 个方向 M1/M2，只出 400×400 缩略图到 work/ 挑定稿
    python3 四级作文/讲义/商品图/商品图.py          # 全部成品（主图用 MAIN；没选上的方向出到 成品/备选/）
    python3 四级作文/讲义/商品图/商品图.py --自检   # 双向验证：字号×0.5、放回“02 / 07”编号、篇数写错、缺字、禁用词都必须报出，正常 0 处

用户要求（2026-10-29，协调会话转述）：Release cet4-writing-handout 上 B 站小店；商品图 5 张左右、1:1；第一张详细展示这套资料到底
包含什么，并把最吸引人的卖点放上去；看到图就想下单。沿用 六级作文/讲义/商品图/ 的做法和原则：
· 图上全部是讲义里的真实内容（讲义自己的排版程序渲染的元素和 PDF 内页），不做假图；
· 每个数字都从数据现算并断言，数据一改就停下核对图上的说法；画面上出现的数字只许是现算的那些（写错篇数会报）；
· 不印“02 / 07”这类编号（踩坑 70）；图上中文走讲义的 esc（末两字不分开、数字与单位不分开），并跑讲义的 WRAP_JS 断行检查；
· 合规：不用绝对化用语（最、第一、100%、保过、必过……），不写纸质版、价格、销量（BANNED）；
· 小店列表缩到 400×400：data-min 元素最小字号不低于下限（主标题 24、钩子 13、卖点 10 像素）；
· 每个字都在所用字体里（fontTools 查 cmap，不许回退系统字体）。
配色、字体与四级写作 B 站封面（四级作文/封面/系列封面.py A：纸面 + 深绿 + 红）同一系列。
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
C = HERE.parents[1]                      # 四级作文/
REPO = C.parent
S = HERE / 'work' / '素材'
WORK = HERE / 'work'
OUT = HERE / '成品'
ALT_DIR = OUT / '备选'
MAIN = 'M1'                              # 定稿的主图方向（草稿缩略图挑定后写在这里）
sys.path.insert(0, str(REPO / 'tools'))
import 作文规则  # noqa: E402


def load(name, f):
    spec = importlib.util.spec_from_file_location(name, f)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


SC = load('cet4w_sucai', HERE / '素材.py')           # 讲义排版程序（SC.J）+ 三份 PDF 的位置
J = SC.J
CV = load('cet4w_cover', C / '封面/系列封面.py')     # 四级写作 B 站封面：配色、字体
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
VOC = sum(len(d['词汇']) for d in D)
DIC = sum(len(d['默写']) for d in D)
STEP = sum(len(d['步骤']) for d in D)
REQ = sum(len(d['要求']) for d in D)
UP = sum(len(d['升格']) for d in D)
ES = [e for y in range(2015, 2100) if (REPO / f'四级/作文/{y}.json').exists() for e in json.loads((REPO / f'四级/作文/{y}.json').read_text('utf-8'))]
WC = [作文规则.counted(e) for e in ES]
EXAMS = OrderedDict()
for p in sorted(SP.values(), key=lambda p: (-int(p['year']), -int(p['month']), int(p['set']))):
    EXAMS.setdefault((int(p['year']), int(p['month'])), []).append(p)
Y0, Y1 = min(y for y, _ in EXAMS), max(y for y, _ in EXAMS)
NEWEST = '{}.{}'.format(*max(EXAMS))
NEWEST_ZH = '{} 年 {} 月'.format(*max(EXAMS))
assert all(d['题目译文'] for d in D)                                     # “每篇原题配中文译文”
assert all(len(x['例句']) == 2 for d in D for x in d['句式'])           # “每个句式 2 个仿写例句”
assert (N, PAT, EX, VOC, DIC, STEP, REQ, UP) == (32, 195, 390, 300, 192, 180, 212, 80), (N, PAT, EX, VOC, DIC, STEP, REQ, UP)
assert (len(ES), min(WC), max(WC), len(EXAMS), Y0, Y1, NEWEST) == (32, 168, 178, 11, 2021, 2026, '2026.6'), (len(ES), min(WC), max(WC), len(EXAMS), Y0, Y1, NEWEST)


def pages(f):
    return int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', str(f)], capture_output=True, text=True).stdout).group(1))


PG = {k: pages(f) for k, f in SC.PDF.items()}
TOTAL = sum(PG.values())
assert PG == {'讲义': 366, '默写卡': 85, '答案': 46}, PG                # 数据或排版一改就停下，先核对图上的说法
SEC = len(re.findall(r"sec\((\d+), '", (C / 'tools/讲义.py').read_text('utf-8')))   # 每篇的板块数（essay_chapter 的 sec(1…10)）
assert SEC == 10, SEC
CHAP = json.loads((S / '章页数.json').read_text('utf-8'))['pages']     # c01 一章的页数（素材.py 量的）
GEN = [s['标题'].split('（')[0] for s in G['小节']]

def _outlines():
    from pypdf import PdfReader
    return {k: len(PdfReader(str(f)).outline) for k, f in SC.PDF.items()}


OUTL = _outlines()                       # 目录可点 / 书签：讲义 = 总攻略 + N 篇 + 句式总表，默写卡、答案各 N 篇
assert OUTL == {'讲义': N + 2, '默写卡': N, '答案': N}, OUTL

PAPER, GREEN, RED, INK, YEL, CREAM = CV.PAPER, CV.GREEN, CV.RED, CV.INK, CV.YEL, CV.CREAM
INK2, MUTE, HY = '#3a3a3a', '#6b6b6b', '#ffe46b'
MIN_TITLE, MIN_HOOK, MIN_SELL = 24, 13, 10      # 缩到 400×400 后的最小字高（像素）
K = 1.0                                         # 字号系数：只给 --自检 用
EXTRA = ''                                      # 自检时往画面里塞的东西
# 广告法绝对化用语 + 讲义没有的东西（纸质版、价格、销量）：图上、标题、描述里一律不许出现
BANNED = ['最', '第一', '顶级', '100%', '百分百', '保过', '必过', '包过', '提分保证', '保证提分', '纸质', '包邮', '销量', '好评', '¥', '元/']
# 画面上允许出现的数字：全部现算；外加讲义自己的篇目标题与板块序号（1…10）、30 分钟写作流程、圆圈序号
ALLOWED_NUM = {str(x) for x in (N, PAT, EX, VOC, DIC, STEP, REQ, UP, len(EXAMS), Y0, Y1, TOTAL, CHAP, SEC, min(WC), max(WC), *PG.values(),
                                 *(y for y, _ in EXAMS), *(m for _, m in EXAMS), *range(1, SEC + 1), EX // PAT, len(GEN))}
ALLOWED_NUM |= {n for v in VP.values() for n in re.findall(r'\d+', v['title'])} | {n for t in GEN for n in re.findall(r'\d+', t)}


def img(name):
    return (S / name).as_uri()


def fs(n):
    return f'{n * K:.0f}px'


CSS = ''.join(f"@font-face{{font-family:{k};src:url('{(CV.FD / f).as_uri()}')}}" for k, (f, _) in CV.FONTS.items()) + f"""
*{{margin:0;padding:0;box-sizing:border-box}}
x-nb{{white-space:nowrap}}
html,body{{width:1000px;height:1000px;overflow:hidden}}
body{{position:relative;font-family:Bold,sans-serif;color:{INK};background:{PAPER}}}
.bar{{position:absolute;left:0;top:0;width:1000px;height:14px;background:{GREEN}}}
.bar2{{position:absolute;left:40px;top:14px;width:920px;height:3px;background:{RED}}}
.ab{{position:absolute;white-space:nowrap}}
.hy{{box-shadow:inset 0 -.42em 0 {HY};padding:0 .04em}}
.h1{{font:900 54px/1.18 Black;color:{INK}}}
.sub{{font:700 25px/1.4 Bold;color:{INK2}}}
.top{{font:900 21px/1 Black;color:#fff;background:{GREEN};padding:9px 20px 10px;border-radius:999px;letter-spacing:.06em}}
.shot{{position:absolute;background:#fff;border-radius:12px;box-shadow:0 2px 0 rgba(0,0,0,.05),0 14px 34px rgba(0,0,0,.16);overflow:hidden}}
.shot img{{display:block;width:100%}}
.tag{{position:absolute;white-space:nowrap;font:900 22px/1 Black;color:#fff;padding:9px 16px 10px;border-radius:10px;box-shadow:0 5px 14px rgba(0,0,0,.22)}}
.tg{{background:{GREEN}}}.tr{{background:{RED}}}.ty{{background:{YEL};color:{INK}}}
.dot{{display:inline-block;width:34px;height:34px;border-radius:50%;background:{RED};color:#fff;font:900 20px/34px Black;text-align:center}}
.page{{position:absolute;background:#fff;box-shadow:0 3px 0 rgba(0,0,0,.06),0 18px 40px rgba(0,0,0,.24);border-radius:3px}}
.page img{{display:block;width:100%;border-radius:3px}}
.band{{position:absolute;left:40px;width:920px;text-align:center;font:900 27px/1 Black;color:#fff;background:{GREEN};padding:18px 0 20px;border-radius:14px}}
.r{{color:{RED}}}.y{{color:{YEL}}}
"""


def head(title, sub, y=34):
    # 不加“02 / 07”这类编号（踩坑 70）
    return (f'<div class="bar"></div><div class="bar2"></div>'
            f'<div class="ab" style="left:50px;top:{y}px"><span class="top">四级英语写作满分范文精讲</span></div>'
            f'<div class="ab h1" data-k="h1" style="left:48px;top:{y + 52}px">{title}</div>'
            + (f'<div class="ab sub" data-k="sub" style="left:50px;top:{y + 124}px">{sub}</div>' if sub else ''))


def seal(x, y, d, rot=-8):
    return (f'<div class="ab" data-k="seal" data-min="{MIN_HOOK}" style="left:{x}px;top:{y}px;width:{d}px;height:{d}px;border-radius:50%;'
            f'background:{RED};color:#fff;transform:rotate({rot}deg);display:flex;flex-direction:column;align-items:center;justify-content:center;'
            f'box-shadow:0 8px 20px rgba(0,0,0,.28);line-height:1.08">'
            f'<i style="position:absolute;inset:{d * .055:.0f}px;border-radius:50%;border:3px dashed rgba(255,255,255,.8)"></i>'
            f'<span style="font:900 {fs(d * .232)} Black;letter-spacing:-.03em">{NEWEST}</span>'
            f'<span style="font:900 {fs(d * .232)} Black">已更新</span></div>')


# ---------------------------------------------------------------- 主图：这套资料包含什么 + 最吸引人的卖点
ITEMS = [('满分范文精讲', '讲义', '内页_05.png', [f'写作总攻略 + {N} 篇精讲', '原题配中文译文', f'{PAT} 个高分句式', f'{UP} 组升格示范']),
         ('作文默写卡', '默写卡', '卡页_默写卡.png', [f'{DIC} 道句式填空', f'{DIC} 句看中文默整句', '每题提醒练什么句式']),
         ('默写卡答案', '答案', '卡页_答案.png', ['填空答案粉色标出', '整句对照范文原句', '默完马上自己批改'])]


def kit(y, cw=196):
    """三份资料：真实封面 + 真实内页 + 页数 + 里面有什么。"""
    out = ''
    for i, (name, key, inner, pts) in enumerate(ITEMS):
        x = 34 + i * 316
        li = ''.join(f'<div style="display:flex;align-items:flex-start"><span style="flex:none;color:{GREEN};font:900 21px/1.42 Black;margin-right:7px">✓</span>'
                     f'<span>{zx(t)}</span></div>' for t in pts)
        out += (f'<div class="page" style="left:{x + 100}px;top:{y + 16}px;width:{cw - 20}px;transform:rotate(6deg)"><img src="{img(inner)}"></div>'
                f'<div class="page" style="left:{x + 22}px;top:{y}px;width:{cw}px;transform:rotate(-3deg)"><img src="{img(f"封面_{key}.png")}"></div>'
                f'<div class="ab" data-k="n{i}" style="left:{x}px;top:{y + 300}px;width:300px;text-align:center">'
                f'<div style="font:900 30px/1.2 Black"><span class="r">{"①②③"[i]}</span> {name}</div>'
                f'<div style="margin-top:7px"><span style="display:inline-block;font:900 25px/1 Black;color:#fff;background:{RED};padding:7px 18px 8px;border-radius:999px">'
                f'{PG[key]} 页</span></div></div>'
                f'<div class="ab" data-k="l{i}" style="left:{x + 34}px;top:{y + 394}px;width:266px;white-space:normal;font:700 21px/1.42 Bold;color:{INK2}">{li}</div>')
    return out


def M1():
    """绿底标题区（与 B 站封面同款大字）+ 三份资料全家福（封面 + 内页 + 页数 + 内容）+ 底部卖点条。定稿。"""
    return f"""<body>
<div style="position:absolute;left:0;top:0;width:1000px;height:300px;background:radial-gradient(ellipse at 40% 30%, #236a4f 0%, {GREEN} 60%, #123b2b 100%)"></div>
<div class="ab" data-k="sell" data-min="{MIN_SELL}" style="left:44px;top:26px;font:900 {fs(30)}/1.2 Black;color:{CREAM}">
{Y0}—{Y1} 全部真题 · <span class="y">{N} 篇</span>全收录</div>
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:40px;top:72px;font:900 {fs(92)}/1.1 Black;color:#fff;letter-spacing:-.01em">
彻底搞定<span class="y">四级</span>写作</div>
<div class="ab" data-k="title2" data-min="{MIN_HOOK}" style="left:44px;top:200px;font:900 {fs(44)}/1 Black;color:{INK};background:{YEL};padding:10px 18px 13px;border-radius:10px;box-shadow:0 8px 0 #0b2a1e">
真题满分范文精讲 + 默写卡</div>
{seal(822, 50, 156, rot=-8)}
<div class="ab" data-k="kitt" style="left:44px;top:322px;font:900 26px/1 Black;color:{GREEN}">这套资料一共 <span class="r">3 份</span> · PDF 电子讲义 {TOTAL} 页</div>
{kit(372)}
<div class="band" data-k="band" data-min="{MIN_SELL}" style="top:908px;font-size:{fs(26)}">{len(EXAMS)} 次考试 · 原题配中文译文 · 每篇 {SEC} 个板块讲透</div>
{EXTRA}</body>"""


def M2():
    """纸面标题（与 B 站封面 A 同款）+ 一大张满分范文 + 三份封面：备选。"""
    return f"""<body><div class="bar"></div><div class="bar2"></div>
<div class="ab" data-k="sell" data-min="{MIN_SELL}" style="left:44px;top:36px;font:900 {fs(30)}/1.2 SerifSC;color:{GREEN}">
{Y0}—{Y1} 全部真题 <span class="r">{N} 篇</span> · {PG['讲义']} 页精讲 + 默写卡</div>
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:40px;top:88px;font:900 {fs(104)}/1.04 Black;letter-spacing:-.02em">
彻底搞定<span class="r">四级</span>写作</div>
<div class="ab" data-k="title2" data-min="{MIN_HOOK}" style="left:46px;top:216px;font:900 {fs(56)}/1 Black;color:#fff;background:{GREEN};padding:10px 18px 14px;box-shadow:8px 8px 0 {RED}">
四级真题满分范文</div>
{seal(800, 214, 150, rot=-8)}
<div class="shot" style="left:50px;top:350px;width:690px;transform:rotate(-1.2deg)"><img src="{img('范文.png')}"></div>
<div class="page" style="left:790px;top:380px;width:160px;transform:rotate(9deg)"><img src="{img('封面_答案.png')}"></div>
<div class="page" style="left:770px;top:470px;width:170px;transform:rotate(4deg)"><img src="{img('封面_默写卡.png')}"></div>
<div class="page" style="left:752px;top:560px;width:180px;transform:rotate(-2deg)"><img src="{img('封面_讲义.png')}"></div>
<div class="band" data-k="band" data-min="{MIN_SELL}" style="top:908px;font-size:{fs(26)}">{len(EXAMS)} 次考试 · 原题配中文译文 · 每篇 {SEC} 个板块讲透</div>
{EXTRA}</body>"""


MAINS = {'M1': M1, 'M2': M2}


# ---------------------------------------------------------------- 每篇 10 个板块 + 原题中文译文
def p_steps():
    steps = [('原题 + 题目译文', '原题截图，下面逐句中文翻译'), ('审题', '要写什么、哪里容易失分'), ('题目要求逐条落实', '每条要求 → 范文哪一句'),
             ('写作思路', '先列提纲，每段一个任务'), ('满分范文', '荧光笔标出高分句式 + 译文'), ('一步一步写', '每一句话是怎么写出来的'),
             ('为什么是满分档', '切题 · 结构与连贯 · 语言'), ('升格示范', '普通句一步一步改成满分句'), ('高分句式', '公式 + 讲解 + 两个仿写例句'),
             ('亮点词汇', '把普通说法换成高分说法')]
    assert len(steps) == SEC
    li = ''.join(f'<div style="display:flex;align-items:center;margin-bottom:10px"><span style="flex:none;width:44px;height:44px;border-radius:10px;background:{GREEN};color:#fff;font:900 23px/44px Black;text-align:center;margin-right:14px">{i}</span>'
                 f'<div><div style="font:900 26px/1.2 Black">{a}</div><div style="font:700 18px/1.3 Bold;color:{MUTE}">{zx(b)}</div></div></div>' for i, (a, b) in enumerate(steps, 1))
    return f"""<body>{head(f'每一篇都讲透：<span class="hy">{SEC} 个板块</span>', f'以 {NEWEST_ZH} 第 1 套为例，这一篇就讲了 {CHAP} 页')}
<div class="ab" data-k="steps" style="left:46px;top:234px">{li}</div>
<div class="tag tr" data-k="t1" style="left:480px;top:236px;transform:rotate(-2deg)">原题看不懂？每篇都有中文译文</div>
<div class="shot" style="left:470px;top:284px;width:490px"><img src="{img('原题译文.png')}"></div>
<div class="page" style="left:735px;top:560px;width:215px;transform:rotate(6deg)"><img src="{img('内页_06.png')}"></div>
<div class="page" style="left:520px;top:575px;width:215px;transform:rotate(-4deg)"><img src="{img('内页_04.png')}"></div>
<div class="tag tg" data-k="t2" style="left:600px;top:910px;transform:rotate(-2deg)">真实内页 · 不是样板</div>
{EXTRA}</body>"""


# ---------------------------------------------------------------- 满分范文
def p_essay():
    return f"""<body>{head('满分范文：<span class="hy">荧光笔</span> + 圆圈编号', f'每篇 {min(WC)}—{max(WC)} 词，高分句式全部标出，后面逐个讲；附参考译文')}
<div class="shot" style="left:50px;top:256px;width:900px"><img src="{img('范文.png')}"></div>
<div class="tag tr" data-k="t1" style="left:640px;top:228px;transform:rotate(3deg)">① 编号 = 后面讲的高分句式</div>
<div class="band" data-k="band" style="top:906px;font-size:25px">题目要求逐条落实到范文原句 · 全书 {REQ} 条</div>
{EXTRA}</body>"""


# ---------------------------------------------------------------- 升格示范
def p_up():
    return f"""<body>{head('升格示范：<span class="hy">普通句 → 满分句</span>', f'全书 {UP} 组：每一步改了什么、为什么更好，全写清楚')}
<div class="shot" style="left:60px;top:240px;width:880px"><img src="{img('升格1.png')}"></div>
<div class="shot" style="left:60px;top:678px;width:880px;height:288px"><img src="{img('升格2.png')}"></div>
<div class="tag tr" data-k="t1" style="left:700px;top:214px;transform:rotate(3deg)">看懂差距在哪里</div>
{EXTRA}</body>"""


# ---------------------------------------------------------------- 高分句式
def p_pat():
    pos = json.loads((S / '句式3位置.json').read_text('utf-8'))
    w, x0, y0 = 740, 160, 248
    im = Image.open(S / '句式3.png')
    h = w * im.height / im.width
    lab = [('mean', '这个句式表达什么'), ('f', '公式：照着套'), ('o', '范文原句 + 中文'), ('why', '讲解：为什么高分'), ('ex', '两个仿写例句 + 中文'), ('alt', '也可以这样说')]
    marks = ''.join(f'<div class="ab" style="left:{x0 - 50}px;top:{y0 + (pos[k][0] + pos[k][1]) / 2 * h - 17:.0f}px"><span class="dot">{i}</span></div>' for i, (k, _) in enumerate(lab, 1))
    legend = ''.join(f'<span style="margin-right:22px;white-space:nowrap"><span class="dot" style="width:28px;height:28px;font-size:17px;line-height:28px;vertical-align:2px;margin-right:6px">{i}</span>{t}</span>' for i, (_, t) in enumerate(lab, 1))
    return f"""<body>{head(f'<span class="r">{PAT}</span> 个<span class="hy">高分句式</span>，个个讲透', f'每个句式：公式、范文原句、讲解、{EX // PAT} 个仿写例句、替换说法，全附中文')}
<div class="shot" style="left:{x0}px;top:{y0}px;width:{w}px"><img src="{img('句式3.png')}"></div>
{marks}
<div class="ab" data-k="legend" style="left:50px;top:{y0 + h + 16:.0f}px;width:900px;white-space:normal;font:700 22px/1.85 Bold;color:{INK}">{legend}</div>
<div class="tag tr" data-k="t1" style="left:690px;top:222px;transform:rotate(3deg)">共 {EX} 个仿写例句</div>
{EXTRA}</body>"""


# ---------------------------------------------------------------- 默写卡
def p_cards():
    return f"""<body>{head('配套默写卡：<span class="hy">默句子</span>，不只是默单词', f'{DIC} 道句式填空 + {DIC} 句看中文默整句 + 答案，右侧提醒这句练什么句式')}
<div class="tag tg" data-k="t1" style="left:180px;top:222px">A 句式填空：补全关键表达</div>
<div class="shot" style="left:180px;top:264px;width:640px"><img src="{img('卡A.png')}"></div>
<div class="tag tg" data-k="t2" style="left:180px;top:492px">B 看中文，默写整句</div>
<div class="shot" style="left:180px;top:534px;width:640px"><img src="{img('卡B.png')}"></div>
<div class="tag tr" data-k="t3" style="left:180px;top:722px">答案：粉色就是填空的部分</div>
<div class="shot" style="left:180px;top:764px;width:640px"><img src="{img('答案卡.png')}"></div>
{EXTRA}</body>"""


# ---------------------------------------------------------------- 32 篇全收录 + 目录可点、已读打勾
def p_all():
    rows = ''
    for (yy, mm), ps in EXAMS.items():
        cells = ''.join(f'<div style="background:#fff;border-radius:9px;padding:5px 10px;box-shadow:0 3px 10px rgba(0,0,0,.07);white-space:normal;display:flex;align-items:center">'
                        f'<span style="flex:none;font:900 15px/1 Black;color:{RED};margin-right:7px">第{p["set"]}套</span>'
                        f'<span style="font:900 18px/1.2 Black;color:{INK}">{zx(VP[p["id"]]["title"])}</span></div>' for p in ps)
        cells += '<div></div>' * (3 - len(ps))
        rows += (f'<div style="display:grid;grid-template-columns:100px repeat(3,1fr);grid-auto-rows:52px;gap:5px;margin-bottom:5px">'
                 f'<div style="display:flex;align-items:center;justify-content:center;font:900 23px/1 Black;color:{GREEN}">{yy}.{mm}</div>{cells}</div>')
    return f"""<body>{head(f'{Y0}—{Y1} 真题 <span class="r">{N}</span> 篇，<span class="hy">一篇不落</span>', f'{len(EXAMS)} 次考试全部收录，{NEWEST_ZH}已更新；书末附 {PAT} 个高分句式总表')}
<div class="ab" data-k="grid" style="left:40px;top:222px;width:920px;white-space:normal">{rows}</div>
<div class="band" data-k="band" style="top:908px;font-size:25px">目录点一下就跳到那一篇 · 侧边栏书签 · 每篇“已读”可打勾</div>
{EXTRA}</body>"""


# ---------------------------------------------------------------- 检查
CHECK_JS = r"""
() => {
  const W = innerWidth, H = innerHeight, out = [], M = 8;
  const els = [...document.querySelectorAll('[data-k]')];
  const r = els.map(e => { const b = e.getBoundingClientRect(); return {k: e.dataset.k, x0: b.left, y0: b.top, x1: b.right, y1: b.bottom}; });
  for (const a of r) if (a.x0 < M || a.y0 < M || a.x1 > W - M || a.y1 > H - M) out.push(`${a.k} 出画 ${JSON.stringify(a)}`);
  for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) {
    if (els[i].contains(els[j]) || els[j].contains(els[i])) continue;
    const a = r[i], b = r[j], ox = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), oy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
    if (ox > 0 && oy > 0) out.push(`${a.k} 与 ${b.k} 重叠 ${ox.toFixed(0)}×${oy.toFixed(0)}`);
  }
  for (const im of document.images) if (!im.complete || !im.naturalWidth) out.push('图片没加载: ' + im.src.slice(-30));
  for (const e of document.querySelectorAll('.shot,.page')) { const b = e.getBoundingClientRect();
    if (b.left < 0 || b.top < 0 || b.right > W || b.bottom > H - 6) out.push('截图出画: ' + (e.querySelector('img') || {src: '空'}).src.split('/').pop() + ' ' + JSON.stringify([b.left, b.top, b.right, b.bottom].map(Math.round))); }
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
    if (/\d{1,2}\s*\/\s*\d{1,2}/.test(t)) out.push('出现页码式编号（用户不要）: ' + t); }
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
  // 每段文字：所用字体 + 文字（Python 端查 cmap、查数字）
  const runs = [];
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let t; (t = tw.nextNode());) if (t.textContent.trim()) runs.push([getComputedStyle(t.parentElement).fontFamily.split(',')[0].replace(/["']/g, '').trim(), t.textContent]);
  return {bad: out, runs};
}"""

_CMAP = {}


def cmap(fam):
    if fam not in _CMAP:
        from fontTools.ttLib import TTFont
        f = CV.FONTS.get(fam)
        _CMAP[fam] = set(TTFont(str(CV.FD / f[0])).getBestCmap()) if f else None
    return _CMAP[fam]


def text_problems(runs):
    bad = []
    for fam, t in runs:
        cm = cmap(fam)
        if cm is None:
            bad.append(f'用了图里没加载的字体 {fam}：{t.strip()[:20]}')
            continue
        miss = sorted({ch for ch in t if not ch.isspace() and ord(ch) not in cm})
        if miss:
            bad.append(f'{fam} 缺字 {"".join(miss)}（会回退系统字体）：{t.strip()[:20]}')
        for n in re.findall(r'\d+', t):
            if n not in ALLOWED_NUM:
                bad.append(f'画面上的数字 {n} 不是现算的数（{t.strip()[:24]}）')
    return bad


def banned(text):
    t = re.sub(r'<[^>]+>', '', text)
    for v in VP.values():               # 真题篇目原名（如“印象最深的校园活动”）是考试题目，不是宣传用语
        t = t.replace(zx(v['title']), '').replace(v['title'], '')
    return [w for w in BANNED if w in t]


def render(br, name, body, out_dir):
    html = WORK / f'{name}.html'
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head>{body}</html>', 'utf-8')
    pg = br.new_page(viewport={'width': 1000, 'height': 1000}, device_scale_factor=2)
    pg.goto(html.as_uri())
    pg.evaluate('document.fonts.ready.then(() => [...document.fonts].forEach(f => f.load()))')
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(500)
    res = pg.evaluate(CHECK_JS)
    bad = res['bad'] + text_problems(res['runs']) + pg.evaluate(WRAP_JS) + [f'禁用词「{w}」' for w in banned(body)]
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


PAGES = [('02_每篇10个板块', p_steps), ('03_满分范文', p_essay), ('04_升格示范', p_up), ('05_高分句式', p_pat),
         ('06_默写卡', p_cards), ('07_32篇全收录', p_all)]


def selftest(br):
    """双向验证：正常 0 处；字号×0.5 时主图每个 data-min 元素都报；放回“02 / 07”编号、篇数写错、缺字、禁用词都必须报出。"""
    global K, EXTRA, N
    bad = []
    for k, f in MAINS.items():
        for kk in (1.0, 0.5):
            K = kk
            body = f()
            res = render(br, f'自检_{k}', body, None)
            hit = {x.split(': ')[1].split()[0] for x in res if '缩略图字高' in x}
            need = set(re.findall(r'data-k="(\w+)" data-min=', body)) | ({'band'} if 'data-k="band" data-min=' in body else set()) if kk < 1 else set()
            if kk < 1 and not {'title', 'title2', 'sell', 'seal', 'band'} <= need:
                bad.append(f'{k} 缺少 data-min 元素：{sorted(need)}')
            if hit != need:
                bad.append(f'{k} 字号×{kk}：报出 {sorted(hit)}，应为 {sorted(need)}')
            if kk == 1.0 and res:
                bad.append(f'{k} 正常版报了 {len(res)} 处：{res[:3]}')
    K = 1.0
    traps = {'编号': ('<div class="ab" style="left:900px;top:960px;font:900 20px Black">02 / 07</div>', '页码式编号'),
             '缺字': ('<div class="ab" data-k="x" style="left:60px;top:960px;font:900 20px Black">✕</div>', '缺字'),
             '禁用词': ('<div class="ab" data-k="x" style="left:60px;top:960px;font:900 20px Black">全网第一</div>', '禁用词')}
    for name, (extra, key) in traps.items():
        EXTRA = extra
        res = render(br, '自检_雷', p_up(), None)
        if not any(key in x for x in res):
            bad.append(f'放进{name}没有报出：{res}')
    EXTRA = ''
    n0, N = N, N + 1                     # 篇数写错（33 篇）：数字检查必须报
    res = render(br, '自检_雷', p_all(), None)
    N = n0
    if not any('不是现算的数' in x and '33' in x for x in res):
        bad.append(f'篇数写错没有报出：{res[:3]}')
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
            print('\n'.join(bad) or '自检通过：正常 0 处；字号×0.5 主图每个 data-min 元素全部报出；放回编号、缺字、禁用词、篇数写错都报出')
            return 1 if bad else 0
        if args and args[0] == '草稿':
            for k, f in MAINS.items():
                bad += render(br, f'草稿_{k}', f(), None)
        else:
            for old in list(OUT.glob('*.jpg')) + list(ALT_DIR.glob('*.jpg')):
                old.unlink()
            bad += render(br, '01_主图', MAINS[MAIN](), OUT)
            for k, f in MAINS.items():
                if k != MAIN:
                    bad += render(br, f'主图备选_{k}', f(), ALT_DIR)
            for name, fn in PAGES:
                bad += render(br, name, fn(), OUT)
            for f in sorted(OUT.glob('*.jpg')):
                print(f'{f.name} {f.stat().st_size / 1e6:.2f} MB')
        br.close()
    if bad:
        print('自查不通过：\n  ' + '\n  '.join(bad))
        return 1
    print('自查通过：文字不出画、互不重叠、不压截图、图片和字体全部加载、不缺字、数字全部现算、断行规则、缩略图字号、禁用词、无编号')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
