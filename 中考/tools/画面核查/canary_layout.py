"""排版复核的埋雷：把某篇的截屏复制成埋雷副本，替换其中 5 屏为故意做坏排版的画面（用生成视频的同一程序渲染后再改样式），
检验排版审阅员（zk-frame-qa.js，lenses: ["visual"]）能否看出排版缺陷——这类缺陷 pixelcheck.py 查不出（它拿同一个程序重画来比，程序本身画坏了两边一样）。
画面文字的雷（形近字、数字）归 pixelcheck.py，见 埋雷位置.json。

    /opt/ttsenv/bin/python 中考/tools/画面核查/canary_layout.py <frames dir> z01 y4   → <frames dir>/y4/ 与 ref/y4.txt，并打印埋了哪几屏
之后用 pixelcheck.py <frames dir> --as y4=z01 确认恰好这几屏不同（雷确实埋进去了）。
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
sys.path.insert(0, str(R / '中考' / 'tools'))
import make_video as M  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

S, src, dst = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
P = {p['id']: p for p in json.loads((R / '中考' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
p = P[src]
sents = [s for pa in p['paras'] for s in pa]
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
    (8, 7, '中文译文第 3 个字变成乱码“\uFFFD”（缺字形的字在本机显示为空白，所以用乱码符号）', lambda h: (lambda i: h[:i + 2] + '\uFFFD' + h[i + 3:])(h.index('<div class="zh">') + len('<div class="zh">')), None),
    (12, 11, '英文行首有一大段异常空白', lambda h: h.replace('<div class="en">', '<div class="en"><span style="display:inline-block;width:520px"></span>', 1), None),
    (15, 14, '词汇栏字号过大，词条超出卡片底边、压到页脚', None, FIT_THEN("document.documentElement.style.setProperty('--vs','62px')")),
]
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': M.W, 'height': M.H})
    f = Path(td) / 'x.html'
    for scr, k, what, edit, js in MINES:
        h = M.title_slide(p) if k == 0 else M.sentence_slide(p, sents[k - 1], k, len(sents))
        if edit:
            h2 = edit(h)
            assert h2 != h, f'雷没有埋进去：{what}'
            h = h2
        f.write_text(h, 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        pg.evaluate(js or (M.FIT if k else '() => 0'))
        pg.screenshot(path=str(S / dst / f'screen{scr:02d}.png'))
        print(f'screen{scr:02d}', what, flush=True)
    br.close()
