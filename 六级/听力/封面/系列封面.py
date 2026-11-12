"""六级听力 B 站封面（2026-11-04）：教室黑板主题，与六级阅读（六级/封面/系列封面.py）、六级写作（六级作文/封面/系列封面.py）同一系列。

    /opt/ttsenv/bin/python 六级/听力/封面/系列封面.py 草稿        # A/B/C 三个方向 16:9 + 4:3 只出 320×180、960×540 缩略图到 work/
    /opt/ttsenv/bin/python 六级/听力/封面/系列封面.py 定稿 A      # A 出 16:9 + 4:3（PNG + JPG）到 系列封面/，B、C 的 16:9 JPG 作备选
    /opt/ttsenv/bin/python 六级/听力/封面/系列封面.py --自检      # 双向验证：字号×0.4 时每个 data-min 元素都要报，正常字号 0 处

老师要求（2026-11-04）：突出“六级听力真题”“彻底搞定六级听力”，大字为主；30 套、2018—2026 年写得非常明白；不写 4K、精读。
老师补充（2026-11-05）：还有“听力原文解析”视频（原文逐句 + 中文翻译 + 生词），真题和原文解析都要突出。
定稿 A：主标题“六级听力”下一行两个并列大块“真题 ＋ 原文解析”（data-k=tags，与主标题同一下限 24 像素）；只有真题的旧定稿留作 系列封面/…_旧版_仅真题_*。
套数、考试次数、起止年份全部从 六级/听力/<yyyymm-n>/ 目录现算（踩坑 70），并与 .github/cet6-listening-all.txt 核对；不印“02 / 09”编号。
渲染后程序自查（同 六级作文/封面/系列封面.py 的 CHECK_JS）：文字不出画、不压木框、不进 B 站底角遮挡区、互不重叠、字体全部加载；
data-min 元素缩到高 180 后最小字号不低于下限（主标题 24、钩子 13、卖点 10 像素，踩坑 76）。
"""
import importlib.util
import re
import sys
from collections import OrderedDict
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
WORK = HERE / 'work'
OUT = HERE / '系列封面'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


L = _load('cet6_cover', REPO / '六级/封面/系列封面.py')          # 黑板主题：配色、滤镜、木框、粉笔涂块、粉笔框标签
W = _load('cet6w_cover', REPO / '六级作文/封面/系列封面.py')     # 同系列的自查程序 CHECK_JS、粉笔下划线

# ───────── 数字现算 ─────────
SETS = sorted(d.name for d in (REPO / '六级/听力').iterdir() if re.fullmatch(r'\d{6}-\d', d.name))
ALL = (REPO / '.github/cet6-listening-all.txt').read_text('utf-8').split()
assert SETS == sorted(ALL), (SETS, ALL)                        # 封面套数 = 发布的套数
N = len(SETS)
EXAMS = OrderedDict()                                          # 年 → {月: 套数}
for s in SETS:
    EXAMS.setdefault(int(s[:4]), OrderedDict()).setdefault(int(s[4:6]), 0)
    EXAMS[int(s[:4])][int(s[4:6])] += 1
YEARS = sorted(EXAMS)
Y0, Y1 = YEARS[0], YEARS[-1]
M0, M1 = min(EXAMS[Y0]), max(EXAMS[Y1])
N_EXAM = sum(len(v) for v in EXAMS.values())
assert (N, N_EXAM, Y0, M0, Y1, M1) == (30, 16, 2018, 12, 2026, 6), (N, N_EXAM, Y0, M0, Y1, M1)   # 数据一变先核对封面说法
assert YEARS == list(range(Y0, Y1 + 1))                        # 年份连续，“全部真题”的年份一排才成立
SPAN = f'{Y1}—{Y0}'          # 2026—2018：新的年份在前、不写月份（老师 2026-11-04）
NEWEST = f'{Y1}'

CHALK, YEL, PNK, BLU, INK, HOT = L.CHALK, L.YEL, L.PNK, L.BLU, L.INK, L.HOT
RED = W.RED
MIN_TITLE, MIN_HOOK, MIN_SELL = 24, 13, 10
K = 1.0                                                        # 字号系数：只给 --自检 用
SIX = f'<span style="color:{HOT}">六级</span>'


def fs(n):
    return f'{n * K:.0f}px'


def y(t):
    return f'<span style="color:{YEL}">{t}</span>'


def seal(x, y_, d, rot=8):
    """“2026 已更新”粉笔红圆章。"""
    return (f'<div class="ab" data-k="seal" data-min="{MIN_SELL}" style="left:{x}px;top:{y_}px;width:{d}px;height:{d}px;transform:rotate({rot}deg);'
            f'display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.05;color:#fff">'
            f'<i style="position:absolute;inset:0;border-radius:50%;background:{RED};filter:url(#rough);box-shadow:0 8px 0 rgba(0,0,0,.3)"></i>'
            f'<i style="position:absolute;inset:{d * .06:.0f}px;border-radius:50%;border:5px dashed rgba(255,255,255,.75)"></i>'
            f'<span class="lat ck" style="position:relative;font-size:{fs(d * .26)}">{NEWEST}</span>'
            f'<span class="ck" style="position:relative;font:900 {fs(d * .25)}/1.15 Black">已更新</span></div>')


def phones(x, y_, s, rot=-8, k='deco'):
    """粉笔画的耳机（听力的一眼标志）。"""
    return (f'<svg class="ab" data-k="{k}" style="left:{x}px;top:{y_}px;width:{300 * s:.0f}px;height:{280 * s:.0f}px;transform:rotate({rot}deg);overflow:visible" '
            f'viewBox="0 0 300 280" filter="url(#line)">'
            f'<path d="M48 170 C 40 60, 120 22, 150 22 C 180 22, 260 60, 252 170" fill="none" stroke="{CHALK}" stroke-width="16" stroke-linecap="round"/>'
            f'<rect x="22" y="150" width="62" height="108" rx="26" fill="{YEL}" stroke="{CHALK}" stroke-width="9"/>'
            f'<rect x="216" y="150" width="62" height="108" rx="26" fill="{YEL}" stroke="{CHALK}" stroke-width="9"/>'
            f'<path d="M110 196 q 14 -18 0 -36 M128 208 q 26 -30 0 -60 M190 196 q -14 -18 0 -36 M172 208 q -26 -30 0 -60" '
            f'fill="none" stroke="{PNK}" stroke-width="8" stroke-linecap="round"/></svg>')


def years(size, mr=10, pad=16, ys=None):
    """年份一排：2018 … 2026 全写出来，最新一年粉笔黄底（框的左右内边距收小，9 个年份一行放得下）。"""
    out, size = '', round(size * K, 1)
    for yy in (ys or YEARS[::-1]):           # 2026 在前
        inner = f'<span class="lat" style="color:{INK}">{yy}</span>' if yy == Y1 else f'<span class="lat">{yy}</span>'
        b = L.badge(inner, size, border=YEL if yy == Y1 else CHALK, fill=YEL if yy == Y1 else 'rgba(0,0,0,.18)', mr=mr)
        out += b.replace('padding:8px 26px 10px', f'padding:6px {pad}px 8px', 1)
    return out


def board(w, h, inner):
    return f'<div class="board"></div><div class="grain"></div>{L.dust(w, h)}{inner}{L.frame(w, h)}'




PLUS = f'<span class="ck" style="color:{CHALK};margin:0 .12em">＋</span>'
JX = '原文解析'                    # 老师的叫法（2026-11-05）：听力原文逐句 + 中文翻译 + 生词


def tags(size, k='tags'):
    """主卖点两个并列大标签：真题（黄块）＋ 原文解析（蓝块），与主标题同一字号下限。"""
    return (f'<div class="ab" data-k="{k}" data-min="{MIN_TITLE}" style="{{pos}};white-space:nowrap;font:900 {fs(size)}/1.22 Black">'
            f'{L.hl("真题", YEL, px=22)}{PLUS}{L.hl(JX, BLU, px=22)}</div>')


# ───────── A：A 版原样式 + 主标题下一行“真题 ＋ 原文解析”两块并列 ─────────
def A(w=1920, h=1080):
    if w < 1900:
        return board(w, h, f"""
<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="left:60px;top:46px;font:900 {fs(128)}/1.18 Black">{L.hl('彻底搞定六级听力', RED, ink='#fff', px=26)}</div>
{seal(1160, 60, 240, rot=6)}
<div class="ab ck" data-k="title" data-min="{MIN_TITLE}" style="left:54px;top:236px;font:900 {fs(230)}/1 Black;letter-spacing:-.02em">{SIX}听力</div>
{tags(158).replace('{pos}', 'left:84px;top:486px')}
{phones(1080, 700, .8)}
<div class="ab ck" data-k="years" data-min="{MIN_SELL}" style="left:60px;top:698px;font:900 {fs(88)}/1.18 Black">
 <span class="lat" style="font-size:1.2em">{y(SPAN)}</span><br>全部真题 {y(N)} 套</div>""")
    return board(w, h, f"""
<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="left:74px;top:40px;font:900 {fs(172)}/1.18 Black">{L.hl('彻底搞定六级听力', RED, ink='#fff', px=32)}</div>
{seal(1590, 46, 252, rot=6)}
<div class="ab ck" data-k="title" data-min="{MIN_TITLE}" style="left:62px;top:272px;font:900 {fs(230)}/1 Black;letter-spacing:-.02em">{SIX}听力</div>
{tags(168).replace('{pos}', 'left:96px;top:520px')}
{phones(1580, 690, .86)}
<div class="ab ck" data-k="years" data-min="{MIN_SELL}" style="left:72px;top:768px;font:900 {fs(108)}/1.2 Black">
 <span class="lat">{y(SPAN)}</span> 全部 {y(N)} 套</div>""")


# ───────── B：主标题一行“六级听力真题 + 原文解析”变成两张粉笔框大卡片，各带一行小说明 ─────────
def card(word, col, note, size, wcard):
    return (f'<div style="position:relative;display:inline-block;vertical-align:top;width:{wcard}px;padding:10px 0 18px;text-align:center;margin-right:36px">'
            f'<i style="position:absolute;inset:0;border:7px solid {col};border-radius:26px;background:rgba(0,0,0,.20);filter:url(#line)"></i>'
            f'<div class="ck" style="position:relative;font:900 {fs(size)}/1.15 Black;color:{col}">{word}</div>'
            f'<div class="ck" data-k="note" data-min="{MIN_SELL}" style="position:relative;font:900 {fs(size * .42)}/1.2 Black;color:{CHALK}">{note}</div></div>')


def B(w=1920, h=1080):
    big = w >= 1900
    sz = 176 if big else 150
    c1 = card('真题', YEL, '视频版考试', sz, round(sz * 2.7))
    c2 = card(JX, PNK, '逐句·翻译·生词', sz, round(sz * 4.7))
    return board(w, h, f"""
<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="left:{74 if big else 60}px;top:{40 if big else 46}px;font:900 {fs(172 if big else 128)}/1.18 Black">{L.hl('彻底搞定六级听力', RED, ink='#fff', px=32 if big else 26)}</div>
{seal(1590 if big else 1160, 46 if big else 60, 252 if big else 240, rot=6)}
<div class="ab ck" data-k="title" data-min="{MIN_TITLE}" style="left:62px;top:{262 if big else 236}px;font:900 {fs(200 if big else 190)}/1 Black">{SIX}听力</div>
<div class="ab" data-k="tags" data-min="{MIN_TITLE}" style="left:{70 if big else 60}px;top:{490 if big else 456}px;white-space:nowrap">{c1}{c2}</div>
<div class="ab ck" data-k="years" data-min="{MIN_SELL}" style="left:72px;top:{820 if big else 800}px;font:900 {fs(96 if big else 84)}/1.2 Black">
 <span class="lat">{y(SPAN)}</span> 全部 {y(N)} 套</div>""")


# ───────── C：主标题两行“六级听力 / 真题＋原文解析”纯粉笔字（不加块），钩子红块压在下面 ─────────
def C(w=1920, h=1080):
    big = w >= 1900
    return board(w, h, f"""
<div class="ab ck" data-k="title" data-min="{MIN_TITLE}" style="left:62px;top:50px;font:900 {fs(236 if big else 214)}/1 Black;letter-spacing:-.02em">{SIX}听力</div>
{seal(1590 if big else 1160, 46 if big else 60, 252 if big else 240, rot=6)}
<div class="ab ck" data-k="tags" data-min="{MIN_TITLE}" style="left:62px;top:{318 if big else 312}px;white-space:nowrap;font:900 {fs(190 if big else 156)}/1 Black">
 <span style="color:{YEL}">真题</span><span style="color:{CHALK}">＋</span><span style="color:{BLU}">{JX}</span></div>
<div class="ab ck" data-k="years" data-min="{MIN_SELL}" style="left:72px;top:{560 if big else 530}px;font:900 {fs(100 if big else 88)}/1.2 Black">
 <span class="lat">{y(SPAN)}</span> 全部 {y(N)} 套</div>
<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="left:{90 if big else 70}px;top:{760 if big else 720}px;font:900 {fs(160 if big else 126)}/1.18 Black">{L.hl('彻底搞定六级听力', RED, ink='#fff', px=30)}</div>""")


DIRS = {'A': A, 'B': B, 'C': C}


def render(br, body, w, h, name, out):
    html = WORK / f'{name}.html'
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{L.css(w, h)}</style></head>'
                    f'<body>{L.SVG_DEFS}{body}</body></html>', 'utf-8')
    pg = br.new_page(viewport={'width': w, 'height': h}, device_scale_factor=2)
    pg.goto(html.as_uri())
    pg.evaluate('document.fonts.ready.then(() => [...document.fonts].forEach(f => f.load()))')
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(500)
    res = pg.evaluate(W.CHECK_JS)
    png = out / f'{name}.png'
    pg.screenshot(path=str(png))
    pg.close()
    return png, res


def selftest(br):
    global K
    bad = []
    for k, f in DIRS.items():
        for w in (1920, 1440):
            for kk in (1.0, 0.4):           # 0.4：钩子放大后 ×0.5 仍高于下限（B 16:9 钩子 164px）
                K = kk
                body = f(w, 1080)
                _, res = render(br, body, w, 1080, f'自检_{k}_{w}', WORK)
                hit = {x.split()[0] for x in res['problems'] if '缩略图字高' in x}
                need = set(re.findall(r'data-k="(\w+)" data-min=', body)) if kk < 1 else set()
                if kk < 1 and not {'hook', 'years', 'title', 'tags'} <= need:
                    bad.append(f'{k}{w} 缺少 data-min 元素：{sorted(need)}')
                if hit != need:
                    bad.append(f'{k}{w} 字号×{kk}：报出 {sorted(hit)}，应为 {sorted(need)}')
    K = 1.0
    return bad


def main(args):
    from playwright.sync_api import sync_playwright
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    bad = []
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        if args[0] == '--自检':
            bad = selftest(br)
            br.close()
            print('\n'.join(bad) or '自检通过：字号×0.4 时每个 data-min 元素全部报出，正常字号不报（A/B/C × 16:9、4:3）')
            return 1 if bad else 0
        final = args[1] if args[0] == '定稿' else None
        stem = f'六级听力真题与原文解析{N}套_封面'
        jobs = []
        for k, f in DIRS.items():
            if final is None:
                jobs += [(f(1920, 1080), 1920, 1080, f'草稿_{k}_16比9', WORK), (f(1440, 1080), 1440, 1080, f'草稿_{k}_4比3', WORK)]
            elif k == final:
                jobs += [(f(1920, 1080), 1920, 1080, f'{stem}_16比9', OUT, True), (f(1440, 1080), 1440, 1080, f'{stem}_4比3', OUT, True)]
            else:
                jobs.append((f(1920, 1080), 1920, 1080, f'{stem}备选{k}_16比9', OUT, False))
        for job in jobs:
            body, w, h, name, out = job[:5]
            keep_png = job[5] if len(job) > 5 else True
            png, res = render(br, body, w, h, name, out)
            im = Image.open(png).convert('RGB')
            assert im.size == (w * 2, h * 2), im.size
            th = round(w * 180 / h)
            im.resize((th, 180), Image.LANCZOS).save(WORK / f'{name}_320.png')
            im.resize((th * 3, 540), Image.LANCZOS).save(WORK / f'{name}_960.png')
            if out is OUT:
                jpg = png.with_suffix('.jpg')
                im.save(jpg, quality=92, optimize=True, progressive=True)
                print(f'{jpg.name} {jpg.stat().st_size / 1e6:.1f} MB')
                if not keep_png:
                    png.unlink()
            bad += [f'{name}: {x}' for x in res['problems']]
        br.close()
    if bad:
        print('自查不通过：\n  ' + '\n  '.join(bad))
        return 1
    print('自查通过：缩略图字高达标、文字不出画、不压木框、不进底角遮挡区、互不重叠、字体全部加载')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['草稿']))
