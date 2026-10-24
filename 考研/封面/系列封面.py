"""考研 B 站系列封面（晴空校园，与视频同一套画面：蓝天、太阳、985 教学楼、白卡片、黄色胶囊）：一条命令生成 16:9 和 4:3 两张。

    /opt/ttsenv/bin/python 考研/封面/系列封面.py

输出 考研/封面/系列封面/：考研阅读真题50篇_封面_16比9.png / .jpg（3840×2160）、考研阅读真题50篇_封面_4比3.png / .jpg（2880×2160），
JPG 供上传（B 站封面有大小上限）；考研/封面/work/（不入库）里有缩略图、B 站信息流模拟图、手机实际大小预览。
用户要求（2026-10-21）：一定要突出“考研”两个字；一眼看出 50 篇考研阅读真题；用来记住考研所有重点单词；要非常吸引考研的 B 站粉丝点进来。
做法与六级系列封面（六级/封面/系列封面.py）相同：所有文字实心、边缘干净；“考研”是全图最大、最醒目的字（橙红，在白卡片上对比最强）。
封面上的数字全部从 考研/data/vocab.json 现算（50 篇、971 句、不重复词条 4121 → “4000+”只往下取整，不夸大）。
渲染后程序自查：文字不出画、不进 B 站左下（播放量）/右下（时长）遮挡区、关键元素互不重叠、字体全部加载。
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

_P = json.loads((REPO / '考研' / 'data' / 'vocab.json').read_text('utf-8'))['passages']
N = len(_P)
SENTS = sum(len(pa) for p in _P for pa in p['paras'])
UNIQ = len({w['h'].strip().lower() for p in _P for pa in p['paras'] for s in pa for w in s['w']})
YEARS = f"{min(p['year'] for p in _P)}—{max(p['year'] for p in _P)}"
assert N == 50 and sum(p['passage'] == 'Part B' for p in _P) == 2 and all(p.get('done') for p in _P)
assert SENTS == 971 and UNIQ == 4121 and YEARS == '2021—2026', (SENTS, UNIQ, YEARS)      # 数据一改就停下，先核对封面上的说法
UNIQ_TXT = f'{UNIQ // 1000 * 1000}+'          # 4121 → “4000+”，只往下取整，不夸大

# 视频的晴空校园配色（tools/video/themes/css/1_晴空校园.css）；“考研”用比视频短语橙更亮的橙红——蓝天、白卡上最跳
NAVY, BLUE, SUN, MARK, KY = '#123a6b', '#1052a8', '#ffc93c', '#ffe27a', '#ff4a12'
THEME = (REPO / 'tools/video/themes/css/1_晴空校园.css').read_text('utf-8')
SKY = re.search(r'body:has\(\.ttl\)\{background-image:url\("(data:image/svg\+xml;utf8,.*?)"\);background-size:cover\}', THEME).group(1)   # 视频片头的蓝天、太阳、985 教学楼


SHOTS = {'front': 'k01_第4句.jpg', 'back': 'k21_第4句.jpg'}      # 真实视频画面（与视频逐像素相同的审阅截图）


def shot(name):
    return (ASSETS / SHOTS[name]).as_uri()


def css(w, h):
    return f"""
@font-face{{font-family:Black;src:url({F_BLACK.as_uri()})}}
@font-face{{font-family:Bold;src:url({F_BOLD.as_uri()})}}
@font-face{{font-family:Inter;font-weight:800;src:url({F_INTER.as_uri()})}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:#9fd6ff}}
body{{position:relative;font-family:Black,sans-serif;color:{NAVY}}}
.sky{{position:absolute;inset:0;background:url("{SKY}") right center/cover no-repeat}}
.sky43{{background-position:-300px center;background-size:auto 100%}}
.ab{{position:absolute;white-space:nowrap}}
.wcard{{position:absolute;background:#fff;border-radius:48px;box-shadow:0 18px 0 rgba(16,82,168,.16),0 26px 60px rgba(18,58,107,.28)}}
.lat{{font-family:Inter,Black,sans-serif;font-weight:800}}
.mk{{box-shadow:inset 0 -.40em 0 {MARK};border-radius:.1em;padding:0 .04em}}
.card{{position:absolute;border:10px solid #fff;border-radius:18px;box-shadow:0 14px 0 rgba(16,82,168,.18),0 22px 50px rgba(18,58,107,.35)}}
.tape{{position:absolute;width:130px;height:40px;background:rgba(255,226,122,.85);box-shadow:0 2px 4px rgba(0,0,0,.18)}}
"""


def pill(text, size):
    """视频片头同款黄色胶囊（KAOYAN · READING）。"""
    return (f'<span style="display:inline-block;font:900 {size}px/1.2 Black;color:#3d2a00;background:{SUN};padding:10px 34px 12px;'
            f'border-radius:999px;box-shadow:0 6px 0 #f0ad1e;letter-spacing:.06em">{text}</span>')


def tag(inner, size, mr=18):
    """数字标签：蓝框白底圆角。"""
    return (f'<span style="display:inline-block;font:900 {size}px/1.25 Black;color:{NAVY};padding:8px 24px 10px;margin-right:{mr}px;'
            f'border:5px solid {BLUE};border-radius:18px;background:#f2f8ff">{inner}</span>')


def tags(size, mr=18):
    y = f'<span style="color:{KY}">'
    return (tag(f'{y}{SENTS}</span> 句逐句精读', size, mr) +
            tag(f'{y}{UNIQ_TXT}</span> 单词短语全标注', size, mr) +
            tag(f'{y}4K</span> 大字版', size, mr))


FEAT = ['逐句朗读', '逐句翻译', '生词编号注释', '一句一屏']


def feat(size, gap=34):
    box = (f'<svg width="{size * .86:.0f}" height="{size * .86:.0f}" viewBox="0 0 40 40" style="vertical-align:-.08em;margin-right:.26em;overflow:visible">'
           f'<rect x="3" y="5" width="32" height="32" rx="7" fill="{BLUE}"/>'
           f'<path d="M10 21 L 17 28 L 30 12" fill="none" stroke="#fff" stroke-width="5.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    return ''.join(f'<span style="margin-right:{gap}px">{box}{t}</span>' for t in FEAT)


def sticker(x, y, d):
    """“50篇”圆形贴纸（视频片头右上角“考研 精读”贴纸同款橙色圆章，放大）。"""
    return (f'<div class="ab" data-k="sticker" style="left:{x}px;top:{y}px;width:{d}px;height:{d}px;border-radius:50%;background:#ff7a1a;'
            f'border:{d * .045:.0f}px solid #fff;box-shadow:0 {d * .04:.0f}px 0 rgba(184,60,0,.35),0 {d * .06:.0f}px {d * .16:.0f}px rgba(18,58,107,.35);'
            f'transform:rotate(-10deg);display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;line-height:1">'
            f'<div><span class="lat" style="font-size:{d * .44:.0f}px;letter-spacing:-.03em">{N}</span><span style="font:900 {d * .2:.0f}px Black">篇</span></div>'
            f'<div style="font:900 {d * .105:.0f}px/1.3 Black;margin-top:{d * .02:.0f}px;letter-spacing:.08em">真题全收录</div></div>')


def cards(x, y, w):
    return (f'<img class="card" data-k="card2" src="{shot("back")}" style="left:{x + 40}px;top:{y + 40}px;width:{w - 24}px;transform:rotate(6deg)">'
            f'<img class="card" data-k="card1" src="{shot("front")}" style="left:{x}px;top:{y}px;width:{w}px;transform:rotate(-4deg)">'
            f'<div class="tape" style="left:{x + w / 2 - 65}px;top:{y - 22}px;transform:rotate(-6deg)"></div>')


KAOYAN = f'<span style="color:{KY};font-size:1.56em;letter-spacing:-.02em;text-shadow:0 .05em 0 {SUN}">考研</span>'


def body_169(w=1920, h=1080):
    return f"""
<div class="sky"></div>
<div class="wcard" style="left:46px;top:42px;width:1268px;height:882px"></div>
<div class="ab" data-k="pill" style="left:104px;top:86px">{pill(f'<span class="lat">{YEARS}</span> · 英语一 + 英语二', 46)}</div>
<div class="ab" data-k="title" style="left:96px;top:176px;font:900 162px/1 Black">{KAOYAN}<span>阅读真题</span></div>
<div class="ab" data-k="hook" style="left:104px;top:470px;font:900 106px/1.2 Black">记住考研<span class="mk" style="font-size:1.1em;color:{KY}">所有重点单词</span></div>
<div class="ab" data-k="tags" style="left:104px;top:654px">{tags(42)}</div>
<div class="ab" data-k="feat" style="left:108px;top:792px;font:700 44px/1.3 Bold;color:{NAVY}">{feat(44)}</div>
{sticker(1290, 40, 300)}
{cards(1352, 392, 520)}"""


def body_43(w=1440, h=1080):
    return f"""
<div class="sky sky43"></div>
<div class="wcard" style="left:36px;top:40px;width:964px;height:880px"></div>
<div class="ab" data-k="pill" style="left:84px;top:80px">{pill(f'<span class="lat">{YEARS}</span> · 英语一 + 英语二', 40)}</div>
<div class="ab" data-k="title" style="left:76px;top:160px;font:900 126px/1 Black">{KAOYAN}<span>阅读真题</span></div>
<div class="ab" data-k="hook" style="left:84px;top:404px;font:900 104px/1.22 Black">记住考研<br><span class="mk" style="font-size:1.1em;color:{KY}">所有重点单词</span></div>
<div class="ab" data-k="tags" style="left:84px;top:694px;line-height:1.8">{tag(f'<span style="color:{KY}">{SENTS}</span> 句逐句精读', 42)}{tag(f'<span style="color:{KY}">4K</span> 大字版', 42, 0)}<br>{tag(f'<span style="color:{KY}">{UNIQ_TXT}</span> 单词短语全标注', 42, 0)}</div>
{sticker(1050, 46, 290)}
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
        for body, w, h, name, tsize in [(body_169(), 1920, 1080, '考研阅读真题50篇_封面_16比9', (320, 180)),
                                        (body_43(), 1440, 1080, '考研阅读真题50篇_封面_4比3', (240, 180))]:
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
