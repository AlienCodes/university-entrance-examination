"""四级听力 B 站系列封面（2026-11-06）：沿用「四级写作」封面风格（四级作文/封面/系列封面.py：配色、字体、版式、圆章、真实画面卡片）。

    python3 四级/听力/封面/系列封面.py 草稿        # A/B/C 三个方向 16:9 + 4:3，只出 320×180、960×540 缩略图到 work/
    python3 四级/听力/封面/系列封面.py 定稿 A      # 定稿出 16:9 + 4:3（PNG + JPG）到 系列封面/，另两个方向 16:9 JPG 作备选
    python3 四级/听力/封面/系列封面.py --自检      # 双向验证：正常 0；字号×0.5、放回年份、写死套数、出现任何数字、缺字、圆章字出圆、缺必有的话都报

老师要求（2026-11-06）：
- 风格与四级写作封面一样，不能与六级听力（黑板）同一风格——两个系列并排要一眼分得开；
- 封面上绝对不出现任何年份（每年加新听力不换封面），用“持续更新 / 最新真题”；套数不写死，用“历年真题全收录”；
- 两种视频都要突出：视频版真题考试（真题）＋ 原文逐句精读（原文解析）；手机信息流 320×180 一眼看清。
程序自查：四级写作的 CHECK_JS（不出画、不进底角遮挡区、不重叠、不压截图、圆章字在圆内、字体加载、缩略图字高 主标题 24 / 钩子 13 / 卖点 10 像素）
＋ text_problems（每个字在所用字体 cmap 里；画面文字不许有任何数字——年份、套数都不许；“N 套”中文数字也报；必有的话都在）。
耳机图标（老师 2026-11-06）：A 中间空白放自己画的 SVG 头戴式耳机（headphones，墨绿头梁＋红耳罩＋黄高光＋投影＋声波，倾斜 −10°），data-k=phones 一起查出画、重叠；4:3 红章缩到 300 移到右上角给耳机腾位置。
素材：画面_原文解析.webp = 已发布的 cet4-listening-202506-1-text.mp4 第 200 秒一帧，裁掉顶部（印着年份月份）和底部（句号进度 “31 / 200”）。
"""
import importlib.util
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
WORK = HERE / 'work'
OUT = HERE / '系列封面'
SHOT = HERE / '画面_原文解析.webp'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


W4 = _load('cet4w_cover', REPO / '四级作文/封面/系列封面.py')     # 四级写作：配色、字体、css、CHECK_JS、cmap
PAPER, GREEN, RED, INK, YEL, CREAM = W4.PAPER, W4.GREEN, W4.RED, W4.INK, W4.YEL, W4.CREAM
FONTS = W4.FONTS
MIN_TITLE, MIN_HOOK, MIN_SELL = 24, 13, 10
MUST = ['彻底搞定四级听力', '真题', '原文解析', '持续更新', '历年真题全收录']
K = 1.0          # 字号系数（只给 --自检 用）
EXTRA = ''       # 自检时往画面里塞的东西
SEAL_R = .28     # 圆章字号 / 直径（自检放大到 .40 必须报“字出了圆”）
JX = '原文解析'


def fs(n):
    return f'{n * K:.0f}px'


def seal(x, y, d, bg=RED, fg='#fff', rot=-8, ring='rgba(255,255,255,.8)'):
    """“持续更新”圆章（钩子；四级写作是“2026.6 已更新”，听力不写年份）。"""
    return (f'<div class="ab" data-k="seal" data-min="{MIN_HOOK}" data-round="1" style="left:{x}px;top:{y}px;width:{d}px;height:{d}px;border-radius:50%;'
            f'background:{bg};color:{fg};transform:rotate({rot}deg);display:flex;flex-direction:column;align-items:center;justify-content:center;'
            f'box-shadow:0 10px 24px rgba(0,0,0,.28);line-height:1.08">'
            f'<i style="position:absolute;inset:{d * .055:.0f}px;border-radius:50%;border:{max(3, d * .016):.0f}px dashed {ring}"></i>'
            f'<span style="font:900 {fs(d * SEAL_R)} Black">持续</span>'
            f'<span style="font:900 {fs(d * SEAL_R)} Black">更新</span></div>')


PHONES_V = 1     # 耳机配色方案（草稿比过 1/2，定稿用 1）


def headphones(x, y, s, rot=-10, v=None):
    """头戴式耳机（自己画的 SVG，老师 2026-11-06）：墨绿头梁 ＋ 红耳罩（厚度、内衬、黄高光、柔和投影）＋ 两侧声波，略微倾斜。
    s = 宽（px），高 = s × 0.8；data-k 让 CHECK_JS 一起查出画、重叠。"""
    v = v or PHONES_V
    band, cup, cupd, pad = (GREEN, RED, '#7f1717', INK) if v == 1 else (RED, GREEN, '#0d3524', INK)
    wave1, wave2 = (YEL, RED) if v == 1 else (YEL, GREEN)
    def side(cx, m):      # m = 1 右、-1 左；耳罩朝里有厚度
        return f'''
  <rect x="{cx - 9}" y="112" width="18" height="34" rx="6" fill="{pad}"/>
  <rect x="{cx - 4}" y="114" width="5" height="28" rx="2" fill="#fff" opacity=".25"/>
  <ellipse cx="{cx - m * 13}" cy="172" rx="30" ry="45" fill="{pad}"/>
  <ellipse cx="{cx - m * 7}" cy="172" rx="33" ry="47" fill="{cupd}"/>
  <ellipse cx="{cx + m * 3}" cy="170" rx="33" ry="47" fill="url(#cg{v})"/>
  <ellipse cx="{cx + m * 3}" cy="170" rx="22" ry="33" fill="none" stroke="{YEL}" stroke-width="4" opacity=".9"/>
  <ellipse cx="{cx + m * 3}" cy="170" rx="9" ry="13" fill="{cupd}" opacity=".55"/>
  <path d="M{cx + m * 3 - 20} {148} Q{cx + m * 3 - 12} {130} {cx + m * 3 + 4} {128}" stroke="#fff" stroke-width="6" stroke-linecap="round" fill="none" opacity=".75"/>'''
    waves = ''.join(
        f'<path d="M{150 + m * (130 + 14 * i)} {172 - 22 - 9 * i} Q{150 + m * (142 + 16 * i)} 172 {150 + m * (130 + 14 * i)} {172 + 22 + 9 * i}" '
        f'stroke="{wave1 if i == 0 else wave2}" stroke-width="{7 - i}" stroke-linecap="round" fill="none" opacity="{1 - .25 * i}"/>'
        for m in (1, -1) for i in (0, 1))
    return f'''<svg class="ab" data-k="phones" viewBox="0 0 300 240" style="left:{x}px;top:{y}px;width:{s}px;height:{s * .8:.0f}px;overflow:visible">
 <defs>
  <radialGradient id="cg{v}" cx=".38" cy=".32" r=".8"><stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset=".35" stop-color="{cup}"/><stop offset="1" stop-color="{cupd}"/></radialGradient>
  <linearGradient id="bg{v}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".25"/><stop offset=".5" stop-color="{band}" stop-opacity="0"/></linearGradient>
  <filter id="sh{v}" x="-20%" y="-20%" width="150%" height="160%"><feDropShadow dx="7" dy="12" stdDeviation="7" flood-color="#000" flood-opacity=".28"/></filter>
 </defs>
 <g transform="rotate({rot} 150 130)">
  {waves}
  <g filter="url(#sh{v})">
   <path d="M86 128 C76 18, 224 18, 214 128" stroke="{pad}" stroke-width="31" stroke-linecap="round" fill="none"/>
   <path d="M86 128 C76 18, 224 18, 214 128" stroke="{band}" stroke-width="23" stroke-linecap="round" fill="none"/>
   <path d="M86 128 C76 18, 224 18, 214 128" stroke="url(#bg{v})" stroke-width="23" stroke-linecap="round" fill="none"/>
   <path d="M104 64 C125 36, 175 36, 196 64" stroke="{YEL}" stroke-width="4" stroke-linecap="round" fill="none" opacity=".85"/>
   {side(86, -1)}{side(214, 1)}
  </g>
 </g>
</svg>'''


TING_V = 2       # “听力”两个字的配色（老师 2026-11-06：要另一个颜色、非常引人注目；比过 1 墨绿 / 2 亮黄黑描边 / 3 白字绿描边，定稿 2）

SIJI = '#ff2e88'  # “四级”两字用亮粉（老师 2026-11-06：B 站标题那种粉、更显眼；比过 #FB7299 / #ff4f9a / #ff2e88 / #ff1f7a）

def ting(v=None, color=None):
    """“四级”“听力”同一种描边＋投影效果（老师 2026-11-06：两个同步，“四级”颜色不变用红）。"""
    v = v or TING_V
    if v == 1:     # 墨绿
        return f'color:{color or GREEN}'
    if v == 2:     # 亮黄字 ＋ 黑描边 ＋ 墨绿错位投影
        return f'color:{color or YEL};-webkit-text-stroke:14px {INK};paint-order:stroke fill;text-shadow:10px 10px 0 {GREEN}'
    return f'color:#fff;-webkit-text-stroke:14px {GREEN};paint-order:stroke fill;text-shadow:10px 10px 0 {YEL}'   # 3：白字 ＋ 墨绿描边 ＋ 黄投影（缩略图里看不清，不用）


def card(x, y, w, rot=3):
    return f'<img class="card" data-k="card" src="{SHOT.as_uri()}" style="left:{x}px;top:{y}px;width:{w}px;transform:rotate({rot}deg)">'


def two(size, pad):
    """“真题 ＋ 原文解析”：墨绿实底白字（与四级写作「四级真题范文」同一块）。"""
    return (f'font:900 {fs(size)}/1 Black;color:#fff;background:{GREEN};padding:{size * .16:.0f}px {size * .22:.0f}px {size * .2:.0f}px;box-shadow:12px 12px 0 {RED}">'
            f'真题<span style="color:{YEL};margin:0 .1em">＋</span>{JX}')


# ───────── A：四级写作定稿同版式（米白纸面 ＋ 真实画面 ＋ 红圆章） ─────────
def A(w=1920, h=1080):
    wide = w >= 1900
    t = 250 if wide else 220
    sub = 150 if wide else 146
    left = 74 if wide else 60
    return f"""
<div style="position:absolute;inset:0;background:{PAPER}"></div>
<div style="position:absolute;left:0;top:0;width:{w}px;height:22px;background:{GREEN}"></div>
<div style="position:absolute;left:{left}px;top:22px;width:{w - 2 * left}px;height:4px;background:{RED}"></div>
<div class="ab" data-k="sell" data-min="{MIN_SELL}" style="left:{left}px;top:44px;font:900 {fs(64)}/1.2 SerifSC;color:{GREEN};letter-spacing:.02em">
 历年真题全收录 · <span style="color:{RED}">逐句精读</span></div>
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:{left - 8}px;top:{128 if wide else 140}px;font:900 {fs(t)}/1.04 Black;color:{INK};letter-spacing:-.02em">
 <div>彻底搞定</div><div><span style="{ting(color=SIJI)}">四级</span><span data-ting="1" style="{ting()}">听力</span></div></div>
<div class="ab" data-k="sub" data-min="{MIN_TITLE}" style="left:{left}px;top:{t * 2.08 + (150 if wide else 168):.0f}px;{two(sub, 0)}</div>
{card(1260, 560, 620, rot=3) if wide else card(1020, 850, 380, rot=4)}
{seal(1520, 50, 340) if wide else seal(1080, 44, 300)}
{headphones(1068, 130, 420) if wide else headphones(1112, 375, 300)}
{EXTRA}"""


# ───────── B：深绿底 · 居中大字（四级写作备选 B 同版式） ─────────
def B(w=1920, h=1080):
    wide = w >= 1900
    c = w / 2
    t = 200 if wide else 156
    sub = 150 if wide else 146
    tops = (40, 150, 380, 640) if wide else (36, 136, 330, 570)
    sl = seal(1580, 600, 300, rot=-6) if wide else seal(c - 170, 680, 340, rot=-6)
    return f"""
<div style="position:absolute;inset:0;background:radial-gradient(ellipse at 50% 40%, #236a4f 0%, {GREEN} 55%, #123b2b 100%)"></div>
<div class="ab" data-k="sell" data-min="{MIN_SELL}" style="left:{c}px;transform:translateX(-50%);top:{tops[0]}px;font:900 {fs(66)}/1.2 Black;color:{CREAM}">
 大学英语四级 · <span style="color:{YEL}">历年真题全收录</span></div>
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:{c}px;transform:translateX(-50%);top:{tops[1]}px;font:900 {fs(t)}/1.1 Black;color:#fff;letter-spacing:-.01em">
 彻底搞定<span style="color:{YEL}">四级</span>听力</div>
<div class="ab" data-k="sub" data-min="{MIN_TITLE}" style="left:{c}px;transform:translateX(-50%);top:{tops[2]}px;font:900 {fs(sub)}/1 Black;color:{INK};background:{YEL};padding:{sub * .14:.0f}px {sub * .26:.0f}px {sub * .18:.0f}px;border-radius:14px;box-shadow:0 14px 0 #0b2a1e">
 真题<span style="color:{RED};margin:0 .1em">＋</span>{JX}</div>
<div class="ab" data-k="sell2" data-min="{MIN_SELL}" style="left:{c}px;transform:translateX(-50%);top:{tops[3]}px;font:900 {fs(64)}/1.2 Black;color:{CREAM}">
 逐句精读 · 中文翻译 · 答案精讲</div>
{sl}
{EXTRA}"""


# ───────── C：黄黑撞色（四级写作备选 C 同版式）＋ 真实画面 ─────────
def C(w=1920, h=1080):
    wide = w >= 1900
    left = 84 if wide else 60
    return f"""
<div style="position:absolute;inset:0;background:{YEL}"></div>
<div class="ab" data-k="sell" data-min="{MIN_SELL}" style="left:{left}px;top:48px;font:900 {fs(64 if wide else 62)}/1.2 Black;color:{INK}">
 大学英语四级 · 历年真题全收录</div>
<div class="ab" data-k="sub" data-min="{MIN_TITLE}" style="left:{left - 6}px;top:130px;font:900 {fs(200 if wide else 150)}/1 Black;color:{INK};letter-spacing:-.02em">
 真题<span style="color:{RED}">＋</span>{JX}</div>
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:{left}px;top:{390 if wide else 350}px;font:900 {fs(150)}/1.2 Black;color:#fff;background:{INK};padding:0 30px 6px">
 彻底搞定<span style="color:{YEL}">四级听力</span></div>
<div class="ab" data-k="sell2" data-min="{MIN_SELL}" style="left:{left}px;top:{630 if wide else 590}px;font:900 {fs(64)}/1.2 Black;color:{INK}">
 视频版考试 · 逐句精读</div>
{card(1130, 650, 660, rot=-3) if wide else card(70, 740, 560, rot=-2)}
{seal(1500, 520, 340, rot=10) if wide else seal(1052, 570, 340, rot=6)}
{EXTRA}"""


DIRS = {'A': A, 'B': B, 'C': C}


def no_year_problems(text):
    """画面文字（老师 2026-11-06）：不许有任何数字（年份、套数、期数都会过时），中文数字＋套也报。"""
    t = text.translate({0xFF10 + i: 0x30 + i for i in range(10)})
    out = ['年份 ' + m.group() for m in re.finditer(r'(?<!\d)(19|20)\d\d(?!\d)', t)]
    out += ['数字 ' + m.group() for m in re.finditer(r'\d+', t) if not re.fullmatch(r'(19|20)\d\d', m.group())]
    out += ['套数 ' + m.group() for m in re.finditer(r'[一二两三四五六七八九十百]+\s*套', t)]
    return out


def text_problems(res):
    out = []
    for fam, t in res['texts']:
        f0 = fam.split(',')[0].strip().strip('"\'')
        if f0 not in FONTS:
            out.append(f'「{t.strip()}」用了不认识的字体 {fam}')
            continue
        miss = {ch for ch in t if not ch.isspace() and ord(ch) not in W4.cmap(f0)}
        if miss:
            out.append(f'「{t.strip()}」{f0} 缺字 {"".join(sorted(miss))}（会回退到系统字体）')
    out += no_year_problems(res['all'])
    flat = re.sub(r'\s+', '', res['all'])
    out += [f'画面上没有「{s}」' for s in MUST if s not in flat]
    return out


def render(br, body, w, h, name, out):
    html = WORK / f'{name}.html'
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{W4.css(w, h)}</style></head><body>{body}</body></html>', 'utf-8')
    pg = br.new_page(viewport={'width': w, 'height': h}, device_scale_factor=2)
    pg.goto(html.as_uri())
    pg.evaluate('document.fonts.ready.then(() => Promise.all([...document.fonts].map(f => f.load())))')
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(400)
    res = pg.evaluate(W4.CHECK_JS)
    png = out / f'{name}.png'
    pg.screenshot(path=str(png))
    pg.close()
    return png, res['problems'] + text_problems(res)


def selftest(br):
    global K, EXTRA, SEAL_R
    bad = []
    ins = lambda s: f'<div class="ab" data-k="num" style="left:900px;top:960px;font:900 40px Black">{s}</div>'
    cases = [('正常', 1.0, '', None),
             ('字号×0.5', 0.5, '', '缩略图字高'),
             ('年份', 1.0, ins('2026 已更新'), '年份 2026'),
             ('年份段', 1.0, ins('2018—2026'), '年份 2018'),
             ('全角年份', 1.0, ins('２０２５年'), '年份 2025'),
             ('套数', 1.0, ins('全部 35 套'), '数字 35'),
             ('中文套数', 1.0, ins('真题三十五套'), '套数 三十五套'),
             ('缺字', 1.0, ins('四级😀'), '缺字'),
             ('圆章字大', 1.0, '', '字出了圆')]
    for k, f in DIRS.items():
        for w in (1920, 1440):
            for nm, kk, extra, want in cases:
                K, EXTRA, SEAL_R = kk, extra, (.40 if nm == '圆章字大' else .28)
                body = f(w, 1080)
                _, probs = render(br, body, w, 1080, f'自检_{k}_{w}_{nm}', WORK)
                if want is None:
                    if probs:
                        bad.append(f'{k}{w} 正常却报 {probs}')
                elif want == '缩略图字高':
                    need = set(re.findall(r'data-k="(\w+)" data-min=', body))
                    hit = {x.split()[0] for x in probs if want in x}
                    if hit != need or not {'title', 'sub', 'seal'} <= need:
                        bad.append(f'{k}{w} {nm}：报出 {sorted(hit)}，应为 {sorted(need)}')
                elif not any(want in x for x in probs):
                    bad.append(f'{k}{w} {nm}：没报出 {want}（{probs}）')
            body = f(w, 1080).replace('历年真题全收录', '历年真题')       # 必有的话
            _, probs = render(br, body, w, 1080, f'自检_{k}_{w}_必有', WORK)
            if not any('历年真题全收录' in x for x in probs):
                bad.append(f'{k}{w} 去掉“历年真题全收录”没报')
    K, EXTRA, SEAL_R = 1.0, '', .28
    return bad


def main(args):
    from playwright.sync_api import sync_playwright
    W4.ensure_fonts()
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    bad = []
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        if args[0] == '--自检':
            bad = selftest(br)
            br.close()
            print('\n'.join(bad) or '自检通过：正常 0 处；字号×0.5、年份（含年份段、全角）、套数（含中文数字）、缺字、圆章字出圆、缺必有的话全部报出（A/B/C × 16:9、4:3）')
            return 1 if bad else 0
        final = args[1] if args[0] == '定稿' else None
        stem = '四级听力真题与原文解析_封面'
        jobs = []
        for k, f in DIRS.items():
            if final is None:
                jobs += [(f(1920, 1080), 1920, 1080, f'草稿_{k}_16比9', WORK, False), (f(1440, 1080), 1440, 1080, f'草稿_{k}_4比3', WORK, False)]
            elif k == final:
                jobs += [(f(1920, 1080), 1920, 1080, f'{stem}_16比9', OUT, True), (f(1440, 1080), 1440, 1080, f'{stem}_4比3', OUT, True)]
            else:
                jobs.append((f(1920, 1080), 1920, 1080, f'{stem}备选{k}_16比9', OUT, False))
        for body, w, h, name, out, keep_png in jobs:
            png, probs = render(br, body, w, h, name, out)
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
            bad += [f'{name}: {x}' for x in probs]
        br.close()
    if bad:
        print('自查不通过：\n  ' + '\n  '.join(bad))
        return 1
    print('自查通过：无年份、无数字；缩略图字高达标、文字不出画、不进底角遮挡区、不压截图、互不重叠、字体全部加载、无缺字')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['草稿']))
