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
SPAN = f'{Y1}—{Y0}'                        # 2026 在前、不写月份（老师 2026-11-04）

title = f'【英语六级听力真题+原文解析】{Y1}-{Y0}大学英语六级听力真题全{N}套｜CET6听力原文逐句精讲+中文翻译+答案｜{Y1}年{M1}月已更新｜六级听力精听'   # 总协调定（2026-11-05）
tags = ['英语六级', '六级听力', '大学英语六级', 'CET6', '六级真题', '听力真题', '六级听力原文', '六级听力解析', '六级听力精听', '六级备考']
cat = [f'P{i} {s[:4]}年{int(s[4:6])}月 第{s[-1]}套' for i, s in enumerate(SETS, 1)]

desc = f"""六级听力总是听不清、跟不上、选不对？
这里是 {SPAN} 年大学英语六级听力全部真题：{len(EXAMS)} 次考试、{N} 套。每套都有两种视频：“视频版真题考试”先完整做一遍，“听力原文解析”再逐句精读，把每一句都听懂。

📌 视频版真题考试
✅ 考试原音原速：真题录音原样播放，不加速、不剪辑
✅ 题目选项同步：念到哪一题，屏幕上就是哪一题的选项
✅ 留出作答时间：每题念完有时间想、有时间选
✅ 答案一目了然：做完马上对答案

📌 听力原文解析（原文精读）
✅ 原文逐句：考试原音一句一句放，屏幕上就是这一句的英文原文
✅ 中文翻译：每一句下面都有中文意思
✅ 生词标注：每一句的生词、短语都标出来，配中文释义

📖 怎么练最有用（建议每套 3 遍）
第 1 遍 实战：准备好答题卡，不暂停、不回放，完整做一套
第 2 遍 对答案：错的题回到原音再听，找出是哪个词没听出来
第 3 遍 精听：看“听力原文解析”，跟着原文逐句听懂、跟读到能完整复述

📅 {N} 天打卡：每天 1 套，评论区打卡“第 N 天”，一起过六级！

🗂 全部 {N} 套目录（新的在前）
""" + '\n'.join(cat) + """

⭐ 觉得有用就点个收藏，考前一周拿出来再刷一遍；关注我，同系列还有六级阅读真题逐句精读、六级写作真题满分范文。"""

assert len(title) <= 80, len(title)
assert '原文解析' in title and '原文解析' in desc and '中文翻译' in desc and '生词' in desc   # 两种视频都要写明（老师 2026-11-05）
assert len(tags) == 10 and all(len(t) <= 20 for t in tags)
assert len(desc) <= 2000, len(desc)
assert not re.search(r'4K|精读视频|\d+\s*/\s*\d+', title)
md = f"""# 六级听力 B站投稿文字（由 标题与简介.py 生成，数字现算）

## 标题（{len(title)} 字，上限 80）

{title}

## 标签（{len(tags)} 个，上限 10）

{'、'.join(tags)}

## 封面

`系列封面/六级听力真题与原文解析{N}套_封面_16比9.jpg`、`_4比3.jpg`（`系列封面.py 定稿`）；另两个方向的 16:9 作备选，只有真题的旧版留作 `…_旧版_仅真题_*.jpg`。

## 简介（{len(desc)} 字，上限 2000）

```
{desc}
```
"""
(HERE / 'B站标题与简介.md').write_text(md, 'utf-8')
print(len(title), len(desc))
