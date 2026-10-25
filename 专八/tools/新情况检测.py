"""截图审阅的省 token 做法（用户 2026-10-23：整屏盲审“一晚上可能用掉一周一半的 token”，这类做法淘汰）：
同一套程序、同一套样式画出来的屏，已经逐屏审过的篇目（截图审阅登记里的）是“见过的”；新篇目里只有出现了“没见过的东西”的屏才可能出新毛病，
其余的由程序检查（layoutcheck 等）兜底。本程序零 token：列出新篇目里每一种没见过的字符和写法，以及出现在哪几屏，只看这几屏。

    DZB_VARIANT=水墨 /opt/ttsenv/bin/python 专八/tools/新情况检测.py --见过 t01 … t10 --新 t11 … t27 [--自检]

“写法”包括：非汉字非英文字母数字的每个字符（标点、符号、带音调字母）、释义里的公式“+”、译文中文单引号、各种括号、超长英文单词、多连字符词、
数字加单位、数字范围、全大写缩写、斜杠、省略号、超长词条、超长释义、一屏两个以上带间隔号的人名、一屏译文超长。
--自检：双向验证——往一篇新篇目的一句译文里放进一个没见过的符号（§），必须报出来；见过的篇目对自己必须 0 处。"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_video as M  # noqa: E402

a = sys.argv[1:]
seen_ids = a[a.index('--见过') + 1:a.index('--新')]
rest = a[a.index('--新') + 1:]
new_ids = [x for i, x in enumerate(rest) if not x.startswith('--') and (i == 0 or rest[i - 1] != '--见过项目')]
P = {p['id']: p for p in json.loads((M.C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}

PATTERNS = {
    '释义里的公式“+”': lambda s: [w['m'] for w in s['w'] if '+' in w['m']],
    '译文中文单引号': lambda s: re.findall(r'[‘’]', s['zh']),
    '超长英文单词（≥15 字母）': lambda s: re.findall(r'[A-Za-z]{15,}', s['en']),
    '多连字符词': lambda s: re.findall(r'\w+(?:-\w+){2,}', s['en']),
    '数字加单位': lambda s: re.findall(r'\d+\s?(?:km|kg|mg|cm|mm|ml|%|percent)\b', s['en']),
    '数字范围': lambda s: re.findall(r'\d[–-]\d', s['en']),
    '全大写缩写': lambda s: re.findall(r'\b[A-Z]{2,}s?\b', s['en']),
    '斜杠': lambda s: [x for x in (s['en'], s['zh']) if '/' in x or '／' in x],
    '超长词条（≥28 字符）': lambda s: [w['h'] for w in s['w'] if len(w['h']) >= 28],
    '超长释义（≥26 字）': lambda s: [w['m'] for w in s['w'] if len(w['m']) >= 26],
    '一屏两个以上带间隔号的人名': lambda s: [s['zh']] if len(re.findall(r'[一-鿿]·[一-鿿]', s['zh'])) >= 2 else [],
    '括注里有英文': lambda s: re.findall(r'[（(][^）)]*[A-Za-z][^）)]*[）)]', s['zh'] + ''.join(w['m'] for w in s['w'])),
}
SPECIAL = re.compile(r'[^一-鿿A-Za-z0-9\s]')


def screens(pid):
    """每一屏显示的内容：(屏号, 句子编号或 None, 这一屏的 句子字典)。分屏的句子只取这一屏的英文、中文、词条。"""
    p = P[pid]
    S = [x for pa in p['paras'] for x in pa]
    out = [('screen01', None, {'en': '', 'zh': str(p.get('title', '')) + str(p.get('summary', '')), 'w': []})]
    n = 2
    for k, s in enumerate(S, 1):
        for lo, hi, zh, tag in M.split_parts(pid, k, s):
            ws = [w for w in s['w'] if lo <= w['sp'][0][0] < hi]
            out.append((f'screen{n:02d}', k, {'en': s['en'][lo:hi], 'zh': zh, 'w': ws}))
            n += 1
    return out


def features(s):
    f = {f'字符 {c}' for c in SPECIAL.findall(s['en'] + s['zh'] + ''.join(w['m'] + w['h'] for w in s['w']))}
    f |= {name for name, fn in PATTERNS.items() if fn(s)}
    if len(s['zh']) >= 70:
        f.add('一屏译文超长（≥70 字）')
    return f


SEEN_PROJ = a[a.index('--见过项目') + 1] if '--见过项目' in a else None     # 见过的篇目在别的项目（专八听力：同一套书卷水墨，见过的是专八阅读 t01—t30）


def novel(seen, new, inject=False):
    global P
    known = set()
    if SEEN_PROJ:
        cur = M.PROJ
        M.set_project(SEEN_PROJ, look=False)
        P0, P = P, {p['id']: p for p in json.loads((M.C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
    for pid in seen:
        for _, _, s in screens(pid):
            known |= features(s)
    if SEEN_PROJ:
        M.set_project(cur, look=False)
        P = P0
    hits = {}
    for pid in new:
        for scr, k, s in screens(pid):
            if inject and pid == new[0] and k == 1:
                s = dict(s, zh=s['zh'] + '§')
            for x in features(s) - known:
                hits.setdefault(x, []).append(f'{pid} {scr}' + (f'（第 {k} 句）' if k else '（片头）'))
    return hits


if '--自检' in a:
    ok = any('§' in k for k in novel(seen_ids, new_ids, inject=True)) and (SEEN_PROJ or not novel(seen_ids, seen_ids))
    print('新情况检测：双向通过（放进的 § 报出来了，见过的篇目对自己 0 处）' if ok else '新情况检测：不通过')
    sys.exit(0 if ok else 1)
hits = novel(seen_ids, new_ids)
allscr = sorted({x.split('（')[0] for v in hits.values() for x in v})
for k, v in sorted(hits.items(), key=lambda kv: len(kv[1])):
    print(f'{k}：{len(v)} 屏  ' + '，'.join(v[:8]) + (' …' if len(v) > 8 else ''))
print(f'没见过的写法 {len(hits)} 种，涉及 {len(allscr)} 屏（{len(new_ids)} 篇共 {sum(len(screens(p)) for p in new_ids)} 屏）')
