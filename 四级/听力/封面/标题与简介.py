"""生成 四级/听力/封面/B站标题与简介.md（2026-11-06）。
    python3 四级/听力/封面/标题与简介.py

老师要求：标题、简介、标签里都不出现任何年份、不写死套数（以后每年加新听力，不改文字）；用“持续更新 / 最新真题 / 历年真题全收录”。
程序保证：no_year_problems（四位年份 19xx/20xx、“2 套及以上”（“每天 1 套 / 做一套”是练法，不算）、“N 次考试”都报，全角数字也算），--自检 双向验证（放回年份 / 套数报，现在 0）。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

title = '【英语四级听力真题+原文解析】大学英语四级听力历年真题全收录｜CET4听力原文逐句精讲+中文翻译+答案｜最新真题持续更新｜四级听力精听'
tags = ['英语四级', '四级听力', '大学英语四级', 'CET4', '四级真题', '听力真题', '四级听力原文', '四级听力解析', '四级听力精听', '四级备考']
desc = """四级听力总是听不清、跟不上、选不对？
这里是大学英语四级听力历年真题全收录，每出一次新考试就更新最新一期。每套都有两种视频：“视频版真题考试”先完整做一遍，“听力原文解析”再逐句精读，把每一句都听懂。

📌 视频版真题考试
✅ 考试原音原速：真题录音原样播放，不加速、不剪辑
✅ 题目选项同步：念到哪一题，屏幕上就是哪一题的选项
✅ 留出作答时间：每题念完有时间想、有时间选
✅ 答案一目了然：做完马上对答案

📌 听力原文解析（原文精读）
✅ 原文逐句：考试原音一句一句放，屏幕上就是这一句的英文原文
✅ 中文翻译：每一句下面都有中文意思
✅ 答案精讲：答案出在哪一句、为什么选它，讲清楚
✅ 生词标注：每一句的生词、短语都标出来，配中文释义

📖 怎么练最有用（建议每套 3 遍）
第 1 遍 实战：准备好答题卡，不暂停、不回放，完整做一套
第 2 遍 对答案：错的题回到原音再听，找出是哪个词没听出来
第 3 遍 精听：看“听力原文解析”，跟着原文逐句听懂、跟读到能完整复述

📅 每天 1 套，评论区打卡“第 N 天”，一起过四级！
🗂 目录在分 P 列表里，新的在前；新一期真题出来就加进来。

⭐ 觉得有用就点个收藏，考前一周拿出来再刷一遍；关注朋克英语，同系列还有四级阅读真题逐句精读、四级写作真题范文。"""


def no_year_problems(text):
    t = text.translate({0xFF10 + i: 0x30 + i for i in range(10)})
    out = ['年份 ' + m.group() for m in re.finditer(r'(?<!\d)(19|20)\d\d(?!\d)', t)]
    out += ['套数 ' + m.group() for m in re.finditer(r'(?<!\d)(?:[2-9]|[1-9]\d+)\s*套|(?:[二两三四五六七八九十百]|一[十百])[一二三四五六七八九十百]*\s*套', t)]
    out += ['考试次数 ' + m.group() for m in re.finditer(r'\d+\s*次考试', t)]
    return out


def selftest():
    bad = []
    base = title + desc + ''.join(tags)
    if no_year_problems(base):
        bad.append(f'现在的文字报出：{no_year_problems(base)}')
    for mine in ('2026年6月已更新', '2018-2026', '全35套', '全 ３５ 套', '16 次考试', '真题三十五套', '２０２５'):
        if not no_year_problems(base + mine):
            bad.append(f'雷 {mine!r} 没报出')
    return bad


if __name__ == '__main__':
    if sys.argv[1:] == ['--自检']:
        b = selftest()
        print('\n'.join(b) or '自检通过：年份 / 套数 / 考试次数 7 颗雷全部报出，现在的文字 0 处')
        sys.exit(1 if b else 0)
    p = no_year_problems(title + '\n' + desc + '\n' + ' '.join(tags))
    assert not p, p
    assert len(title) <= 80, len(title)
    assert '原文解析' in title and '原文解析' in desc and '中文翻译' in desc and '生词' in desc
    assert len(tags) == 10 and all(len(t) <= 20 for t in tags)
    assert len(desc) <= 2000, len(desc)
    (HERE / 'B站标题与简介.md').write_text(f"""# 四级听力 B站投稿文字（由 标题与简介.py 生成；不出现年份、不写死套数）

## 标题（{len(title)} 字，上限 80）

{title}

## 标签（{len(tags)} 个，上限 10）

{'、'.join(tags)}

## 封面

`系列封面/四级听力真题与原文解析_封面_16比9.jpg`、`_4比3.jpg`（`系列封面.py 定稿 A`，四级写作同风格：米白纸面、红绿大字、真实画面、“持续更新”圆章）；B（深绿居中）、C（黄黑撞色）的 16:9 作备选。

## 简介（{len(desc)} 字，上限 2000）

```
{desc}
```
""", 'utf-8')
    print(len(title), len(desc))
