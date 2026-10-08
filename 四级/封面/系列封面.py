"""B 站系列封面：60 篇四级真题 · 阅读 Passage One + Passage Two · 记住四级所有重点单词。

    /opt/ttsenv/bin/python 四级/封面/系列封面.py

用户要求（2026-10-08）封面必须一眼看出：① 60 篇；② 四级真题；③ 阅读 Passage One / Passage Two；④ 目的是记住四级所有重点单词。
输出 16:9（3840×2160）和 4:3（2880×2160）两种，各一张 PNG（无损）和一张 JPG（体积小，方便上传）。
封面上的数字都来自数据：60 篇（30 篇 Passage One + 30 篇 Passage Two）、1123 句、3744 个不重复的标注词条（单词和短语）。
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import 生成封面 as G  # noqa: E402  复用字体、真实视频截图

OUT = HERE / '系列封面'
YEL, RED, INK = '#FFD60A', '#E63946', '#111'

d = json.loads((G.C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']
N = len(d)
SENTS = sum(len(para) for p in d for para in p['paras'])
UNIQ = len({w['h'].lower() for p in d for para in p['paras'] for s in para for w in s['w']})
YEARS = f"{min(p['paper'][:4] for p in d)}—{max(p['paper'][:4] for p in d)}"
assert N == 60 and sum(p['passage'] == 'Passage One' for p in d) == 30


def chips(size):
    items = [f'{YEARS} 年真题', f'{SENTS} 句逐句精读', f'{UNIQ // 100 * 100}+ 词汇全标注', '4K 高清']
    return ''.join(f'<span style="display:inline-block;background:#fff;border:4px solid {INK};font:900 {size}px/1.25 SansBlack;'
                   f'padding:6px 20px;margin:0 16px 16px 0;box-shadow:6px 6px 0 {INK}">{x}</span>' for x in items)


def cards(img1, img2, left, top, w):
    return (f'<img src="{img2.as_uri()}" style="position:absolute;left:{left + 40}px;top:{top + 70}px;width:{w}px;transform:rotate(7deg);'
            f'border:10px solid #fff;box-shadow:14px 16px 0 rgba(0,0,0,.85)">'
            f'<img src="{img1.as_uri()}" style="position:absolute;left:{left}px;top:{top}px;width:{w}px;transform:rotate(-3deg);'
            f'border:10px solid #fff;box-shadow:14px 16px 0 rgba(0,0,0,.85)">')


def body_169(img1, img2):
    return f"""
<div class="bg" style="background:{YEL}"></div>
<div style="position:absolute;left:90px;top:56px;font:700 46px SansBold;color:{INK};letter-spacing:.06em">大学英语四级 · 仔细阅读（Section C）</div>
<div style="position:absolute;left:80px;top:96px;white-space:nowrap;line-height:1"><span style="font:900 240px SansBlack;color:{RED};letter-spacing:-.03em">60</span><span style="font:900 188px SansBlack;color:{INK}">篇四级真题</span></div>
<div style="position:absolute;left:90px;top:436px;background:{INK};color:{YEL};font:900 70px/1.3 SansBlack;padding:4px 30px;white-space:nowrap">阅读 Passage One + Passage Two</div>
<div style="position:absolute;left:84px;top:568px;white-space:nowrap;font:900 118px/1.2 SansBlack;color:{INK}">记住四级<span style="background:{RED};color:#fff;padding:0 18px;margin-left:10px">所有重点单词</span></div>
<div style="position:absolute;left:90px;top:778px;width:1300px">{chips(42)}</div>
{cards(img1, img2, 1400, 180, 460)}
<div style="position:absolute;left:0;right:0;bottom:0;height:110px;background:{INK};color:{YEL};font:900 52px/110px SansBlack;text-align:center;letter-spacing:.06em">逐句朗读 · 逐句翻译 · 生词编号注释 · 一句一屏</div>"""


def body_43(img1, img2):
    return f"""
<div class="bg" style="background:{YEL}"></div>
<div style="position:absolute;left:70px;top:46px;font:700 42px SansBold;color:{INK};letter-spacing:.06em">大学英语四级 · 仔细阅读（Section C）</div>
<div style="position:absolute;left:60px;top:92px;white-space:nowrap;line-height:1"><span style="font:900 210px SansBlack;color:{RED};letter-spacing:-.03em">60</span><span style="font:900 168px SansBlack;color:{INK}">篇四级真题</span></div>
<div style="position:absolute;left:70px;top:388px;background:{INK};color:{YEL};font:900 62px/1.3 SansBlack;padding:4px 26px;white-space:nowrap">阅读 Passage One + Passage Two</div>
<div style="position:absolute;left:64px;top:510px;white-space:nowrap;font:900 108px/1.2 SansBlack;color:{INK}">记住四级<span style="background:{RED};color:#fff;padding:0 16px;margin-left:8px">所有重点单词</span></div>
<div style="position:absolute;left:70px;top:705px;width:720px">{chips(38)}</div>
{cards(img1, img2, 830, 690, 450)}
<div style="position:absolute;left:0;right:0;bottom:0;height:100px;background:{INK};color:{YEL};font:900 46px/100px SansBlack;text-align:center;letter-spacing:.05em">逐句朗读 · 逐句翻译 · 生词编号注释</div>"""


def render(pg, body, w, h, name):
    f = OUT / f'_{name}.html'
    f.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{G.FONTS}*{{margin:0;padding:0;box-sizing:border-box}}'
                 f'html,body{{width:{w}px;height:{h}px;overflow:hidden}}.bg{{position:absolute;inset:0}}</style></head><body>{body}</body></html>', 'utf-8')
    pg.set_viewport_size({'width': w, 'height': h})
    pg.goto(f.as_uri())
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(300)
    png = OUT / f'{name}.png'
    pg.screenshot(path=str(png))
    f.unlink()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(png), '-q:v', '2', str(OUT / f'{name}.jpg')], check=True)
    return png


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page()
        img1, img2 = G.preview_png('c60', pg), G.preview_png('c59', pg)       # 两张真实视频画面（Passage Two、Passage One）
        hd = br.new_page(device_scale_factor=2)                                  # 高清：两倍像素
        print(render(hd, body_169(img1, img2), 1920, 1080, '四级真题60篇_封面_16比9'))
        print(render(hd, body_43(img1, img2), 1440, 1080, '四级真题60篇_封面_4比3'))
        br.close()
