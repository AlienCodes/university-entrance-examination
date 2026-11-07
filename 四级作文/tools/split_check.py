"""检查分屏方案：逐句按方案拆屏、渲染，核对分屏点（唯一、在词边界、不切断生词）、中文片段（是定稿译文的原样片段、合起来不多不少）和每屏字号下限。

    /opt/ttsenv/bin/python 专八/tools/split_check.py 方案.json        # 方案格式与 分屏.json 相同：{"t01": {"12": {"at": ["…"], "zh": ["…", "…"]}}}
    /opt/ttsenv/bin/python 专八/tools/split_check.py --need t01 t02  # 列出不拆屏就放不下的句子（与 fitcheck.py 相同）

只读：不改 分屏.json。全部通过时最后一行是 “ALL OK”。
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_video as M  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

P = {p['id']: p for p in json.loads((M.C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}


def render_all(pg, td, p, k, s, parts):
    out = []
    S = [x for para in p['paras'] for x in para]
    for part in parts:
        f = Path(td) / 'x.html'
        f.write_text(M.sentence_slide(p, s, k, len(S), part), 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        fs, vs, fits = pg.evaluate(M.FIT)
        out.append((fs, vs, fits and fs >= M.MIN_FS and vs >= M.MIN_VS))
    return out


def main():
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': M.W, 'height': M.H})
        bad = 0
        if sys.argv[1] == '--need':
            for pid in sys.argv[2:]:
                p = P[pid]
                for k, s in enumerate([x for para in p['paras'] for x in para], 1):
                    r = render_all(pg, td, p, k, s, [(0, len(s['en']), s['zh'], '')])
                    if not r[0][2]:
                        bad += 1
                        print(f'{pid} {k} 需要拆屏（英文 {r[0][0]}px、词汇 {r[0][1]}px、{len(s["w"])} 个词条、{len(s["en"].split())} 词）')
            print(f'共 {bad} 句需要拆屏')
        else:
            plan = json.loads(Path(sys.argv[1]).read_text('utf-8'))
            for pid, d in plan.items():
                if pid.startswith('_'):
                    continue
                p = P[pid]
                S = [x for para in p['paras'] for x in para]
                for k, c in d.items():
                    s = S[int(k) - 1]
                    M.SPLIT.setdefault(pid, {})[k] = c
                    try:
                        parts = M.split_parts(pid, int(k), s)
                    except SystemExit as e:
                        bad += 1
                        print(f'{pid} {k} ❌ {e}')
                        continue
                    r = render_all(pg, td, p, int(k), s, parts)
                    ok = all(x[2] for x in r)
                    bad += not ok
                    print(f'{pid} {k} {"OK" if ok else "❌ 仍放不下"} ' + ' | '.join(f'第{i + 1}屏 英文{x[0]}px 词汇{x[1]}px' for i, x in enumerate(r)))
            print('ALL OK' if not bad else f'{bad} 句不通过')
        br.close()


if __name__ == '__main__':
    main()
