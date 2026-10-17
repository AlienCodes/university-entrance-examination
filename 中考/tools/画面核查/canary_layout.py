"""排版复核的埋雷：把某篇的截屏复制成埋雷副本，替换其中 5 屏为故意做坏排版的画面（用生成视频的同一程序渲染后再改样式），
检验排版审阅员（zk-frame-qa.js，lenses: ["visual"]）能否看出排版缺陷——这类缺陷 pixelcheck.py 查不出（它拿同一个程序重画来比，程序本身画坏了两边一样）。
画面文字的雷（形近字、数字）归 pixelcheck.py，见 埋雷位置.json。

    /opt/ttsenv/bin/python 中考/tools/画面核查/canary_layout.py <frames dir> z01 y4   → <frames dir>/y4/ 与 ref/y4.txt，并打印埋了哪几屏
之后用 pixelcheck.py <frames dir> --as y4=z01 确认恰好这几屏不同（雷确实埋进去了）。
专八：加 --project 专八（如 canary_layout.py --project 专八 <frames dir> t03 q3）。六级大字版：canary_layout.py --project 六级 --style 3 六级/样片/截图 s07 k7
（截图是无损 WebP，雷也存成 WebP；参考文字在 六级/样片/截图/ref/）。专八样片某种画面：再加 --style 2（截图方式与 样片.py --stills 相同）。屏号按分屏实际计算（第 k 句之前每个分屏多出的屏都算上），
埋雷的句子选不分屏的句子（分屏的句子顺延到下一个不分屏的句子），专八与中考都适用。
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
from layoutcheck import project  # noqa: E402
PROJ, T, ARGV = project(sys.argv[1:])
sys.path.insert(0, str(T))
import make_video as M  # noqa: E402
STYLE = None
if '--style' in ARGV:                             # 专八样片：按某种画面埋雷（C、1–6），截图方式与 样片.py --stills 相同（按 4K 排版画，再缩成 1080p）
    j = ARGV.index('--style')
    STYLE, ARGV = ARGV[j + 1], ARGV[:j] + ARGV[j + 2:]
    M.set_style(STYLE)
from playwright.sync_api import sync_playwright  # noqa: E402

S, src, dst = Path(ARGV[0]), ARGV[1], ARGV[2]
P = {p['id']: p for p in json.loads((R / PROJ / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
p = P[src]
sents = [s for pa in p['paras'] for s in pa]
nparts = [len(M.split_parts(src, k, s)) for k, s in enumerate(sents, 1)]


def screen_of(k):
    """第 k 句（不分屏）的屏号：片头是第 1 屏，之前每句占 nparts 屏。"""
    return 2 + sum(nparts[:k - 1])


def plain(k):
    """从第 k 句起第一个不分屏的句子（埋雷整句排在一屏上，与视频里这一屏的结构相同）。"""
    while nparts[k - 1] > 1:
        k += 1
    return k
shutil.rmtree(S / dst, ignore_errors=True)
shutil.copytree(S / src, S / dst)
shutil.copy(S / 'ref' / f'{src}.txt', S / 'ref' / f'{dst}.txt')
for f in S.glob(f'diff_{dst}_*.png'):
    f.unlink()

FIT_THEN = lambda js: f'() => {{ ({M.FIT})(); {js} }}'
# （屏号, 句号；0 = 片头, 缺陷, 改 HTML, 渲染后执行的 JS）
MINES = [
    (1, 0, '片头标题字号过大，超出白色卡片', lambda h: h.replace('</head>', '<style>.ttl h1{font-size:230px!important;white-space:nowrap}</style></head>'), None),
    (4, 3, '英文字号过大，溢出句子区、压到中文和页脚', None, FIT_THEN("document.documentElement.style.setProperty('--fs','112px')")),
    (8, 7, '中文译文第 3 个字变成乱码“\uFFFD”（缺字形的字在本机显示为空白，所以用乱码符号）', 'ZH3', None),
    (12, 11, '英文行首有一大段异常空白', lambda h: h.replace('<div class="en">', '<div class="en"><span style="display:inline-block;width:520px"></span>', 1), None),
    (15, 14, '词汇栏字号过大，词条超出卡片底边、压到页脚', None, FIT_THEN("document.documentElement.style.setProperty('--vs','62px')")),
]
MINES = [(1, 0, *m[2:]) if m[1] == 0 else (screen_of(plain(m[1])), plain(m[1]), *m[2:]) for m in MINES]      # 中考无分屏的篇目：屏号与原表相同
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': M.W, 'height': M.H}, device_scale_factor=2 if STYLE else 1)
    f = Path(td) / 'x.html'
    for scr, k, what, edit, js in MINES:
        s = sents[k - 1] if k else None
        if edit == 'ZH3':                         # 改数据再渲染（译文由 zh_html 逐字排版，不能直接改 HTML）
            s, edit = dict(s, zh=s['zh'][:2] + '\uFFFD' + s['zh'][3:]), None
        h = M.title_slide(p) if k == 0 else M.sentence_slide(p, s, k, len(sents))
        if edit:
            h2 = edit(h)
            assert h2 != h, f'雷没有埋进去：{what}'
            h = h2
        f.write_text(h, 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        pg.evaluate(js or (M.FIT if k else '() => 0'))
        if STYLE:
            pg.screenshot(path=str(Path(td) / 'big.png'))
            out = S / dst / f'screen{scr:02d}.webp'          # 六级的截图是无损 WebP（大字版.py）：雷也存成同一格式、同一文件名，不多出一张 PNG
            if out.exists():
                M.small(Path(td) / 'big.png').save(out, 'WEBP', lossless=True, method=0)
            else:
                M.small(Path(td) / 'big.png').save(S / dst / f'screen{scr:02d}.png')
        else:
            pg.screenshot(path=str(S / dst / f'screen{scr:02d}.png'))
        print(f'screen{scr:02d}', f'第 {k} 句' if k else '片头', what, flush=True)
    br.close()
