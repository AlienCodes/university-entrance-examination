"""B 站封面（1920×1080，16:9）。

    /opt/ttsenv/bin/python 四级/封面/生成封面.py 对比 c60          # 三种方案对比图（给用户挑）
    /opt/ttsenv/bin/python 四级/封面/生成封面.py A c60 c59 …        # 按选定方案生成封面

设计要点（B 站信息流里封面只有约 320×180 大）：
- 主标题字极大、极粗（思源黑体 Black），缩小到缩略图仍一眼能读；
- 一眼看出是哪年哪套（大家按年份、套数搜真题）；
- 放一张该视频真实的画面截图，让人看到“生词高亮 + 编号释义 + 逐句翻译”的实际效果；
- 关键内容都放在中间 4:3 范围内（左右各留 240 像素），B 站个别位置把封面裁成 4:3 也不会切掉字。
"""
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
sys.path.insert(0, str(C4 / 'tools'))
import make_video as M  # noqa: E402

OUT = HERE / 'png'
W, H = 1920, 1080
FONTS = f"""
@font-face{{font-family:'SansBlack';src:url('{(HERE / 'fonts' / 'NotoSansSC_900Black.ttf').as_uri()}');font-weight:900}}
@font-face{{font-family:'SansBold';src:url('{(HERE / 'fonts' / 'NotoSansSC_700Bold.ttf').as_uri()}');font-weight:700}}
"""
DATA = {p['id']: p for p in json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
esc = html.escape


def preview_png(pid, pg):
    """该视频第一张生词较多的句子画面（真实视频截图），作为封面里的预览卡片。"""
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f'_slide_{pid}.png'
    if f.exists():
        return f
    p = DATA[pid]
    S = [s for para in p['paras'] for s in para]
    k = next((i for i, s in enumerate(S, 1) if 4 <= len(s['w']) <= 8 and len(s['en']) < 140), 1)
    s = S[k - 1]
    parts = M.split_parts(pid, k, s)
    h = OUT / f'_slide_{pid}.html'
    h.write_text(M.sentence_slide(p, s, k, len(S), parts[0]), 'utf-8')
    pg.set_viewport_size({'width': 1920, 'height': 1080})
    pg.goto(h.as_uri())
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(150)
    pg.evaluate(M.FIT)
    pg.screenshot(path=str(f))
    h.unlink()
    return f


def paper_parts(p):
    # “2026年6月 第3套” + “Passage Two”
    return p['paper'], p['passage']


def design_A(p, img):
    """黄黑考试风：最高对比度，信息流里最扎眼。"""
    paper, passage = paper_parts(p)
    return f"""
<div class="bg" style="background:#FFD60A"></div>
<div style="position:absolute;left:250px;top:70px;font:700 44px SansBold;color:#111;letter-spacing:.08em">大学英语四级 · 仔细阅读</div>
<div style="position:absolute;left:240px;top:140px;font:900 215px/1.02 SansBlack;color:#111;letter-spacing:-.02em">四级阅读</div>
<div style="position:absolute;left:250px;top:390px;background:#111;color:#FFD60A;font:900 160px/1.15 SansBlack;padding:0 34px;letter-spacing:.02em">逐句精读</div>
<div style="position:absolute;left:250px;top:640px;transform:rotate(-3deg);background:#E63946;color:#fff;font:900 70px/1.3 SansBlack;padding:6px 30px;box-shadow:8px 8px 0 #111">{esc(paper)} · {esc(passage)}</div>
<div style="position:absolute;left:256px;top:790px;width:900px;font:700 54px/1.3 SansBold;color:#111">《{esc(p['title'])}》</div>
<img src="{img.as_uri()}" style="position:absolute;left:1140px;top:170px;width:560px;transform:rotate(4deg);border:10px solid #fff;box-shadow:16px 18px 0 rgba(0,0,0,.85)">
<div style="position:absolute;left:0;right:0;bottom:0;height:120px;background:#111;color:#FFD60A;font:900 56px/120px SansBlack;text-align:center;letter-spacing:.06em">真题原文 · 逐句翻译 · 生词全标注 · 4K</div>"""


def design_B(p, img):
    """墨绿高级风：与视频画面同一套颜色，系列感强。"""
    paper, passage = paper_parts(p)
    return f"""
<div class="bg" style="background:radial-gradient(circle at 75% 40%,#2a7a62 0%,#16443a 55%,#0e2c25 100%)"></div>
<div style="position:absolute;left:250px;top:90px;border:4px solid #FFD166;color:#FFD166;font:900 64px/1.3 SansBlack;padding:4px 26px">{esc(paper)} · {esc(passage)}</div>
<div style="position:absolute;left:240px;top:210px;font:900 205px/1.05 SansBlack;color:#fff">四级真题</div>
<div style="position:absolute;left:240px;top:440px;font:900 205px/1.05 SansBlack;color:#FFD166">逐句精读</div>
<div style="position:absolute;left:250px;top:720px;width:1300px;font:700 60px/1.3 SansBold;color:#e8efe9">{esc(p['title'])}</div>
<img src="{img.as_uri()}" style="position:absolute;left:1130px;top:230px;width:570px;border-radius:14px;box-shadow:0 30px 60px rgba(0,0,0,.55);transform:rotate(-3deg);border:8px solid #fbf9f4">
<div style="position:absolute;left:250px;bottom:70px;font:700 46px SansBold;color:#9fc7b6;letter-spacing:.1em">逐句翻译 ｜ 生词编号注释 ｜ 4K 高清</div>"""


def design_C(p, img):
    """提问钩子：一句问话勾起好奇心，“读懂几句”让人想点进来自测。"""
    paper, passage = paper_parts(p)
    return f"""
<div class="bg" style="background:#FBF9F4"></div>
<div style="position:absolute;left:0;top:0;width:28px;height:1080px;background:#1f5c4a"></div>
<div style="position:absolute;left:250px;top:80px;background:#1f5c4a;color:#fff;font:900 62px/1.35 SansBlack;padding:2px 26px">四级 {esc(paper)} · {esc(passage)}</div>
<div style="position:absolute;left:240px;top:200px;font:900 170px/1.15 SansBlack;color:#111">这篇真题</div>
<div style="position:absolute;left:240px;top:400px;font:900 170px/1.15 SansBlack;color:#111">你能读懂<span style="color:#E63946;background:linear-gradient(transparent 62%,#FFD60A 62%)">几句</span>？</div>
<div style="position:absolute;left:250px;top:660px;width:900px;font:700 50px/1.35 SansBold;color:#333">《{esc(p['title'])}》</div>
<img src="{img.as_uri()}" style="position:absolute;left:1180px;top:640px;width:500px;border:8px solid #fff;box-shadow:0 18px 40px rgba(0,0,0,.35);transform:rotate(3deg)">
<div style="position:absolute;left:1400px;top:215px;width:280px;height:280px;border-radius:50%;background:#E63946;color:#fff;transform:rotate(10deg);display:flex;flex-direction:column;align-items:center;justify-content:center;font:900 60px/1.25 SansBlack;box-shadow:10px 10px 0 #111">逐句<br>精读<span style="font:700 36px SansBold;margin-top:8px">附翻译+生词</span></div>"""


DESIGNS = {'A': design_A, 'B': design_B, 'C': design_C}


def page(body):
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{FONTS}*{{margin:0;padding:0;box-sizing:border-box}}html,body{{width:{W}px;height:{H}px;overflow:hidden}}.bg{{position:absolute;inset:0}}</style></head><body>{body}</body></html>'


def cover_name(p):
    return M.video_name(p)[:-4] + '.png'


def render(pg, design, pid, out):
    p = DATA[pid]
    img = preview_png(pid, pg)
    f = OUT / f'_cover_{design}_{pid}.html'
    f.write_text(page(DESIGNS[design](p, img)), 'utf-8')
    pg.set_viewport_size({'width': W, 'height': H})
    pg.goto(f.as_uri())
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(200)
    pg.screenshot(path=str(out))
    f.unlink()
    return out


def compare(pg, pid):
    """三种方案一张图：左边大图，右边是 B 站信息流里的实际大小（约 320×180）。"""
    files = {d: render(pg, d, pid, OUT / f'_{d}.png') for d in DESIGNS}
    rows = ''.join(f'''<div class="row"><div class="lab">{d}</div><img class="big" src="{files[d].as_uri()}">
      <div class="feed"><img class="small" src="{files[d].as_uri()}"><div class="cap">信息流实际大小</div></div></div>''' for d in DESIGNS)
    h = f'''<!doctype html><html><head><meta charset="utf-8"><style>{FONTS}*{{margin:0;padding:0}}
      body{{width:1500px;background:#f1f1f1;font-family:SansBold}} .row{{display:flex;align-items:center;gap:30px;padding:24px 30px;border-bottom:2px solid #ddd}}
      .lab{{font:900 90px SansBlack;width:80px;color:#E63946}} .big{{width:960px;height:540px;box-shadow:0 6px 18px rgba(0,0,0,.2)}}
      .small{{width:320px;height:180px;border-radius:6px;box-shadow:0 3px 10px rgba(0,0,0,.25)}} .cap{{font-size:22px;color:#666;margin-top:8px;text-align:center}}</style></head><body>{rows}</body></html>'''
    f = OUT / '_compare.html'
    f.write_text(h, 'utf-8')
    pg.set_viewport_size({'width': 1500, 'height': 1800})
    pg.goto(f.as_uri())
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(300)
    out = HERE / f'封面方案对比_{pid}.png'
    pg.screenshot(path=str(out), full_page=True)
    f.unlink()
    return out


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    mode, ids = sys.argv[1], sys.argv[2:]
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page()
        if mode == '对比':
            print(compare(pg, ids[0]))
        else:
            dest = HERE / '成品'
            dest.mkdir(exist_ok=True)
            for pid in ids:
                print(render(pg, mode, pid, dest / cover_name(DATA[pid])))
        br.close()
