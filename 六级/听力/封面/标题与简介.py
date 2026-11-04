"""生成 六级/听力/封面/B站标题与简介.md：套数、年份、目录全部从 六级/听力/<yyyymm-n>/ 现算（踩坑 70），长度超限就报错。
    python3 六级/听力/封面/标题与简介.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SETS = sorted((d.name for d in (REPO / '六级/听力').iterdir() if re.fullmatch(r'\d{6}-\d', d.name)), reverse=True)
assert sorted(SETS) == sorted((REPO / '.github/cet6-listening-all.txt').read_text('utf-8').split())
N = len(SETS)
EXAMS = sorted({s[:6] for s in SETS})
Y0, M0, Y1, M1 = int(EXAMS[0][:4]), int(EXAMS[0][4:]), int(EXAMS[-1][:4]), int(EXAMS[-1][4:])
SPAN = f'{Y0}.{M0}—{Y1}.{M1:02d}'

title = f'【六级听力真题】{Y0}-{Y1}大学英语六级听力真题全{N}套｜{Y1}年{M1}月已更新｜考试原音+题目同步+答案｜彻底搞定六级听力'
tags = ['英语六级', '六级听力', '大学英语六级', 'CET6', '六级真题', '听力真题', '英语听力', '六级备考', '四六级', '英语学习']
cat = [f'P{i} {s[:4]}年{int(s[4:6])}月 第{s[-1]}套' for i, s in enumerate(SETS, 1)]

desc = f"""六级听力总是听不清、跟不上、选不对？
这里是 {SPAN} 大学英语六级听力全部真题：{len(EXAMS)} 次考试、{N} 套，每套都做成了“视频版真题考试”，打开就能像在考场一样完整做一遍。

📌 每一套都有
✅ 考试原音原速：真题录音原样播放，不加速、不剪辑
✅ 题目选项同步：念到哪一题，屏幕上就是哪一题的选项
✅ 留出作答时间：每题念完有时间想、有时间选
✅ 答案一目了然：做完马上对答案

📖 怎么练最有用（建议每套 3 遍）
第 1 遍 实战：准备好答题卡，不暂停、不回放，完整做一套
第 2 遍 对答案：错的题回到原音再听，找出是哪个词没听出来
第 3 遍 精听：把错题那一段反复听，跟读到能完整复述

📅 {N} 天打卡：每天 1 套，评论区打卡“第 N 天”，一起过六级！

🗂 全部 {N} 套目录（新的在前）
""" + '\n'.join(cat) + """

⭐ 觉得有用就点个收藏，考前一周拿出来再刷一遍；关注我，同系列还有六级阅读真题逐句精读、六级写作真题满分范文。"""

assert len(title) <= 80, len(title)
assert len(tags) == 10 and all(len(t) <= 20 for t in tags)
assert len(desc) <= 2000, len(desc)
assert not re.search(r'4K|精读视频|\d+\s*/\s*\d+', title)
md = f"""# 六级听力 B站投稿文字（由 标题与简介.py 生成，数字现算）

## 标题（{len(title)} 字，上限 80）

{title}

## 标签（{len(tags)} 个，上限 10）

{'、'.join(tags)}

## 封面

`系列封面/六级听力真题{N}套_封面_16比9.jpg`、`_4比3.jpg`（`系列封面.py 定稿 A`）；B、C 的 16:9 作备选。

## 简介（{len(desc)} 字，上限 2000）

```
{desc}
```
"""
(HERE / 'B站标题与简介.md').write_text(md, 'utf-8')
print(len(title), len(desc))
