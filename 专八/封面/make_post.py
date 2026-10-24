"""专八 B 站投稿文案：标题（推荐 + 2 个备选）、简介、标签、粉丝动态。数字全部从 专八/data/vocab.json 现算，并检查 B 站字数限制。

    python3 专八/封面/make_post.py      → 专八/封面/B站上传文案.md

用户要求（2026-10-24）：让想学专八、专八词汇的学生尽可能搜得到。所以标题最前面放最常搜的词（专八 / 专八阅读 / 专八真题 / 专八词汇），
后面带上 英语专业八级、TEM-8、英专、逐句精读/翻译、年份、篇数；读起来要通顺、有点击欲，不堆关键词。字数限制同 中考/tools/封面/make_post.py。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TITLE_MAX, DESC_MAX, TAG_MAX, TAG_LEN, DYN_MAX = 80, 2000, 10, 20, 233

P = json.loads((REPO / '专八/data/vocab.json').read_text('utf-8'))['passages']
N = len(P)
SENTS = sum(len(pa) for p in P for pa in p['paras'])
UNIQ = len({w['h'].strip().lower() for p in P for pa in p['paras'] for s in pa for w in s['w']})
WORDS = sum(p['words'] for p in P)
Y0, Y1 = min(p['year'] for p in P), max(p['year'] for p in P)
U = f'{UNIQ // 1000 * 1000}+'          # 只往下取整，与封面一致
assert all(p.get('done') for p in P) and 2020 not in {p['year'] for p in P}

TITLE = f'专八阅读｜专八真题{N}篇逐句精读，用文章记住专八{U}重点词汇｜英语专业八级TEM-8 {Y0}—{Y1}｜英专必看'
ALTS = [f'【专八真题】{Y0}—{Y1}英语专业八级阅读{N}篇全收录｜逐句翻译+生词注释，读文章记住专八单词｜TEM8 英专',
        f'专八词汇别死背！{N}篇专八阅读真题帮你记住{U}重点单词｜英语专业八级TEM-8逐句精读 {Y0}—{Y1}']
TAGS = ['专八', '英语专业八级', '专八阅读', '专八真题', '专八词汇', '专八单词', 'TEM8', '英专', '英语精读', '逐句翻译']

CAT = '\n'.join(f"P{i} {p['year']} {p['passage']} {p['title']}" for i, p in enumerate(P, 1))
DESC = f"""【这是什么】{Y0}—{Y1} 年英语专业八级（专八 / TEM-8）阅读真题 {N} 篇全收录（每年 Passage One—Three，2020 年停考），一句一屏逐句精读，用真题文章记忆专八重点词汇：{N} 篇共 {WORDS} 词、{SENTS} 句，标注 {UNIQ} 个单词和短语。
【视频里有什么】逐句朗读 + 逐句中文翻译 + 生词短语编号注释（词性 + 中文释义），4K 大字版，手机上也看得清。
【适合谁】备考专八的英专生、想积累专八词汇 / 专八单词的同学、练英语精读和阅读理解的同学。
【怎么用】先听一遍原文，再暂停逐句看翻译和生词；每天 1—2 篇，读完 {N} 篇就把专八阅读里的重点词汇过了一遍。
【目录】
{CAT}"""
DYN = f'专八阅读真题{N}篇逐句精读来啦！{Y0}—{Y1}年英语专业八级阅读全收录，逐句朗读+逐句翻译+生词注释，用文章记住专八{U}重点词汇，英专备考收藏起来慢慢刷～'

errs = [f'{n} {len(t)} 字，超过 {TITLE_MAX}' for n, t in [('标题', TITLE)] + [(f'备选{i}', a) for i, a in enumerate(ALTS, 1)] if len(t) > TITLE_MAX]
if len(DESC) > DESC_MAX:
    errs.append(f'简介 {len(DESC)} 字，超过 {DESC_MAX}')
if len(DYN) > DYN_MAX:
    errs.append(f'粉丝动态 {len(DYN)} 字，超过 {DYN_MAX}')
if len(TAGS) > TAG_MAX or len(set(TAGS)) != len(TAGS) or any(len(t) > TAG_LEN for t in TAGS):
    errs.append('标签超出限制或重复')
for kw in ['专八', '专八阅读', '专八真题', '英语专业八级', '英专']:          # 搜索词必须都在推荐标题里
    if kw not in TITLE:
        errs.append(f'推荐标题缺搜索词：{kw}')
if errs:
    sys.exit('文案检查不通过：\n  ' + '\n  '.join(errs))

alts = '\n'.join(f'- 备选 {i}（{len(a)} 字）：{a}' for i, a in enumerate(ALTS, 1))
(HERE / 'B站上传文案.md').write_text(f"""# 专八阅读真题 {N} 篇 · B 站上传文案

由 `专八/封面/make_post.py` 从 `专八/data/vocab.json` 生成，数字与视频、封面一致；字数已按 B 站限制检查（标题 ≤ {TITLE_MAX} 字、简介 ≤ {DESC_MAX} 字、标签 ≤ {TAG_MAX} 个且每个 ≤ {TAG_LEN} 字、粉丝动态 ≤ {DYN_MAX} 字）。

## 标题

推荐（{len(TITLE)} 字）：{TITLE}

{alts}

## 标签（{len(TAGS)} 个，按搜索量排）

{'　'.join(TAGS)}

## 简介（{len(DESC)} 字）

{DESC}

## 粉丝动态（{len(DYN)} 字）

{DYN}

## 封面

`专八/封面/系列封面/专八阅读真题{N}篇_封面_16比9.jpg`、`专八阅读真题{N}篇_封面_4比3.jpg`
""", 'utf-8')
print(TITLE, len(TITLE))
for a in ALTS:
    print(a, len(a))
print(len(DESC), len(DYN))
