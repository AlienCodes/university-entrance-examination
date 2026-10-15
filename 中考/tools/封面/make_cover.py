"""B 站封面：40 篇中考阅读精读视频在 B 站合成一个视频（40P），这是整个合集的封面。

    /opt/ttsenv/bin/python 中考/tools/封面/make_cover.py   → 中考/封面/中考英语阅读40篇_B站封面.jpg（1920×1080）+ 手机信息流尺寸预览

封面先说清“这是什么”：40 篇中考阅读真题（C/D 压轴篇为主），专门用来背中考单词；再想办法让人点进来：
  1. 最大的字是数字承诺：背完 N 个中考词汇（N = 40 篇视频里编号注释的全部单词和短语，去重，与视频一致，不夸大）；
  2. 真实的视频画面（逐句高亮 + 编号注释 + 中文翻译），一眼看出视频质量；
  3. 覆盖的省市全部列出——学生会找自己的城市；
  4. 配色与视频一致（紫黄撞色），在 B 站白底信息流里很跳；
  5. 左下角、右下角留给 B 站叠加的播放量和时长，不放关键信息；手机信息流里封面只有约 180 像素宽，所以主信息都用大字。
所有数字由程序从定稿数据统计，不手填。
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

W, H, BAND = 1600, 1200, (150, 1050)     # B 站投稿封面 4:3（手机首页显示整张）；电脑端裁成 16:9/16:10 只剩中间 150—1050 这一条，关键内容都放在这条里

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1600px;height:1200px;overflow:hidden}
body{font-family:'Noto Sans SC',sans-serif;color:#fff;position:relative;
  background:radial-gradient(circle at 22% 45%,#6a35f0 0,#5420d1 40%,#360d9e 100%)}
.stripe{position:absolute;inset:0;background:repeating-linear-gradient(-35deg,rgba(255,255,255,.045) 0 24px,transparent 24px 64px)}
.sun{position:absolute;width:620px;height:620px;border-radius:50%;background:#ffd84a;right:-210px;top:-250px}
.k{-webkit-text-stroke:12px #1e1538;paint-order:stroke fill}
.head{position:absolute;left:60px;top:46px;font-weight:900;font-size:46px;letter-spacing:6px;color:#fff;opacity:.92}
.top{position:absolute;left:58px;top:174px;display:flex;gap:16px}
.pill{font-weight:900;font-size:54px;line-height:1;padding:14px 24px 18px;border-radius:20px;box-shadow:0 9px 0 #1e1538}
.y{background:#ffd84a;color:#1e1538}.p{background:#ff6fae;color:#fff}
.h1{position:absolute;left:54px;top:290px;font-weight:900;font-size:96px;line-height:1.1;letter-spacing:1px;white-space:nowrap}
.h1 small{display:block;font-size:43px;letter-spacing:0;color:#ffd84a;margin-top:4px}
.hero{position:absolute;left:54px;top:530px;display:flex;align-items:flex-end}
.hero .a{position:absolute;left:4px;top:-50px;transform:rotate(-6deg);background:#ff6fae;font-weight:900;font-size:52px;line-height:1;
  padding:9px 18px 12px;border-radius:14px;box-shadow:0 7px 0 #1e1538;z-index:2}
.num{font-family:'Fredoka','Noto Sans SC';font-weight:600;font-size:228px;line-height:.86;color:#ffd84a;letter-spacing:-4px;
  -webkit-text-stroke:15px #1e1538;paint-order:stroke fill;text-shadow:12px 12px 0 #1e1538}
.hero .u{font-weight:900;font-size:78px;line-height:1.04;margin:0 0 16px 14px;white-space:nowrap}
.hero .u em{font-style:normal;color:#ffd84a}
.sub{position:absolute;left:58px;top:800px;display:flex;gap:12px;flex-wrap:wrap;width:800px}
.sub span{background:#1e1538;font-weight:700;font-size:36px;line-height:1;padding:13px 20px 15px;border-radius:14px;white-space:nowrap}
.sub b{color:#ffd84a;font-weight:900}
.shot{position:absolute;left:896px;top:206px;width:650px;transform:rotate(2.5deg);border:9px solid #fff;border-radius:18px;
  box-shadow:13px 15px 0 #1e1538;overflow:hidden;background:#fff}
.shot img{display:block;width:100%}
.tag{position:absolute;left:846px;top:186px;transform:rotate(-8deg);background:#ff6fae;color:#fff;font-weight:900;font-size:34px;
  padding:10px 18px 12px;border-radius:12px;box-shadow:0 7px 0 #1e1538;z-index:2}
.reg{position:absolute;left:896px;top:616px;width:650px;background:rgba(30,21,56,.9);border-radius:22px;padding:16px 20px 20px}
.reg h4{font-weight:900;font-size:38px;line-height:1.1;color:#ffd84a;margin-bottom:12px;white-space:nowrap}
.reg h4 small{color:#fff;font-size:32px;font-weight:700;margin-left:10px}
.chips{display:grid;grid-template-columns:repeat(5,1fr);gap:9px}
.chips i{font-style:normal;background:#fff;color:#5420d1;font-weight:900;font-size:32px;line-height:1;text-align:center;padding:9px 0 11px;border-radius:11px}
.foot{position:absolute;left:0;right:0;top:1078px;text-align:center}
.foot span{display:inline-block;background:#1e1538;color:#fff;font-weight:900;font-size:48px;line-height:1;padding:16px 34px 20px;border-radius:18px}
.foot b{color:#ffd84a}
"""


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


def cover_html(st, shot_uri):
    fonts = ''.join(f'<link rel="stylesheet" href="{(FONTS / f).as_uri()}">' for f in ('fonts.css', 'noto-sans-sc/900.css'))
    chips = ''.join(f'<i>{M.esc(r)}</i>' for r in st['regions'])
    y0, y1 = min(st['years']), max(st['years'])
    return f"""<!doctype html><html><head><meta charset="utf-8">{fonts}<style>{CSS}</style></head><body>
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


def main():
    from playwright.sync_api import sync_playwright
    from PIL import Image
    from 画面核查.layoutcheck import screens
    P = json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']
    st = stats(P)
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': 1920, 'height': 1080})
        cp = br.new_page(viewport={'width': W, 'height': H})
        f, shot = Path(td) / 'c.html', Path(td) / 'shot.png'
        _, h, fit = screens(M, {p['id']: p for p in P}[DEMO[0]])[DEMO[1] - 1]          # 与视频完全相同的一屏
        f.write_text(h, 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        if fit:
            pg.evaluate(M.FIT)
        pg.screenshot(path=str(shot))
        f.write_text(cover_html(st, shot.as_uri()), 'utf-8')
        cp.goto(f.as_uri())
        cp.evaluate('document.fonts.ready')
        bad = cp.evaluate("""([W, y0, y1]) => { const r = [];
            for (const e of document.querySelectorAll('.top,.h1,.hero,.sub,.shot,.reg,.tag')) { const b = e.getBoundingClientRect();     // 关键内容：电脑端 16:9 也看得到
              if (b.left < 0 || b.right > W || b.top < y0 + 10 || b.bottom > y1 - 50) r.push('关键内容出了中间安全区（电脑端会被裁掉或压到角标）：' + e.className); }
            for (const e of document.querySelectorAll('.head,.foot span')) { const b = e.getBoundingClientRect(); if (b.top < 10 || b.bottom > 1190) r.push('出界：' + e.className); }
            const L = Math.max(...[...document.querySelectorAll('.h1,.hero,.sub span')].map(e => e.getBoundingClientRect().right));
            const R = Math.min(...[...document.querySelectorAll('.shot,.reg')].map(e => e.getBoundingClientRect().left));
            if (L > R - 10) r.push(`左栏文字压到右栏：${L} > ${R}`);
            for (const e of document.querySelectorAll('.chips i')) if (e.scrollWidth > e.clientWidth + 1) r.push('省市名放不下：' + e.textContent);
            return r; }""", [W, *BAND])
        if bad:
            raise SystemExit(f'封面排版有问题：{bad}')
        out = OUT / '中考英语阅读40篇_B站封面_4比3.jpg'
        cp.screenshot(path=str(Path(td) / 'c.png'))
        im = Image.open(Path(td) / 'c.png').convert('RGB')
        im.save(out, quality=93)
        wide = im.crop((0, BAND[0], W, BAND[1]))                             # 电脑端 16:9 裁切后的样子
        prev = Image.new('RGB', (800 + 20 + 640 + 20 + 360, 600 + 20 + 200), 'white')
        prev.paste(im.resize((800, 600)), (0, 0))                            # 整张（手机首页）
        prev.paste(wide.resize((640, 360)), (820, 0))                        # 电脑端 16:9
        prev.paste(im.resize((180, 135)), (1480, 0))                         # 手机首页信息流实际大小（约 180 宽）
        prev.paste(wide.resize((300, 169)), (1480, 160))                     # 电脑信息流实际大小
        prev.save(OUT / '预览_整张_电脑裁切_信息流尺寸.png')
        br.close()
    print(out, st)


if __name__ == '__main__':
    main()
