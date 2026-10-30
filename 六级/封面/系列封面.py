"""六级 B 站系列封面（教室黑板，用户 2026-10-17 从 4 种设计里选定 B 黑板粉笔版）：一条命令生成 16:9 和 4:3 两张。

    /opt/ttsenv/bin/python 六级/封面/系列封面.py

输出 六级/封面/系列封面/：六级阅读真题60篇_封面_16比9.png / .jpg（3840×2160）、六级阅读真题60篇_封面_4比3.png / .jpg（2880×2160），
JPG 供上传（B 站封面有大小上限）；六级/封面/work/（不入库）里有缩略图、B 站信息流模拟图、手机实际大小预览。
用户要求（2026-10-17）：一眼看出 60 篇、六级真题、仔细阅读 Passage One + Passage Two、记住六级所有重点单词；手机上 16:9 和 4:3 都要看得特别清楚。
  → 所有文字实心、边缘干净（粉笔味只留在黑板、粉笔涂块、框线上，不在字上做颗粒和毛边——缩到手机大小时颗粒会让字发虚）。
封面上的数字全部从 六级/data/vocab.json 现算（60 篇、1342 句、不重复词条 4563 → “4500+”只往下取整，不夸大）。
渲染后程序自查：文字不出画、不进 B 站左下（播放量）/右下（时长）遮挡区、关键元素互不重叠、字体全部加载；手机大小下主标题字高够大。
"""
import json
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

_P = json.loads((REPO / '六级' / 'data' / 'vocab.json').read_text('utf-8'))['passages']
N = len(_P)
SENTS = sum(len(pa) for p in _P for pa in p['paras'])
UNIQ = len({w['h'].strip().lower() for p in _P for pa in p['paras'] for s in pa for w in s['w']})
YEARS = f"{min(p['year'] for p in _P)}—{max(p['year'] for p in _P)}"
assert N == 60 and sum(p['passage'] == 'Passage One' for p in _P) == 30 and sum(p['passage'] == 'Passage Two' for p in _P) == 30
assert SENTS == 1342 and UNIQ == 4563 and YEARS == '2021—2026', (SENTS, UNIQ, YEARS)      # 数据一改就停下，先核对封面上的说法
UNIQ_TXT = f'{UNIQ // 500 * 500}+'          # 4563 → “4500+”，只往下取整，不夸大

# 视频里的黑板配色（tools/video/themes/css/3_教室黑板.css），亮度略提，缩略图里更跳
BOARD, CHALK, YEL, PNK, BLU, INK = '#1f4a3c', '#f7f4ea', '#ffde59', '#ff9fd2', '#9dd5f0', '#123328'
HOT = '#ff7cc8'      # “六级”两个字（用户 2026-10-17：要让人一眼看到“六级”）：比短语粉更艳的粉——粉红是黑板绿的补色，在绿底上最跳
SIX = f'<span style="color:{HOT};font-size:1.1em">六级</span>'        # 标题里放大 10%
SIX_HOOK = f'<span style="color:{HOT}">六级</span>'


SHOTS = {'v1_30': '2026年6月第3套PassageTwo_第4句.jpg', 'v2_120': '2026年6月第3套PassageOne_第11句.jpg'}


def shot(name):
    """真实视频画面（六级/最终视频_黑板/ 里两个视频的截图，缩成 1920×1080 存在 六级/封面/素材/）。"""
    return (ASSETS / SHOTS[name]).as_uri()


SVG_DEFS = """
<svg width="0" height="0" style="position:absolute">
 <defs>
  <!-- 粉笔字：边缘毛糙 + 稀疏的细小粉笔颗粒缺口（字仍是实心亮色，缩略图里一眼能读） -->
  <filter id="chalk" x="-3%" y="-6%" width="106%" height="112%" color-interpolation-filters="sRGB">
   <feTurbulence type="fractalNoise" baseFrequency="0.3" numOctaves="2" seed="4" result="n"/>
   <feDisplacementMap in="SourceGraphic" in2="n" scale="2.6" xChannelSelector="R" yChannelSelector="G" result="d"/>
   <feTurbulence type="fractalNoise" baseFrequency="1.2" numOctaves="2" seed="11" result="g"/>
   <feColorMatrix in="g" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -16 11.6" result="holes"/>
   <feComposite in="d" in2="holes" operator="in"/>
  </filter>
  <!-- 粉笔涂块：边缘起伏 + 横向笔触 -->
  <filter id="rough" x="-4%" y="-12%" width="108%" height="124%" color-interpolation-filters="sRGB">
   <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="3" seed="2" result="n"/>
   <feDisplacementMap in="SourceGraphic" in2="n" scale="16" xChannelSelector="R" yChannelSelector="G" result="d"/>
   <feTurbulence type="fractalNoise" baseFrequency="0.006 0.32" numOctaves="2" seed="8" result="s"/>
   <feColorMatrix in="s" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.5 1.72" result="streak"/>
   <feComposite in="d" in2="streak" operator="in"/>
  </filter>
  <!-- 粉笔线条（框、下划线、箭头） -->
  <filter id="line" x="-5%" y="-20%" width="110%" height="140%">
   <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="5" result="n"/>
   <feDisplacementMap in="SourceGraphic" in2="n" scale="3" xChannelSelector="R" yChannelSelector="G" result="d"/>
   <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.6 2.1" result="h"/>
   <feComposite in="d" in2="h" operator="in"/>
  </filter>
  <filter id="wood" x="0" y="0" width="100%" height="100%">
   <feTurbulence type="fractalNoise" baseFrequency="0.004 0.22" numOctaves="3" seed="3"/>
   <feColorMatrix values="0 0 0 0 .22  0 0 0 0 .12  0 0 0 0 .05  0 0 0 1.6 -.55"/>
  </filter>
  <filter id="woodv" x="0" y="0" width="100%" height="100%">
   <feTurbulence type="fractalNoise" baseFrequency="0.22 0.004" numOctaves="3" seed="5"/>
   <feColorMatrix values="0 0 0 0 .22  0 0 0 0 .12  0 0 0 0 .05  0 0 0 1.6 -.55"/>
  </filter>
  <filter id="dust"><feGaussianBlur stdDeviation="22"/></filter>
 </defs>
</svg>"""


def css(w, h):
    return f"""
@font-face{{font-family:Black;src:url({F_BLACK.as_uri()})}}
@font-face{{font-family:Bold;src:url({F_BOLD.as_uri()})}}
@font-face{{font-family:Inter;font-weight:800;src:url({F_INTER.as_uri()})}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:{BOARD}}}
body{{position:relative;font-family:Black,sans-serif;color:{CHALK}}}
.board{{position:absolute;inset:0;background:
  radial-gradient(ellipse 70% 65% at 42% 42%,#2c6450 0%,#22533f 45%,#183f31 100%)}}
.grain{{position:absolute;inset:0;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='320' height='320'><filter id='w' x='0' y='0'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' seed='7' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 -5 2.1'/></filter><filter id='k' x='0' y='0'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' seed='7' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 5 -2.9'/></filter><rect width='320' height='320' filter='url(%23k)' opacity='.2'/><rect width='320' height='320' filter='url(%23w)' opacity='.11'/></svg>");background-size:320px 320px}}
.ab{{position:absolute;white-space:nowrap}}
.ck{{text-shadow:0 3px 0 rgba(0,0,0,.30),0 0 2px rgba(0,0,0,.25)}}
.hl{{position:relative;display:inline-block}}
.hl>i{{position:absolute;filter:url(#rough)}}
.hl>b{{position:relative;font-weight:inherit}}
.lat{{font-family:Inter,Black,sans-serif;font-weight:800}}
.card{{position:absolute;border:9px solid #fbf8ef;box-shadow:10px 14px 0 rgba(0,0,0,.45),0 0 40px rgba(0,0,0,.35)}}
.tape{{position:absolute;width:120px;height:38px;background:rgba(255,240,200,.72);box-shadow:0 1px 3px rgba(0,0,0,.25)}}
"""


def frame(w, h):
    """木框：上、左、右窄边，下面粉笔槽（粉笔放在中间，B 站左下/右下遮挡区只有木头）。"""
    t, s, b = 18, 18, 46
    mid = w / 2
    sticks = ''
    for x, wd, col, rot in [(mid - 300, 92, CHALK, 0), (mid - 190, 58, YEL, -2), (mid - 112, 74, PNK, 1), (mid - 20, 40, BLU, 0)]:
        sticks += (f'<g transform="rotate({rot} {x + wd / 2} {h - b + 22})"><rect x="{x}" y="{h - b + 14}" width="{wd}" height="15" rx="7.5" fill="{col}"/>'
                   f'<rect x="{x + 4}" y="{h - b + 16}" width="{wd - 8}" height="3.5" rx="1.7" fill="#fff" opacity=".55"/></g>')
    eraser = (f'<rect x="{mid + 150}" y="{h - b + 6}" width="170" height="26" rx="5" fill="#d9c7a5"/>'
              f'<rect x="{mid + 150}" y="{h - b + 22}" width="170" height="10" rx="4" fill="#5b4a3a"/>')
    return f"""<svg class="ab" style="left:0;top:0" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
 <g fill="#a87348"><rect x="0" y="0" width="{w}" height="{t}"/><rect x="0" y="0" width="{s}" height="{h}"/>
  <rect x="{w - s}" y="0" width="{s}" height="{h}"/><rect x="0" y="{h - b}" width="{w}" height="{b}"/></g>
 <rect x="0" y="0" width="{w}" height="{t}" filter="url(#wood)"/><rect x="0" y="{h - b}" width="{w}" height="{b}" filter="url(#wood)"/>
 <rect x="0" y="0" width="{s}" height="{h}" filter="url(#woodv)"/><rect x="{w - s}" y="0" width="{s}" height="{h}" filter="url(#woodv)"/>
 <rect x="{s}" y="{t}" width="{w - 2 * s}" height="6" fill="#000" opacity=".28"/>
 <rect x="{s}" y="{t}" width="6" height="{h - t - b}" fill="#000" opacity=".22"/><rect x="{w - s - 6}" y="{t}" width="6" height="{h - t - b}" fill="#000" opacity=".22"/>
 <rect x="0" y="{h - b}" width="{w}" height="4" fill="#fff" opacity=".18"/>
 <rect x="0" y="{h - b - 10}" width="{w}" height="10" fill="#000" opacity=".25"/>
 {sticks}{eraser}
</svg>"""


def dust(w, h):
    """黑板上没擦干净的粉笔灰（很淡，只为真实感）。"""
    return f"""<svg class="ab" style="left:0;top:0" width="{w}" height="{h}"><g fill="none" stroke="#fff" stroke-linecap="round" filter="url(#dust)">
 <path d="M{w*.05} {h*.16} C {w*.2} {h*.08}, {w*.36} {h*.1}, {w*.5} {h*.05}" stroke-width="110" opacity=".05"/>
 <path d="M{w*.62} {h*.93} C {w*.75} {h*.88}, {w*.86} {h*.91}, {w*.97} {h*.86}" stroke-width="90" opacity=".05"/>
 <path d="M{w*.72} {h*.12} C {w*.82} {h*.06}, {w*.9} {h*.12}, {w*.98} {h*.07}" stroke-width="80" opacity=".045"/>
</g></svg>"""


def hl(text, color, ink=INK, px=22, extra=''):
    """粉笔涂块高亮：底块单独做毛边滤镜，字本身不变形。"""
    return (f'<span class="hl" style="{extra}"><i style="left:-{px}px;right:-{px}px;top:7%;bottom:3%;background:{color}"></i>'
            f'<b style="color:{ink}">{text}</b></span>')


def badge(inner, size, col=CHALK, border=CHALK, fill='rgba(0,0,0,.18)', mr=22, bw=4.6):
    """粉笔框标签：框线用真实像素尺寸的 div 画（不拉伸 SVG，左右两端不会糊）。"""
    return (f'<span style="display:inline-block;position:relative;font:900 {size}px/1.25 Black;color:{col};padding:8px 26px 10px;margin-right:{mr}px">'
            f'<i style="position:absolute;inset:0;border:{bw}px solid {border};border-radius:16px;background:{fill};filter:url(#line)"></i>'
            f'<span class="ck" style="position:relative">{inner}</span></span>')


def plane(x, y, s=1.0):
    """视频片头同款的粉笔纸飞机 + 虚线轨迹 + 小星星（装饰，放在右上空白处）。"""
    return f"""<svg class="ab" style="left:{x}px;top:{y}px;overflow:visible" width="{380 * s}" height="{120 * s}" viewBox="0 0 380 120" filter="url(#line)">
 <path d="M8 104 C 70 92, 120 60, 170 78 S 250 96, 286 58" fill="none" stroke="{CHALK}" stroke-width="4" stroke-dasharray="2 13" stroke-linecap="round" opacity=".85"/>
 <g fill="none" stroke="{CHALK}" stroke-width="4.5" stroke-linejoin="round" stroke-linecap="round">
  <path d="M296 52 L 372 8 L 340 92 Z"/><path d="M372 8 L 318 64 L 322 90"/></g>
 <path d="M120 18 l6 16 l16 6 l-16 6 l-6 16 l-6 -16 l-16 -6 l16 -6 z" fill="{YEL}"/>
 <path d="M206 6 l3.5 9 l9 3.5 l-9 3.5 l-3.5 9 l-3.5 -9 l-9 -3.5 l9 -3.5 z" fill="{BLU}"/>
</svg>"""


TOP = f'大学英语六级（CET-6）· <span style="color:{YEL}">{YEARS}</span> 年真题'
PILL = '仔细阅读 <span class="lat">Passage One + Passage Two</span>'
FEAT = ['逐句朗读', '逐句翻译', '生词编号注释', '一句一屏']


def feat(size, gap=40):
    """视频片头“今日目标”同款的粉笔勾选框。"""
    box = (f'<svg width="{size * .86:.0f}" height="{size * .86:.0f}" viewBox="0 0 40 40" style="vertical-align:-.08em;margin-right:.28em;overflow:visible" filter="url(#line)">'
           f'<rect x="3" y="5" width="32" height="32" rx="4" fill="none" stroke="{CHALK}" stroke-width="3.6"/>'
           f'<path d="M10 20 L 18 29 L 38 2" fill="none" stroke="{YEL}" stroke-width="5.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    return ''.join(f'<span style="margin-right:{gap}px">{box}{t}</span>' for t in FEAT)


def badges(size, mr=22):
    y = f'<span style="color:{YEL}">'
    return (badge(f'{y}{SENTS}</span> 句逐句精读', size, mr=mr) +
            badge(f'{y}{UNIQ_TXT}</span> <span style="color:{YEL}">单词</span><span style="color:{PNK}">短语</span>全标注', size, mr=mr) +
            badge(f'{y}4K</span> 黑板大字版', size, mr=mr))


def legend(size):
    """视频片头同款图例：黄色粉笔＝单词，粉色粉笔＝短语。"""
    def stick(col, dark):
        return (f'<i style="display:inline-block;position:relative;width:{size * 1.7:.0f}px;height:{size * .42:.0f}px;border-radius:{size}px;'
                f'background:linear-gradient({col} 0 58%,{dark} 58%);vertical-align:.18em;margin-right:.3em;transform:rotate(-3deg);'
                f'box-shadow:0 3px 6px rgba(0,0,0,.35)"></i>')
    return (f'<span style="margin-right:{size * .9:.0f}px">{stick(YEL, "#c9a93a")}单词</span>'
            f'<span>{stick(PNK, "#c47aa3")}短语</span>')


def cards(x, y, w):
    return (f'<img class="card" data-k="card2" src="{shot("v2_120")}" style="left:{x + 34}px;top:{y + 36}px;width:{w - 20}px;transform:rotate(5deg)">'
            f'<img class="card" data-k="card1" src="{shot("v1_30")}" style="left:{x}px;top:{y}px;width:{w}px;transform:rotate(-4deg)">'
            f'<div class="tape" style="left:{x + w / 2 - 60}px;top:{y - 22}px;transform:rotate(-7deg)"></div>')


def body_169(w=1920, h=1080):
    return f"""
<div class="board"></div><div class="grain"></div>{dust(w, h)}
<div class="ab ck" data-k="top" style="left:84px;top:34px;font:700 56px/1.3 Bold;color:{BLU};letter-spacing:.04em">{TOP}</div>
{plane(1500, 30)}
<div class="ab" data-k="title" style="left:66px;top:108px;line-height:1">
 <span class="ck" style="font:900 272px/1 Black;color:{YEL};letter-spacing:-.04em">60</span><span class="ck" style="font:900 206px/1 Black;color:{CHALK}">篇{SIX}阅读真题</span></div>
<div class="ab" data-k="pill" style="left:84px;top:410px">{badge(PILL, 64, CHALK, BLU, bw=5.6)}</div>
<div class="ab ck" data-k="legend" style="left:1390px;top:430px;font:700 50px/1.3 Bold;color:{CHALK}">{legend(50)}</div>
<div class="ab" data-k="hook" style="left:80px;top:520px;font:900 138px/1.2 Black">
 <span class="ck">记住{SIX_HOOK}</span>{hl('所有重点单词', YEL, extra='margin-left:34px;font-size:162px')}</div>
<div class="ab" data-k="badges" style="left:84px;top:740px">{badges(46, mr=20)}</div>
<div class="ab ck" data-k="feat" style="left:90px;top:868px;font:700 46px/1.3 Bold;color:{CHALK};letter-spacing:.03em">{feat(46, gap=34)}</div>
{cards(1440, 740, 430)}
{frame(w, h)}"""


def body_43(w=1440, h=1080):
    return f"""
<div class="board"></div><div class="grain"></div>{dust(w, h)}
<div class="ab ck" data-k="top" style="left:62px;top:32px;font:700 50px/1.3 Bold;color:{BLU};letter-spacing:.03em">{TOP}</div>
{plane(1120, 40, .76)}
<div class="ab" data-k="title" style="left:48px;top:100px;line-height:1">
 <span class="ck" style="font:900 212px/1 Black;color:{YEL};letter-spacing:-.04em">60</span><span class="ck" style="font:900 154px/1 Black;color:{CHALK}">篇{SIX}阅读真题</span></div>
<div class="ab" data-k="pill" style="left:62px;top:334px">{badge(PILL, 56, CHALK, BLU, bw=5.2)}</div>
<div class="ab" data-k="hook" style="left:56px;top:436px;font:900 114px/1.2 Black">
 <span class="ck">记住{SIX_HOOK}</span>{hl('所有重点单词', YEL, px=18, extra='margin-left:28px;font-size:136px')}</div>
<div class="ab" data-k="badges" style="left:62px;top:636px;width:720px;white-space:normal;line-height:0">{badges(41, mr=0).replace('margin-right:0px', 'margin:0 0 16px 0')}</div>
<div class="ab ck" data-k="legend" style="left:68px;top:898px;font:700 40px/1.25 Bold;color:{CHALK}">{legend(40)}</div>
{cards(800, 664, 540)}
{frame(w, h)}"""


CHECK_JS = """
() => {
  const W = innerWidth, H = innerHeight, out = [];
  const els = [...document.querySelectorAll('[data-k]')];
  const r = els.map(e => { const b = e.getBoundingClientRect(); return {k: e.dataset.k, x0: b.left, y0: b.top, x1: b.right, y1: b.bottom}; });
  for (const a of r) {
    if (a.x0 < 18 || a.y0 < 18 || a.x1 > W - 18 || a.y1 > H - 46) out.push(`${a.k} 出画/压到木框 ${JSON.stringify(a)}`);
    // B 站缩略图左下（播放量/弹幕）、右下（时长）遮挡区：宽 25%、高 12%
    if (!a.k.startsWith('card') && a.y1 > H * 0.88 && (a.x0 < W * 0.25 || a.x1 > W * 0.75)) out.push(`${a.k} 进入底角遮挡区`);
  }
  for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) {
    const a = r[i], b = r[j];
    if (a.k.startsWith('card') && b.k.startsWith('card')) continue;
    const ox = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), oy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
    if (ox > 0 && oy > 0) out.push(`${a.k} 与 ${b.k} 重叠 ${ox.toFixed(0)}×${oy.toFixed(0)}`);
  }
  const fonts = [...document.fonts].filter(f => f.status !== 'loaded').map(f => f.family);
  if (fonts.length) out.push('字体未加载: ' + fonts.join(','));
  return {problems: out, boxes: r};
}"""


def render(br, body, w, h, name):
    html = WORK / f'{name}.html'
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{css(w, h)}</style></head>'
                    f'<body>{SVG_DEFS}{body}</body></html>', 'utf-8')
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
    # B 站信息流模拟：左下播放量/弹幕、右下时长的深色渐变条（各约宽 25%、高 12%）
    sim = t.copy().convert('RGBA')
    ov = Image.new('RGBA', sim.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    W, H = sim.size
    for y in range(int(H * 0.78), H):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(150 * (y - H * 0.78) / (H * 0.22))))
    d.text((6, H - 16), '▶ 1.2万  ☰ 86', fill=(255, 255, 255, 255))
    d.text((W - 42, H - 16), '08:31', fill=(255, 255, 255, 255))
    sim = Image.alpha_composite(sim, ov).convert('RGB')
    big = sim.resize((W * 3, H * 3), Image.NEAREST)     # 放大看像素（不插值），模拟手机屏上的实际清晰度
    big.save(WORK / f'feed_{name}.png')
    return WORK / f'{name}.png'



def phone(png, name):
    """手机上实际显示的像素：16:9 按 B 站手机首页双列（约 186pt 宽，3 倍屏 558×314），4:3 按约 160pt 宽（480×360）；
    另存 1 倍（186×105 / 160×120）放大 3 倍的图，看最差情况（低分屏）下主标题还读不读得出。"""
    im = Image.open(png).convert('RGB')
    w = 558 if '16比9' in name else 480
    h = round(w * im.height / im.width)
    im.resize((w, h), Image.LANCZOS).save(WORK / f'{name}_手机3倍屏.png')
    s = im.resize((w // 3, h // 3), Image.LANCZOS)
    s.resize((w, h), Image.NEAREST).save(WORK / f'{name}_手机1倍屏放大.png')


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    bad = []
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for body, w, h, name, tsize in [(body_169(), 1920, 1080, '六级阅读真题60篇_封面_16比9', (320, 180)), (body_43(), 1440, 1080, '六级阅读真题60篇_封面_4比3', (240, 180))]:
            png, res = render(br, body, w, h, name)
            im = Image.open(png)
            assert im.size == (w * 2, h * 2), im.size
            t = thumbs(png, tsize, name + '_缩略图')
            phone(png, name)
            jpg = png.with_suffix('.jpg')             # 上传用：PNG 有 8–11 MB，B 站封面有大小上限，JPG 质量 92 约 1–2 MB
            im.convert('RGB').save(jpg, quality=92, optimize=True, progressive=True)
            print(f'   {jpg.name} {jpg.stat().st_size / 1e6:.1f} MB')
            print(png, im.size, '→', t, tsize)
            for b in res['boxes']:
                print(f"   {b['k']:8s} x {b['x0']:7.1f}–{b['x1']:7.1f}  y {b['y0']:6.1f}–{b['y1']:6.1f}")
            bad += [f'{name}: {x}' for x in res['problems']]
        br.close()
    if bad:
        print('自查不通过：\n  ' + '\n  '.join(bad))
        sys.exit(1)
    print('自查通过：文字不出画、不进底角遮挡区、关键元素互不重叠、字体全部加载')
