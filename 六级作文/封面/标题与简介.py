"""生成 六级作文/封面/B站标题与简介.md：数字、目录全部从数据现算（踩坑 70），长度超限就报错。
    python3 六级作文/封面/标题与简介.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'tools'))
import 作文规则  # noqa: E402

ES = [e for y in range(2015, 2100) if (REPO / f'六级/作文/{y}.json').exists() for e in json.loads((REPO / f'六级/作文/{y}.json').read_text('utf-8'))]
WC = [作文规则.counted(e) for e in ES]
SUM = json.loads((REPO / '六级作文/大字版/截图/汇总.json').read_text('utf-8'))
EPS = [(k, v['篇目']) for k, v in sorted(SUM.items()) if k.startswith('c') and '篇目' in v]
N, Y0, Y1 = len(ES), min(int(e['id'][1:5]) for e in ES), max(int(e['id'][1:5]) for e in ES)
EXAMS = sorted({e['id'][1:8] for e in ES}, reverse=True)
NEWEST = EXAMS[0].replace('-0', '年').replace('-', '年') + '月'
assert len(EPS) == N, (len(EPS), N)

title = f'【六级写作】{Y0}-{Y1}大学英语六级作文真题满分范文全{N}篇｜{NEWEST}已更新｜逐句精读+翻译｜六级作文模板句式背诵'
tags = ['英语六级', '六级作文', '六级写作', '大学英语六级', 'CET6', '六级真题', '满分范文', '英语作文', '六级备考', '英语学习']

cat = []
for i, (k, t) in enumerate(EPS, 1):
    m = re.match(r'(\d{4})年(\d+)月大学英语六级 (第\d套) 写作 Part I (.+)', t)
    cat.append(f'P{i} {m[1]}.{m[2]} {m[3]}｜{m[4]}' if m else f'P{i} {t}')

desc = f"""六级作文总是写不满、写不好？背了模板一下笔还是卡壳？
这套视频把 {Y0}—{Y1} 年大学英语六级写作真题全部做成了满分范文逐句精读：{len(EXAMS)} 次考试、{N} 篇，每篇 {min(WC)}—{max(WC)} 词（题目要求 150—200 词），一句一句读给你听、翻给你看。

📌 每一集都有
✅ 原题高清：先看清楚题目要求
✅ 逐句朗读：一句一屏，边听边看
✅ 逐句中文翻译：看得懂才记得住
✅ 高分词句标注：黄色是单词、粉色是短语，右边词汇栏给出词性和意思

📖 怎么看最有用（建议每篇 3 遍）
第 1 遍 看懂：先暂停在原题，自己想 1 分钟怎么写，再看范文怎么写
第 2 遍 跟读：每句跟着读，把标出来的词句抄进笔记本
第 3 遍 默写：关掉声音，只看中文说出 / 写出英文——默得出来，考场上就写得出来

📅 {N} 天打卡：每天 1 集，评论区打卡“第 N 天”，一起过六级！

🗂 全部 {N} 集目录
""" + '\n'.join(cat) + """

⭐ 觉得有用就点个收藏，考前一周拿出来再刷一遍；关注我，同系列还有六级阅读真题逐句精读。"""

assert len(title) <= 80, len(title)
assert len(tags) == 10 and all(len(t) <= 20 for t in tags)
assert len(desc) <= 2000, len(desc)
md = f"""# 六级写作 B站投稿文字（由 标题与简介.py 生成，数字现算）

## 标题（{len(title)} 字，上限 80）

{title}

## 标签（{len(tags)} 个，上限 10）

{'、'.join(tags)}

## 封面

`系列封面/六级写作真题满分范文{N}篇_封面_16比9.jpg`、`_4比3.jpg`（`系列封面.py 定稿 A`）；备选 B、C 的 16:9 在同一文件夹。

## 简介（{len(desc)} 字，上限 2000）

```
{desc}
```
"""
(HERE / 'B站标题与简介.md').write_text(md, 'utf-8')
print(len(title), len(desc))
