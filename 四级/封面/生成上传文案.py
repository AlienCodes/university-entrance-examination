"""B 站上传文案：合集标题、简介、标签，以及 60 个视频（分P）的标题。标题长度按 B 站上限 80 字检查。"""
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
C4 = HERE.parent
d = json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']
d = sorted(d, key=lambda p: p['id'], reverse=True)                    # 2026 → 2021
SENTS = sum(len(para) for p in d for para in p['paras'])
UNIQ = len({w['h'].lower() for p in d for para in p['paras'] for s in para for w in s['w']})

def short(p):            # “2026年6月 第3套” → “2026年6月第3套”
    return p['paper'].replace(' ', '')

def video_title(p):
    t = f"【四级阅读真题】{short(p)} {p['passage']}｜{p['title']}｜逐句精读 中英对照 生词全标注 CET4仔细阅读"
    if len(t) > 80:
        t = f"【四级阅读真题】{short(p)} {p['passage']}｜{p['title']}｜逐句精读 生词全标注"
    assert len(t) <= 80, t
    return t

SERIES = f"【60篇】四级阅读真题逐句精读｜2021-2026 CET4仔细阅读 Passage One+Two｜中英对照 生词全标注 记住四级重点单词｜4K"
assert len(SERIES) <= 80, len(SERIES)
TAGS = ['英语四级', '四级阅读', '四级真题', '大学英语四级', 'CET4', '四级词汇', '仔细阅读', '英语阅读', '逐句精读', '四级备考']
assert len(TAGS) == 10 and all(len(t) <= 20 for t in TAGS)

DESC = f"""60篇大学英语四级（CET-4）仔细阅读真题，逐句精读，配英文朗读、中文翻译和生词注释。2021年6月到2026年6月的四级真题，Passage One 和 Passage Two 各30篇。

【每个视频里有什么】
1. 真题原文一句一屏，男声逐句朗读，适合跟读、听读、磨耳朵
2. 每句都有中文翻译，中英对照，读懂每一句
3. 句子里的生词、词组全部标出，带编号、词性和释义，60篇共 {UNIQ}+ 个词汇，{SENTS} 句
4. 4K 高清，手机上也看得清

【怎么用效果最好】
先只看英文，试着自己理解 → 听朗读跟读 → 看翻译核对 → 把标出的生词记下来。一篇大约 2 到 3 分钟，每天几篇，坚持刷完 60 篇，四级阅读里反复出现的重点单词都会见过很多遍。

【适合谁】
准备大学英语四级（CET4）考试的同学；想提高英语阅读、扩充四级词汇、练习英语听力和朗读的同学。也可以作为六级、专升本、考研英语的基础阅读练习。

篇目按时间从新到旧排列，2026年6月第1、2、3套在最前。

关键词：英语四级 四级阅读 四级真题 四级阅读真题 大学英语四级 CET4 CET-4 仔细阅读 Section C 篇章阅读 阅读理解 Passage One Passage Two 逐句精读 逐句翻译 中英对照 四级单词 四级词汇 背单词 四级备考 英语阅读 英语精读 英语朗读 英语听力 跟读 2026年6月四级 2025年12月四级 2025年6月四级 2024年四级 2023年四级 2022年四级 2021年四级"""
assert len(DESC) <= 2000, len(DESC)

lines = ['# B 站上传文案（四级阅读真题 60 篇）', '',
         f'## 合集 / 分P 视频的总标题（{len(SERIES)} 字，上限 80）', '', '```', SERIES, '```', '',
         '## 标签（10 个，B 站上限 10 个）', '', '```', ' '.join(TAGS), '```', '',
         f'## 简介（{len(DESC)} 字，上限 2000）', '', '```', DESC, '```', '',
         '## 60 个视频的标题（单独上传时用作视频标题；分P 上传时用作每一P的标题）', '',
         '每个都带年份、月份、第几套、第几篇和中文题目，方便别人按“2026年6月四级第3套”这样搜到。', '']
lines += [f'{i}. `{video_title(p)}`（{len(video_title(p))} 字）' for i, p in enumerate(d, 1)]
lines += ['', '## 篇目清单（可以放在评论区置顶）', '']
lines += [f'P{i} {short(p)} {p["passage"]} {p["title"]}' for i, p in enumerate(d, 1)]
(HERE / 'B站上传文案.md').write_text('\n'.join(lines) + '\n', 'utf-8')
print('series', len(SERIES), 'desc', len(DESC), 'max video title', max(len(video_title(p)) for p in d))
print(video_title(d[0])); print(video_title(d[-1]))
