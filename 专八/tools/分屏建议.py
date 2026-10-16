"""分屏建议（不花 token 的那一半）：找出一篇在任何一种画面（C、1–6）里一屏放不下或字号低于下限的句子，并给出分屏点候选。

    /opt/ttsenv/bin/python 专八/tools/分屏建议.py t03 [--styles C,1,2,3,4,5,6]

做法：
1. 按 分屏.json 现有方案，用生成视频的同一排版（make_video.layout）把每种画面的每一屏排一遍，列出不合格的句子（放不下、英文或词汇栏低于下限）。
2. 对每个不合格的句子，在英文的句中停顿处（逗号、分号、冒号、破折号后面，朗读在这些地方停 0.28 秒）逐个试切：一刀不够就试两刀；
   中文暂按与英文比例最接近的中文标点（，；：）切开（只为估算版面，正式的中文分段要人按意思核对后写进 分屏.json，split_parts 逐字核对）；
   7 种画面全部放得下、字号不低于下限的才算可行，按各屏英文长度最均衡排序。
输出：每句的候选（第二屏从哪几个词开始、建议的中文切分、各画面字号）。最终方案由人按意思选定、写进 分屏.json，再跑 样片.py --stills 全查
（其中用语音识别核对换屏时刻落在音频的句中停顿里）。
"""
import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_video as M  # noqa: E402

ZPUN = '，；：'


def zh_cut(zh, frac):
    """按比例找最接近的中文标点（标点留在前一段）。"""
    cand = [i + 1 for i, c in enumerate(zh[:-1]) if c in ZPUN]
    return min(cand, key=lambda i: abs(i / len(zh) - frac)) if cand else None


def en_cuts(en, s):
    """英文的句中停顿处：标点（, ; : — ) ”）后面、下一个词开头；不切断生词。"""
    out = []
    for m in re.finditer(r'[,;:)”]\s+(?=\S)|—(?=\S)', en):
        c = m.end()
        if 12 < c < len(en) - 12 and not any(a < c < b for w in s['w'] for a, b in w['sp']):
            out.append(c)
    return out


def fit_parts(pg, f, p, k, s, n, parts):
    """一种画面下，这句按 parts 分屏后的统一字号（取各屏最小）和是否都放得下。"""
    got = []
    for part in parts:
        f.write_text(M.sentence_slide(p, s, k, n, part), 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        got.append(pg.evaluate(M.FIT))
    st = [min(g[0] for g in got), min(g[1] for g in got)]
    ok = True
    for part in parts:
        f.write_text(M.sentence_slide(p, s, k, n, part), 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        fs, vs, fits = pg.evaluate(M.FIT, st)
        ok = ok and fits and fs >= M.MIN_FS and vs >= M.MIN_VS and [fs, vs] == st
    return st, ok


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    looks = (sys.argv[sys.argv.index('--styles') + 1].split(',') if '--styles' in sys.argv else list(M.LOOKS))
    pid = args[0]
    p = next(x for x in json.loads((HERE.parent / 'data' / 'vocab.json').read_text('utf-8'))['passages'] if x['id'] == pid)
    sents = [s for pa in p['paras'] for s in pa]
    n = len(sents)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': M.W, 'height': M.H}, device_scale_factor=2)
        f = Path(td) / 'x.html'
        bad, cur = {}, {}
        for look in looks:
            M.set_style(look)
            for k, s in enumerate(sents, 1):
                st, ok = fit_parts(pg, f, p, k, s, n, M.split_parts(pid, k, s))
                cur.setdefault(k, {})[look] = st
                if not ok:
                    bad.setdefault(k, []).append(f'{look}:{st[0]}/{st[1]}')
            print(f'画面 {look}（下限 {M.MIN_FS}/{M.MIN_VS}）：不合格 {sorted(k for k, v in bad.items() if any(x.startswith(look + ":") for x in v))}', flush=True)
        res = {}
        for k in sorted(bad):
            s = sents[k - 1]
            en, zh = s['en'], s['zh']
            cs = en_cuts(en, s)
            trials = [[c] for c in cs] + [[a, b] for i, a in enumerate(cs) for b in cs[i + 1:]]
            good = []
            for cuts in trials:
                if good and len(cuts) > len(good[0][0]):      # 一刀可行就不试两刀
                    break
                b = [0] + cuts + [len(en)]
                zc = [zh_cut(zh, c / len(en)) for c in cuts]
                if None in zc or zc != sorted(set(zc)):
                    continue
                zb = [0] + zc + [len(zh)]
                parts = [(b[x], b[x + 1], zh[zb[x]:zb[x + 1]], f' · PART {x + 1}/{len(b) - 1}') for x in range(len(b) - 1)]
                sizes, ok = {}, True
                for look in looks:
                    M.set_style(look)
                    st, o = fit_parts(pg, f, p, k, s, n, parts)
                    sizes[look] = st
                    ok = ok and o
                    if not ok:
                        break
                if ok:
                    good.append((cuts, [z[2] for z in parts], sizes, max(y - x for x, y in zip(b, b[1:]))))
            good.sort(key=lambda g: g[3])
            res[k] = {'不合格': bad[k], '现在': cur[k], '候选': [{'at': [' '.join(en[c:].split(' ')[:4]) for c in g[0]],
                                                           '中文（暂按比例，需按意思核对）': g[1], '字号': g[2]} for g in good[:4]]}
            print(f'\n第 {k} 句（{len(en)} 字符）不合格：{bad[k]}', flush=True)
            for g in good[:4]:
                print('  第二屏起：', ' | '.join('“' + ' '.join(en[c:].split(' ')[:4]) + '”' for c in g[0]), ' 字号', g[2], flush=True)
            if not good:
                print('  没有找到可行的切法（试过一刀、两刀）', flush=True)
        br.close()
    print('\n详细结果（JSON）：')
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
