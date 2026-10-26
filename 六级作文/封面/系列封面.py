"""六级写作 B 站封面（2026-10-26）：教室黑板主题，与六级阅读封面（六级/封面/系列封面.py，用户定稿 B）同一系列。

    /opt/ttsenv/bin/python 六级作文/封面/系列封面.py 草稿        # A/B/C 三个方向 16:9 只出 320×180、960×540 缩略图到 work/
    /opt/ttsenv/bin/python 六级作文/封面/系列封面.py 定稿 A      # A 出 16:9 + 4:3（PNG + JPG）到 系列封面/，B、C 的 16:9 JPG 作备选
    /opt/ttsenv/bin/python 六级作文/封面/系列封面.py --自检      # 双向验证：字号×0.5 时每个 data-min 元素都要报，正常字号 0 处

用户要求（2026-10-26）：特别吸引 B 站用户点进来；突出“彻底解决写作问题”“真题范文、满分范文”；所有年份写好；关键字一眼看到。
按信息流缩略图（320×180）设计（踩坑 76）：一个焦点（六级写作 / 真题满分范文）+ 一个钩子（彻底解决写作问题），其余卖点（年份、篇数、词数）次要。
封面上的数字全部从 六级/作文/<年>.json 现算（篇数、每次考试的套数、词数范围按 tools/作文规则.counted），不手写（踩坑 70）；不印“02 / 09”编号。
渲染后程序自查：文字不出画、不压木框、不进 B 站底角遮挡区、互不重叠、字体全部加载；data-min 元素缩到高 180 后最小字号不低于下限
（主标题 24、钩子 13、卖点 10 像素，同 专八/封面/系列封面.py）。
"""
import importlib.util
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORK = HERE / 'work'
OUT = HERE / '系列封面'
ASSETS = HERE / '素材'
sys.path.insert(0, str(REPO / 'tools'))
import 作文规则  # noqa: E402

_spec = importlib.util.spec_from_file_location('cet6_cover', REPO / '六级/封面/系列封面.py')
L = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L)        # 黑板主题：配色、滤镜、木框、粉笔涂块、粉笔框标签、纸飞机

# ───────── 数字现算 ─────────
ESSAYS = [e for y in range(2015, 2100) if (REPO / f'六级/作文/{y}.json').exists()
          for e in json.loads((REPO / f'六级/作文/{y}.json').read_text('utf-8'))]
N = len(ESSAYS)
WC = [作文规则.counted(e) for e in ESSAYS]
EXAMS = OrderedDict()                                  # 年 → {月: 套数}
for e in sorted(ESSAYS, key=lambda e: e['id'], reverse=True):
    y, m, _ = e['id'][1:].split('-')
    EXAMS.setdefault(int(y), OrderedDict()).setdefault(int(m), 0)
    EXAMS[int(y)][int(m)] += 1
YEARS = sorted(EXAMS)
Y0, Y1 = YEARS[0], YEARS[-1]
NEWEST = f'{Y1}.{max(EXAMS[Y1])}'
N_EXAM = sum(len(v) for v in EXAMS.values())
assert (N, N_EXAM, Y0, Y1, min(WC), max(WC)) == (31, 11, 2021, 2026, 190, 200), (N, N_EXAM, Y0, Y1, min(WC), max(WC))  # 数据一变先核对封面说法
assert YEARS == list(range(Y0, Y1 + 1))               # 年份连续，“2021—2026 全部”才成立

BOARD, CHALK, YEL, PNK, BLU, INK, HOT = L.BOARD, L.CHALK, L.YEL, L.PNK, L.BLU, L.INK, L.HOT
RED = '#ff6b6b'                                        # 粉笔红：钩子
MIN_TITLE, MIN_HOOK, MIN_SELL = 24, 13, 10
K = 1.0                                                # 字号系数：只给 --自检 用


def fs(n):
    return f'{n * K:.0f}px'


def y(t):
    return f'<span style="color:{YEL}">{t}</span>'


SIX = f'<span style="color:{HOT}">六级</span>'


def shot():
    return (ASSETS / '2021年6月第2套_第1句.jpg').as_uri()


def card(x, y_, w, rot=-3):
    return (f'<img class="card" data-k="card1" src="{shot()}" style="left:{x}px;top:{y_}px;width:{w}px;transform:rotate({rot}deg)">'
            f'<div class="tape" style="left:{x + w / 2 - 60}px;top:{y_ - 22}px;transform:rotate(-6deg)"></div>')


def seal(x, y_, d, rot=8):
    """“2026.6 已更新”粉笔红圆章。"""
    return (f'<div class="ab" data-k="seal" data-min="{MIN_SELL}" style="left:{x}px;top:{y_}px;width:{d}px;height:{d}px;transform:rotate({rot}deg);'
            f'display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.05;color:#fff">'
            f'<i style="position:absolute;inset:0;border-radius:50%;background:{RED};filter:url(#rough);box-shadow:0 8px 0 rgba(0,0,0,.3)"></i>'
            f'<i style="position:absolute;inset:{d * .06:.0f}px;border-radius:50%;border:5px dashed rgba(255,255,255,.75)"></i>'
            f'<span class="lat ck" style="position:relative;font-size:{fs(d * .26)}">{NEWEST}</span>'
            f'<span class="ck" style="position:relative;font:900 {fs(d * .25)}/1.15 Black">已更新</span></div>')


def years(size, mr=16, label=True):
    """年份一排：2021 … 2026 全写出来，最新一年粉笔黄底。"""
    out, size = '', round(size * K, 1)
    for yy in YEARS:
        if yy == Y1:
            out += L.badge(f'<span class="lat" style="color:{INK}">{yy}</span>', size, border=YEL, fill=YEL, mr=mr)
        else:
            out += L.badge(f'<span class="lat">{yy}</span>', size, mr=mr)
    return out


def underline(w, col=YEL):
    return (f'<svg width="{w}" height="26" viewBox="0 0 {w} 26" style="display:block;overflow:visible" filter="url(#line)">'
            f'<path d="M6 16 C {w * .3} 6, {w * .65} 22, {w - 6} 9" fill="none" stroke="{col}" stroke-width="9" stroke-linecap="round"/></svg>')


def board(w, h, inner):
    return f'<div class="board"></div><div class="grain"></div>{L.dust(w, h)}{inner}{L.frame(w, h)}'


# ───────── A：标题特大 + 右侧真实画面 + 年份一排 ─────────
def A(w=1920, h=1080):
    if w < 1900:
        return A43(w, h)
    return board(w, h, f"""
<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="left:70px;top:56px;font:900 {fs(104)}/1.2 Black">{L.hl('彻底解决写作问题', RED, ink='#fff', px=26)}</div>
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:62px;top:228px;line-height:1">
 <div class="ck" style="font:900 {fs(250)}/1 Black;letter-spacing:-.02em">{SIX}写作</div>
 <div class="ck" style="font:900 {fs(172)}/1 Black;color:{YEL};margin-top:34px;letter-spacing:.01em">真题满分范文</div></div>
{card(1210, 368, 620)}
{seal(1556, 48, 280, rot=6)}
<div class="ab" data-k="years" data-min="{MIN_SELL}" style="left:66px;top:752px">{years(64)}</div>
<div class="ab ck" data-k="sell" data-min="{MIN_SELL}" style="left:72px;top:866px;font:900 {fs(66)}/1.2 Black">
 全部真题 {y(N)} 篇 · 逐句精读 · 模板句式</div>""")


def A43(w=1440, h=1080):
    return board(w, h, f"""
<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="left:60px;top:52px;font:900 {fs(96)}/1.2 Black">{L.hl('彻底解决写作问题', RED, ink='#fff', px=24)}</div>
{seal(1104, 44, 262, rot=6)}
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:54px;top:222px;line-height:1">
 <div class="ck" style="font:900 {fs(236)}/1 Black;letter-spacing:-.02em">{SIX}写作</div>
 <div class="ck" style="font:900 {fs(164)}/1 Black;color:{YEL};margin-top:32px">真题满分范文</div></div>
{card(1084, 372, 320, rot=4)}
<div class="ab" data-k="years" data-min="{MIN_SELL}" style="left:58px;top:704px">{years(60, mr=14)}</div>
<div class="ab ck" data-k="sell" data-min="{MIN_SELL}" style="left:64px;top:836px;font:900 {fs(64)}/1.2 Black">
 全部真题 {y(N)} 篇 · 逐句精读 · 模板句式</div>""")


# ───────── B：钩子打头、居中对称（无截图） ─────────
def B(w=1920, h=1080):
    c = w / 2
    big = 1 if w >= 1900 else .82
    return board(w, h, f"""
{L.plane(w - 470 * big, 40, .9 * big)}
<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="left:{c}px;transform:translateX(-50%);top:58px;font:900 {fs(118 * big)}/1.15 Black;color:{CHALK}">
 <span class="ck">彻底解决</span><span class="ck" style="color:{RED}">写作问题</span><span class="ck">！</span></div>
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:{c}px;transform:translateX(-50%);text-align:center;top:{236 * big + 10:.0f}px;line-height:1">
 <div class="ck" style="font:900 {fs(236 * big)}/1 Black">{SIX}写作</div>
 <div style="font:900 {fs(178 * big)}/1.2 Black;margin-top:22px">{L.hl('真题满分范文', YEL, px=28)}</div></div>
<div class="ab" data-k="years" data-min="{MIN_SELL}" style="left:{c}px;transform:translateX(-50%);top:{745 if big == 1 else 690}px">{years(64 if big == 1 else 62, mr=14)}</div>
<div class="ab ck" data-k="sell" data-min="{MIN_SELL}" style="left:{c}px;transform:translateX(-50%);top:{870 if big == 1 else 912}px;font:900 {fs(64 * big if big == 1 else 60)}/1.2 Black">
 {y(N_EXAM)} 次考试 {y(N)} 篇 · 篇篇满分</div>""")


# ───────── C：左标题 + 右“年份清单”黑板（每次考试都列出） ─────────
def C(w=1920, h=1080):
    rows = ''
    for yy in reversed(YEARS):
        ms = EXAMS[yy]
        mon = ' · '.join(f'{m}月' for m in sorted(ms, reverse=True))
        rows += (f'<div style="display:flex;align-items:baseline;gap:26px;padding:4px 0">'
                 f'<span class="lat" style="color:{YEL if yy == Y1 else CHALK};min-width:2.6em">{yy}</span>'
                 f'<span style="font-family:Black">{mon}</span>'
                 f'<span style="margin-left:auto;color:{PNK};font-family:Black">{sum(ms.values())}篇</span></div>')
    return board(w, h, f"""
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:66px;top:70px;line-height:1">
 <div class="ck" style="font:900 {fs(232)}/1 Black">{SIX}写作</div>
 <div class="ck" style="font:900 {fs(156)}/1 Black;color:{YEL};margin-top:34px">真题满分范文</div></div>
<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="left:66px;top:520px;font:900 {fs(110)}/1.2 Black">
 <span class="ck">彻底解决</span><br><span class="ck" style="color:{RED}">写作问题</span><span class="ck">！</span></div>
<div class="ab ck" data-k="sell" data-min="{MIN_SELL}" style="left:72px;top:820px;font:900 {fs(62)}/1.2 Black">每篇 {y(f'{min(WC)}—{max(WC)}')} 词 · 逐句精读</div>
<div class="ab" data-k="years" data-min="{MIN_SELL}" style="left:1090px;top:74px;width:770px;padding:26px 44px 30px;font:800 {fs(66)}/1.18 Inter">
 <i style="position:absolute;inset:0;border:6px solid {CHALK};border-radius:22px;background:rgba(0,0,0,.20);filter:url(#line)"></i>
 <div class="ck" style="position:relative;font:900 {fs(62)}/1.3 Black;color:{BLU};margin-bottom:8px">{Y0}—{Y1} 全部真题</div>
 <div class="ck" style="position:relative">{rows}</div></div>""")


DIRS = {'A': A, 'B': B, 'C': C}

CHECK_JS = r"""
() => {
  const W = innerWidth, H = innerHeight, out = [];
  const r = [...document.querySelectorAll('[data-k]')].map(e => { const b = e.getBoundingClientRect(); return {k: e.dataset.k, x0: b.left, y0: b.top, x1: b.right, y1: b.bottom}; });
  for (const a of r) {
    const card = a.k.startsWith('card');
    if (!card && (a.x0 < 24 || a.y0 < 24 || a.x1 > W - 24 || a.y1 > H - 52)) out.push(`${a.k} 出画/压到木框 ${JSON.stringify(a)}`);
    if (card && (a.x1 > W - 10 || a.y1 > H - 46)) out.push(`${a.k} 压到木框`);
    if (!card && a.y1 > H * 0.88 && (a.x0 < W * 0.25 || a.x1 > W * 0.75)) out.push(`${a.k} 进入底角遮挡区`);
  }
  for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) {
    const a = r[i], b = r[j];
    const ox = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), oy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
    if (ox > 0 && oy > 0) out.push(`${a.k} 与 ${b.k} 重叠 ${ox.toFixed(0)}×${oy.toFixed(0)}`);
  }
  // 文字（含居中整行的 data-k）不得盖住截图：逐个文字节点量真实字框
  const cards = [...document.querySelectorAll('.card')].map(e => e.getBoundingClientRect());
  for (const e of document.querySelectorAll('[data-k]:not(.card)')) {
    const tw = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
    for (let t; (t = tw.nextNode());) if (t.textContent.trim()) {
      const rg = document.createRange(); rg.selectNodeContents(t);
      for (const q of rg.getClientRects()) {
        if (q.left < 24 || q.right > W - 24) out.push(`${e.dataset.k} 文字出画「${t.textContent.trim()}」`);
        for (const c of cards) if (q.right > c.left && q.left < c.right && q.bottom > c.top && q.top < c.bottom) out.push(`${e.dataset.k} 文字压到截图「${t.textContent.trim()}」`);
      }
    }
  }
  // 信息流缩略图字号：整张缩到高 180 后，data-min 元素里最小的字不得低于下限
  for (const e of document.querySelectorAll('[data-min]')) {
    const tw = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
    let m = 1e9;
    for (let t; (t = tw.nextNode());) if (t.textContent.trim()) m = Math.min(m, parseFloat(getComputedStyle(t.parentElement).fontSize));
    const px = m * 180 / H;
    if (px < +e.dataset.min) out.push(`${e.dataset.k} 缩略图字高 ${px.toFixed(1)}px < 下限 ${e.dataset.min}px（320×180）`);
  }
  const fonts = [...document.fonts].filter(f => f.status !== 'loaded').map(f => f.family);
  if (fonts.length) out.push('字体未加载: ' + fonts.join(','));
  return {problems: out, boxes: r};
}"""


def render(br, body, w, h, name, out):
    html = WORK / f'{name}.html'
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{L.css(w, h)}</style></head>'
                    f'<body>{L.SVG_DEFS}{body}</body></html>', 'utf-8')
    pg = br.new_page(viewport={'width': w, 'height': h}, device_scale_factor=2)
    pg.goto(html.as_uri())
    pg.evaluate('document.fonts.ready.then(() => [...document.fonts].forEach(f => f.load()))')
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(500)
    res = pg.evaluate(CHECK_JS)
    png = out / f'{name}.png'
    pg.screenshot(path=str(png))
    pg.close()
    return png, res


def selftest(br):
    global K
    bad = []
    for k, f in DIRS.items():
        for w in (1920, 1440):
            for kk in (1.0, 0.5):
                K = kk
                body = f(w, 1080)
                _, res = render(br, body, w, 1080, f'自检_{k}_{w}', WORK)
                hit = {x.split()[0] for x in res['problems'] if '缩略图字高' in x}
                need = set(re.findall(r'data-k="(\w+)" data-min=', body)) if kk < 1 else set()
                if kk < 1 and not {'title', 'hook', 'years'} <= need:
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
            print('\n'.join(bad) or '自检通过：字号×0.5 时每个 data-min 元素全部报出，正常字号不报（A/B/C × 16:9、4:3）')
            return 1 if bad else 0
        final = args[1] if args[0] == '定稿' else None
        jobs = []
        for k, f in DIRS.items():
            if final is None:
                jobs += [(f(1920, 1080), 1920, 1080, f'草稿_{k}_16比9', WORK, False)]
            elif k == final:
                jobs += [(f(1920, 1080), 1920, 1080, f'六级写作真题满分范文{N}篇_封面_16比9', OUT, True),
                         (f(1440, 1080), 1440, 1080, f'六级写作真题满分范文{N}篇_封面_4比3', OUT, True)]
            else:
                jobs.append((f(1920, 1080), 1920, 1080, f'六级写作真题满分范文{N}篇_封面备选{k}_16比9', OUT, False))
        for body, w, h, name, out, keep_png in jobs:
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
    print('自查通过：缩略图字高达标、文字不出画、不压木框、不进底角遮挡区、不压截图、互不重叠、字体全部加载')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['草稿']))
