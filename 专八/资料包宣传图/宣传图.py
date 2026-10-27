"""专八阅读真题 30 篇学习资料包 · B 站动态宣传图（1:1，1440×1440，PNG，最多 9 张）。

    python3 专八/资料包宣传图/素材.py                         # 先从资料包真实 PDF 裁出素材（work/素材，不入库）
    /opt/ttsenv/bin/python 专八/资料包宣传图/宣传图.py         # 出 成品/01_….png …（文件名序号 = 发布顺序，图上不印编号）
    /opt/ttsenv/bin/python 专八/资料包宣传图/宣传图.py --封面   # 封面 A/B/C 三个方向 + 360 像素缩略图对比（work/）
    /opt/ttsenv/bin/python 专八/资料包宣传图/宣传图.py --预览   # 另拼一张 B 站动态 3×3 网格预览（work/预览_3x3.png）
    /opt/ttsenv/bin/python 专八/资料包宣传图/宣传图.py --自检   # 双向验证：正常 0 处；放回编号、缩小字号、断出孤字、禁用词、缺字都报

用户原话（2026-10-27）：把这套专八资料的图片解说做出来，发在 B 站动态里；图片一定要好看、极具吸引力，一看到就想获得这些资料。
原则：
- 图上展示的全部是资料包里真实的页面（素材.py 从发布的 PDF 渲染裁出），不做假图；
- 图上的每个数字都从数据现算（专八/data/vocab.json、长难句 json、PDF 页数、听写卡条目、朗读时长），数据一变就停下核对；
- 不写价格、免费、限时、保过、押题，不写“最 / 第一 / 唯一”（“最新”除外，2026 年是最新一年），不编评价销量，不放二维码、外链；
  图上不写领取流程（获取方式 / 领取方式 / 私信 / 网盘 / 链接都报错），领取方式只在动态正文里留给用户填；
  首尾两张必须有“充电”（充电即可获取全套资料，用户 2026-10-27）；列内容一律长难句分析在首位。
渲染后程序自查（CHECK_JS + 讲义 WRAP_JS + 缺字）：
- 文字不出画、标了 data-k 的块互不重叠、图片字体全部加载；
- 不出现“02 / 09”这类编号（踩坑 70）、不出现别的项目名（踩坑 57）、禁用词；
- 缩到 B 站动态 3×3 缩略图（每格约 360 像素）后，data-min 元素的字高不低于下限（踩坑 76）；整图正文字号不低于 17px（720 设计宽）；
- 断行：末两字不分开、数字与单位不分开……（讲义 WRAP_JS，踩坑 69）；
- 每个字都在所用字体里（不回退到系统字体）。
"""
import glob
import html as H
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
Z8 = REPO / '专八'
S = HERE / 'work' / '素材'
WORK = HERE / 'work'
OUT = HERE / '成品'
F_BLACK = REPO / '四级/封面/fonts/NotoSansSC_900Black.ttf'
F_BOLD = REPO / '四级/封面/fonts/NotoSansSC_700Bold.ttf'
F_INTER = REPO / '专八/tools/fonts/inter/files/inter-latin-800-normal.woff2'
F_GARA = REPO / '专八/tools/fonts/files/eb-garamond-latin-700-normal.woff2'
VIDEO_FRAME = Z8 / '封面/素材/t01_第4屏.jpg'      # 专八单词视频（书卷水墨）真实画面
W = 720                                            # 设计宽（CSS 像素），截图 ×2 = 1440
THUMB = 360                                        # B 站动态 3×3 每格约 360 像素

# ---------------------------------------------------------------- 数字（全部现算）
_P = json.loads((Z8 / 'data/vocab.json').read_text('utf-8'))['passages']
FOLDERS = sorted(p.name for p in (Z8 / '听写卡').iterdir() if p.is_dir())
N = len(FOLDERS)
YEARS = sorted({int(f[3:7]) for f in FOLDERS}, reverse=True)
NY = len(YEARS)
LONG = sum(len(json.loads(Path(f).read_text('utf-8'))['sentences']) for f in glob.glob(str(Z8 / '长难句/t*.json')))
SENTS = sum(len(pa) for p in _P for pa in p['paras'])
WORDS = sum(int(p['words']) for p in _P)
_T = json.loads((Z8 / 'audio/timings.json').read_text('utf-8'))['cet4_male']
AUDIO_MIN = sum(x['duration'] for x in _T.values()) / 60
AUDIO_H = int(AUDIO_MIN // 60)                     # “3 小时+” 只往下取整


def _pages(f):
    return int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', str(f)], capture_output=True, text=True).stdout).group(1))


KINDS = ['0 逐句精读', '1 汉译英', '2 英译汉', '3 文章填空', '4 长难句分析']
PG = {k: 0 for k in KINDS}
for f in FOLDERS:
    for k in KINDS:
        PG[k] += _pages(next((Z8 / '听写卡' / f).glob(f'* - {k}.pdf')))
TOTAL_PG = sum(PG.values())


def _items(f):
    """听写卡第一页抬头“共 N 个 / 共 N 空”。"""
    t = subprocess.run(['pdftotext', '-l', '1', str(f), '-'], capture_output=True, text=True).stdout
    return int(re.search(r'共\s*(\d+)\s*[个空]', t.replace('\n', '')).group(1))


CARD = sum(_items(next((Z8 / '听写卡' / f).glob('* - 1 汉译英.pdf'))) for f in FOLDERS)
assert CARD == sum(_items(next((Z8 / '听写卡' / f).glob('* - 2 英译汉.pdf'))) for f in FOLDERS)  # 两种卡条目相同，图上才能合写“生词 N 个”
GAPS = sum(_items(next((Z8 / '听写卡' / f).glob('* - 3 文章填空.pdf'))) for f in FOLDERS)
# 数据一改就停下，先核对图上的说法
_KNOWN = dict(N=30, NY=10, YEARS=(2026, 2016), LONG=234, SENTS=1416, WORDS=28991, AUDIO_H=3, TOTAL_PG=4487, PG0=2080)
_NOW = dict(N=N, NY=NY, YEARS=(YEARS[0], YEARS[-1]), LONG=LONG, SENTS=SENTS, WORDS=WORDS, AUDIO_H=AUDIO_H, TOTAL_PG=TOTAL_PG, PG0=PG['0 逐句精读'])
assert _NOW == _KNOWN, _NOW
assert 2020 not in YEARS and len(_T) == N
NEW = sum(f[3:7] == str(YEARS[0]) for f in FOLDERS)
YR = f'{YEARS[-1]}—{YEARS[0]}'


def titles():
    """[(年份, [(Passage, 题目)…])]，与资料包文件夹顺序相同。"""
    out = {}
    for f in FOLDERS:
        m = re.match(r'\d+ (\d{4})年专八 Passage (\w+) (.+)$', f)
        out.setdefault(m[1], []).append((m[2], m[3]))
    return list(out.items())


# ---------------------------------------------------------------- 断行规则（讲义 esc：末两字不分开、数字与单位不分开）
import importlib.util as _u  # noqa: E402

_spec = _u.spec_from_file_location('jy', REPO / '考研作文' / 'tools' / '讲义.py')
_J = _u.module_from_spec(_spec)
_spec.loader.exec_module(_J)
WRAP_JS = _J.WRAP_JS
ESC = _J.esc


def e(s):
    return ESC(s)


SCALE = 1.0          # 自检时 0.25：data-min 元素字号缩小，必须报出


def fs(n):
    return f'{n * SCALE:.1f}px'


# 缩到 360 像素（720 设计宽 × 0.5）后的字高下限（像素）
MIN_TITLE, MIN_HOOK, MIN_H1, MIN_SELL = 22, 12, 14, 9
MIN_BODY = 17        # 720 设计宽里任何文字的下限（手机看整张图时约 9.4pt）

# 书卷水墨配色（专八/封面/系列封面.py）
INK, INK2, PAPER, CLOTH, DIAN, ZHU, KY, YEL, MUTE = '#1e1b17', '#3b352c', '#f4eee2', '#1c3150', '#1f4677', '#b03c2a', '#d8301a', '#f5c451', '#6d6559'


def img(p):
    p = Path(p)
    return (p if p.is_absolute() else S / p).as_uri()


def css():
    return f"""
@font-face{{font-family:Black;src:url({F_BLACK.as_uri()})}}
@font-face{{font-family:Bold;src:url({F_BOLD.as_uri()})}}
@font-face{{font-family:Inter;font-weight:800;src:url({F_INTER.as_uri()})}}
@font-face{{font-family:Gara;font-weight:700;src:url({F_GARA.as_uri()})}}
*{{margin:0;padding:0;box-sizing:border-box}}
x-nb{{white-space:nowrap}}
html,body{{width:{W}px;height:{W}px;overflow:hidden}}
body{{position:relative;font-family:Bold,sans-serif;color:{INK};background:{PAPER}}}
.paper{{background:{PAPER} radial-gradient(circle at 1px 1px,rgba(60,50,30,.07) 1px,transparent 1.4px) 0 0/14px 14px}}
.cloth{{background:{CLOTH} repeating-linear-gradient(45deg,rgba(255,255,255,.025) 0 2px,transparent 2px 6px)}}
.ab{{position:absolute}}
.nw{{white-space:nowrap}}
.lat{{font-family:Inter,Black,sans-serif;font-weight:800}}
.pill{{display:inline-block;font:900 17px/1 Black;color:{PAPER};background:{CLOTH};padding:8px 16px 9px;border-radius:999px;letter-spacing:.08em}}
.h1{{font:900 {fs(44)}/1.18 Black;color:{INK};letter-spacing:.01em}}
.sub{{font:700 19px/1.5 Bold;color:{INK2}}}
.zhu{{color:{KY}}}
.shot{{position:absolute;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 0 rgba(30,27,23,.06),0 12px 28px rgba(30,27,23,.22)}}
.shot img{{display:block;width:100%}}
.tag{{position:absolute;white-space:nowrap;font:900 17px/1 Black;color:#fff;background:{KY};padding:7px 12px 8px;border-radius:8px;box-shadow:0 4px 10px rgba(30,27,23,.25)}}
.tag.n{{background:{DIAN}}}
.chip{{display:inline-block;white-space:nowrap;font:900 19px/1 Black;padding:9px 14px 10px;border-radius:10px;margin:0 8px 8px 0}}
.seal{{display:flex;align-items:center;justify-content:center;text-align:center;color:#fff;background:{KY};border-radius:10px;
  font:900 22px/1.1 Black;box-shadow:inset 0 0 0 3px rgba(255,255,255,.55),inset 0 0 0 6px {KY}}}
"""


def head(title, sub, top=34):
    # 不加“02 / 09”这类编号（踩坑 70）；右上角统一的小“充电获取”标识（用户 2026-10-27）
    return (BADGE +f'<div class="ab" data-k="pill" style="left:36px;top:{top}px"><span class="pill">英语专八阅读真题 · 学习资料包</span></div>'
            f'<div class="ab h1" data-k="h1" data-min="{MIN_H1}" style="left:34px;top:{top + 46}px;width:652px"><div>{title}</div></div>'
            + (f'<div class="ab sub" data-k="sub" style="left:36px;top:{top + 104}px;width:648px"><div>{sub}</div></div>' if sub else ''))


CHARGE = '充电即可获取'
ZT = '历年专八真题 2015—2026'      # 用户网盘里的历年真题全套（不写具体套数：2020 年停考，套数未核实）
BADGE = (f'<div class="ab" data-k="badge" style="right:36px;top:34px"><span class="pill" style="background:{KY};color:#fff">充电获取</span></div>')


def n(x, c=KY):
    return f'<span class="lat" style="color:{c}">{x}</span>'


# ---------------------------------------------------------------- 01 封面：三个方向
def cover_A():
    """靛蓝书衣：朱红钩子“充电即可获取全套资料” + 大标题 + 卖点（长难句在首位）+ 底部扇形真实页面。"""
    chip = f'class="chip" style="background:{PAPER};color:{CLOTH};font-size:{fs(19)};padding:8px 12px 9px;margin:0 7px 7px 0"'
    return f"""<body class="cloth">
<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="left:36px;top:34px;background:{KY};color:#fff;padding:12px 22px 14px;border-radius:12px;font:900 {fs(36)}/1 Black;box-shadow:0 6px 16px rgba(0,0,0,.3)">
<div>{CHARGE}全套资料</div></div>
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:32px;top:114px;color:{PAPER};font:900 {fs(104)}/1.08 Black;letter-spacing:.01em">
<div>专八阅读</div><div>真题 <span class="lat" style="color:{YEL};font-size:1.12em;letter-spacing:-.02em">{N}</span> 篇</div></div>
<div class="ab" data-k="sell" data-min="{MIN_SELL}" style="left:36px;top:364px;color:{YEL};font:900 {fs(28)}/1.3 Black">
<div>含 {YEARS[0]} 最新真题 · 每篇 6 件套</div></div>
<div class="ab" data-k="chips" data-min="{MIN_SELL}" style="left:36px;top:408px;width:660px">
<span {chip}>长难句分析 {LONG} 句</span><span {chip}>{ZT} + 答案解析 + 听力音频</span><span {chip}>逐句精读</span><span {chip}>三种听写卡</span><span {chip}>男声朗读</span></div>
<div class="shot bleed" style="left:24px;top:586px;width:300px;transform:rotate(-5deg)"><img src="{img('cs_full1.png')}"></div>
<div class="shot bleed" style="left:410px;top:584px;width:290px;transform:rotate(5deg)"><img src="{img('zt_2025.png')}"></div>
<div class="shot bleed" style="left:170px;top:560px;width:380px"><img src="{img('jd_01_2.png')}"></div>
</body>"""


def cover_B():
    """米白宣纸：朱红“专八”最大 + 右侧一叠真实页面 + 底部靛蓝条。"""
    return f"""<body class="paper">
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:30px;top:44px;font:900 {fs(170)}/1 Black;color:{KY};letter-spacing:-.02em"><div>专八</div></div>
<div class="ab" data-k="t2" data-min="{MIN_TITLE}" style="left:36px;top:220px;font:900 {fs(64)}/1.15 Black;color:{INK}"><div>阅读真题</div><div><span class="lat" style="color:{CLOTH}">{N}</span> 篇</div></div>
<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="left:36px;top:388px;width:300px"><div class="seal" style="width:280px;height:66px;font-size:{fs(28)}">含 {YEARS[0]} 最新真题</div></div>
<div class="ab" data-k="sell" data-min="{MIN_SELL}" style="left:38px;top:476px;font:900 {fs(30)}/1.4 Black;color:{INK2};width:300px"><div>全套学习资料包</div><div>每篇 6 件套</div></div>
<div class="shot" style="left:450px;top:40px;width:240px;transform:rotate(6deg)"><img src="{img('dk1_full.png')}"></div>
<div class="shot" style="left:400px;top:70px;width:260px;transform:rotate(-3deg)"><img src="{img('cs_full1.png')}"></div>
<div class="shot" style="left:330px;top:380px;width:370px;transform:rotate(2deg)"><img src="{img('jd_25_2.png')}"></div>
<div class="ab" data-k="band" data-min="{MIN_SELL}" style="left:0;top:620px;width:{W}px;height:100px;background:{CLOTH};color:{PAPER};display:flex;align-items:center;justify-content:center;font:900 {fs(27)}/1 Black">
<div>长难句 {n(LONG, YEL)} 句 · 逐句精读 · 听写卡 · 朗读</div></div>
</body>"""


def cover_C():
    """上半张真实的逐句精读页（与视频画面相同），下半靛蓝大字。"""
    return f"""<body class="cloth">
<div class="ab" style="left:0;top:0;width:{W}px;height:405px;overflow:hidden"><img src="{img('jd_01_2.png')}" style="width:{W}px;display:block"></div>
<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="left:440px;top:322px;background:{KY};color:#fff;padding:10px 18px 12px;border-radius:12px;font:900 {fs(28)}/1 Black;transform:rotate(-3deg);box-shadow:0 6px 16px rgba(0,0,0,.3)">
<div>含 {YEARS[0]} 最新真题</div></div>
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:34px;top:428px;color:{PAPER};font:900 {fs(64)}/1.1 Black"><div>专八阅读真题 <span class="lat" style="color:{YEL}">{N}</span> 篇</div></div>
<div class="ab" data-k="sell" data-min="{MIN_SELL}" style="left:36px;top:530px;color:{YEL};font:900 {fs(40)}/1.2 Black"><div>全套学习资料包</div></div>
<div class="ab" data-k="chips" data-min="{MIN_SELL}" style="left:36px;top:600px;width:660px">
<span class="chip" style="background:{PAPER};color:{CLOTH};font-size:{fs(21)}">长难句 {LONG} 句</span><span class="chip" style="background:{PAPER};color:{CLOTH};font-size:{fs(21)}">逐句精读</span><span class="chip" style="background:{PAPER};color:{CLOTH};font-size:{fs(21)}">三种听写卡</span><span class="chip" style="background:{PAPER};color:{CLOTH};font-size:{fs(21)}">男声朗读</span></div>
</body>"""


COVERS = {'A': cover_A, 'B': cover_B, 'C': cover_C}
COVER = 'A'          # 2026-10-27 三个方向拼 360 像素缩略图比较：A 标题最大、钩子和四个卖点在缩略图里都读得出，选 A


# ---------------------------------------------------------------- 02 资料包总览：6 件套
def timeline(tid='t28', h=56, w=200, color=DIAN):
    """一篇朗读的真实句子时间轴（timings.json）：每句一段，长度 = 时长。"""
    x = _T[tid]
    d = x['duration']
    bars = ''.join(f'<div style="position:absolute;left:{s["start"] / d * w:.1f}px;width:{max(1.2, (s["end"] - s["start"]) / d * w - 1.4):.1f}px;'
                   f'top:{h * (0.5 - (0.18 + 0.32 * ((i * 7) % 5) / 4) / 1)}px;height:{h * 2 * (0.18 + 0.32 * ((i * 7) % 5) / 4)}px;background:{color};border-radius:2px"></div>'
                   for i, s in enumerate(x['sentences']))
    return f'<div style="position:relative;width:{w}px;height:{h}px">{bars}</div>'


def p_all():
    """总览：两大块——30 篇阅读精读资料包、历年专八真题全套；列的顺序长难句在首位（用户 2026-10-27）。"""
    def tile(x, y, w, h, im, name, num, unit, ih=None):
        ih = ih or h - 84
        pic = (f'<img src="{img(im)}" style="width:100%;height:100%;object-fit:cover;object-position:left top">' if im else
               f'<div style="height:100%;display:flex;align-items:center;justify-content:center;background:{PAPER}">{timeline(w=w - 40, h=60)}</div>')
        return (f'<div class="ab" data-k="t{x}_{y}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:#fff;border-radius:12px;box-shadow:0 8px 20px rgba(30,27,23,.15);overflow:hidden">'
                f'<div style="height:{ih}px;overflow:hidden;border-bottom:1px solid #e6dfd0">{pic}</div>'
                f'<div style="padding:10px 14px 0"><div style="font:900 22px/1.2 Black">{e(name)}</div>'
                f'<div style="font:700 18px/1.45 Bold;color:{MUTE}">{n(num, ZHU)} {e(unit)}</div></div></div>')
    zt = ''.join(f'<span class="chip" style="background:{PAPER};color:{CLOTH};font-size:18px;padding:7px 10px 8px;margin:0 6px 6px 0">{e(t)}</span>' for t in ('真题', '答案', '解析', '听力音频'))
    return f"""<body class="paper">{head('充电即可获取：两大块全套资料', '30 篇阅读精读资料包（每篇一个文件夹）+ 历年专八真题全套')}
{tile(36, 190, 316, 236, 'cs_card.png', '① 长难句分析', LONG, f'句逐层拆解 · {PG["4 长难句分析"]} 页')}
<div class="ab" data-k="zt" style="left:368px;top:190px;width:316px;height:236px;background:{CLOTH};border-radius:12px;box-shadow:0 8px 20px rgba(30,27,23,.2);overflow:hidden">
<div style="height:64px;overflow:hidden;opacity:.95"><img src="{img('zt_2025.png')}" style="width:100%;display:block"></div>
<div style="padding:10px 14px 0;color:{PAPER}"><div style="font:900 22px/1.2 Black">② 历年专八真题全套</div>
<div style="font:700 18px/1.5 Bold;color:{YEL}"><span class="lat">2015—2026</span> · 10 年以上</div>
<div style="margin-top:6px">{zt}</div></div></div>
{tile(36, 442, 204, 236, 'jd_01_2.png', '③ 逐句精读', SENTS, f'句 · {PG["0 逐句精读"]} 页')}
{tile(258, 442, 204, 236, 'dk3.png', '④ 三种听写卡', PG["1 汉译英"] + PG["2 英译汉"] + PG["3 文章填空"], '页')}
{tile(480, 442, 204, 236, None, '⑤ 朗读音频', f'{AUDIO_H}小时+', f'· {N} 段男声')}
<div class="ab" data-k="band" style="left:36px;top:690px;width:648px;text-align:center;font:900 19px/1 Black;color:{CLOTH}">
<div>阅读资料包 PDF 共 {n(TOTAL_PG, KY)} 页 · 2026→2016 排好</div></div>
</body>"""


# ---------------------------------------------------------------- 03 长难句
def p_long():
    return f"""<body class="paper">{head(f'长难句 {n(LONG)} 句，一层一层拆开', '每句都按五步走：切意群 → 找主干 → 层层拆解 → 一步步读懂 → 易错点')}
<div class="shot" style="left:30px;top:200px;width:560px"><img src="{img('cs_card.png')}"></div>
<div class="shot" style="left:378px;top:540px;width:320px;transform:rotate(2deg)"><img src="{img('cs_steps.png')}"></div>
<div class="tag" style="left:440px;top:208px">红色 = 主干</div>
<div class="tag n" style="left:600px;top:400px">缩进 = 层级</div>
<div class="tag" style="left:600px;top:522px;transform:rotate(2deg)">易错点</div>
</body>"""


# ---------------------------------------------------------------- 04 逐句精读
def p_read():
    return f"""<body class="paper">{head(f'逐句精读 {n(SENTS)} 句', '英文 + 译文 + 生词释义，和视频画面一模一样，一句一页')}
<div class="shot" style="left:36px;top:196px;width:648px"><img src="{img('jd_25_2.png')}"></div>
<div class="shot" style="left:36px;top:574px;width:206px"><img src="{img('jd_06_4.png')}"></div>
<div class="shot" style="left:257px;top:574px;width:206px"><img src="{img('jd_17_3.png')}"></div>
<div class="shot" style="left:478px;top:574px;width:206px"><img src="{img('jd_01_3.png')}"></div>
<div class="tag" style="left:560px;top:180px;transform:rotate(3deg)">生词就在旁边</div>
</body>"""


# ---------------------------------------------------------------- 05 三种听写卡
def p_dict():
    rows = [('dk1.png', '汉译英', '看中文，写出英文'), ('dk2.png', '英译汉', '看英文，写出中文'), ('dk3.png', '文章填空', '回到原文，把生词填回去')]
    out = ''
    for i, (im, a, b) in enumerate(rows):
        y = 196 + i * 172
        out += (f'<div class="ab" data-k="lab{i}" style="left:36px;top:{y}px;width:150px">'
                f'<div style="font:900 26px/1.2 Black;color:{CLOTH}">{e(a)}</div><div style="font:700 18px/1.45 Bold;color:{MUTE};margin-top:6px">{e(b)}</div></div>'
                f'<div class="shot" style="left:196px;top:{y}px;width:488px;height:160px"><img src="{img(im)}" style="width:100%"></div>')
    return f"""<body class="paper">{head('三种听写卡，边听边写', f'生词 {n(CARD)} 个 · 原文填空 {n(GAPS)} 空，配朗读音频一起用')}
{out}
</body>"""


# ---------------------------------------------------------------- 06 朗读 + 配套视频
def p_audio():
    return f"""<body class="cloth">{BADGE}
<div class="ab" data-k="pill" style="left:36px;top:34px"><span class="pill" style="background:{PAPER};color:{CLOTH}">英语专八阅读真题 · 学习资料包</span></div>
<div class="ab h1" data-k="h1" data-min="{MIN_H1}" style="left:34px;top:80px;color:{PAPER}"><div>{N} 段男声朗读，共 {n(f'{AUDIO_H} 小时+', YEL)}</div></div>
<div class="ab sub" data-k="sub" style="left:36px;top:138px;width:648px;color:#d9d2c3"><div>和专八单词视频同一个声音、同一套文章：看视频记单词，拿资料精读、听写、跟读</div></div>
<div class="shot" style="left:36px;top:226px;width:648px"><img src="{img(VIDEO_FRAME)}"></div>
<div class="tag" style="left:560px;top:210px;transform:rotate(3deg)">配套视频画面</div>
<div class="ab" data-k="tl" style="left:36px;top:618px;width:648px;height:76px;background:rgba(255,255,255,.08);border-radius:12px;padding:12px 18px;display:flex;align-items:center;gap:18px">
<div style="font:900 19px/1.4 Black;color:{PAPER};white-space:nowrap"><div>{YEARS[0]} Passage One</div><div style="font:700 17px Bold;color:#bfb7a7">每一段 = 一句</div></div>
{timeline('t28', h=50, w=430, color=YEL)}</div>
</body>"""


# ---------------------------------------------------------------- 07 篇目一览
def p_list():
    rows = ''
    for i, (y, ps) in enumerate(titles()):
        cells = ''.join(f'<div style="flex:1;padding:0 8px 0 0;font:700 17px/1.22 Bold;color:{INK}">{e(t)}</div>' for _, t in ps)
        bg = f'background:{"#fff" if i % 2 == 0 else "transparent"};'
        new = f'<span style="display:block;font:900 17px/1 Black;color:#fff;background:{KY};border-radius:5px;padding:3px 0 4px;margin-top:4px;text-align:center">新</span>' if y == str(YEARS[0]) else ''
        rows += (f'<div style="display:flex;align-items:center;{bg}border-radius:8px;padding:4px 8px;min-height:44px">'
                 f'<div class="lat" style="width:62px;font-size:20px;color:{KY if y == str(YEARS[0]) else CLOTH}">{y}{new}</div>{cells}</div>')
    return f"""<body class="paper">{head(f'{YR} · {NY} 年 {n(N)} 篇', f'每年 Passage One—Three 全收录，从新到旧（{2020} 年停考）')}
<div class="ab" data-k="list" style="left:30px;top:178px;width:660px">{rows}</div>
</body>"""


# ---------------------------------------------------------------- 08 学习路线
def p_route():
    steps = [('jd_01_2.png', '看视频 + 逐句精读', '先把每一句读懂：英文、译文、生词一页看全'),
             ('cs_full1.png', '啃长难句', f'{LONG} 句逐层拆解，学会自己切意群、找主干'),
             ('dk1_full.png', '三种听写', '汉译英 → 英译汉 → 文章填空，生词真正记住'),
             (None, '跟读朗读', '对着男声朗读一句一句跟，语感和听力一起练')]
    out = ''
    for i, (im, a, b) in enumerate(steps):
        y = 196 + i * 128
        pic = (f'<img src="{img(im)}" style="width:100%;height:100%;object-fit:cover;object-position:top">' if im else
               f'<div style="height:100%;display:flex;align-items:center;justify-content:center;background:{CLOTH}">{timeline(w=120, h=50, color=YEL)}</div>')
        out += (f'<div class="ab" data-k="s{i}" style="left:36px;top:{y}px;width:648px;height:112px;background:#fff;border-radius:14px;box-shadow:0 6px 16px rgba(30,27,23,.12);display:flex;align-items:center;overflow:hidden">'
                f'<div class="lat" style="width:76px;text-align:center;font-size:44px;color:{KY}">{i + 1}</div>'
                f'<div style="flex:1;padding-right:14px"><div style="font:900 26px/1.25 Black">{e(a)}</div><div style="font:700 18px/1.45 Bold;color:{MUTE};margin-top:4px">{e(b)}</div></div>'
                f'<div style="width:150px;height:112px;overflow:hidden;border-left:1px solid #e6dfd0">{pic}</div></div>')
    return f"""<body class="paper">{head('怎么用：一篇文章练四遍', '每篇都按这四步走，读懂、拆透、写出、读出')}
{out}
<div class="ab" data-k="note" style="left:36px;top:712px;width:1px;height:1px"></div>
</body>"""


# ---------------------------------------------------------------- 09 收尾
def p_end():
    """收尾：行动号召——为 UP 主充电，获取全套资料；列的顺序长难句在首位。"""
    items = [(f'{LONG}', '句长难句分析', '主干 · 意群层级 · 易错点'), ('2015—2026', '历年专八真题', '10 年以上 · 答案 · 解析 · 听力'),
             (f'{SENTS}', '句逐句精读', f'{N} 篇 · 含 {YEARS[0]} 最新 {NEW} 篇'), (f'{CARD}', '个生词听写', f'三种听写卡 · {GAPS} 空填空'),
             (f'{AUDIO_H}小时+', '男声朗读', f'{N} 段，和视频同一个声音')]
    rows = ''.join(f'<div style="display:flex;align-items:baseline;padding:9px 0;border-bottom:1px solid rgba(244,238,226,.18)">'
                   f'<div class="lat" style="width:196px;text-align:right;font-size:{34 if len(a) > 6 else 40}px;color:{YEL};letter-spacing:-.01em;white-space:nowrap">{a}</div>'
                   f'<div style="font:900 25px/1.2 Black;color:{PAPER};margin:0 12px 0 14px;white-space:nowrap">{e(b)}</div>'
                   f'<div style="font:700 18px/1.3 Bold;color:#c9c1b1">{e(c)}</div></div>' for a, b, c in items)
    return f"""<body class="cloth">
<div class="ab" data-k="pill" style="left:36px;top:34px"><span class="pill" style="background:{PAPER};color:{CLOTH}">英语专八阅读真题 · 学习资料包</span></div>
<div class="ab h1" data-k="h1" data-min="{MIN_H1}" style="left:34px;top:80px;color:{PAPER}"><div>为 UP 主充电，获取全套资料</div></div>
<div class="ab" data-k="rows" style="left:24px;top:156px;width:660px">{rows}</div>
<div class="ab" data-k="pg" style="left:36px;top:504px;width:648px;text-align:center;font:900 21px/1 Black;color:{PAPER}"><div>阅读资料包 PDF 共 {n(TOTAL_PG, YEL)} 页 · 每篇一个文件夹</div></div>
<div class="ab" data-k="get" data-min="{MIN_HOOK}" style="left:60px;top:556px;width:600px;height:112px"><div class="seal" style="width:600px;height:112px;font-size:{fs(44)}">{CHARGE}全套资料</div></div>
</body>"""


PAGES = [('01_封面', None), ('02_资料包总览', p_all), ('03_长难句分析', p_long), ('04_逐句精读', p_read), ('05_三种听写卡', p_dict),
         ('06_朗读与配套视频', p_audio), ('07_30篇篇目', p_list), ('08_学习路线', p_route), ('09_一套资料', p_end)]

# ---------------------------------------------------------------- 程序自查
BANNED = ['考研', '六级', '四级', '中考', '高考', '雅思', '托福', 'CET', '价格', '免费', '限时', '保过', '押题', '包过', '必过', '第一', '唯一',
          '全网', '销量', '好评', '¥', '元', 'http', 'www', '二维码', '扫码',
          '获取方式', '领取方式', '私信', '网盘', '链接']        # 图上不写领取流程（只在动态正文里留给用户填）

CHECK_JS = """
(MIN_BODY) => {
  const W = innerWidth, H = innerHeight, out = [];
  const r = [...document.querySelectorAll('[data-k]')].map(e => { const b = e.getBoundingClientRect(); return {k: e.dataset.k, x0: b.left, y0: b.top, x1: b.right, y1: b.bottom}; });
  for (const a of r) if (a.x1 - a.x0 > 1 && (a.x0 < 0 || a.y0 < 0 || a.x1 > W || a.y1 > H)) out.push(`${a.k} 出画 ${JSON.stringify(a)}`);
  for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) {
    const a = r[i], b = r[j], ox = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), oy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
    if (ox > 0.5 && oy > 0.5) out.push(`${a.k} 与 ${b.k} 重叠 ${ox.toFixed(0)}×${oy.toFixed(0)}`);
  }
  // 文字的实际范围不能出画（含旋转的标签）
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT), rg = document.createRange();
  for (let t; (t = tw.nextNode());) {
    if (!t.textContent.trim()) continue;
    rg.selectNodeContents(t);
    for (const q of rg.getClientRects()) if (q.left < 6 || q.top < 6 || q.right > W - 6 || q.bottom > H - 6) { out.push('文字出画: ' + t.textContent.slice(0, 20)); break; }
    const f = parseFloat(getComputedStyle(t.parentElement).fontSize);
    if (f < MIN_BODY) out.push(`字号 ${f}px < ${MIN_BODY}px: ` + t.textContent.slice(0, 20));
  }
  // 截图卡片不能压住文字块；overflow:hidden 的框不能把里面的内容裁掉
  const shots = [...document.querySelectorAll('.shot')].map(e => e.getBoundingClientRect());
  for (const a of r) for (const q of shots) {
    const ox = Math.min(a.x1, q.right) - Math.max(a.x0, q.left), oy = Math.min(a.y1, q.bottom) - Math.max(a.y0, q.top);
    if (ox > 0.5 && oy > 0.5) out.push(`${a.k} 与截图重叠 ${ox.toFixed(0)}×${oy.toFixed(0)}`);
  }
  for (const e of document.querySelectorAll('[data-k] *')) if (getComputedStyle(e).overflow === 'hidden' && !e.querySelector('img') && e.scrollHeight > e.clientHeight + 1)
    out.push(`${e.closest('[data-k]').dataset.k} 内容被裁掉 ${e.scrollHeight}>${e.clientHeight}`);
  for (const e of document.querySelectorAll('[data-k]')) if (getComputedStyle(e).overflow === 'hidden' && e.scrollHeight > e.clientHeight + 1)
    out.push(`${e.dataset.k} 内容被裁掉 ${e.scrollHeight}>${e.clientHeight}`);
  for (const im of document.images) if (!im.complete || !im.naturalWidth) out.push('图片没加载: ' + im.src.slice(-30));
  for (const e of document.querySelectorAll('.shot:not(.bleed)')) { const b = e.getBoundingClientRect();
    if (b.left < 0 || b.top < 0 || b.right > W || b.bottom > H) out.push('截图出画: ' + e.querySelector('img').src.split('/').pop() + ' ' + JSON.stringify([b.left, b.top, b.right, b.bottom].map(Math.round))); }
  // 缩到 B 站动态缩略图（每格约 360 像素）后的字高
  for (const e of document.querySelectorAll('[data-min]')) {
    const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT); let m = 1e9;
    for (let t; (t = w.nextNode());) if (t.textContent.trim()) m = Math.min(m, parseFloat(getComputedStyle(t.parentElement).fontSize));
    const px = m * %THUMB% / W;
    if (px < +e.dataset.min) out.push(`${e.dataset.k} 缩略图字高 ${px.toFixed(1)}px < 下限 ${e.dataset.min}px（%THUMB% 像素缩略图）`);
  }
  // 页码式编号（踩坑 70）
  for (const e of document.querySelectorAll('body *')) { const t = [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
    if (/^\\d{1,2}\\s*\\/\\s*\\d{1,2}$/.test(t)) out.push('出现页码式编号（用户不要）: ' + t); }
  const fonts = [...document.fonts].filter(f => f.status !== 'loaded').map(f => f.family);
  if (fonts.length) out.push('字体未加载: ' + fonts.join(','));
  return {out, text: document.body.innerText};
}""".replace('%THUMB%', str(THUMB))


def _cmap(p):
    from fontTools.ttLib import TTFont
    return set(TTFont(str(p)).getBestCmap())


_CM = None


def missing_glyphs(text):
    """图上的每个字都要在 Noto Sans SC（中文、标点）或 Inter（英文数字）里，不回退到系统字体。"""
    global _CM
    if _CM is None:
        _CM = _cmap(F_BLACK) & _cmap(F_BOLD)
    return sorted({c for c in text if not c.isspace() and ord(c) not in _CM})


def text_problems(text):
    out = []
    for _, ps in titles():          # 篇目原题（如“……改进最能推动……”）是资料本身的名字，不算宣传用语
        for _, t in ps:
            text = text.replace(t, '')
    for w in BANNED:
        if w in text:
            out.append(f'禁用词或别的项目名：{w}')
    if re.search(r'最(?!新)', text):
        out.append('绝对词：最（只许“最新”）')
    if re.search(r'\b\d{1,2}\s*/\s*\d{1,2}\b', text):
        out.append('页码式编号')
    miss = missing_glyphs(text)
    if miss:
        out.append('字体里没有这些字（会回退到系统字体）：' + ''.join(miss))
    return out


MUST = {'01_封面': '充电', '09_一套资料': '充电'}   # 第 1 张和最后一张必须有“充电”（用户 2026-10-27：充电即可获取全套资料）


def render(br, body, name, out_dir=WORK, must=None):
    if not body.startswith('<body'):
        body = '<body>' + body + '</body>'
    WORK.mkdir(parents=True, exist_ok=True)
    f = WORK / f'{name}.html'
    f.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{css()}</style></head>{body}</html>', 'utf-8')
    pg = br.new_page(viewport={'width': W, 'height': W}, device_scale_factor=2)
    pg.goto(f.as_uri())
    pg.evaluate('document.fonts.ready.then(() => [...document.fonts].forEach(f => f.load()))')
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(400)
    res = pg.evaluate(CHECK_JS, MIN_BODY)
    bad = res['out'] + pg.evaluate(WRAP_JS) + text_problems(res['text'])
    if must and must not in res['text']:
        bad.append(f'缺少“{must}”')
    png = out_dir / f'{name}.png'
    out_dir.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(png))
    pg.close()
    assert Image.open(png).size == (2 * W, 2 * W)
    return png, [f'{name}: {x}' for x in bad]


def grid(pngs, path, cell=THUMB, cols=3, gap=6):
    rows = (len(pngs) + cols - 1) // cols
    c = Image.new('RGB', (cols * cell + (cols + 1) * gap, rows * cell + (rows + 1) * gap), '#f1f2f3')
    for i, p in enumerate(pngs):
        c.paste(Image.open(p).convert('RGB').resize((cell, cell), Image.LANCZOS), (gap + (i % cols) * (cell + gap), gap + (i // cols) * (cell + gap)))
    c.save(path)
    return path


def launch(pw):
    return pw.chromium.launch(executable_path='/opt/pw-browsers/chromium') if Path('/opt/pw-browsers/chromium').exists() else pw.chromium.launch()


def selftest(br):
    """双向验证：正常 0 处；每种故意放进去的错误都必须报出。"""
    global SCALE, ESC
    fails = []
    _, bad = render(br, cover_A(), '_t_正常', must='充电')
    _, bad2 = render(br, p_end(), '_t_正常2', must='充电')
    if bad or bad2:
        fails.append(f'正常版式报了问题：{bad + bad2}')
    cases = {
        '放回编号': (lambda: p_end().replace('</body>', '<div class="ab" style="right:30px;top:30px;font:900 24px Black;color:#fff">02 / 09</div></body>'), '编号'),
        '禁用词': (lambda: p_end().replace('为 UP 主充电', '免费领取，为 UP 主充电'), '禁用词'),
        '别的项目名': (lambda: p_end().replace('每篇一个文件夹', '考研资料'), '别的项目名'),
        '缺字': (lambda: p_end().replace('每篇一个文件夹', '每篇一个文件夹𠀾'), '字体里没有'),
        '字号过小': (lambda: p_end().replace('font:700 18px/1.3', 'font:700 12px/1.3'), '字号'),
        '写了领取方式': (lambda: p_end().replace('每篇一个文件夹', '获取方式见动态正文'), '禁用词'),
        '写了网盘': (lambda: p_all().replace('两大块全套资料', '网盘资料'), '禁用词'),
        '写了私信': (lambda: p_end().replace('每篇一个文件夹', '充电后私信'), '禁用词'),
    }
    cases['截图压住文字'] = (lambda: cover_A().replace('left:170px;top:560px', 'left:170px;top:470px'), '与截图重叠')
    cases['内容被裁掉'] = (lambda: p_all().replace('<div style="height:64px;overflow:hidden', '<div style="height:150px;overflow:hidden'), '内容被裁掉')
    cases['封面没有充电'] = (lambda: cover_A().replace(CHARGE, '含全套'), '缺少“充电”')
    cases['收尾没有充电'] = (lambda: p_end().replace(CHARGE, '全套资料').replace('为 UP 主充电', '为 UP 主'), '缺少“充电”')
    for k, (fn, key) in cases.items():
        _, b = render(br, fn(), f'_t_{k}', must='充电')
        if not any(key in x for x in b):
            fails.append(f'{k}：没报出（{b}）')
    SCALE = 0.25       # 字号缩到 1/4：每个 data-min 元素都必须报（B 的“专八”本身特别大，×0.5 仍合格）
    for name, fn in [('A', cover_A), ('B', cover_B), ('C', cover_C), ('end', p_end), ('long', p_long)]:
        body = fn()
        _, b = render(br, body, f'_t_缩小_{name}')
        need = set(re.findall(r'data-k="(\w+)" data-min=', body))
        got = {x.split(': ')[1].split(' ')[0] for x in b if '缩略图字高' in x}
        if not need or need - got:
            fails.append(f'字号×0.25（{name}）漏报：{sorted(need - got)}')
    SCALE = 1.0
    # 孤字：同一段文字，经过 esc 不报，不经过 esc 必须报
    t = '每篇都按五步走切意群找主干层层拆解一步步读懂易错点'
    blk = lambda s: f'<body class="paper"><div class="ab" data-k="t" style="left:40px;top:300px;width:{26 * 24 + 4}px;font:700 26px/1.5 Bold"><div>{s}</div></div></body>'
    _, b1 = render(br, blk(ESC(t)), '_t_孤字_esc')
    _, b2 = render(br, blk(H.escape(t)), '_t_孤字_无esc')
    if b1 or not any('孤字' in x for x in b2):
        fails.append(f'孤字检查失效：esc 后 {b1}，不 esc {b2}')
    for p in WORK.glob('_t_*'):
        p.unlink()
    return fails


def main(argv):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = launch(pw)
        if '--自检' in argv:
            fails = selftest(br)
            br.close()
            print('\n'.join(fails) or '自检通过：正常 0 处；放回编号、禁用词、别的项目名、缺字、字号过小、写领取方式 / 网盘 / 私信、首尾图缺“充电”、截图压住文字、框里内容被裁掉、缩略图字号×0.25、孤字（不经过 esc）全部报出')
            return 1 if fails else 0
        bad = []
        if '--封面' in argv:
            pngs = []
            for k, fn in COVERS.items():
                p, b = render(br, fn(), f'封面{k}')
                pngs.append(p)
                bad += b
            grid(pngs, WORK / '封面对比_360.png')
            print('封面对比：', WORK / '封面对比_360.png')
        else:
            only = [a for a in argv if not a.startswith('--')]
            pngs = []
            for name, fn in PAGES:
                body = (fn or COVERS[COVER])()
                if only and not any(name.startswith(o) for o in only):
                    continue
                p, b = render(br, body, name, OUT, MUST.get(name))
                pngs.append(p)
                bad += b
                print(f'{p.name} {p.stat().st_size / 1e6:.2f} MB')
            if '--预览' in argv or not only:
                print('3×3 预览：', grid(pngs, WORK / '预览_3x3.png'))
        br.close()
    if bad:
        print('自查不通过：\n  ' + '\n  '.join(bad))
        return 1
    print(f'自查通过（{N} 篇，长难句 {LONG} 句，PDF {TOTAL_PG} 页，生词 {CARD}，填空 {GAPS}，朗读 {AUDIO_MIN:.1f} 分钟）')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
