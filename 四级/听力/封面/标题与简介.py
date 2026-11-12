"""生成 四级/听力/封面/B站标题与简介.md（2026-11-06）。
    python3 四级/听力/封面/标题与简介.py

老师要求：标题、简介、标签里不写死当前年份、不写死套数（以后每年加新听力，不改文字）；用“持续更新 / 最新真题 / 历年真题全收录”。
2026-11-09 老师：年份范围写成“最新—2018”（倒序），只许出现起点 2018，任何其他具体年份都报（防写死）。
程序保证：no_year_problems（2018 以外的四位年份 19xx/20xx、“2 套及以上”（“每天 1 套 / 做一套”是练法，不算）、“N 次考试”都报，全角数字也算），--自检 双向验证（放回年份 / 套数报，现在 0）。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

title = '【英语四级听力真题】最新—2018历年真题全收录（倒序）｜CET4听力原文逐句精讲+中文翻译+答案解析｜持续更新'
tags = ['英语四级', '四级听力', '大学英语四级', 'CET4', '四级真题', '听力真题', '四级听力原文', '四级听力解析', '四级听力精听', '四级备考']
desc = """英语四级听力真题，从最新一套倒序收录到 2018 年，每次考完都会持续更新最新真题。

每套听力都有：
✅ 原声真题音频，考场原速
✅ 听力原文逐句精讲，生词、短语逐个标注
✅ 每句配中文翻译
✅ 每道题的答案与解析

适合大学英语四级（CET4）备考：精听练耳、对照原文查漏、考前刷真题。

建议用法：先盲听做题 → 再看原文逐句精听 → 最后跟读模仿。

觉得有用记得点赞、收藏、关注，新一期真题出来第一时间更新！"""


ALLOWED_YEAR = '2018'  # 收录起点，固定不变；当前年份一律不写


def no_year_problems(text):
    t = text.translate({0xFF10 + i: 0x30 + i for i in range(10)})
    out = ['年份 ' + m.group() for m in re.finditer(r'(?<!\d)(19|20)\d\d(?!\d)', t) if m.group() != ALLOWED_YEAR]
    out += ['套数 ' + m.group() for m in re.finditer(r'(?<!\d)(?:[2-9]|[1-9]\d+)\s*套|(?:[二两三四五六七八九十百]|一[十百])[一二三四五六七八九十百]*\s*套', t)]
    out += ['考试次数 ' + m.group() for m in re.finditer(r'\d+\s*次考试', t)]
    return out


def selftest():
    bad = []
    base = title + desc + ''.join(tags)
    if no_year_problems(base):
        bad.append(f'现在的文字报出：{no_year_problems(base)}')
    for ok in ('最新—2018', '2018至今（倒序）', '收录到 2018 年'):
        if no_year_problems(base + ok):
            bad.append(f'{ok!r} 被误报')
    if '2018' not in title:
        bad.append('标题里没有起点 2018')
    for mine in ('2026', '最新—2026', '2018—2025', '2026年6月已更新', '2018-2026', '全35套', '全 ３５ 套', '16 次考试', '真题三十五套', '２０２５'):
        if not no_year_problems(base + mine):
            bad.append(f'雷 {mine!r} 没报出')
    return bad


if __name__ == '__main__':
    if sys.argv[1:] == ['--自检']:
        b = selftest()
        print('\n'.join(b) or '自检通过：其他年份 / 套数 / 考试次数 10 颗雷全部报出，“最新—2018”等 3 种写法不报，现在的文字 0 处')
        sys.exit(1 if b else 0)
    p = no_year_problems(title + '\n' + desc + '\n' + ' '.join(tags))
    assert not p, p
    assert len(title) <= 80, len(title)
    assert '最新—2018' in title and '2018' in desc and '原文' in title and '原文' in desc and '中文翻译' in desc and '生词' in desc
    assert len(tags) == 10 and all(len(t) <= 20 for t in tags)
    assert len(desc) <= 2000, len(desc)
    (HERE / 'B站标题与简介.md').write_text(f"""# 四级听力 B站投稿文字（由 标题与简介.py 生成；年份只写起点 2018（最新—2018 倒序），不写死当前年份和套数）

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
