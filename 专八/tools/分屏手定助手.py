"""人工指定分屏的助手（水墨：DZB_VARIANT=水墨）：
    DZB_VARIANT=水墨 /opt/ttsenv/bin/python 专八/tools/分屏手定助手.py t11 11                 # 看：英文、译文、词条位置、朗读停顿（音频分句）、整句一屏的字号
    DZB_VARIANT=水墨 /opt/ttsenv/bin/python 专八/tools/分屏手定助手.py t11 11 '<JSON 方案>'   # 试：{"at": [...], "zh": [...]|"整句", "无停顿": "..."}，逐屏字号、空屏、对齐
试的结果与 split_check.py 相同（下限 英文 73px、词汇 34px；每屏至少一个词条）。
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_video as M  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

pid, k = sys.argv[1], int(sys.argv[2])
P = {p['id']: p for p in json.loads((M.C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
p = P[pid]
S = [x for para in p['paras'] for x in para]
s = S[k - 1]
T = json.loads((M.C4 / 'audio' / 'timings.json').read_text('utf-8'))[M.VOICE][pid]['sentences'][k - 1]
if len(sys.argv) == 3:
    print('英文：', s['en'])
    print('译文：', s['zh'])
    print('词条（原文位置 → 词头 = 释义）：')
    for i, w in enumerate(s['w'], 1):
        print(f"  {i:2d}. [{w['sp'][0][0]}] {s['en'][w['sp'][0][0]:w['sp'][-1][1]]!r} → {w['h']} = {w['m']}")
    import re
    sys.path.insert(0, str(HERE.parent.parent / 'tools' / 'tts'))
    import gaokao_tts as G  # noqa: E402
    read = T.get('read', '')
    parts = [x for x in G.CLAUSE.split(re.sub(r'—(?=\S)', '— ', read)) if x.strip()]
    print(f'朗读停顿：音频分成 {len(T["parts"])} 段（各段之间是 0.28 秒停顿，切在这些段的开头＝落在停顿里）：')
    for (a, b), x in zip(T['parts'], parts if len(parts) == len(T['parts']) else [''] * len(T['parts'])):
        print(f'  {a:7.2f}–{b:7.2f}  {x}')
    if len(parts) != len(T['parts']):
        print('  （分句文字与音频段数对不上，以音频段数为准；段的开头可用换屏检查确认）')
    plan = None
else:
    plan = json.loads(sys.argv[3])
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': M.W, 'height': M.H})
    if plan is None:
        parts = [(0, len(s['en']), s['zh'], '')]
    else:
        M.SPLIT.setdefault(pid, {})[str(k)] = {x: y for x, y in plan.items() if x != '理由'}
        try:
            parts = M.split_parts(pid, k, s)
        except SystemExit as e:
            sys.exit(f'❌ 方案不成立：{e}')
    bad = False
    for j, part in enumerate(parts, 1):
        f = Path(td) / 'x.html'
        f.write_text(M.sentence_slide(p, s, k, len(S), part), 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        fs, vs, fits = pg.evaluate(M.FIT)
        lo, hi = part[0], part[1]
        n = sum(1 for w in s['w'] if lo <= w['sp'][0][0] < hi)
        ok = fits and fs >= M.MIN_FS and vs >= M.MIN_VS and n > 0
        bad |= not ok
        print(f"{'✅' if ok else '❌'} 第 {j} 屏：英文 {fs}px 词汇 {vs}px（下限 {M.MIN_FS}/{M.MIN_VS}）词条 {n} 个  | {s['en'][lo:hi]!r}  | 中文：{part[2]!r}")
    br.close()
print('整句一屏' if plan is None else ('全部通过' if not bad else '不通过'))
