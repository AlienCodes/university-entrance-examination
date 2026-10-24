"""B 站封面：40 篇中考阅读精读视频在 B 站合成一个视频（40P），这是整个合集的封面，出两张：

    /opt/ttsenv/bin/python 中考/tools/封面/make_cover.py
      → 中考/封面/中考英语阅读40篇_B站封面_4比3.jpg   （3200×2400，投稿主封面：手机首页显示整张，电脑端裁成 16:9/16:10 只剩中间一条）
      → 中考/封面/中考英语阅读40篇_B站封面_16比9.jpg  （3840×2160，单独上传 16:9 封面的地方用）
      → 中考/封面/预览_….png（整张、电脑端裁切、手机/电脑信息流实际大小）

封面先说清“这是什么”：40 篇中考阅读真题（C/D 压轴篇为主），专门用来背中考单词；再想办法让人点进来：
  1. 最大的字是数字承诺：背完 N 个中考词汇（N = 40 篇视频里编号注释的全部单词和短语，去重，与视频一致，不夸大）；
  2. 真实的视频画面（逐句高亮 + 编号注释 + 中文翻译），一眼看出视频质量；
  3. 覆盖的省市全部列出——学生会找自己的城市；
  4. 配色与视频一致（紫黄撞色），在 B 站白底信息流里很跳；
  5. 左下角、右下角留给 B 站叠加的播放量和时长，不放关键信息；手机信息流里封面只有约 180 像素宽，所以主信息都用大字。
清晰度：按 2 倍像素渲染（文字是矢量直接画的，不是放大的），视频画面也用 4K 原画缩小嵌入；JPEG 质量从 95 往下调，每张不超过 2 MB。
所有数字由程序从定稿数据统计，不手填；排版由程序检查（出界、压到右栏、关键内容出了电脑端裁切安全区、放不下）。
"""
import collections
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
T = HERE.parent
C4 = T.parent
sys.path.insert(0, str(T))
import make_video as M  # noqa: E402

OUT = C4 / '封面'
FONTS = T / 'fonts'
DEMO = ('z01', 2)          # 封面上展示的视频画面：北京 阅读C 第 1 句（高亮多、编号全，最能说明视频内容）
DPR = 2                    # 2 倍像素渲染
MAX_BYTES = 2_000_000

BASE = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Noto Sans SC',sans-serif;color:#fff;position:relative;overflow:hidden;
  background:radial-gradient(circle at 22% 45%,#6a35f0 0,#5420d1 40%,#360d9e 100%)}
.stripe{position:absolute;inset:0;background:repeating-linear-gradient(-35deg,rgba(255,255,255,.045) 0 24px,transparent 24px 64px)}
.sun{position:absolute;border-radius:50%;background:#ffd84a}
.k{paint-order:stroke fill;-webkit-text-stroke:var(--ks) #1e1538}
.top{position:absolute;display:flex}
.pill{font-weight:900;line-height:1}
.y{background:#ffd84a;color:#1e1538}.p{background:#ff6fae;color:#fff}
.h1{position:absolute;font-weight:900;line-height:1.1;white-space:nowrap}
.h1 small{display:block;color:#ffd84a}
.hero{position:absolute;display:flex;align-items:flex-end}
.hero .a{position:absolute;transform:rotate(-6deg);background:#ff6fae;font-weight:900;line-height:1;z-index:2}
.num{font-family:'Fredoka','Noto Sans SC';font-weight:600;line-height:.86;color:#ffd84a;letter-spacing:-4px;paint-order:stroke fill}
.hero .u{font-weight:900;line-height:1.04;white-space:nowrap}
.hero .u em{font-style:normal;color:#ffd84a}
.sub{position:absolute;display:flex;flex-wrap:wrap}
.sub span{background:#1e1538;font-weight:700;line-height:1;white-space:nowrap}
.sub b{color:#ffd84a;font-weight:900}
.shot{position:absolute;transform:rotate(2.5deg);border-style:solid;border-color:#fff;overflow:hidden;background:#fff}
.shot img{display:block;width:100%}
.tag{position:absolute;transform:rotate(-8deg);background:#ff6fae;color:#fff;font-weight:900;z-index:2}
.reg{position:absolute;background:rgba(30,21,56,.9)}
.reg h4{font-weight:900;line-height:1.1;color:#ffd84a;white-space:nowrap}
.reg h4 small{color:#fff;font-weight:700}
.chips{display:grid;grid-template-columns:repeat(5,1fr)}
.chips i{font-style:normal;background:#fff;color:#5420d1;font-weight:900;line-height:1;text-align:center}
.head{position:absolute;font-weight:900;color:#fff;opacity:.92}
.foot{position:absolute;left:0;right:0;text-align:center}
.foot span{display:inline-block;background:#1e1538;color:#fff;font-weight:900;line-height:1}
.foot b{color:#ffd84a}
"""

# 4:3（1600×1200）：手机首页显示整张；电脑端裁成 16:9 只剩中间 150—1050，关键内容都放在这条里；顶部一行和底部一句只在手机上看得到
L43 = """
html,body{width:1600px;height:1200px}
.sun{width:620px;height:620px;right:-210px;top:-250px}
.k{--ks:12px}
.head{left:60px;top:46px;font-size:46px;letter-spacing:6px}
.top{left:58px;top:174px;gap:16px}
.pill{font-size:54px;padding:14px 24px 18px;border-radius:20px;box-shadow:0 9px 0 #1e1538}
.h1{left:54px;top:290px;font-size:96px;letter-spacing:1px}
.h1 small{font-size:43px;margin-top:4px}
.hero{left:54px;top:530px}
.hero .a{left:4px;top:-50px;font-size:52px;padding:9px 18px 12px;border-radius:14px;box-shadow:0 7px 0 #1e1538}
.num{font-size:228px;-webkit-text-stroke:15px #1e1538;text-shadow:12px 12px 0 #1e1538}
.hero .u{font-size:78px;margin:0 0 16px 14px}
.sub{left:58px;top:800px;gap:12px;width:800px}
.sub span{font-size:36px;padding:13px 20px 15px;border-radius:14px}
.shot{left:896px;top:206px;width:650px;border-width:9px;border-radius:18px;box-shadow:13px 15px 0 #1e1538}
.tag{left:846px;top:186px;font-size:34px;padding:10px 18px 12px;border-radius:12px;box-shadow:0 7px 0 #1e1538}
.reg{left:896px;top:616px;width:650px;border-radius:22px;padding:16px 20px 20px}
.reg h4{font-size:38px;margin-bottom:12px}
.reg h4 small{font-size:32px;margin-left:10px}
.chips{gap:9px}
.chips i{font-size:32px;padding:9px 0 11px;border-radius:11px}
.foot{top:1078px}
.foot span{font-size:48px;padding:16px 34px 20px;border-radius:18px}
"""

# 16:9（1920×1080）：整张显示，不裁切；只有左下、右下角留给 B 站角标
L169 = """
html,body{width:1920px;height:1080px}
.sun{width:700px;height:700px;right:-230px;top:-330px}
.k{--ks:14px}
.head,.foot{display:none}
.top{left:80px;top:58px;gap:20px}
.pill{font-size:66px;padding:18px 30px 22px;border-radius:24px;box-shadow:0 10px 0 #1e1538}
.h1{left:74px;top:208px;font-size:116px;letter-spacing:2px}
.h1 small{font-size:54px;letter-spacing:1px;margin-top:6px}
.hero{left:74px;top:470px}
.hero .a{left:6px;top:-58px;font-size:64px;padding:10px 22px 14px;border-radius:16px;box-shadow:0 8px 0 #1e1538}
.num{font-size:270px;-webkit-text-stroke:18px #1e1538;text-shadow:14px 14px 0 #1e1538}
.hero .u{font-size:96px;margin:0 0 20px 18px}
.sub{left:80px;top:790px;gap:16px;width:1000px}
.sub span{font-size:44px;padding:16px 24px 18px;border-radius:16px}
.shot{left:1074px;top:96px;width:780px;border-width:10px;border-radius:22px;box-shadow:16px 18px 0 #1e1538}
.tag{left:1010px;top:70px;font-size:40px;padding:12px 22px 14px;border-radius:14px;box-shadow:0 8px 0 #1e1538}
.reg{left:1064px;top:588px;width:790px;border-radius:26px;padding:20px 26px 24px}
.reg h4{font-size:46px;margin-bottom:14px}
.reg h4 small{font-size:36px;margin-left:12px}
.chips{gap:10px}
.chips i{font-size:36px;padding:10px 0 12px;border-radius:12px}
"""

LAYOUTS = [  # 名字, 宽, 高, 样式, 关键内容安全区（上、下）
    ('4比3', 1600, 1200, L43, (150, 1050)),
    ('16比9', 1920, 1080, L169, (0, 1080)),
]


def stats(P):
    heads, phr = set(), set()
    for p in P:
        for s in (s for pa in p['paras'] for s in pa):
            for w in s['w']:
                heads.add(w['h'].lower())
                if w['t'] == 'phr':
                    phr.add(w['h'].lower())
    regions = list(dict.fromkeys(p['region'] for p in P))
    kinds = collections.Counter(p['passage'] for p in P)
    years = collections.Counter(p['year'] for p in P)
    return dict(n=len(P), heads=len(heads), phr=len(phr), single=len(heads) - len(phr), regions=regions,
                cd=kinds['阅读C'] + kinds['阅读D'], years=years, words=sum(p['words'] for p in P))


def cover_html(st, shot_uri, css):
    fonts = ''.join(f'<link rel="stylesheet" href="{(FONTS / f).as_uri()}">' for f in ('fonts.css', 'noto-sans-sc/900.css'))
    chips = ''.join(f'<i>{M.esc(r)}</i>' for r in st['regions'])
    y0, y1 = min(st['years']), max(st['years'])
    return f"""<!doctype html><html><head><meta charset="utf-8">{fonts}<style>{BASE}{css}</style></head><body>
<div class="sun"></div><div class="stripe"></div>
<div class="head">中考英语 · 阅读理解 · 逐句精读</div>
<div class="top"><div class="pill y">{y0}—{y1}真题</div><div class="pill p">{st['n']}P合集</div></div>
<div class="h1 k">{st['n']}篇中考阅读真题<small>C/D 压轴篇为主 · 逐句精读背单词</small></div>
<div class="hero"><div class="a">背完</div><div class="num">{st['heads']}</div><div class="u k">个中考<br><em>词汇</em></div></div>
<div class="sub"><span><b>{st['single']}</b> 单词 + <b>{st['phr']}</b> 短语</span><span>每句中英对照</span><span>生词编号注释</span></div>
<div class="tag">视频画面 ↓</div>
<div class="shot"><img src="{shot_uri}"></div>
<div class="reg"><h4>{len(st['regions'])}个省市真题<small>找找你的城市 →</small></h4><div class="chips">{chips}</div></div>
<div class="foot"><span>每天 1 篇，<b>{st['n']} 天</b>背完 <b>{st['heads']}</b> 个中考词汇</span></div>
</body></html>"""


CHECK = """([W, H, y0, y1]) => { const r = [];
  for (const e of document.querySelectorAll('.top,.h1,.hero,.sub,.shot,.reg,.tag')) { const b = e.getBoundingClientRect();
    if (b.left < 0 || b.right > W || b.top < y0 + 10 || b.bottom > y1 - 50)
      r.push('关键内容出界、出了电脑端裁切安全区或压到 B 站角标：' + e.className); }
  for (const e of document.querySelectorAll('.head,.foot span')) { const b = e.getBoundingClientRect();
    if (b.width && (b.top < 10 || b.bottom > H - 10 || b.right > W)) r.push('出界：' + e.className); }
  const L = Math.max(...[...document.querySelectorAll('.h1,.hero,.sub span')].map(e => e.getBoundingClientRect().right));
  const R = Math.min(...[...document.querySelectorAll('.shot,.reg')].map(e => e.getBoundingClientRect().left));
  if (L > R - 10) r.push(`左栏文字压到右栏：${L} > ${R}`);
  for (const e of document.querySelectorAll('.chips i, .reg h4')) if (e.scrollWidth > e.clientWidth + 1) r.push('放不下：' + e.textContent);
  return r; }"""


def save_jpg(im, path):
    for q in range(95, 84, -1):
        im.save(path, quality=q, subsampling=0 if q >= 90 else 2)
        if path.stat().st_size <= MAX_BYTES:
            return q
    raise SystemExit(f'{path.name} 压到质量 85 仍超过 {MAX_BYTES} 字节')


def main():
    from playwright.sync_api import sync_playwright
    from PIL import Image
    from 画面核查.layoutcheck import screens
    P = json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']
    st = stats(P)
    OUT.mkdir(exist_ok=True)
    ims = {}
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        f, shot = Path(td) / 'c.html', Path(td) / 'shot.png'
        vp = br.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2)     # 视频画面：与 4K 视频同样清晰
        _, h, fit = screens(M, {p['id']: p for p in P}[DEMO[0]])[DEMO[1] - 1]
        f.write_text(h, 'utf-8')
        vp.goto(f.as_uri())
        vp.evaluate('document.fonts.ready')
        if fit:
            vp.evaluate(M.FIT)
        vp.screenshot(path=str(shot))
        for name, W, H, css, band in LAYOUTS:
            pg = br.new_page(viewport={'width': W, 'height': H}, device_scale_factor=DPR)
            f.write_text(cover_html(st, shot.as_uri(), css), 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            bad = pg.evaluate(CHECK, [W, H, *band])
            if bad:
                raise SystemExit(f'{name} 封面排版有问题：{bad}')
            png = Path(td) / f'{name}.png'
            pg.screenshot(path=str(png))
            im = Image.open(png).convert('RGB')
            assert im.size == (W * DPR, H * DPR), im.size
            out = OUT / f'中考英语阅读40篇_B站封面_{name}.jpg'
            q = save_jpg(im, out)
            ims[name] = im
            print(f'{out.name}：{im.size[0]}×{im.size[1]}，JPEG 质量 {q}，{out.stat().st_size / 1e6:.2f} MB', flush=True)
        br.close()
    a, b = ims['4比3'], ims['16比9']
    crop = a.crop((0, 150 * DPR, a.width, 1050 * DPR))                     # 4:3 在电脑端裁成 16:9 后的样子
    prev = Image.new('RGB', (800 + 20 + 800, 600 + 20 + 160), 'white')
    prev.paste(a.resize((800, 600), Image.LANCZOS), (0, 0))
    prev.paste(b.resize((800, 450), Image.LANCZOS), (820, 0))
    prev.paste(crop.resize((320, 180), Image.LANCZOS), (820, 460))          # 4:3 封面在电脑端被裁成 16:9
    for x, (img, w) in zip([0, 200, 460], [(a, 180), (b, 240), (b, 300)]):  # 信息流里的实际大小
        prev.paste(img.resize((w, round(w * img.height / img.width)), Image.LANCZOS), (x, 620))
    prev.save(OUT / '预览_4比3_16比9_裁切与信息流尺寸.png')
    for old in OUT.glob('预览_整张_电脑裁切_信息流尺寸.png'):
        old.unlink()
    print(st)


if __name__ == '__main__':
    main()
