"""四级听力 B 站系列封面（2026-11-06）：与六级听力封面（六级/听力/封面/系列封面.py）同一黑板系列，改成四级。

    /opt/ttsenv/bin/python 四级/听力/封面/系列封面.py 草稿        # A/B/C 三个方向 16:9 + 4:3，只出 320×180、960×540 缩略图到 work/
    /opt/ttsenv/bin/python 四级/听力/封面/系列封面.py 定稿 A      # 定稿出 16:9 + 4:3（PNG + JPG）到 系列封面/，另两个方向 16:9 JPG 作备选
    /opt/ttsenv/bin/python 四级/听力/封面/系列封面.py --自检      # 双向验证：①字号×0.4 每个 data-min 元素都报、正常 0；②放进年份 / “N 套”必须报、现在 0

老师要求（2026-11-06）：封面上绝对不出现任何年份（每年加新听力不换封面），改用“持续更新 / 最新真题”；套数也不写死，用“历年真题全收录”。
两种视频都要突出：视频版真题考试（真题）＋ 原文逐句精读（原文解析：中文翻译、答案、精讲）。
程序自查：六级作文 CHECK_JS（不出画、不压框、不进底角遮挡区、不重叠、字体加载、缩略图字高，踩坑 76）＋ NO_YEAR（画面文字里出现 19xx/20xx 或“数字＋套”就报）。
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


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


L = _load('cet6_cover', REPO / '六级/封面/系列封面.py')            # 黑板主题：配色、滤镜、木框、粉笔涂块
W = _load('cet6w_cover', REPO / '六级作文/封面/系列封面.py')       # 自查程序 CHECK_JS
S6 = _load('cet6l_cover', REPO / '六级/听力/封面/系列封面.py')     # 粉笔耳机、黑板底

CHALK, YEL, PNK, BLU, INK, HOT = L.CHALK, L.YEL, L.PNK, L.BLU, L.INK, L.HOT
RED = W.RED
MIN_TITLE, MIN_HOOK, MIN_SELL = 24, 13, 10
K = 1.0                                                          # 字号系数：只给 --自检 用
FOUR = f'<span style="color:{HOT}">四级</span>'
JX = '原文解析'
PLUS = f'<span class="ck" style="color:{CHALK};margin:0 .12em">＋</span>'
board, phones = S6.board, S6.phones

# 画面文字里不许有年份、不许有具体套数（老师 2026-11-06）；全角数字先折成半角再查
NO_YEAR_JS = r"""() => {
  const t = document.body.innerText.replace(/[０-９]/g, c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0));
  const out = [];
  for (const m of t.matchAll(/(?<!\d)(19|20)\d\d(?!\d)/g)) out.push('年份 ' + m[0]);
  for (const m of t.matchAll(/(?<!\d)(?:[2-9]|[1-9]\d+)\s*套|(?:[二两三四五六七八九十百]|一[十百])[一二三四五六七八九十百]*\s*套/g)) out.push('套数 ' + m[0].replace(/\s+/g, ''));
  return out;
}"""


def fs(n):
    return f'{n * K:.0f}px'


def y(t):
    return f'<span style="color:{YEL}">{t}</span>'


def seal(x, y_, d, rot=8, top='持续', bot='更新'):
    """“持续更新”粉笔红圆章（六级是“2026 已更新”，四级不写年份）。"""
    return (f'<div class="ab" data-k="seal" data-min="{MIN_SELL}" style="left:{x}px;top:{y_}px;width:{d}px;height:{d}px;transform:rotate({rot}deg);'
            f'display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.05;color:#fff">'
            f'<i style="position:absolute;inset:0;border-radius:50%;background:{RED};filter:url(#rough);box-shadow:0 8px 0 rgba(0,0,0,.3)"></i>'
            f'<i style="position:absolute;inset:{d * .06:.0f}px;border-radius:50%;border:5px dashed rgba(255,255,255,.75)"></i>'
            f'<span class="ck" style="position:relative;font:900 {fs(d * .27)}/1.12 Black">{top}</span>'
            f'<span class="ck" style="position:relative;font:900 {fs(d * .27)}/1.12 Black">{bot}</span></div>')


def tags(size, pos, k='tags'):
    return (f'<div class="ab" data-k="{k}" data-min="{MIN_TITLE}" style="{pos};white-space:nowrap;font:900 {fs(size)}/1.22 Black">'
            f'{L.hl("真题", YEL, px=22)}{PLUS}{L.hl(JX, BLU, px=22)}</div>')


def hook(size, pos, px=30):
    return f'<div class="ab" data-k="hook" data-min="{MIN_HOOK}" style="{pos};font:900 {fs(size)}/1.18 Black">{L.hl("彻底搞定四级听力", RED, ink="#fff", px=px)}</div>'


# ───────── A：六级定稿同版式；年份一行换成“历年真题全收录” ─────────
def A(w=1920, h=1080):
    big = w >= 1900
    if not big:
        return board(w, h, f"""
{hook(128, 'left:60px;top:46px', 26)}
{seal(1160, 60, 240, rot=6)}
<div class="ab ck" data-k="title" data-min="{MIN_TITLE}" style="left:54px;top:236px;font:900 {fs(230)}/1 Black;letter-spacing:-.02em">{FOUR}听力</div>
{tags(158, 'left:84px;top:486px')}
{phones(1080, 700, .8)}
<div class="ab ck" data-k="years" data-min="{MIN_SELL}" style="left:60px;top:712px;font:900 {fs(96)}/1.2 Black">历年真题<br>{y('全收录')}</div>""")
    return board(w, h, f"""
{hook(172, 'left:74px;top:40px', 32)}
{seal(1590, 46, 252, rot=6)}
<div class="ab ck" data-k="title" data-min="{MIN_TITLE}" style="left:62px;top:272px;font:900 {fs(230)}/1 Black;letter-spacing:-.02em">{FOUR}听力</div>
{tags(168, 'left:96px;top:520px')}
{phones(1580, 690, .86)}
<div class="ab ck" data-k="years" data-min="{MIN_SELL}" style="left:72px;top:768px;font:900 {fs(116)}/1.2 Black">历年真题 {y('全收录')}</div>""")


# ───────── B：两张粉笔框大卡片，各带一行小说明 ─────────
def card(word, col, note, size, wcard):
    return (f'<div style="position:relative;display:inline-block;vertical-align:top;width:{wcard}px;padding:10px 0 18px;text-align:center;margin-right:36px">'
            f'<i style="position:absolute;inset:0;border:7px solid {col};border-radius:26px;background:rgba(0,0,0,.20);filter:url(#line)"></i>'
            f'<div class="ck" style="position:relative;font:900 {fs(size)}/1.15 Black;color:{col}">{word}</div>'
            f'<div class="ck" data-k="note" data-min="{MIN_SELL}" style="position:relative;font:900 {fs(size * .42)}/1.2 Black;color:{CHALK}">{note}</div></div>')


def B(w=1920, h=1080):
    big = w >= 1900
    sz = 176 if big else 150
    c1 = card('真题', YEL, '视频版考试', sz, round(sz * 2.7))
    c2 = card(JX, PNK, '逐句·翻译·精讲', sz, round(sz * 4.7))
    return board(w, h, f"""
{hook(172 if big else 128, f'left:{74 if big else 60}px;top:{40 if big else 46}px', 32 if big else 26)}
{seal(1590 if big else 1160, 46 if big else 60, 252 if big else 240, rot=6)}
<div class="ab ck" data-k="title" data-min="{MIN_TITLE}" style="left:62px;top:{262 if big else 236}px;font:900 {fs(200 if big else 190)}/1 Black">{FOUR}听力</div>
<div class="ab" data-k="tags" data-min="{MIN_TITLE}" style="left:{70 if big else 60}px;top:{490 if big else 456}px;white-space:nowrap">{c1}{c2}</div>
<div class="ab ck" data-k="years" data-min="{MIN_SELL}" style="left:72px;top:{820 if big else 800}px;font:900 {fs(100 if big else 90)}/1.2 Black">历年真题 {y('全收录')}</div>""")


# ───────── C：主标题两行纯粉笔字，钩子红块压在下面 ─────────
def C(w=1920, h=1080):
    big = w >= 1900
    return board(w, h, f"""
<div class="ab ck" data-k="title" data-min="{MIN_TITLE}" style="left:62px;top:50px;font:900 {fs(236 if big else 214)}/1 Black;letter-spacing:-.02em">{FOUR}听力</div>
{seal(1590 if big else 1160, 46 if big else 60, 252 if big else 240, rot=6, top='最新', bot='真题')}
<div class="ab ck" data-k="tags" data-min="{MIN_TITLE}" style="left:62px;top:{318 if big else 312}px;white-space:nowrap;font:900 {fs(190 if big else 156)}/1 Black">
 <span style="color:{YEL}">真题</span><span style="color:{CHALK}">＋</span><span style="color:{BLU}">{JX}</span></div>
<div class="ab ck" data-k="years" data-min="{MIN_SELL}" style="left:72px;top:{560 if big else 530}px;font:900 {fs(104 if big else 92)}/1.2 Black">历年真题 {y('全收录')}</div>
{hook(160 if big else 126, f'left:{90 if big else 70}px;top:{760 if big else 720}px', 30)}""")


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
    res['problems'] += pg.evaluate(NO_YEAR_JS)
    png = out / f'{name}.png'
    pg.screenshot(path=str(png))
    pg.close()
    return png, res


def selftest(br):
    global K
    bad = []
    for k, f in DIRS.items():
        for w in (1920, 1440):
            for kk in (1.0, 0.4):
                K = kk
                body = f(w, 1080)
                _, res = render(br, body, w, 1080, f'自检_{k}_{w}', WORK)
                hit = {x.split()[0] for x in res['problems'] if '缩略图字高' in x}
                need = set(re.findall(r'data-k="(\w+)" data-min=', body)) if kk < 1 else set()
                if kk < 1 and not {'hook', 'years', 'title', 'tags'} <= need:
                    bad.append(f'{k}{w} 缺少 data-min 元素：{sorted(need)}')
                if hit != need:
                    bad.append(f'{k}{w} 字号×{kk}：报出 {sorted(hit)}，应为 {sorted(need)}')
                other = [x for x in res['problems'] if '缩略图字高' not in x]
                if kk == 1.0 and other:
                    bad.append(f'{k}{w} 正常版报出：{other}')
            K = 1.0
            # 年份 / 套数雷：六级的旧说法放回去必须报（各种写法）
            for mine, want in ((seal(1590, 46, 252, top='2026', bot='已更新'), '年份 2026'),
                               ('历年真题 全收录', None),
                               ('历年真题 <span>2018—2026</span>', '年份 2018'),
                               ('全部 <span style="color:#ff0">35</span> 套', '套数 35套'),
                               ('全部 ２０２５ 年', '年份 2025'),
                               ('真题三十五套', '套数 三十五套')):
                body = f(w, 1080).replace('</div>', f'</div><div class="ab" style="left:300px;top:300px">{mine}</div>', 1)
                _, res = render(br, body, w, 1080, f'自检雷_{k}_{w}', WORK)
                got = [x for x in res['problems'] if x.startswith(('年份', '套数'))]
                if want is None and got:
                    bad.append(f'{k}{w} 雷 {mine!r} 不该报：{got}')
                if want and want not in got:
                    bad.append(f'{k}{w} 雷 {mine!r} 没报出 {want}：{got}')
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
            print('\n'.join(bad) or '自检通过：字号×0.4 每个 data-min 元素全部报出、正常 0；年份 / 套数雷全部报出、正常 0（A/B/C × 16:9、4:3）')
            return 1 if bad else 0
        final = args[1] if args[0] == '定稿' else None
        stem = '四级听力真题与原文解析_封面'
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
    print('自查通过：无年份、无套数；缩略图字高达标、文字不出画、不压木框、不进底角遮挡区、互不重叠、字体全部加载')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['草稿']))
