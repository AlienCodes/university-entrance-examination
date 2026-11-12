"""商品图（1:1，5 张）：中考英语阅读 40 篇学习资料包（用户 2026-10-15）。

    /opt/ttsenv/bin/python 中考/tools/封面/make_shop.py   → 中考/封面/商品图/商品图1_主图.jpg … 商品图5_中考原题.jpg（2400×2400）

每张底部都有醒目的提示：虚拟商品 一旦售出 无法退款（请确认需要后再购买）。
图里展示的文件夹、文件名、大小、页数、页面预览全部取自真实的资料包（.github/zk-materials-release.txt 的清单、中考/听写卡/、中考/audio/、中考/真题/），
数字由程序统计——商品图与买家实际下载到的东西一致。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
T = HERE.parent
C4 = T.parent
ROOT = C4.parent
sys.path[:0] = [str(T), str(HERE)]
import make_video as M  # noqa: E402
from make_cover import stats  # noqa: E402

OUT = C4 / '封面' / '商品图'
FONTS = T / 'fonts'
TOP = '中考英语阅读40篇学习资料'
PAPERS = '中考英语真题原卷（23份）'
W = 1200
esc = M.esc

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1200px;height:1200px;overflow:hidden}
body{font-family:'Noto Sans SC',sans-serif;color:#1e1538;position:relative;background:radial-gradient(circle at 25% 20%,#6a35f0 0,#5420d1 45%,#360d9e 100%)}
.stripe{position:absolute;inset:0;background:repeating-linear-gradient(-35deg,rgba(255,255,255,.045) 0 22px,transparent 22px 58px)}
.sun{position:absolute;width:520px;height:520px;border-radius:50%;background:#ffd84a;right:-190px;top:-230px}
.k{paint-order:stroke fill;-webkit-text-stroke:10px #1e1538}
.brand{position:absolute;left:48px;top:40px;display:flex;gap:12px;align-items:center}
.pill{font-weight:900;font-size:34px;line-height:1;padding:12px 20px 14px;border-radius:16px;box-shadow:0 7px 0 #1e1538}
.y{background:#ffd84a;color:#1e1538}.p{background:#ff6fae;color:#fff}.w{background:#fff;color:#5420d1}
h1{position:absolute;left:44px;color:#fff;font-weight:900;line-height:1.08;letter-spacing:1px}
h1 em{font-style:normal;color:#ffd84a}
.note{position:absolute;left:0;right:0;bottom:0;height:150px;background:#fff;border-top:10px solid #e8202a;display:flex;flex-direction:column;align-items:center;justify-content:center}
.note b{font-weight:900;font-size:64px;line-height:1;color:#e8202a;letter-spacing:4px}
.note b i{font-style:normal;background:#e8202a;color:#fff;padding:2px 14px 6px;border-radius:12px;margin-right:16px;letter-spacing:2px}
.note span{font-weight:700;font-size:28px;color:#1e1538;margin-top:12px}
.win{position:absolute;background:#fff;border-radius:16px;box-shadow:14px 16px 0 #1e1538;overflow:hidden;border:3px solid #1e1538}
.bar{height:50px;background:#eef0f5;display:flex;align-items:center;padding:0 16px;gap:12px;border-bottom:2px solid #d7dae3}
.bar .dots{display:flex;gap:8px}.bar .dots i{width:14px;height:14px;border-radius:50%;background:#ff5f57}.bar .dots i:nth-child(2){background:#febc2e}.bar .dots i:nth-child(3){background:#28c840}
.addr{flex:1;background:#fff;border:1.5px solid #c9cdd8;border-radius:8px;height:32px;display:flex;align-items:center;padding:0 12px;font-size:19px;color:#3f3a5a;white-space:nowrap;overflow:hidden}
.addr s{text-decoration:none;color:#9aa0b0;margin:0 8px}
.head,.row{display:grid;grid-template-columns:1fr 150px 116px;align-items:center;padding:0 18px;column-gap:12px}
.head{height:40px;font-size:17px;color:#7a8094;border-bottom:1.5px solid #e3e5ec}
.row{height:var(--rh,46px);font-size:var(--fs,20px);border-bottom:1px solid #f0f1f5;white-space:nowrap}
.row .n{display:flex;align-items:center;gap:12px;overflow:hidden;font-weight:500}.row .n span{overflow:hidden;text-overflow:ellipsis}
.row .t,.row .z{color:#7a8094;font-size:calc(var(--fs,20px) - 3px)}.row .z{text-align:right}
.row.hl{background:#fff4c2}
.more{height:46px;display:flex;align-items:center;padding:0 18px;color:#5420d1;font-weight:900;font-size:21px;background:#f6f3ff}
svg{flex:none}
.card{position:absolute;background:#fff;border:3px solid #1e1538;border-radius:12px;box-shadow:10px 12px 0 #1e1538;overflow:hidden}
.card img{display:block;width:100%}
.tag{position:absolute;font-weight:900;font-size:30px;line-height:1;padding:10px 18px 12px;border-radius:14px;box-shadow:0 6px 0 #1e1538;z-index:3}
.big{position:absolute;color:#fff;font-weight:900}
.chips{position:absolute;display:grid;grid-template-columns:repeat(5,1fr);gap:10px}
.chips i{font-style:normal;background:#fff;color:#5420d1;font-weight:900;font-size:30px;line-height:1;text-align:center;padding:12px 0 14px;border-radius:12px;box-shadow:0 5px 0 #1e1538}
.list{position:absolute;color:#fff;font-size:30px;font-weight:700;line-height:1.55}
.list b{color:#ffd84a;font-weight:900}
"""

NOTE = ('<div class="note"><b><i>虚拟商品</i>一旦售出 无法退款</b>'
        '<span>电子版资料，请确认自己需要后再购买，感谢理解</span></div>')


def icon(kind, s=30):
    if kind == 'dir':
        return (f'<svg width="{s}" height="{s}" viewBox="0 0 32 32"><path d="M2 8a3 3 0 0 1 3-3h7l3 3h12a3 3 0 0 1 3 3v14a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3z" fill="#f4b73a"/>'
                '<path d="M2 12h28v13a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3z" fill="#ffd25c"/></svg>')
    col, txt = {'pdf': ('#e8202a', 'PDF'), 'mp3': ('#5420d1', 'MP3'), 'docx': ('#2b5cd8', 'W')}[kind]
    return (f'<svg width="{s}" height="{s}" viewBox="0 0 32 32"><path d="M7 2h13l7 7v19a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#fff" stroke="#9aa0b0" stroke-width="1.5"/>'
            f'<path d="M20 2v7h7" fill="none" stroke="#9aa0b0" stroke-width="1.5"/><rect x="3" y="15" width="22" height="11" rx="2" fill="{col}"/>'
            f'<text x="14" y="23.6" font-size="8" font-weight="700" text-anchor="middle" fill="#fff" font-family="Arial">{txt}</text></svg>')


def size(n):
    return f'{n / 2**20:.1f} MB' if n >= 2**20 else f'{max(1, round(n / 1024))} KB'


def row(kind, name, typ, sz, hl=False):
    return (f'<div class="row{" hl" if hl else ""}"><div class="n">{icon(kind)}<span>{esc(name)}</span></div>'
            f'<div class="t">{esc(typ)}</div><div class="z">{esc(sz)}</div></div>')


def window(x, y, w, path, rows, more='', style=''):
    addr = '<s>›</s>'.join(esc(p) for p in path)
    return (f'<div class="win" style="left:{x}px;top:{y}px;width:{w}px;{style}"><div class="bar"><div class="dots"><i></i><i></i><i></i></div>'
            f'<div class="addr">{addr}</div></div><div class="head"><div>名称</div><div>类型</div><div style="text-align:right">大小</div></div>'
            f'{"".join(rows)}{more}</div>')


def page(body, extra=''):
    fonts = ''.join(f'<link rel="stylesheet" href="{(FONTS / f).as_uri()}">' for f in ('fonts.css', 'noto-sans-sc/900.css'))
    return (f'<!doctype html><html><head><meta charset="utf-8">{fonts}<style>{CSS}{extra}</style></head><body>'
            f'<div class="sun"></div><div class="stripe"></div>{body}{NOTE}</body></html>')


def main():
    from playwright.sync_api import sync_playwright
    P = json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']
    st = stats(P)
    lines = [l.split('|') for l in (ROOT / '.github' / 'zk-materials-release.txt').read_text('utf-8').split('\n')[1:] if l.strip()]
    assert len(lines) == 40
    folders = [f'{i} {n}' for i, (n, _) in enumerate(lines, 1)]
    papers = sorted((C4 / '真题').glob('*.docx'), key=lambda f: (-int(f.name[:4]), f.name))
    assert len(papers) == 23
    name1, audio1 = lines[0]
    d1 = C4 / '听写卡' / name1
    files1 = [(f'{name1} - {k}.pdf', d1 / f'{name1} - {k}.pdf') for k in ('0 逐句精读', '1 汉译英', '2 英译汉', '3 文章填空')]
    mp3 = C4 / 'audio' / audio1
    npdf = 40 * 4
    pages = lambda f: int(subprocess.run(['pdfinfo', str(f)], capture_output=True, text=True, check=True).stdout.split('Pages:')[1].split()[0])
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        subprocess.run(['pdftoppm', '-r', '60', '-f', '1', '-l', '3', '-png', str(files1[0][1]), str(td / 'read')], check=True)
        for k, (_, f) in enumerate(files1[1:], 1):
            n = pages(f)
            subprocess.run(['pdftoppm', '-r', '80', '-f', '1', '-l', '1', '-png', str(f), str(td / f'c{k}a')], check=True)
            subprocess.run(['pdftoppm', '-r', '80', '-f', str(n), '-l', str(n), '-png', str(f), str(td / f'c{k}z')], check=True)
        img = lambda pat: sorted(td.glob(pat))[0].as_uri()
        reads = [f.as_uri() for f in sorted(td.glob('read*.png'))]

        top_rows = [row('dir', PAPERS, '文件夹', f'{len(papers)} 份')] + [row('dir', f, '文件夹', '5 个文件', hl=(i == 0)) for i, f in enumerate(folders[:9])]
        imgs = {}
        # 1 主图
        imgs['商品图1_主图'] = page(f"""
<div class="brand"><div class="pill y">中考英语</div><div class="pill p">{min(st['years'])}—{max(st['years'])}真题</div><div class="pill w">电子版</div></div>
<h1 class="k" style="top:128px;font-size:84px">{st['n']}篇中考阅读真题<br><em>全套学习资料</em></h1>
<div class="list" style="left:52px;top:356px">✔ <b>{st['n']}</b> 篇逐句精读 PDF（和视频画面一样）<br>✔ <b>{st['n'] * 3}</b> 份听写卡：汉译英 · 英译汉 · 文章填空<br>✔ <b>{st['n']}</b> 段男声朗读音频 MP3<br>✔ <b>{len(papers)}</b> 份中考英语真题原卷（Word）<br>✔ 覆盖 <b>{st['heads']}</b> 个中考词汇（{st['single']} 单词 + {st['phr']} 短语）</div>
{window(52, 640, 1096, [TOP], top_rows[:6], f'<div class="more">… 共 {len(folders)} 个篇目文件夹 + 1 个原卷文件夹，按年份排好</div>', '--rh:40px;--fs:19px')}""")
        # 2 打开一篇文件夹
        rows2 = [row('pdf', n, f'PDF · {pages(f)} 页', size(f.stat().st_size)) for n, f in files1] + [row('mp3', f'{name1} - 朗读音频.mp3', 'MP3 音频', size(mp3.stat().st_size))]
        imgs['商品图2_打开文件夹'] = page(f"""
<div class="brand"><div class="pill y">打开就能用</div><div class="pill p">每篇 5 个文件</div></div>
<h1 class="k" style="top:128px;font-size:70px">每篇一个文件夹<br><em>精读 + 听写 + 朗读</em> 全配齐</h1>
{window(40, 330, 1120, [TOP, folders[0]], rows2, '', '--rh:58px;--fs:21px')}
<div class="list" style="left:52px;top:760px;font-size:29px">① <b>逐句精读</b>：英文高亮 + 编号生词 + 中文翻译，一句一页<br>② <b>汉译英 / 英译汉</b>：默写单词短语，最后一页附答案<br>③ <b>文章填空</b>：原文挖空 + 每空提示，最后一页附答案<br>④ <b>朗读音频</b>：男声逐句朗读，跟读磨耳朵</div>""")
        # 3 逐句精读预览
        imgs['商品图3_逐句精读'] = page(f"""
<div class="brand"><div class="pill y">0 逐句精读.pdf</div><div class="pill p">和视频画面一样</div></div>
<h1 class="k" style="top:128px;font-size:70px">一句一页 <em>逐句精读</em><br>生词编号 + 中文翻译</h1>
<div class="card" style="left:70px;top:340px;width:700px;transform:rotate(-3deg)"><img src="{reads[0]}"></div>
<div class="card" style="left:300px;top:520px;width:820px;transform:rotate(2deg);z-index:2"><img src="{reads[1]}"></div>
<div class="tag y" style="left:640px;top:330px;transform:rotate(4deg)">英文高亮 · 编号生词</div>""")
        # 4 听写卡预览
        imgs['商品图4_听写卡'] = page(f"""
<div class="brand"><div class="pill y">3 份听写卡</div><div class="pill p">A4 直接打印</div></div>
<h1 class="k" style="top:128px;font-size:70px">汉译英 · 英译汉 · 文章填空<br><em>最后一页都附答案</em></h1>
<div class="card" style="left:40px;top:350px;width:360px;transform:rotate(-4deg)"><img src="{img('c1a*.png')}"></div>
<div class="card" style="left:420px;top:330px;width:360px;transform:rotate(1deg);z-index:2"><img src="{img('c2a*.png')}"></div>
<div class="card" style="left:800px;top:350px;width:360px;transform:rotate(4deg)"><img src="{img('c3a*.png')}"></div>
<div class="tag y" style="left:110px;top:900px">汉译英</div><div class="tag y" style="left:520px;top:900px">英译汉</div><div class="tag y" style="left:880px;top:900px">文章填空</div>""",
                                     '.card img{height:auto}')
        # 5 中考原题 + 覆盖地区
        prow = [row('docx', f.name, 'Word 文档', size(f.stat().st_size)) for f in papers[:6]]
        chips = ''.join(f'<i>{esc(r)}</i>' for r in st['regions'])
        imgs['商品图5_中考原题'] = page(f"""
<div class="brand"><div class="pill y">附送</div><div class="pill p">中考真题原卷</div></div>
<h1 class="k" style="top:128px;font-size:70px"><em>{len(papers)}</em> 份中考英语真题原卷<br>{len(st['regions'])} 个省市 · {min(st['years'])}—{max(st['years'])}</h1>
{window(40, 330, 1120, [TOP, PAPERS], prow, f'<div class="more">… 共 {len(papers)} 份 Word 原卷</div>', '--rh:40px;--fs:19px')}
<div class="chips" style="left:52px;top:748px;width:1096px">{chips}</div>""")
        with __import__('playwright.sync_api', fromlist=['sync_playwright']).sync_playwright() as pw:
            br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
            pg = br.new_page(viewport={'width': W, 'height': W}, device_scale_factor=2)
            from PIL import Image
            for name, h in imgs.items():
                f = td / 'p.html'
                f.write_text(h, 'utf-8')
                pg.goto(f.as_uri())
                pg.evaluate('document.fonts.ready')
                bad = pg.evaluate("""() => { const r = [], note = document.querySelector('.note').getBoundingClientRect();
                    for (const e of document.querySelectorAll('h1,.list,.win,.card,.chips,.brand,.tag')) { const b = e.getBoundingClientRect();
                      if (b.left < 0 || b.right > 1200 || b.top < 0 || b.bottom > note.top - 4) r.push('出界或压到退款提示：' + e.className + ' ' + Math.round(b.bottom)); }
                    for (const e of document.querySelectorAll('.addr, .row .n span')) if (e.scrollWidth > e.clientWidth + 1) r.push('被截断：' + e.textContent.slice(0, 20));
                    return r; }""")
                if bad:
                    raise SystemExit(f'{name}：{bad}')
                png = td / 'p.png'
                pg.screenshot(path=str(png))
                Image.open(png).convert('RGB').save(OUT / f'{name}.jpg', quality=92)
                print(OUT / f'{name}.jpg', flush=True)
            br.close()


if __name__ == '__main__':
    main()
