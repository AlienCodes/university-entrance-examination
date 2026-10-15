"""B 站投稿文案（40P 合集）：标题、简介、标签、40 个分 P 标题，数字全部由程序从定稿数据统计，并检查 B 站字数限制。

    /opt/ttsenv/bin/python 中考/tools/封面/make_post.py   → 中考/封面/B站投稿文案.md

标题的两个任务：①搜得到——尽量覆盖学生搜“中考英语”时会用的关键词（中考英语、阅读理解、真题、单词/词汇、精读、初中英语、
备考年份……），地区名放不进标题的放进简介、标签和分 P 标题；②想点进来——数字承诺（40 篇、N 个词汇）、合集、C/D 压轴篇、中英对照。
"""
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parents[1]
sys.path.insert(0, str(HERE))
from make_cover import stats  # noqa: E402

TITLE_MAX, DESC_MAX, TAG_MAX, TAG_LEN, DYN_MAX = 80, 2000, 10, 20, 233     # 粉丝动态（投稿时推给粉丝的那段话）最多 233 字
FIRST = ['北京', '山东', '济南', '烟台']      # 用户 2026-10-15：每年北京卷第一，山东卷第二，济南卷第三（烟台同为山东的市卷，接在济南后面）


def release_order(P):
    """合集顺序（B 站 40P、合集下载包共用）：先按年份从新到旧；同一年里北京、山东、济南、烟台在前，其余按原来的省份顺序（行政区划代码，
    省卷在前、市卷在后）；同一地区按原来的篇目顺序。"""
    idx = {p['id']: i for i, p in enumerate(P)}
    return sorted(P, key=lambda p: (-p['year'], FIRST.index(p['region']) if p['region'] in FIRST else len(FIRST), idx[p['id']]))


def file_name(p):
    """合集下载包里的文件名，用户 2026-10-15 指定格式“26北京 C篇 海洋变暖与南极海冰骤减”：两位年份+地区、篇目、题目，前面不加序号
    （包里的先后顺序按 release_order）。阅读B/C/D 写成 B/C/D篇；任务型阅读、七选五、没有字母编号的“阅读”照原样。"""
    part = re.sub(r'^阅读([A-E])$', r'\1篇', p['passage'])
    return f"{p['year'] % 100:02d}{p['region']} {part} {p.get('title') or ''}.mp4"


def main():
    P = json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']
    st = stats(P)
    y0, y1 = min(st['years']), max(st['years'])
    n, heads = st['n'], st['heads']
    # 用户 2026-10-15：开头先说最重要的——几年、几篇中考英语阅读真题、用来记忆中考重点单词；后面再放其他关键词
    title = (f'{y0}-{y1}年{n}篇中考英语阅读真题记忆中考重点单词｜逐句精读 背完{heads}个单词短语｜C/D篇中英对照｜'
             f'{n}P合集 {y1 + 1}中考复习 初中英语阅读理解')
    alt = f'中考英语阅读真题{n}篇逐句精读，背完{heads}个中考单词短语！{y0}-{y1}全国{len(st["regions"])}省市C/D篇｜中英对照｜{y1 + 1}中考必看'
    regions = '、'.join(st['regions'])
    by_year = '，'.join(f'{y} 年 {c} 篇' for y, c in sorted(st['years'].items(), reverse=True))
    order = release_order(P)
    papers = len({(p['year'], p['region']) for p in P})
    sents = sum(len(pa) for p in P for pa in p['paras'])
    kinds = collections.Counter(p.get('genre', '').split(' ')[0] for p in P)
    import subprocess
    sys.path.insert(0, str(C4 / 'tools'))
    import make_video as MV
    durs = [float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                                  str(C4 / '最终视频' / MV.video_name(p))], capture_output=True, text=True).stdout) for p in P]
    avg_min, total_min = round(sum(durs) / len(durs) / 60), round(sum(durs) / 60)
    plist = '\n'.join(f"P{k} {file_name(p)[:-4]}" for k, p in enumerate(order, 1))
    regions_kw = '、'.join(r + '中考英语' for r in st['regions'])
    # 用户 2026-10-15：简介要特别详细，尽量让需要的人都能搜到——写清是什么、视频里有什么、适合谁、怎么用、40P 目录（地区 + 题目）、题材、覆盖试卷和搜索词
    desc = f"""【这是什么】{y0}—{y1} 年 {n} 篇中考英语阅读真题（{len(st['regions'])} 个省市、{papers} 份试卷，阅读 C/D 压轴篇 {st['cd']} 篇），一句一屏逐句精读，专门用来记忆中考重点单词：看完 {n} 篇 = 过一遍 {heads} 个中考词汇（{st['single']} 个单词 + {st['phr']} 个短语），{n} 篇共 {st['words']} 词、{sents} 句。

【视频里有什么】
① 英文原句：要背的单词、短语都在句子里高亮并编号（单词紫色，短语黄底）；
② 生词栏：同屏右侧按编号给出词性和中文释义，在真题句子里记单词，记得牢；
③ 中文翻译：每一句都有准确的中文翻译，读懂每一句；
④ 男声朗读（四六级同款声音），句与句之间有停顿，方便跟读、磨耳朵；
⑤ 4K 高清，手机上也看得清。

【适合谁】初一、初二、初三学生；{y1 + 1} 中考备考、中考英语一轮/二轮复习、考前冲刺；想扩大词汇量、提高阅读理解速度的同学；老师课堂投屏、家长陪孩子背单词。

【怎么用最有效】
1. 每天 1 篇（每篇约 {avg_min} 分钟，{n} 篇共约 {total_min} 分钟），{n} 天刷完全部 {heads} 个词汇；
2. 第一遍看翻译、认生词；第二遍只看英文、跟着朗读读；第三遍遮住右侧生词栏，看编号回忆意思；
3. 记不住的词写下来，隔几天再看一遍对应的那一 P。

【分P目录】按年份从新到旧，每年北京、山东、济南、烟台在前，其余按省份：
{plist}

【文章题材】说明文 {kinds['说明文']} 篇、记叙文 {kinds['记叙文']} 篇、议论文 {kinds['议论文']} 篇，话题有人工智能、机器人、海洋、气候变化、环保、动物、中医、中国诗歌、贝聿铭、志愿服务、睡眠健康、情绪管理、人际交往等。

🔍 中考英语｜中考英语阅读理解｜中考英语真题｜中考英语单词｜中考词汇｜中考重点单词｜中考核心词汇｜中考英语复习｜中考英语冲刺｜中考阅读C篇｜中考阅读D篇｜初中英语阅读｜初三英语｜初二英语｜英语逐句精读｜中英对照｜背单词｜记单词｜英语跟读｜{y1}中考真题｜{y1 + 1}中考
🔍 {regions_kw}

觉得有用请点赞、投币、收藏支持一下！评论区说说你在哪个城市，{y1 + 1} 中考加油！"""
    # 粉丝动态（用户 2026-10-15）：粉丝刷到的第一句话——先说是什么、能得到什么，再给每天怎么刷，最后点名城市引评论，结尾带话题
    dyn = (f"🎉 {n}篇中考英语阅读真题逐句精读合集来啦！{y0}—{y1}年{len(st['regions'])}个省市真题，C/D压轴篇为主，"
           f"每句英文高亮生词+编号释义+中文翻译+男声朗读，看完就过一遍{heads}个中考词汇（{st['single']}单词+{st['phr']}短语）。"
           f"每天1篇、每篇约{avg_min}分钟，{n}天刷完！北京、山东、济南、深圳、成都……你的城市在不在里面？评论区告诉我～"
           f"{y1 + 1}中考的同学先收藏，备考一定用得上！#中考英语# #中考单词# #英语阅读理解#")
    tags = ['中考英语', '中考英语阅读', '中考阅读理解', '中考单词', '中考词汇', '中考真题', '初中英语', f'{y1 + 1}中考', '英语阅读精读', '背单词']
    parts = [f"P{k} {p['year']}{p['region']}中考英语 {p['passage']}｜{p.get('title') or ''}" for k, p in enumerate(release_order(P), 1)]
    errs = []
    for name, t in (('标题', title), ('备选标题', alt)):
        if len(t) > TITLE_MAX:
            errs.append(f'{name} {len(t)} 字，超过 {TITLE_MAX}')
    if len(dyn) > DYN_MAX:
        errs.append(f'粉丝动态 {len(dyn)} 字，超过 {DYN_MAX}')
    if len(desc) > DESC_MAX:
        errs.append(f'简介 {len(desc)} 字，超过 {DESC_MAX}')
    if len(tags) > TAG_MAX or any(len(t) > TAG_LEN for t in tags):
        errs.append('标签超出限制')
    errs += [f'分P标题超过 {TITLE_MAX} 字：{x}' for x in parts if len(x) > TITLE_MAX]
    if errs:
        raise SystemExit('\n'.join(errs))
    md = f"""# B 站投稿文案（{n}P 合集）

由 `中考/tools/封面/make_post.py` 从定稿数据生成，数字与视频一致；字数已按 B 站限制检查（标题 ≤ {TITLE_MAX} 字、简介 ≤ {DESC_MAX} 字、标签 ≤ {TAG_MAX} 个且每个 ≤ {TAG_LEN} 字）。

## 标题（{len(title)} 字）

{title}

备选（{len(alt)} 字）：{alt}

## 简介

{desc}

## 粉丝动态（{len(dyn)} 字，限 {DYN_MAX} 字）

{dyn}

## 标签（{len(tags)} 个）

{'　'.join(tags)}

## 分 P 标题（按 P1—P{n} 顺序上传，与合集下载包里的先后顺序一致）

""" + '\n'.join(parts) + '\n'
    out = C4 / '封面' / 'B站投稿文案.md'
    out.write_text(md, 'utf-8')
    print(title, len(title))
    print(alt, len(alt))
    print(out)


if __name__ == '__main__':
    main()
