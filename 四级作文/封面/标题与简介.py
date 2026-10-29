"""生成 四级作文/封面/B站标题与简介.md：数字、目录全部从数据现算（踩坑 70），长度超限就报错。
    python3 四级作文/封面/标题与简介.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'tools'))
import 作文规则  # noqa: E402

ES = [e for y in range(2015, 2100) if (REPO / f'四级/作文/{y}.json').exists() for e in json.loads((REPO / f'四级/作文/{y}.json').read_text('utf-8'))]
WC = [作文规则.counted(e) for e in ES]
LIM = {tuple(map(int, re.findall(r'\d+', e['limit']))) for e in ES}      # 题目原话的字数要求（at least 120 … not more than 180）
assert len(LIM) == 1, LIM
LO, HI = LIM.pop()
EPS = json.loads((REPO / '四级作文/data/vocab.json').read_text('utf-8'))['passages']     # c01 = 最新一套，视频顺序
N, Y0, Y1 = len(ES), min(int(e['id'][1:5]) for e in ES), max(int(e['id'][1:5]) for e in ES)
EXAMS = sorted({e['id'][1:8] for e in ES}, reverse=True)
NEWEST = f'{int(EXAMS[0][:4])}年{int(EXAMS[0][5:])}月'
assert len(EPS) == N and {p['src'] for p in EPS} == {e['id'] for e in ES}, (len(EPS), N)

title = f'【四级真题范文】彻底搞定四级写作｜{Y0}-{Y1}大学英语四级作文真题全{N}篇｜{NEWEST}已更新｜CET4满分范文逐句精读｜四级作文模板｜12月四级必看'
tags = ['四级作文', '英语四级', '四级写作', '四级真题', '四级范文', '大学英语四级', 'CET4', '四级作文模板', f'{Y1}年12月四级', '四级备考']
# 协调会话 2026-10-29 定的标题与标签：现算结果必须逐字相同，不同就报错（数据一变先改这里）
assert title == '【四级真题范文】彻底搞定四级写作｜2021-2026大学英语四级作文真题全32篇｜2026年6月已更新｜CET4满分范文逐句精读｜四级作文模板｜12月四级必看', title
assert tags == ['四级作文', '英语四级', '四级写作', '四级真题', '四级范文', '大学英语四级', 'CET4', '四级作文模板', '2026年12月四级', '四级备考'], tags

cat = []
for i, p in enumerate(EPS, 1):
    y, m, k = p['src'][1:].split('-')
    cat.append(f'P{i} {y}.{int(m)} 第{k}套｜{p["title"]}')

desc = f"""四级作文不知道怎么开头、写不满 {LO} 词？背了模板一下笔还是卡壳？
这套视频把 {Y0}—{Y1} 年大学英语四级写作真题全部做成了范文逐句精读：{len(EXAMS)} 次考试、{N} 篇，每篇 {min(WC)}—{max(WC)} 词（题目要求 {LO}—{HI} 词），一句一句读给你听、翻给你看。

📌 每一集都有
✅ 原题 + 题目中文翻译：先看清楚题目要求
✅ 逐句朗读：一句一屏，边听边看
✅ 逐句中文翻译：看得懂才记得住
✅ 好词好句标注：绿色是单词、红色是短语，右边词汇栏给出词性和意思

📖 怎么看最有用（建议每篇 3 遍）
第 1 遍 看懂：先暂停在原题，自己想 1 分钟怎么写，再看范文怎么写
第 2 遍 跟读：每句跟着读，把标出来的词句抄进笔记本
第 3 遍 默写：关掉声音，只看中文说出 / 写出英文——默得出来，考场上就写得出来

📅 {N} 天打卡：每天 1 集，评论区打卡“第 N 天”，一起过四级！

🗂 全部 {N} 集目录
""" + '\n'.join(cat) + """

⭐ 觉得有用就点个收藏，考前一周拿出来再刷一遍；关注我，同系列还有四级阅读真题逐句精读。"""

assert len(title) <= 80, len(title)
assert len(tags) == 10 and all(len(t) <= 20 for t in tags)
assert len(desc) <= 2000, len(desc)
md = f"""# 四级写作 B站投稿文字（由 标题与简介.py 生成，数字现算）

## 标题（{len(title)} 字，上限 80）

{title}

## 标签（{len(tags)} 个，上限 10）

{'、'.join(tags)}

## 封面

`系列封面/四级写作真题范文{N}篇_封面_16比9.jpg`、`_4比3.jpg`（`系列封面.py 定稿 A`）；B、C 的 16:9 作备选。

## 简介（{len(desc)} 字，上限 2000）

```
{desc}
```
"""
(HERE / 'B站标题与简介.md').write_text(md, 'utf-8')
print(len(title), len(desc))
