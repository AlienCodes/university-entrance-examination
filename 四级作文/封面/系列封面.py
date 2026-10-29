"""四级写作 B 站系列封面（2026-10-29）：Release cet4-writing，四级真题范文逐句精读。

    python3 四级作文/封面/系列封面.py 草稿        # A/B/C 三个方向，16:9 + 4:3，只出 320×180、960×540 缩略图到 work/
    python3 四级作文/封面/系列封面.py 定稿 A      # A 出 16:9（3840×2160）+ 4:3（2880×2160），PNG + JPG；B、C 的 16:9 JPG 作备选
    python3 四级作文/封面/系列封面.py --自检      # 双向验证：字号×0.5、放回“02 / 09”编号、数字写错、缺字都必须报出，正常 0 处

用户要求（2026-10-29）：“绝对完美”，绝对能吸引考四级的人点进来；封面上一定要有「四级真题范文」和「彻底搞定四级写作」。
按 B 站信息流缩略图（320×180）设计（踩坑 76）：一个焦点（彻底搞定四级写作 / 四级真题范文）+ 一个钩子（2026.6 已更新、32 篇），其余次要。
数字全部从 四级/作文/<年>.json 现算（篇数、考试次数、年份、最新一次），不手写（踩坑 70）；不印“02 / 09”编号。
程序自查：文字不出画、不进 B 站底角遮挡区（播放量 / 时长）、互不重叠、不压截图、字体全部加载、每个字都在所用字体里（fontTools 查 cmap，
不许回退到系统字体）、缩到高 180 后字号不低于下限（主标题 24、钩子 13、卖点 10 像素，同 专八/封面/系列封面.py）、画面上没有“数字/数字”、
画面上出现的数字都是现算的那几个、两句必有的话都在。
素材：视频真实画面 四级作文/大字版/截图/c01/screen07.webp（2026 年 6 月第 1 套，四级杂志样式）。
字体：四级/封面/fonts/（思源黑体 900/700、思源宋体 900，ttf 不进仓库；缺了自动从 Google Fonts 下载）。
"""
import json
import re
import sys
import urllib.request
from collections import OrderedDict
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORK = HERE / 'work'
OUT = HERE / '系列封面'
SHOT = REPO / '四级作文/大字版/截图/c01/screen07.webp'
FD = REPO / '四级/封面/fonts'
FONTS = {   # 名字 → (文件, Google Fonts 地址)
    'Black': ('NotoSansSC_900Black.ttf', 'https://fonts.gstatic.com/s/notosanssc/v41/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaG3bCnYw.ttf'),
    'Bold': ('NotoSansSC_700Bold.ttf', 'https://fonts.gstatic.com/s/notosanssc/v41/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaGzjCnYw.ttf'),
    'SerifSC': ('NotoSerifSC_900Black.ttf', 'https://fonts.gstatic.com/s/notoserifsc/v36/H4cyBXePl9DZ0Xe7gG9cyOj7uK2-n-D2rd4FY7QrrCWv.ttf'),
}

# ───────── 数字现算 ─────────
ESSAYS = [e for y in range(2015, 2100) if (REPO / f'四级/作文/{y}.json').exists()
          for e in json.loads((REPO / f'四级/作文/{y}.json').read_text('utf-8'))]
N = len(ESSAYS)
EXAMS = OrderedDict()                                    # 年 → {月: 套数}
for e in sorted(ESSAYS, key=lambda e: e['id']):
    yy, mm, _ = e['id'][1:].split('-')
    EXAMS.setdefault(int(yy), OrderedDict()).setdefault(int(mm), 0)
    EXAMS[int(yy)][int(mm)] += 1
YEARS = sorted(EXAMS)
Y0, Y1 = YEARS[0], YEARS[-1]
M1 = max(EXAMS[Y1])
NEWEST = f'{Y1}.{M1}'
N_EXAM = sum(len(v) for v in EXAMS.values())
assert YEARS == list(range(Y0, Y1 + 1))                 # 年份连续，“2021—2026 全部真题”才成立
assert (N, N_EXAM, Y0, Y1, M1) == (32, 11, 2021, 2026, 6), (N, N_EXAM, Y0, Y1, M1)   # 数据一变先核对封面说法
ALLOWED_NUM = {str(N), str(N_EXAM), str(M1), '4', *map(str, YEARS)}   # 4 只出现在 CET-4 / 4K
MUST = ['彻底搞定四级写作', '四级真题范文', f'{N}篇', f'{Y0}—{Y1}', '已更新']

PAPER, GREEN, RED, INK, YEL, CREAM = '#fbf8f1', '#1d5741', '#c8402a', '#141414', '#FFD60A', '#fff6dc'
MIN_TITLE, MIN_HOOK, MIN_SELL = 24, 13, 10
K = 1.0          # 字号系数（只给 --自检 用）
EXTRA = ''       # 自检时往画面里塞的东西
SEAL_R = .232    # 圆章字号 / 直径（自检放回草稿的 .3 必须报“字出了圆”）


def fs(n):
    return f'{n * K:.0f}px'


def css(w, h):
    ff = ''.join(f"@font-face{{font-family:{k};src:url('{(FD / f).as_uri()}')}}" for k, (f, _) in FONTS.items())
    return (f'{ff}*{{margin:0;padding:0;box-sizing:border-box}}html,body{{width:{w}px;height:{h}px;overflow:hidden}}'
            f'body{{font-family:Black;position:relative}}.ab{{position:absolute;white-space:nowrap}}'
            f'.card{{position:absolute;border:8px solid #fff;box-shadow:0 18px 40px rgba(0,0,0,.35),0 0 0 2px rgba(0,0,0,.12)}}')


def seal(x, y, d, bg=RED, fg='#fff', rot=-8, ring='rgba(255,255,255,.8)'):
    """“2026.6 已更新”圆章（钩子）。"""
    return (f'<div class="ab" data-k="seal" data-min="{MIN_HOOK}" data-round="1" style="left:{x}px;top:{y}px;width:{d}px;height:{d}px;border-radius:50%;'
            f'background:{bg};color:{fg};transform:rotate({rot}deg);display:flex;flex-direction:column;align-items:center;justify-content:center;'
            f'box-shadow:0 10px 24px rgba(0,0,0,.28);line-height:1.08">'
            f'<i style="position:absolute;inset:{d * .055:.0f}px;border-radius:50%;border:{max(3, d * .016):.0f}px dashed {ring}"></i>'
            f'<span style="font:900 {fs(d * SEAL_R)} Black;letter-spacing:-.03em">{NEWEST}</span>'
            f'<span style="font:900 {fs(d * SEAL_R)} Black">已更新</span></div>')


def card(x, y, w, rot=3):
    return f'<img class="card" data-k="card" src="{SHOT.as_uri()}" style="left:{x}px;top:{y}px;width:{w}px;transform:rotate({rot}deg)">'


# ───────── A：四级杂志纸面（与视频同一画风）＋ 真实画面 ─────────
def A(w=1920, h=1080):
    wide = w >= 1900
    t = 250 if wide else 220                       # 主标题字号
    sub = 170 if wide else 160
    left = 74 if wide else 60
    return f"""
<div style="position:absolute;inset:0;background:{PAPER}"></div>
<div style="position:absolute;left:0;top:0;width:{w}px;height:22px;background:{GREEN}"></div>
<div style="position:absolute;left:{left}px;top:22px;width:{w - 2 * left}px;height:4px;background:{RED}"></div>
<div class="ab" data-k="sell" data-min="{MIN_SELL}" style="left:{left}px;top:44px;font:900 {fs(64)}/1.2 SerifSC;color:{GREEN};letter-spacing:.02em">
 {Y0}—{Y1} 全部真题 <span style="color:{RED}">{N}篇</span> · 逐句精读</div>
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:{left - 8}px;top:{128 if wide else 140}px;font:900 {fs(t)}/1.04 Black;color:{INK};letter-spacing:-.02em">
 <div>彻底搞定</div><div><span style="color:{RED}">四级</span>写作</div></div>
<div class="ab" data-k="sub" data-min="{MIN_TITLE}" style="left:{left}px;top:{t * 2.08 + (150 if wide else 168):.0f}px;font:900 {fs(sub)}/1 Black;color:#fff;background:{GREEN};padding:{sub * .16:.0f}px {sub * .22:.0f}px {sub * .2:.0f}px;box-shadow:12px 12px 0 {RED}">
 四级真题范文</div>
{card(1210, 440, 650, rot=3) if wide else card(1104, 640, 300, rot=4)}
{seal(1520, 50, 340) if wide else seal(1040, 170, 340)}
{EXTRA}"""


# ───────── B：深绿底 · 居中大字（无截图，信息流里对比最强） ─────────
def B(w=1920, h=1080):
    wide = w >= 1900
    c = w / 2
    t = 200 if wide else 156
    sub = 164 if wide else 156
    tops = (56, 180, 440, 700) if wide else (36, 136, 330, 570)
    sl = seal(1530, 560, 340, bg=RED, rot=-6) if wide else seal(c - 170, 680, 340, bg=RED, rot=-6)
    return f"""
<div style="position:absolute;inset:0;background:radial-gradient(ellipse at 50% 40%, #236a4f 0%, {GREEN} 55%, #123b2b 100%)"></div>
<div class="ab" data-k="sell" data-min="{MIN_SELL}" style="left:{c}px;transform:translateX(-50%);top:{tops[0]}px;font:900 {fs(66)}/1.2 Black;color:{CREAM}">
 {Y0}—{Y1} · {N_EXAM} 次考试 · <span style="color:{YEL}">{N}篇</span></div>
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:{c}px;transform:translateX(-50%);top:{tops[1]}px;font:900 {fs(t)}/1.1 Black;color:#fff;letter-spacing:-.01em">
 彻底搞定<span style="color:{YEL}">四级</span>写作</div>
<div class="ab" data-k="sub" data-min="{MIN_TITLE}" style="left:{c}px;transform:translateX(-50%);top:{tops[2]}px;font:900 {fs(sub)}/1 Black;color:{INK};background:{YEL};padding:{sub * .14:.0f}px {sub * .26:.0f}px {sub * .18:.0f}px;border-radius:14px;box-shadow:0 14px 0 #0b2a1e">
 四级真题范文</div>
<div class="ab" data-k="sell2" data-min="{MIN_SELL}" style="left:{c}px;transform:translateX(-50%);top:{tops[3]}px;font:900 {fs(64)}/1.2 Black;color:{CREAM}">
 逐句精读 · 生词标注 · 中文翻译</div>
{sl}
{EXTRA}"""


# ───────── C：黄黑撞色（与四级阅读系列封面同一品牌色）＋ 真实画面 ─────────
def C(w=1920, h=1080):
    wide = w >= 1900
    left = 84 if wide else 60
    return f"""
<div style="position:absolute;inset:0;background:{YEL}"></div>
<div class="ab" data-k="sell" data-min="{MIN_SELL}" style="left:{left}px;top:48px;font:900 {fs(64 if wide else 62)}/1.2 Black;color:{INK}">
 大学英语四级 · {Y0}—{Y1} 全部真题</div>
<div class="ab" data-k="sub" data-min="{MIN_TITLE}" style="left:{left - 6}px;top:{130 if wide else 130}px;line-height:1;font:900 {fs(214 if wide else 160)}/1 Black;color:{INK};letter-spacing:-.02em">
 <span style="color:{RED}">{N}</span>篇四级真题范文</div>
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="left:{left}px;top:{390 if wide else 350}px;font:900 {fs(150)}/1.2 Black;color:#fff;background:{INK};padding:0 30px 6px">
 彻底搞定<span style="color:{YEL}">四级写作</span></div>
<div class="ab" data-k="sell2" data-min="{MIN_SELL}" style="left:{left}px;top:{630 if wide else 590}px;font:900 {fs(64)}/1.2 Black;color:{INK}">
 满分范文 · 逐句精读 · 生词标注</div>
{card(1130, 650, 660, rot=-3) if wide else card(70, 740, 560, rot=-2)}
{seal(1500, 520, 340, rot=10) if wide else seal(1052, 570, 340, rot=6)}
{EXTRA}"""


DIRS = {'A': A, 'B': B, 'C': C}

CHECK_JS = r"""
() => {
  const W = innerWidth, H = innerHeight, out = [];
  const els = [...document.querySelectorAll('[data-k]')];
  const r = els.map(e => { const b = e.getBoundingClientRect(); return {k: e.dataset.k, x0: b.left, y0: b.top, x1: b.right, y1: b.bottom}; });
  for (const a of r) {
    const card = a.k === 'card';
    if (!card && (a.x0 < 24 || a.y0 < 24 || a.x1 > W - 24 || a.y1 > H - 24)) out.push(`${a.k} 出画 ${JSON.stringify(a)}`);
    if (card && (a.x0 < 0 || a.x1 > W || a.y1 > H + 200)) out.push(`${a.k} 截图出画过多`);
    if (!card && a.y1 > H * 0.86 && (a.x0 < W * 0.25 || a.x1 > W * 0.75)) out.push(`${a.k} 进入底角遮挡区`);
  }
  for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) {
    const a = r[i], b = r[j];
    if (els[i].contains(els[j]) || els[j].contains(els[i])) continue;
    if (a.k === 'seal' && b.k === 'card' || a.k === 'card' && b.k === 'seal') continue;    // 圆章故意盖在截图一角
    const ox = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), oy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
    if (ox > 0 && oy > 0) out.push(`${a.k} 与 ${b.k} 重叠 ${ox.toFixed(0)}×${oy.toFixed(0)}`);
  }
  const cards = [...document.querySelectorAll('.card')].map(e => e.getBoundingClientRect());
  const texts = [];
  for (const e of document.querySelectorAll('[data-k]:not(.card)')) {
    const tw = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
    for (let t; (t = tw.nextNode());) if (t.textContent.trim()) {
      texts.push([getComputedStyle(t.parentElement).fontFamily, t.textContent]);
      if (e.dataset.k === 'seal') continue;
      const rg = document.createRange(); rg.selectNodeContents(t);
      for (const q of rg.getClientRects())
        for (const c of cards) if (q.right > c.left && q.left < c.right && q.bottom > c.top && q.top < c.bottom) out.push(`${e.dataset.k} 文字压到截图「${t.textContent.trim()}」`);
    }
  }
  for (const e of document.querySelectorAll('[data-min]')) {
    const tw = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
    let m = 1e9;
    for (let t; (t = tw.nextNode());) if (t.textContent.trim()) m = Math.min(m, parseFloat(getComputedStyle(t.parentElement).fontSize));
    const px = m * 180 / H;
    if (px < +e.dataset.min) out.push(`${e.dataset.k} 缩略图字高 ${px.toFixed(1)}px < 下限 ${e.dataset.min}px（320×180）`);
  }
  for (const e of document.querySelectorAll('[data-round]')) {     // 圆章：每个字框四角都在圆内（留 4% 边）
    const tf = e.style.transform; e.style.transform = 'none';       // 在没旋转的坐标里量
    const b = e.getBoundingClientRect(), cx = (b.left + b.right) / 2, cy = (b.top + b.bottom) / 2, R = e.offsetWidth / 2 * 0.96;
    const tw = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
    for (let t; (t = tw.nextNode());) if (t.textContent.trim()) {
      const rg = document.createRange(); rg.selectNodeContents(t);
      for (const q of rg.getClientRects()) {
        const dx = Math.max(Math.abs(q.left - cx), Math.abs(q.right - cx)), dy = Math.max(Math.abs(q.top + q.height * .2 - cy), Math.abs(q.bottom - q.height * .2 - cy));
        if (Math.hypot(dx, dy) > R) out.push(`${e.dataset.k} 字出了圆「${t.textContent.trim()}」`);
      }
    }
    e.style.transform = tf;
  }
  const bad = [...document.fonts].filter(f => f.status !== 'loaded').map(f => f.family);
  if (bad.length) out.push('字体未加载: ' + bad.join(','));
  return {problems: out, texts: texts, all: document.body.innerText};
}"""

_CMAP = {}


def cmap(fam):
    if fam not in _CMAP:
        from fontTools.ttLib import TTFont
        _CMAP[fam] = set(TTFont(FD / FONTS[fam][0], lazy=True).getBestCmap())
    return _CMAP[fam]


def text_problems(res):
    """缺字 / 字体回退、“数字/数字”编号、数字与数据一致、必有的话。"""
    out = []
    for fam, t in res['texts']:
        f0 = fam.split(',')[0].strip().strip('"\'')
        if f0 not in FONTS:
            out.append(f'「{t.strip()}」用了不认识的字体 {fam}')
            continue
        miss = {ch for ch in t if not ch.isspace() and ord(ch) not in cmap(f0)}
        if miss:
            out.append(f'「{t.strip()}」{f0} 缺字 {"".join(sorted(miss))}（会回退到系统字体）')
    flat = re.sub(r'\s+', '', res['all'])
    for m in re.finditer(r'\d+\s*[/／]\s*\d+', res['all']):
        out.append(f'画面上有“数字/数字”编号「{m.group()}」（踩坑 70）')
    for num in re.findall(r'\d+', res['all']):
        if num not in ALLOWED_NUM:
            out.append(f'数字 {num} 不是从数据现算的（应为 {sorted(ALLOWED_NUM)} 之一）')
    for s in MUST:
        if s not in flat:
            out.append(f'画面上没有「{s}」')
    return out


def ensure_fonts():
    for f, url in FONTS.values():
        p = FD / f
        if not p.exists() or p.stat().st_size < 1e6:
            print('下载字体', f)
            urllib.request.urlretrieve(url, p)


def render(br, body, w, h, name, out):
    html = WORK / f'{name}.html'
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{css(w, h)}</style></head><body>{body}</body></html>', 'utf-8')
    pg = br.new_page(viewport={'width': w, 'height': h}, device_scale_factor=2)
    pg.goto(html.as_uri())
    pg.evaluate('document.fonts.ready.then(() => Promise.all([...document.fonts].map(f => f.load())))')
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(400)
    res = pg.evaluate(CHECK_JS)
    png = out / f'{name}.png'
    pg.screenshot(path=str(png))
    pg.close()
    return png, res['problems'] + text_problems(res)


def selftest(br):
    """双向验证：正常 0 处；字号×0.5 每个 data-min 都报；放回“02 / 09”、写错篇数、塞进字体里没有的字都报。"""
    global K, EXTRA, SEAL_R
    bad = []
    cases = [('正常', 1.0, '', None),
             ('字号×0.5', 0.5, '', '缩略图字高'),
             ('编号', 1.0, '<div class="ab" data-k="num" style="left:900px;top:960px;font:900 40px Black">02 / 09</div>', '数字/数字'),
             ('篇数写错', 1.0, '<div class="ab" data-k="num" style="left:900px;top:960px;font:900 40px Black">31篇</div>', '不是从数据现算'),
             ('缺字', 1.0, '<div class="ab" data-k="num" style="left:900px;top:960px;font:900 40px Black">四级😀</div>', '缺字'),
             ('圆章字大', 1.0, '', '字出了圆')]
    for k, f in DIRS.items():
        for w in (1920, 1440):
            for nm, kk, extra, want in cases:
                K, EXTRA, SEAL_R = kk, extra, (.3 if nm == "圆章字大" else .232)
                body = f(w, 1080)
                _, probs = render(br, body, w, 1080, f'自检_{k}_{w}_{nm}', WORK)
                if want is None:
                    if probs:
                        bad.append(f'{k}{w} 正常却报 {probs}')
                    continue
                if want == '缩略图字高':
                    need = set(re.findall(r'data-k="(\w+)" data-min=', body))
                    hit = {x.split()[0] for x in probs if want in x}
                    if hit != need or not {'title', 'sub', 'seal'} <= need:
                        bad.append(f'{k}{w} {nm}：报出 {sorted(hit)}，应为 {sorted(need)}')
                elif not any(want in x for x in probs):
                    bad.append(f'{k}{w} {nm}：没报出')
    K, EXTRA, SEAL_R = 1.0, "", .232
    return bad


def main(args):
    from playwright.sync_api import sync_playwright
    ensure_fonts()
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    bad = []
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        if args[0] == '--自检':
            bad = selftest(br)
            br.close()
            print('\n'.join(bad) or '自检通过：正常 0 处；字号×0.5、“02 / 09”编号、篇数写错、缺字、圆章字出圆全部报出（A/B/C × 16:9、4:3）')
            return 1 if bad else 0
        final = args[1] if args[0] == '定稿' else None
        jobs = []
        for k, f in DIRS.items():
            if final is None:
                jobs += [(f(1920, 1080), 1920, 1080, f'草稿_{k}_16比9', WORK, False), (f(1440, 1080), 1440, 1080, f'草稿_{k}_4比3', WORK, False)]
            elif k == final:
                jobs += [(f(1920, 1080), 1920, 1080, f'四级写作真题范文{N}篇_封面_16比9', OUT, True),
                         (f(1440, 1080), 1440, 1080, f'四级写作真题范文{N}篇_封面_4比3', OUT, True)]
            else:
                jobs.append((f(1920, 1080), 1920, 1080, f'四级写作真题范文{N}篇_封面备选{k}_16比9', OUT, False))
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
    print('自查通过：缩略图字高达标、文字不出画、不进底角遮挡区、不压截图、互不重叠、字体全部加载、无缺字、无编号、数字与数据一致')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['草稿']))
