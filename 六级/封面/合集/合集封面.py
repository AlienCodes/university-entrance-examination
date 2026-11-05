"""B 站「六级」合集（系列）封面（2026-11-05）：黑板主题，与六级阅读 / 听力 / 写作各自的封面同一系列。

    /opt/ttsenv/bin/python 六级/封面/合集/合集封面.py 草稿      # A/B/C 三个方向，只出缩略图（16:9 320×180、960×540；裁后 4:3 240×180）到 work/
    /opt/ttsenv/bin/python 六级/封面/合集/合集封面.py 定稿 A    # A 出 3840×2160 PNG + 1920×1080 JPG + 裁后 4:3 预览，B、C 出 JPG 作备选
    /opt/ttsenv/bin/python 六级/封面/合集/合集封面.py --自检    # 双向验证（见 selftest）

老师要求（2026-11-05）：B 站六级系列；“六级”两个字绝对焦点、特大；一眼看到就想点；16:9。
总协调补充（同日）：合集封面外面按 16:9 显示、点进去按 4:3（同一张图从中间裁，左右各裁 12.5%）。所以一张图两用：
全部文字和关键图形都在中间 4:3 区域（1920 宽下 x = 240—1680，留 ≥ 20 CSS 像素 = 3840 下 40 像素边距），左右两条只放背景 / 装饰。
数字全部现算（踩坑 70）：阅读篇数与年份取 六级/封面/系列封面.py（vocab.json），听力套数与年份取 六级/听力/封面/系列封面.py（目录 + 发布清单），
写作篇数与年份取 六级作文/封面/系列封面.py（作文 json）；不印“02 / 09”编号，不写“保过”“提分”之类兑现不了的话。
程序自查：沿用同系列 CHECK_JS（不出画、不压木框、不进底角遮挡区、不重叠、字体加载、缩到高 180 后字号下限 主标题 24 / 钩子 13 / 卖点 10），
另加 SAFE_JS：每个 data-k 元素外框、每个文字节点的字框都在中间 4:3 安全区内；裁后 4:3 的底角遮挡区也不放字；画面上不许有“数字 / 数字”。
"""
import importlib.util
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
WORK = HERE / 'work'
OUT = HERE / '成品'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


L = _load('cet6_cover', REPO / '六级/封面/系列封面.py')               # 黑板主题、阅读数字
W = _load('cet6w_cover', REPO / '六级作文/封面/系列封面.py')          # CHECK_JS、写作数字
T = _load('cet6l_cover', REPO / '六级/听力/封面/系列封面.py')         # 听力数字

# ───────── 数字现算 ─────────
R_N = L.N
R_Y0, R_Y1 = (int(x) for x in L.YEARS.split('—'))
T_N, T_Y0, T_Y1 = T.N, T.Y0, T.Y1
W_N, W_Y0, W_Y1 = W.N, W.Y0, W.Y1
# 听力两种视频（视频版真题考试、原文精读）各 30 套：发布清单与听力目录逐套相同
T_TEXT = [s for s in (REPO / '.github/cet6-listening-text-render.txt').read_text('utf-8').split() if re.fullmatch(r'\d{6}-\d', s)]
assert sorted(T_TEXT) == T.SETS, '原文精读套数与听力真题套数不同，封面说法要改'
Y0, Y1 = min(R_Y0, T_Y0, W_Y0), max(R_Y1, T_Y1, W_Y1)
assert R_Y1 == T_Y1 == W_Y1 == Y1, '三项不是都更新到最新一年，“已更新”不能这样写'
assert (R_N, T_N, W_N, Y0, Y1) == (60, 30, 31, 2018, 2026), (R_N, T_N, W_N, Y0, Y1)   # 数据一变先核对封面说法
SPAN = f'{Y1}—{Y0}'            # 新的年份在前（老师 2026-11-04）

CHALK, YEL, PNK, BLU, INK, HOT, RED = L.CHALK, L.YEL, L.PNK, L.BLU, L.INK, L.HOT, W.RED
MIN_TITLE, MIN_HOOK, MIN_SELL = 24, 13, 10
K = 1.0                         # 字号系数：只给 --自检 用
SHIFT = None                    # 自检：把主标题挪到 left:SHIFT
NUMBERED = False                # 自检：画面上放一个“02 / 09”
VW, VH = 1920, 1080             # CSS 尺寸（截图 ×2 = 3840×2160）
SX0, SX1 = VW * .125, VW * .875  # 中间 4:3：240—1680
MARGIN = 20                     # CSS 像素（3840 下 40）
CX = VW / 2


def fs(n):
    return f'{n * K:.0f}px'


def yl(t):
    return f'<span style="color:{YEL}">{t}</span>'


def board(inner):
    side = ''.join(   # 左右两条（裁 4:3 时会去掉）只放装饰：淡粉笔字母
        f'<div class="ab" style="left:{x}px;top:{t}px;font:900 {s}px/1 Inter;color:rgba(255,255,255,.07);transform:rotate({r}deg)">{c}</div>'
        for x, t, s, r, c in [(46, 120, 200, -10, 'A'), (70, 520, 170, 8, 'B'), (40, 780, 150, -4, 'C'),
                              (1740, 110, 190, 9, 'D'), (1716, 470, 210, -8, '6'), (1760, 790, 150, 6, '?')])
    extra = ''
    if NUMBERED:
        extra = f'<div class="ab ck" data-k="num" style="left:{CX - 60}px;top:930px;font:900 40px/1 Black">02 / 09</div>'
    return f'<div class="board"></div><div class="grain"></div>{L.dust(VW, VH)}{side}{inner}{extra}{L.frame(VW, VH)}'


def title_pos(default):
    return f'left:{SHIFT}px' if SHIFT is not None else default


def brand(top):
    return (f'<div class="ab ck" data-k="brand" style="left:{SX0 + 40}px;top:{top}px;font:700 {fs(34)}/1 Bold;color:rgba(247,244,234,.78)">'
            f'朋克英语</div>')


def seal(x, y_, d, rot=8, k='hook', mn=MIN_HOOK):
    """“2026 已更新”粉笔红圆章。"""
    return (f'<div class="ab" data-k="{k}" data-min="{mn}" style="left:{x}px;top:{y_}px;width:{d}px;height:{d}px;transform:rotate({rot}deg);'
            f'display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.05;color:#fff">'
            f'<i style="position:absolute;inset:0;border-radius:50%;background:{RED};filter:url(#rough);box-shadow:0 8px 0 rgba(0,0,0,.3)"></i>'
            f'<i style="position:absolute;inset:{d * .06:.0f}px;border-radius:50%;border:5px dashed rgba(255,255,255,.75)"></i>'
            f'<span class="lat ck" style="position:relative;font-size:{fs(d * .27)}">{Y1}</span>'
            f'<span class="ck" style="position:relative;font:900 {fs(d * .25)}/1.15 Black">已更新</span></div>')


SUBJ = [('阅读', YEL, f'{R_N} 篇'), ('听力', BLU, f'{T_N} 套'), ('写作', PNK, f'{W_N} 篇')]
SUBJ_NOTE = {'阅读': '逐句精读', '听力': '真题＋原文', '写作': '满分范文'}


def tile(name, col, num, size, wd, note=True):
    """一门一块：大字科目（彩色粉笔框）+ 数字（+ 一行小说明）。"""
    sub = (f'<div class="ck" style="position:relative;font:900 {fs(size * .44)}/1.2 Black;color:{CHALK}">{SUBJ_NOTE[name]}</div>' if note else '')
    return (f'<div style="position:relative;display:inline-block;vertical-align:top;width:{wd}px;padding:8px 0 14px;text-align:center">'
            f'<i style="position:absolute;inset:0;border:6px solid {col};border-radius:24px;background:rgba(0,0,0,.20);filter:url(#line)"></i>'
            f'<div class="ck" style="position:relative;font:900 {fs(size)}/1.12 Black;color:{col}">{name}'
            f'<span style="font-size:.7em;color:{CHALK};margin-left:.2em"><span class="lat">{num.split()[0]}</span>{num.split()[1]}</span></div>{sub}</div>')


def tiles(top, size, wd, gap, note=True, k='sell'):
    row = f'<span style="display:inline-block;width:{gap}px"></span>'.join(tile(n, c, m, size, wd, note) for n, c, m in SUBJ)
    total = 3 * wd + 2 * gap
    return f'<div class="ab" data-k="{k}" data-min="{MIN_SELL}" style="left:{CX - total / 2:.0f}px;top:{top}px;white-space:nowrap">{row}</div>'


# ───────── A：“六级”特大居中 + 上方红色钩子条 + 下方三门三块 ─────────
MID = f'left:{CX}px;transform:translateX(-50%)'


def A():
    return board(f"""
{brand(54)}
<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="{MID};top:40px;font:900 {fs(92)}/1.18 Black">{L.hl(f'<span class="lat">{Y1}</span> 已更新', RED, ink='#fff', px=28)}</div>
<div class="ab ck" data-k="title" data-min="{MIN_TITLE}" style="{title_pos(MID)};top:162px;font:900 {fs(510)}/1 Black;color:{HOT}">六级</div>
<div class="ab ck" data-k="span" data-min="{MIN_SELL}" style="{MID};top:684px;font:900 {fs(76)}/1 Black">{yl(f'<span class="lat">{SPAN}</span>')} 真题逐句精读</div>
{tiles(796, 92, 420, 30, note=False)}""")


# ───────── B：左边“六级”特大 + 下方“真题逐句精读”，右栏圆章 + 三门竖排 ─────────
def B():
    x0 = SX0 + 46
    col = ''.join(f'<div style="margin-bottom:22px">{tile(n, c, m, 92, 450, note=False)}</div>' for n, c, m in SUBJ)
    return board(f"""
<div class="ab ck" data-k="title" data-min="{MIN_TITLE}" style="{title_pos(f'left:{x0}px')};top:70px;font:900 {fs(420)}/1 Black;color:{HOT}">六级</div>
{seal(1256, 52, 316, rot=8)}
<div class="ab ck" data-k="sub" data-min="{MIN_SELL}" style="left:{x0 + 10}px;top:540px;font:900 {fs(132)}/1 Black">真题{yl('逐句')}精读</div>
<div class="ab ck" data-k="span" data-min="{MIN_SELL}" style="left:{x0 + 14}px;top:716px;font:900 {fs(72)}/1 Black">{yl(f'<span class="lat">{SPAN}</span>')} 年真题</div>
<div class="ab ck" data-k="brand" style="left:{x0 + 16}px;top:842px;font:700 {fs(36)}/1 Bold;color:rgba(247,244,234,.78)">朋克英语</div>
<div class="ab" data-k="sell" data-min="{MIN_SELL}" style="left:1176px;top:420px;white-space:normal;width:460px">{col}</div>""")


# ───────── C：“六级”压在黄色粉笔涂块上（深色字），右上圆章，下方一行三门 ─────────
def C():
    return board(f"""
{brand(54)}
{seal(1306, 64, 316, rot=10)}
<div class="ab" data-k="title" data-min="{MIN_TITLE}" style="{title_pos(f'left:{SX0 + 96}px')};top:150px;font:900 {fs(440)}/1.1 Black">{L.hl('六级', YEL, px=44)}</div>
<div class="ab ck" data-k="sub" data-min="{MIN_SELL}" style="left:{SX0 + 70}px;top:660px;font:900 {fs(104)}/1 Black">真题{yl('逐句')}精读 <span class="lat" style="font-size:.66em;color:{CHALK}">{SPAN}</span></div>
{tiles(800, 92, 420, 30, note=False)}""")


DIRS = {'A': A, 'B': B, 'C': C}

SAFE_JS = r"""
([X0, X1, M, H]) => {
  const out = [], a = X0 + M, b = X1 - M, cw = X1 - X0;
  const bad = (q) => q.left < a - .5 || q.right > b + .5;
  const corner = (q) => q.bottom > H * .88 && (q.left < X0 + cw * .25 || q.right > X1 - cw * .25);
  for (const e of document.querySelectorAll('[data-k]')) {
    const q = e.getBoundingClientRect();
    if (bad(q)) out.push(`${e.dataset.k} 出了中间 4:3 安全区 x=${q.left.toFixed(0)}—${q.right.toFixed(0)}（应在 ${a}—${b}）`);
  }
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let t; (t = tw.nextNode());) {
    const s = t.textContent.trim();
    if (!s || t.parentElement.closest('svg,style')) continue;
    const st = getComputedStyle(t.parentElement);
    if (parseFloat(st.color.split(',')[3] ?? 1) < .1) continue;             // 左右两条的淡装饰字母
    const rg = document.createRange(); rg.selectNodeContents(t);
    for (const q of rg.getClientRects()) {
      if (bad(q)) out.push(`文字出了中间 4:3 安全区「${s}」x=${q.left.toFixed(0)}—${q.right.toFixed(0)}`);
      if (corner(q)) out.push(`文字进入裁后 4:3 的底角遮挡区「${s}」`);
    }
  }
  const all = document.body.innerText;
  for (const m of all.matchAll(/\d+\s*[\/／]\s*\d+/g)) out.push(`画面上有编号「${m[0]}」（踩坑 70）`);
  return out;
}"""


def render(br, body, name, out):
    html = WORK / f'{name}.html'
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{L.css(VW, VH)}</style></head>'
                    f'<body>{L.SVG_DEFS}{body}</body></html>', 'utf-8')
    pg = br.new_page(viewport={'width': VW, 'height': VH}, device_scale_factor=2)
    pg.goto(html.as_uri())
    pg.evaluate('document.fonts.ready.then(() => [...document.fonts].forEach(f => f.load()))')
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(500)
    res = pg.evaluate(W.CHECK_JS)['problems'] + pg.evaluate(SAFE_JS, [SX0, SX1, MARGIN, VH])
    png = out / f'{name}.png'
    pg.screenshot(path=str(png))
    pg.close()
    return png, res


def selftest(br):
    """双向验证：①正常 0 处；②字号 ×0.25 每个 data-min 元素都报；③主标题挪到 left:150（3840 下 300）必须报安全区；④放“02 / 09”必须报编号。"""
    global K, SHIFT, NUMBERED
    bad = []
    for k, f in DIRS.items():
        for case in ('正常', '字号', '左移', '编号'):
            K, SHIFT, NUMBERED = (0.25 if case == '字号' else 1.0), (150 if case == '左移' else None), case == '编号'
            body = f()
            _, res = render(br, body, f'自检_{k}_{case}', WORK)
            if case == '正常' and res:
                bad.append(f'{k} 正常也报：{res}')
            if case == '字号':
                hit = {x.split()[0] for x in res if '缩略图字高' in x}
                need = set(re.findall(r'data-k="(\w+)" data-min=', body))
                if not {'title', 'hook'} <= need or hit != need:
                    bad.append(f'{k} 字号×0.25：报出 {sorted(hit)}，应为 {sorted(need)}')
            if case == '左移' and not any(x.startswith('title 出了中间 4:3') for x in res):
                bad.append(f'{k} 主标题左移没报安全区：{res}')
            if case == '编号' and not any('编号' in x for x in res):
                bad.append(f'{k} 放了“02 / 09”没报')
    K, SHIFT, NUMBERED = 1.0, None, False
    return bad


def thumbs(png, name):
    im = Image.open(png).convert('RGB')
    assert im.size == (VW * 2, VH * 2), im.size
    crop = im.crop((round(SX0 * 2), 0, round(SX1 * 2), VH * 2))
    im.resize((320, 180), Image.LANCZOS).save(WORK / f'{name}_320.png')
    im.resize((960, 540), Image.LANCZOS).save(WORK / f'{name}_960.png')
    crop.resize((240, 180), Image.LANCZOS).save(WORK / f'{name}_裁4比3_240.png')
    return im, crop


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
            print('\n'.join(bad) or '自检通过：正常 0 处；字号×0.25 每个 data-min 都报；主标题左移报安全区；“02 / 09”报编号（A/B/C）')
            return 1 if bad else 0
        final = args[1] if args[0] == '定稿' else None
        stem = '六级合集封面'
        for k, f in DIRS.items():
            if final is None:
                name, out = f'草稿_{k}', WORK
            else:
                name, out = (f'{stem}_16比9', OUT) if k == final else (f'{stem}_备选{k}_16比9', OUT)
            png, res = render(br, f(), name, out)
            bad += [f'{name}: {x}' for x in res]
            im, crop = thumbs(png, name)
            if out is OUT:
                im.resize((VW, VH), Image.LANCZOS).save(png.with_suffix('.jpg'), quality=92, optimize=True, progressive=True)
                if k == final:
                    crop.resize((1440, 1080), Image.LANCZOS).save(OUT / f'{stem}_裁后4比3预览.jpg', quality=90, optimize=True)
                else:
                    png.unlink()
        br.close()
    if bad:
        print('自查不通过：\n  ' + '\n  '.join(bad))
        return 1
    print('自查通过：字号下限、中间 4:3 安全区、裁后底角、不出画、不重叠、字体、无编号')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['草稿']))
