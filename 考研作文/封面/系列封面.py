"""考研写作 B 站系列封面（手账笔记本，与写作视频同一套画面：天蓝色线圈本封面、白色点阵、粉色和纸胶带、黄色圆贴纸、荧光笔）：一条命令生成 16:9 和 4:3 两张。

    /opt/ttsenv/bin/python 考研作文/封面/系列封面.py

输出 考研作文/封面/系列封面/：考研写作真题范文24篇_封面_16比9.png / .jpg（3840×2160）、_4比3.png / .jpg（2880×2160），
JPG 供上传（B 站封面有大小上限）；考研作文/封面/work/（不入库）里有缩略图、B 站信息流模拟图、手机实际大小预览。
用户要求（2026-10-23）：极具吸引力，让不会写考研作文的人一定点进来；突出 2021—2026 所有真题范文、彻底搞定考研写作；16:9 和 4:3 都要。
做法与考研阅读系列封面（考研/封面/系列封面.py）相同：所有文字实心、边缘干净；“考研”是全图最大、最醒目的字（橙红）；右边贴两张真实视频画面（与视频逐像素相同的审阅截图）。
封面上的数字全部从 考研作文/data/vocab.json 现算（24 篇 = 6 年 × 英一英二 × 大小作文；226 句；标注的高分词句 819 → “800+”只往下取整，不夸大）。
渲染后程序自查：文字不出画、不进 B 站左下（播放量）/右下（时长）遮挡区、关键元素互不重叠、不伸出标签卡、字体全部加载。
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSETS = HERE / '素材'
WORK = HERE / 'work'
OUT = HERE / '系列封面'
F_BLACK = REPO / '四级/封面/fonts/NotoSansSC_900Black.ttf'
F_BOLD = REPO / '四级/封面/fonts/NotoSansSC_700Bold.ttf'
F_INTER = REPO / '专八/tools/fonts/inter/files/inter-latin-800-normal.woff2'

_P = json.loads((REPO / '考研作文' / 'data' / 'vocab.json').read_text('utf-8'))['passages']
N = len(_P)
SENTS = sum(len(pa) for p in _P for pa in p['paras'])
UNIQ = len({w['h'].strip().lower() for p in _P for pa in p['paras'] for s in pa for w in s['w']})
YEARS = f"{min(p['year'] for p in _P)}—{max(p['year'] for p in _P)}"
NA, NB = sum(p['passage'] == 'Part A' for p in _P), sum(p['passage'] == 'Part B' for p in _P)
assert N == 24 and NA == NB == 12 and all(p.get('done') for p in _P), (N, NA, NB)
assert {(p['year'], '英语一' in p['paper'], p['passage']) for p in _P} == {(y, e, s) for y in range(2021, 2027) for e in (True, False) for s in ('Part A', 'Part B')}
assert SENTS == 226 and UNIQ == 819 and YEARS == '2021—2026', (SENTS, UNIQ, YEARS)      # 数据一改就停下，先核对封面上的说法
UNIQ_TXT = f'{UNIQ // 100 * 100}+'          # 819 → “800+”，只往下取整，不夸大

# 写作视频的手账笔记本配色（tools/video/themes/css/2_手账笔记本.css）；“考研”用与阅读封面相同的橙红——系列一致，蓝底上最跳
INK, PB, PR, HY, HP, COVER, KY = '#1f2537', '#2456a6', '#c0185a', '#ffe46b', '#ffaecb', '#7db4e8', '#ff4a12'
THEME = (REPO / 'tools/video/themes/css/2_手账笔记本.css').read_text('utf-8')
BAND = re.search(r'body:has\(\.ttl\) \.band\{width:92px;background:\s*(url\("data:[^"]+"\))', THEME).group(1)      # 视频片头的线圈
DOODLE = re.search(r'body:has\(\.ttl\)::after\{[^}]*?background:\s*(url\("data:[^"]+"\))', THEME, re.S).group(1)  # 白色中性笔涂鸦（星星）

SHOTS = {'front': 'w02_第2句.jpg', 'back': 'w02_原题.jpg'}      # 真实视频画面：范文逐句（荧光笔 + 词汇卡）、原题高清


def shot(name):
    return (ASSETS / SHOTS[name]).as_uri()


def css(w, h):
    return f"""
@font-face{{font-family:Black;src:url({F_BLACK.as_uri()})}}
@font-face{{font-family:Bold;src:url({F_BOLD.as_uri()})}}
@font-face{{font-family:Inter;font-weight:800;src:url({F_INTER.as_uri()})}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:{COVER}}}
body{{position:relative;font-family:Black,sans-serif;color:{INK}}}
.dots{{position:absolute;inset:0;background:radial-gradient(circle at 2px 2px,rgba(255,255,255,.30) 1.8px,transparent 2.3px) 22px 22px/44px 44px}}
.band{{position:absolute;left:0;top:0;bottom:0;width:92px;background:{BAND} 0 0/92px 60px repeat-y}}
.doodle{{position:absolute;width:220px;height:160px;background:{DOODLE} 0 0/220px 160px no-repeat}}
.ab{{position:absolute;white-space:nowrap}}
.label{{position:absolute;background:#fffdf8;border-radius:40px;box-shadow:0 14px 0 -4px rgba(31,37,55,.12),0 26px 60px rgba(20,50,90,.30)}}
.washi{{position:absolute;background:repeating-linear-gradient(135deg,rgba(255,150,190,.95) 0 18px,rgba(255,206,224,.95) 18px 36px);
  clip-path:polygon(0 5%,3% 0,6% 7%,9% 0,100% 0,100% 95%,97% 100%,94% 93%,91% 100%,0 100%)}}
.lat{{font-family:Inter,Black,sans-serif;font-weight:800}}
.hy{{box-shadow:inset 0 -.46em 0 {HY};border-radius:.08em;padding:0 .05em}}
.hp{{box-shadow:inset 0 -.46em 0 {HP};border-radius:.08em;padding:0 .05em}}
.card{{position:absolute;border:10px solid #fff;border-radius:16px;box-shadow:0 14px 0 rgba(20,50,90,.16),0 22px 50px rgba(20,50,90,.38)}}
.tape{{position:absolute;width:140px;height:42px;background:rgba(255,228,107,.88);box-shadow:0 2px 4px rgba(0,0,0,.16);
  clip-path:polygon(0 6%,4% 0,8% 8%,12% 0,100% 0,100% 94%,96% 100%,92% 92%,88% 100%,0 100%)}}
"""


def pill(text, size):
    """蓝色笔的标签胶囊（视频片头 KAOYAN · WRITING 同色）。"""
    return (f'<span style="display:inline-block;font:900 {size}px/1.2 Black;color:#fff;background:{PB};padding:10px 34px 12px;'
            f'border-radius:999px;box-shadow:0 6px 0 #173d7a;letter-spacing:.05em">{text}</span>')


def tag(inner, size, mr=18):
    """数字标签：蓝框白底圆角。"""
    return (f'<span style="display:inline-block;font:900 {size}px/1.25 Black;color:{INK};padding:8px 22px 10px;margin-right:{mr}px;'
            f'border:5px solid {PB};border-radius:18px;background:#f2f7ff">{inner}</span>')


def num(x):
    return f'<span style="color:{KY}">{x}</span>'


FEAT = ['原题高清', '逐句朗读', '逐句翻译', '一句一屏']


def feat(size, gap=30):
    box = (f'<svg width="{size * .86:.0f}" height="{size * .86:.0f}" viewBox="0 0 40 40" style="vertical-align:-.08em;margin-right:.24em;overflow:visible">'
           f'<rect x="3" y="5" width="32" height="32" rx="7" fill="{PB}"/>'
           f'<path d="M10 21 L 17 28 L 30 12" fill="none" stroke="#fff" stroke-width="5.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    return ''.join(f'<span style="margin-right:{gap}px">{box}{t}</span>' for t in FEAT)


def sticker(x, y, d):
    """“24篇”圆贴纸（视频片头右上角黄色圆贴纸同款，放大）。"""
    return (f'<div class="ab" data-k="sticker" style="left:{x}px;top:{y}px;width:{d}px;height:{d}px;border-radius:50%;background:{HY};'
            f'box-shadow:0 {d * .03:.0f}px {d * .08:.0f}px rgba(20,50,90,.30),inset 0 0 0 {d * .04:.0f}px #fff3b3,inset 0 0 0 {d * .05:.0f}px #f0cf45;'
            f'transform:rotate(10deg);display:flex;flex-direction:column;align-items:center;justify-content:center;color:{INK};line-height:1">'
            f'<div><span class="lat" style="font-size:{d * .42:.0f}px;letter-spacing:-.03em;color:{KY}">{N}</span><span style="font:900 {d * .19:.0f}px Black">篇</span></div>'
            f'<div style="font:900 {d * .105:.0f}px/1.3 Black;margin-top:{d * .025:.0f}px;letter-spacing:.06em">真题全收录</div></div>')


def cards(x, y, w, bx, by, bw):
    """两张真实视频画面：后面一张（原题）往下错开，露出下半截的图表；前面一张（范文逐句 + 词汇卡）压在上面，胶带贴住。"""
    return (f'<img class="card" data-k="card2" src="{shot("back")}" style="left:{bx}px;top:{by}px;width:{bw}px;transform:rotate(5deg)">'
            f'<img class="card" data-k="card1" src="{shot("front")}" style="left:{x}px;top:{y}px;width:{w}px;transform:rotate(-4deg)">'
            f'<div class="tape" style="left:{x + w / 2 - 70}px;top:{y - 24}px;transform:rotate(-5deg)"></div>')


KAOYAN = f'<span style="color:{KY};font-size:1.3em;letter-spacing:-.02em;text-shadow:0 .05em 0 {HY}">考研</span>'
HOOK = f'<span class="hp" style="color:{PR}">彻底搞定</span>'


def body_169(w=1920, h=1080):
    return f"""
<div class="dots"></div><div class="band"></div>
<div class="doodle" style="left:1620px;top:880px"></div>
<div class="label" style="left:150px;top:52px;width:1160px;height:900px"></div>
<div class="washi" style="left:112px;top:30px;width:280px;height:66px;transform:rotate(-9deg)"></div>
<div class="ab" data-k="pill" style="left:212px;top:110px">{pill(f'<span class="lat">{YEARS}</span> · 英语一 + 英语二', 46)}</div>
<div class="ab" data-k="title" style="left:200px;top:196px;font:900 176px/1 Black">{KAOYAN}<span>写作</span></div>
<div class="ab" data-k="line2" style="left:210px;top:448px;font:900 132px/1.12 Black"><span class="hy">真题满分范文</span></div>
<div class="ab" data-k="hook" style="left:210px;top:614px;font:900 108px/1.15 Black">{HOOK}<span>大小作文</span></div>
<div class="ab" data-k="tags" style="left:210px;top:774px">{tag(f'大作文 {num(NB)} + 小作文 {num(NA)}', 36, 14)}{tag(f'{num(SENTS)} 句逐句精读', 36, 14)}{tag(f'{num(UNIQ_TXT)} 高分词句', 36, 0)}</div>
<div class="ab" data-k="feat" style="left:214px;top:872px;font:700 40px/1.3 Bold;color:{INK}">{feat(40)}</div>
{sticker(1262, 48, 296)}
{cards(1338, 400, 540, 1386, 612, 500)}"""


def body_43(w=1440, h=1080):
    return f"""
<div class="dots"></div><div class="band"></div>
<div class="label" style="left:132px;top:52px;width:900px;height:900px"></div>
<div class="washi" style="left:96px;top:30px;width:250px;height:62px;transform:rotate(-9deg)"></div>
<div class="ab" data-k="pill" style="left:184px;top:108px">{pill(f'<span class="lat">{YEARS}</span> · 英语一 + 英语二', 40)}</div>
<div class="ab" data-k="title" style="left:174px;top:188px;font:900 168px/1 Black">{KAOYAN}<span>写作</span></div>
<div class="ab" data-k="line2" style="left:182px;top:430px;font:900 124px/1.12 Black"><span class="hy">真题满分范文</span></div>
<div class="ab" data-k="hook" style="left:182px;top:594px;font:900 96px/1.15 Black">{HOOK}<span>大小作文</span></div>
<div class="ab" data-k="tags" style="left:182px;top:752px;line-height:1.75">{tag(f'大作文 {num(NB)} + 小作文 {num(NA)}', 40, 0)}<br>{tag(f'{num(SENTS)} 句逐句精读', 40)}{tag(f'{num(UNIQ_TXT)} 高分词句', 40, 0)}</div>
{sticker(1086, 40, 270)}
{cards(1046, 452, 366, 1070, 640, 340)}"""


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
  // 文字不能伸出标签卡（贴纸、截图卡片除外）
  const wc = document.querySelector('.label').getBoundingClientRect();
  for (const a of r) if (!['sticker', 'card1', 'card2'].includes(a.k) && (a.x1 > wc.right - 30 || a.y1 > wc.bottom - 20))
    out.push(`${a.k} 伸出标签卡 ${JSON.stringify(a)}`);
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
    d.text((W - 42, H - 16), '12:40', fill=(255, 255, 255, 255))
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
        for body, w, h, name, tsize in [(body_169(), 1920, 1080, '考研写作真题范文24篇_封面_16比9', (320, 180)),
                                        (body_43(), 1440, 1080, '考研写作真题范文24篇_封面_4比3', (240, 180))]:
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
    print('自查通过：文字不出画、不进底角遮挡区、不伸出标签卡、关键元素互不重叠、字体全部加载')
