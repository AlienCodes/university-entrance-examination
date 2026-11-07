"""双向验证：中文左右半空白标点集合（踩坑 58）。排版引擎（专八/tools/make_video.py ZCLOSE / ZOPEN，专八、六级、考研、考研作文共用）
与排版检查（layoutcheck.py 的 JS 第 74 行附近、Python 两处）各写一份，全靠手工同步。这里逐份抽出来核对：
四份完全一致、都含全角方括号［］〔〕；埋雷：任何一份少一个字符必须报出。
    python3 tools/防复发/验证/标点集合.py"""
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
MUST_C, MUST_O = set('，。、：；！？）”’］〕'), set('（“‘［〔')


def extract(eng, lc):
    out = {}
    m = re.search(r"ZCLOSE, ZOPEN = set\('([^']+)'\), set\('([^']+)'\)", eng)
    out['引擎 make_video'] = (m.group(1), m.group(2)) if m else None
    m = re.search(r"const ZC='([^']+)', ZO='([^']+)'", lc)
    out['layoutcheck JS'] = (m.group(1), m.group(2)) if m else None
    m = re.search(r"zc, zo = '([^']+)', '([^']+)'", lc)
    out['layoutcheck zc/zo'] = (m.group(1), m.group(2)) if m else None
    m = re.search(r"if b in '([^']+)…' or a in '([^']+)'", lc)
    out['layoutcheck 断行'] = (m.group(1), m.group(2)) if m else None
    return out


def check(sets):
    errs = [f'{k}：找不到标点集合（代码改了，验证要跟着改）' for k, v in sets.items() if v is None]
    got = {k: (frozenset(c), frozenset(o)) for k, (c, o) in ((k, v) for k, v in sets.items() if v)}
    ref = got.get('引擎 make_video')
    for k, (c, o) in got.items():
        if ref and (c, o) != ref:
            errs.append(f'{k} 与引擎不一致：右标点差 {"".join(sorted(c ^ ref[0]))}，左标点差 {"".join(sorted(o ^ ref[1]))}')
        if not MUST_C <= c or not MUST_O <= o:
            errs.append(f'{k} 缺 {"".join(sorted((MUST_C - c) | (MUST_O - o)))}')
    return errs


eng = (R / '专八/tools/make_video.py').read_text('utf-8')
lc = (R / '中考/tools/画面核查/layoutcheck.py').read_text('utf-8')
bad = []
e0 = check(extract(eng, lc))
print(f"  {'✅' if not e0 else '❌'} 现在的 4 份集合一致、含［］〔〕：{e0 or '0 处'}")
bad += e0
lc_bad = lc.replace("zc, zo = '，。、：；！？）”’】」》］〕'", "zc, zo = '，。、：；！？）”’】」》〕'", 1)
e1 = check(extract(eng, lc_bad))
print(f"  {'✅' if e1 else '❌'} 埋雷：layoutcheck 一处少了］ → {e1 or '没报出'}")
if not e1:
    bad.append('埋雷没报出')
print('标点集合双向验证：' + ('全部通过' if not bad else f'{len(bad)} 处失败'))
sys.exit(1 if bad else 0)
