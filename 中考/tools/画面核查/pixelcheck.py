"""画面与定稿文字逐屏机械比对（不靠人眼）：用生成视频的同一套程序，按复核定稿的数据（中考/data/vocab.json）重新渲染每一屏，
和从成品视频里截出的对应屏（extract.py 截的 1920 宽画面）逐块比较像素。任何一个字、一个编号、一个标点不同，都会在那一块留下明显差异；
视频压缩的噪声很小。埋雷测试（形近字、同音字、数字）人眼复核会漏，这里必须全部查出。

    /opt/ttsenv/bin/python 中考/tools/画面核查/pixelcheck.py <frames dir> z01 z02 … [--as y3=z13]

--as 埋雷副本=原篇：用原篇的定稿数据比对埋雷副本（应报出所有埋入的缺陷）。
输出每篇“OK”或列出有差异的屏和位置（屏号、差异块的坐标），并把差异最大的块存成对比图。
"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
sys.path.insert(0, str(R / '中考' / 'tools'))
import make_video as M  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

S = Path(sys.argv[1])
argv = sys.argv[2:]
alias = {}
if '--as' in argv:
    j = argv.index('--as')
    alias = dict(a.split('=') for a in argv[j + 1].split(','))
    argv = argv[:j] + argv[j + 2:]
ids = argv + list(alias)
P = {p['id']: p for p in json.loads((R / '中考' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
SCALES = [(16, 50), (8, 70)]   # （块大小, 阈值）：块内平均灰度差超过阈值算“不同”。实测视频压缩噪声：16 像素块最大 33、8 像素块最大 54；
                               # 埋雷：一个字、数字不同 16 像素块 75—177；页脚、编号圆圈这类小字只改一个数字时 16 像素块只有 20—46，8 像素块 79—100


def screens(p):
    sents = [s for pa in p['paras'] for s in pa]
    out = [('title', M.title_slide(p), False)]
    for k, s in enumerate(sents, 1):
        for part in M.split_parts(p['id'], k, s):
            out.append((f's{k}', M.sentence_slide(p, s, k, len(sents), part), True))
    return out


def blocks(d, B):
    h, w = d.shape[0] // B * B, d.shape[1] // B * B
    return d[:h, :w].reshape(h // B, B, w // B, B).mean(axis=(1, 3))


bad_all = {}
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': M.W, 'height': M.H})
    f = Path(td) / 'x.html'
    for vid in ids:
        src = alias.get(vid, vid)
        shots = sorted((S / vid).glob('screen*.png'))
        want = screens(P[src])
        bad = []
        if len(shots) != len(want):
            bad.append(f'屏数 {len(shots)}，应为 {len(want)}')
        for i, ((label, h, fit), shot) in enumerate(zip(want, shots), 1):
            f.write_text(h, 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            if fit:
                pg.evaluate(M.FIT)
            ref = Path(td) / 'r.png'
            pg.screenshot(path=str(ref))
            a = np.asarray(Image.open(ref).convert('L'))
            b = np.asarray(Image.open(shot).convert('L').resize((a.shape[1], a.shape[0])))
            d = np.abs(a.astype(np.int16) - b.astype(np.int16)).astype(np.float32)
            hit = None
            for B, lim in SCALES:
                m = blocks(d, B)
                ys, xs = np.where(m > lim)
                if len(ys):
                    y, x = int(ys[m[ys, xs].argmax()]), int(xs[m[ys, xs].argmax()])
                    hit = (B, len(ys), float(m.max()), x * B, y * B)
                    break
            if hit:
                B, n, mx, x, y = hit
                x, y = x // B, y // B
                bad.append(f'第 {i} 屏（{label}）：{n} 块不同（{B} 像素块），最大差异 {mx:.0f}，位置 x≈{x * B} y≈{y * B}')
                x0, y0 = max(0, x * B - 200), max(0, y * B - 60)
                crop = (x0, y0, min(a.shape[1], x0 + 600), min(a.shape[0], y0 + 160))
                pair = Image.new('L', (600, 330), 255)
                pair.paste(Image.fromarray(a).crop(crop), (0, 0))
                pair.paste(Image.fromarray(b).crop(crop), (0, 170))
                pair.save(S / f'diff_{vid}_{i:02d}.png')
        bad_all[vid] = bad
        print(vid, 'OK' if not bad else '有差异：\n  ' + '\n  '.join(bad), flush=True)
    br.close()
print('全部一致' if not any(bad_all.values()) else f'有差异的：{[k for k, v in bad_all.items() if v]}')
