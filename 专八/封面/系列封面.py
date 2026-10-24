"""专八 B 站系列封面（书卷水墨，与视频同一套画面：靛蓝书衣、宣纸题签、双线框、朱砂印章、淡墨远山）：一条命令生成 16:9 和 4:3 两张。

    /opt/ttsenv/bin/python 专八/封面/系列封面.py

输出 专八/封面/系列封面/：专八阅读真题27篇_封面_16比9.png / .jpg（3840×2160）、专八阅读真题27篇_封面_4比3.png / .jpg（2880×2160），
JPG 供上传；专八/封面/work/（不入库）里有缩略图、B 站信息流模拟图、手机实际大小预览。
用户要求（2026-10-24）：B 站用户看到就想点进来；一定要突出“八级真题”“用文章记住八级所有重点单词”。
信息层级：①“专八”全图最大、最醒目（朱红实心粗体）②“真题”（墨底反白）③“用文章记住专八所有重点单词”④真实数字。
做法照搬考研系列封面（考研/封面/系列封面.py）：主标题用 NotoSansSC Black 实心高对比，水墨只做氛围，不用细楷书做标题。
封面上的数字全部从 专八/data/vocab.json 现算（27 篇、1279 句、不重复词条 5150 → “5000+”只往下取整，不夸大）。
渲染后程序自查：文字不出画、不进 B 站左下（播放量）/右下（时长）遮挡区、关键元素互不重叠、字体全部加载。
"""
import json
import sys
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSETS = HERE / '素材'
WORK = HERE / 'work'
OUT = HERE / '系列封面'
F_BLACK = REPO / '四级/封面/fonts/NotoSansSC_900Black.ttf'
F_BOLD = REPO / '四级/封面/fonts/NotoSansSC_700Bold.ttf'
F_INTER = REPO / '专八/tools/fonts/inter/files/inter-latin-800-normal.woff2'

_P = json.loads((REPO / '专八' / 'data' / 'vocab.json').read_text('utf-8'))['passages']
N = len(_P)
SENTS = sum(len(pa) for p in _P for pa in p['paras'])
UNIQ = len({w['h'].strip().lower() for p in _P for pa in p['paras'] for s in pa for w in s['w']})
YEARS = f"{min(p['year'] for p in _P)}—{max(p['year'] for p in _P)}"
_PER = {}
for p in _P:
    _PER.setdefault(p['year'], set()).add(p['passage'])
# 每年 Passage One/Two/Three 三篇都在（2020 年专八停考），“真题全收录”才成立
assert all(v == {'Passage One', 'Passage Two', 'Passage Three'} for v in _PER.values()) and 2020 not in _PER
# 数据一改就停下，先核对封面上的说法。27 篇版（2016—2025）是 git 版本 99fab65 的数据；30 篇版加 2026 三篇（2026-10-24）。
# 文件名带篇数，30 篇版另存新文件，不覆盖已发布的 27 篇版。
_KNOWN = {27: (1279, 5150, '2016—2025'), 30: (1416, 5637, '2016—2026')}
assert N in _KNOWN and all(p.get('done') for p in _P)
assert (SENTS, UNIQ, YEARS) == _KNOWN[N], (SENTS, UNIQ, YEARS)
UNIQ_TXT = f'{UNIQ // 1000 * 1000}+'          # 5150 → “5000+”，只往下取整，不夸大

# 书卷水墨配色（专八/tools/样式.css、样式/C_水墨大字.css）；“专八”用比视频朱砂更亮的朱红——宣纸上最跳
INK, INK2, PAPER, CLOTH, DIAN, ZHU, KY, BLUE = '#1e1b17', '#34302a', '#f4eee2', '#1c3150', '#1f4677', '#b03c2a', '#d8301a', '#1f6fd6'
MARK = '#cfe0f7'

# 淡墨远山：几层靛灰山影，越远越淡（只做氛围）
_MTN = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1920 520' preserveAspectRatio='none'>"
        "<path fill='#3a5680' fill-opacity='.55' d='M0 300 C160 250 260 140 380 170 C470 195 520 120 640 90 C760 60 820 170 930 190 C1040 210 1100 80 1230 60 "
        "C1360 40 1420 160 1540 150 C1650 140 1720 60 1820 80 C1880 92 1910 120 1920 130 L1920 520 L0 520Z'/>"
        "<path fill='#2c4670' fill-opacity='.75' d='M0 380 C140 340 230 270 360 290 C480 310 560 230 690 220 C820 210 880 300 1010 300 C1130 300 1200 200 1330 190 "
        "C1450 180 1520 280 1640 270 C1760 260 1840 210 1920 220 L1920 520 L0 520Z'/>"
        "<path fill='#22395c' d='M0 450 C180 420 300 370 450 390 C600 410 700 350 860 350 C1010 350 1090 410 1240 400 C1400 390 1480 330 1630 340 "
        "C1760 348 1850 380 1920 375 L1920 520 L0 520Z'/></svg>")
MTN = 'data:image/svg+xml;utf8,' + quote(_MTN)

SHOTS = {'front': 't24_第7屏.jpg', 'back': 't01_第4屏.jpg'}      # 真实视频画面（与视频逐像素相同的审阅截图，大字版水墨）


def shot(name):
    return (ASSETS / SHOTS[name]).as_uri()


def css(w, h):
    return f"""
@font-face{{font-family:Black;src:url({F_BLACK.as_uri()})}}
@font-face{{font-family:Bold;src:url({F_BOLD.as_uri()})}}
@font-face{{font-family:Inter;font-weight:800;src:url({F_INTER.as_uri()})}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:{CLOTH}}}
body{{position:relative;font-family:Black,sans-serif;color:{INK};
  background:radial-gradient(ellipse at 80% 20%,#2a4670 0,{CLOTH} 60%),{CLOTH}}}
.mtn{{position:absolute;left:0;right:0;bottom:0;height:52%;background:url("{MTN}") center bottom/100% 100% no-repeat}}
.moon{{position:absolute;border-radius:50%;background:radial-gradient(circle,rgba(233,223,201,.22) 0,rgba(233,223,201,.10) 55%,rgba(233,223,201,0) 70%)}}
.ab{{position:absolute;white-space:nowrap}}
.wcard{{position:absolute;background:{PAPER};border-radius:6px;
  box-shadow:inset 0 0 0 18px {PAPER},inset 0 0 0 22px {INK},inset 0 0 0 28px {PAPER},inset 0 0 0 30px {INK},0 20px 0 rgba(0,0,0,.22),0 30px 70px rgba(0,0,0,.45)}}
.lat{{font-family:Inter,Black,sans-serif;font-weight:800}}
.mk{{box-shadow:inset 0 -.38em 0 {MARK};border-radius:.08em;padding:0 .04em}}
.zt{{display:inline-block;background:{INK};color:{PAPER};border-radius:.12em;padding:.02em .1em .06em;margin-left:.06em}}
.card{{position:absolute;border:10px solid {PAPER};border-radius:8px;box-shadow:0 14px 0 rgba(0,0,0,.25),0 22px 50px rgba(0,0,0,.5)}}
.tape{{position:absolute;width:130px;height:40px;background:rgba(216,48,26,.82);box-shadow:0 2px 4px rgba(0,0,0,.25)}}
"""


def pill(text, size):
    """朱砂题签条（TEM-8 · 年份 · 英语专业八级）。"""
    return (f'<span style="display:inline-block;font:900 {size}px/1.2 Black;color:{PAPER};background:{ZHU};padding:10px 34px 12px;'
            f'border-radius:10px;box-shadow:inset 0 0 0 4px {ZHU},inset 0 0 0 6px {PAPER};letter-spacing:.06em">{text}</span>')


def tag(inner, size, mr=18):
    """数字标签：靛青框宣纸底。"""
    return (f'<span style="display:inline-block;font:900 {size}px/1.25 Black;color:{INK};padding:8px 24px 10px;margin-right:{mr}px;'
            f'border:5px solid {DIAN};border-radius:12px;background:#fbf7ee">{inner}</span>')


def num(t):
    return f'<span style="color:{KY}">{t}</span>'


def tags(size, mr=18):
    return (tag(f'{num(SENTS)} 句逐句精读', size, mr) +
            tag(f'{num(UNIQ_TXT)} 单词短语全标注', size, mr) +
            tag(f'{num("4K")} 大字版', size, mr))


FEAT = ['逐句朗读', '逐句翻译', '生词编号注释', '一句一屏']


def feat(size, gap=34):
    box = (f'<svg width="{size * .86:.0f}" height="{size * .86:.0f}" viewBox="0 0 40 40" style="vertical-align:-.08em;margin-right:.26em;overflow:visible">'
           f'<rect x="3" y="5" width="32" height="32" rx="7" fill="{BLUE}"/>'
           f'<path d="M10 21 L 17 28 L 30 12" fill="none" stroke="#fff" stroke-width="5.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    return ''.join(f'<span style="margin-right:{gap}px">{box}{t}</span>' for t in FEAT)


def sticker(x, y, d):
    """“27篇”朱砂方印（视频片头“专八精读”印章同款，放大）。"""
    return (f'<div class="ab" data-k="sticker" style="left:{x}px;top:{y}px;width:{d}px;height:{d}px;border-radius:{d * .06:.0f}px;background:{KY};'
            f'box-shadow:inset 0 0 0 {d * .035:.0f}px {KY},inset 0 0 0 {d * .055:.0f}px {PAPER},0 {d * .04:.0f}px 0 rgba(0,0,0,.3),0 {d * .06:.0f}px {d * .16:.0f}px rgba(0,0,0,.45);'
            f'transform:rotate(-8deg);display:flex;flex-direction:column;align-items:center;justify-content:center;color:{PAPER};line-height:1">'
            f'<div><span class="lat" style="font-size:{d * .44:.0f}px;letter-spacing:-.03em">{N}</span><span style="font:900 {d * .2:.0f}px Black">篇</span></div>'
            f'<div style="font:900 {d * .105:.0f}px/1.3 Black;margin-top:{d * .02:.0f}px;letter-spacing:.08em">真题全收录</div></div>')


def cards(x, y, w):
    return (f'<img class="card" data-k="card2" src="{shot("back")}" style="left:{x + 40}px;top:{y + 40}px;width:{w - 24}px;transform:rotate(6deg)">'
            f'<img class="card" data-k="card1" src="{shot("front")}" style="left:{x}px;top:{y}px;width:{w}px;transform:rotate(-4deg)">'
            f'<div class="tape" style="left:{x + w / 2 - 65}px;top:{y - 22}px;transform:rotate(-6deg)"></div>')


ZB = f'<span style="color:{KY};font-size:1.56em;letter-spacing:-.02em;text-shadow:0 .045em 0 rgba(30,27,23,.18)">专八</span>'
TITLE = f'{ZB}<span>阅读</span><span class="zt">真题</span>'
HOOK1 = '用文章记住'
HOOK2 = f'专八<span class="mk" style="font-size:1.1em;color:{BLUE}">所有重点单词</span>'


def body_169(w=1920, h=1080):
    return f"""
<div class="moon" style="left:1380px;top:-120px;width:620px;height:620px"></div>
<div class="mtn"></div>
<div class="wcard" style="left:46px;top:42px;width:1268px;height:882px"></div>
<div class="ab" data-k="pill" style="left:104px;top:86px">{pill(f'TEM-8 · <span class="lat">{YEARS}</span> · 英语专业八级', 46)}</div>
<div class="ab" data-k="title" style="left:96px;top:168px;font:900 150px/1 Black">{TITLE}</div>
<div class="ab" data-k="hook1" style="left:104px;top:432px;font:900 76px/1.2 Black;color:{INK2}">{HOOK1}</div>
<div class="ab" data-k="hook2" style="left:104px;top:530px;font:900 112px/1.2 Black">{HOOK2}</div>
<div class="ab" data-k="tags" style="left:104px;top:708px">{tags(42)}</div>
<div class="ab" data-k="feat" style="left:108px;top:824px;font:700 44px/1.3 Bold;color:{INK}">{feat(44)}</div>
{sticker(1300, 46, 290)}
{cards(1352, 392, 520)}"""


def body_43(w=1440, h=1080):
    return f"""
<div class="moon" style="left:960px;top:-120px;width:560px;height:560px"></div>
<div class="mtn"></div>
<div class="wcard" style="left:36px;top:40px;width:964px;height:880px"></div>
<div class="ab" data-k="pill" style="left:84px;top:80px">{pill(f'TEM-8 · <span class="lat">{YEARS}</span> · 专业八级', 38)}</div>
<div class="ab" data-k="title" style="left:76px;top:156px;font:900 118px/1 Black">{TITLE}</div>
<div class="ab" data-k="hook1" style="left:84px;top:372px;font:900 70px/1.2 Black;color:{INK2}">{HOOK1}</div>
<div class="ab" data-k="hook2" style="left:84px;top:456px;font:900 98px/1.2 Black">{HOOK2}</div>
<div class="ab" data-k="tags" style="left:84px;top:640px;line-height:1.8">{tag(f'{num(SENTS)} 句逐句精读', 42)}{tag(f'{num("4K")} 大字版', 42, 0)}<br>{tag(f'{num(UNIQ_TXT)} 单词短语全标注', 42, 0)}</div>
<div class="ab" data-k="feat" style="left:88px;top:830px;font:700 34px/1.3 Bold;color:{INK}">{feat(34, 24)}</div>
{sticker(1052, 50, 280)}
{cards(1040, 400, 352)}"""


CHECK_JS = """
() => {
  const W = innerWidth, H = innerHeight, out = [];
  const els = [...document.querySelectorAll('[data-k]')];
  const r = els.map(e => { const b = e.getBoundingClientRect(); return {k: e.dataset.k, x0: b.left, y0: b.top, x1: b.right, y1: b.bottom}; });
  for (const a of r) {
    if (a.x0 < 12 || a.y0 < 12 || a.x1 > W - 12 || a.y1 > H - 12) out.push(`${a.k} 出画 ${JSON.stringify(a)}`);
    // B 站缩略图左下（播放量/弹幕）、右下（时长）遮挡区：宽 25%、高 12%
    if (!a.k.startsWith('card') && a.y1 > H * 0.88 && (a.x0 < W * 0.25 || a.x1 > W * 0.75)) out.push(`${a.k} 进入底角遮挡区`);
  }
  for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) {
    const a = r[i], b = r[j];
    if (a.k.startsWith('card') && b.k.startsWith('card')) continue;
    const ox = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), oy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
    if (ox > 0 && oy > 0) out.push(`${a.k} 与 ${b.k} 重叠 ${ox.toFixed(0)}×${oy.toFixed(0)}`);
  }
  // 文字不能伸出白卡片（贴纸、截图卡片除外）
  const wc = document.querySelector('.wcard').getBoundingClientRect();
  for (const a of r) if (!['sticker', 'card1', 'card2'].includes(a.k) && (a.x1 > wc.right - 30 || a.y1 > wc.bottom - 20))
    out.push(`${a.k} 伸出白卡片 ${JSON.stringify(a)}`);
  const fonts = [...document.fonts].filter(f => f.status !== 'loaded').map(f => f.family);
  if (fonts.length) out.push('字体未加载: ' + fonts.join(','));
  return {problems: out, boxes: r};
}"""


def render(br, body, w, h, name):
    html = WORK / f'{name}.html'
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{css(w, h)}</style></head>'
                    f'<body>{body}</body></html>', 'utf-8')
    pg = br.new_page(viewport={'width': w, 'height': h}, device_scale_factor=2)
    pg.goto(html.as_uri())
    pg.evaluate('document.fonts.ready.then(() => [...document.fonts].forEach(f => f.load()))')
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(500)
    res = pg.evaluate(CHECK_JS)
    png = OUT / f'{name}.png'
    pg.screenshot(path=str(png))
    pg.close()
    return png, res


def thumbs(png, size, name):
    im = Image.open(png).convert('RGB')
    t = im.resize(size, Image.LANCZOS)
    t.save(WORK / f'{name}.png')
    sim = t.copy().convert('RGBA')            # B 站信息流模拟：左下播放量/弹幕、右下时长的深色渐变条
    ov = Image.new('RGBA', sim.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    W, H = sim.size
    for y in range(int(H * 0.78), H):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(150 * (y - H * 0.78) / (H * 0.22))))
    d.text((6, H - 16), '▶ 1.2万  ☰ 86', fill=(255, 255, 255, 255))
    d.text((W - 42, H - 16), '08:31', fill=(255, 255, 255, 255))
    sim = Image.alpha_composite(sim, ov).convert('RGB')
    sim.resize((W * 3, H * 3), Image.NEAREST).save(WORK / f'feed_{name}.png')
    return WORK / f'{name}.png'


def phone(png, name):
    """手机上实际显示的像素：16:9 按 B 站手机首页双列（3 倍屏 558×314），4:3 按 480×360；另存 1 倍屏放大 3 倍（最差情况）。"""
    im = Image.open(png).convert('RGB')
    w = 558 if '16比9' in name else 480
    h = round(w * im.height / im.width)
    im.resize((w, h), Image.LANCZOS).save(WORK / f'{name}_手机3倍屏.png')
    im.resize((w // 3, h // 3), Image.LANCZOS).resize((w, h), Image.NEAREST).save(WORK / f'{name}_手机1倍屏放大.png')


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    bad = []
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for body, w, h, name, tsize in [(body_169(), 1920, 1080, f'专八阅读真题{N}篇_封面_16比9', (320, 180)),
                                        (body_43(), 1440, 1080, f'专八阅读真题{N}篇_封面_4比3', (240, 180))]:
            png, res = render(br, body, w, h, name)
            im = Image.open(png)
            assert im.size == (w * 2, h * 2), im.size
            thumbs(png, tsize, name + '_缩略图')
            phone(png, name)
            jpg = png.with_suffix('.jpg')             # 上传用：B 站封面有大小上限
            im.convert('RGB').save(jpg, quality=92, optimize=True, progressive=True)
            print(f'{jpg.name} {jpg.stat().st_size / 1e6:.1f} MB')
            for b in res['boxes']:
                print(f"   {b['k']:8s} x {b['x0']:7.1f}–{b['x1']:7.1f}  y {b['y0']:6.1f}–{b['y1']:6.1f}")
            bad += [f'{name}: {x}' for x in res['problems']]
        br.close()
    if bad:
        print('自查不通过：\n  ' + '\n  '.join(bad))
        sys.exit(1)
    print('自查通过：文字不出画、不进底角遮挡区、不伸出白卡片、关键元素互不重叠、字体全部加载')
