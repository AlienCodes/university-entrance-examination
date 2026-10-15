"""B 站投稿文案（40P 合集）：标题、简介、标签、40 个分 P 标题，数字全部由程序从定稿数据统计，并检查 B 站字数限制。

    /opt/ttsenv/bin/python 中考/tools/封面/make_post.py   → 中考/封面/B站投稿文案.md

标题的两个任务：①搜得到——尽量覆盖学生搜“中考英语”时会用的关键词（中考英语、阅读理解、真题、单词/词汇、精读、初中英语、
备考年份……），地区名放不进标题的放进简介、标签和分 P 标题；②想点进来——数字承诺（40 篇、N 个词汇）、合集、C/D 压轴篇、中英对照。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parents[1]
sys.path.insert(0, str(HERE))
from make_cover import stats  # noqa: E402

TITLE_MAX, DESC_MAX, TAG_MAX, TAG_LEN = 80, 2000, 10, 20
FIRST = ['北京', '山东', '济南', '烟台']      # 用户 2026-10-15：每年北京卷第一，山东卷第二，济南卷第三（烟台同为山东的市卷，接在济南后面）


def release_order(P):
    """合集顺序（B 站 40P、合集下载包共用）：先按年份从新到旧；同一年里北京、山东、济南、烟台在前，其余按原来的省份顺序（行政区划代码，
    省卷在前、市卷在后）；同一地区按原来的篇目顺序。"""
    idx = {p['id']: i for i, p in enumerate(P)}
    return sorted(P, key=lambda p: (-p['year'], FIRST.index(p['region']) if p['region'] in FIRST else len(FIRST), idx[p['id']]))


def file_name(p):
    """合集下载包里的文件名：年份地区中考英语 + 篇目 + 题目（用户 2026-10-15：文件名前面不加序号；包里的先后顺序按 release_order）。"""
    return f"{p['year']}{p['region']}中考英语 {p['passage']} {p.get('title') or ''}.mp4"


def main():
    P = json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']
    st = stats(P)
    y0, y1 = min(st['years']), max(st['years'])
    n, heads = st['n'], st['heads']
    title = (f'【{n}P合集】{y0}-{y1}中考英语阅读真题逐句精读｜背完{heads}个中考单词短语｜C/D篇+中英对照｜'
             f'备战{y1 + 1}中考复习 初中英语阅读理解')
    alt = f'中考英语阅读真题{n}篇逐句精读，背完{heads}个中考单词短语！{y0}-{y1}全国{len(st["regions"])}省市C/D篇｜中英对照｜{y1 + 1}中考必看'
    regions = '、'.join(st['regions'])
    by_year = '，'.join(f'{y} 年 {c} 篇' for y, c in sorted(st['years'].items(), reverse=True))
    desc = f"""{n} 篇中考英语阅读真题逐句精读，专门用来背中考单词：一句一屏，英文朗读 + 中文翻译 + 生词编号注释，看完 {n} 篇 = 过一遍 {heads} 个中考词汇（{st['single']} 个单词 + {st['phr']} 个短语）。
📌 真题来源：{len(st['regions'])} 个省市的 {y0}—{y1} 年中考英语试卷（{by_year}），以阅读 C/D 压轴篇为主（{st['cd']} 篇）。
📌 覆盖地区：{regions}——找找你所在城市的真题（分 P 标题里有地区和篇目）。
📌 怎么用：每天 1 篇，先听一遍、对照翻译记生词，再跟着朗读读一遍；{n} 天背完全部 {heads} 个词汇。
📌 视频：4K 高清、男声朗读、每句之间停顿方便跟读；每个生词都在句子里高亮并编号，右栏给出词性和释义。
适合：初三 / 初二学生中考英语复习，{y1 + 1} 中考备考，中考英语阅读理解、中考英语单词、中考词汇、初中英语阅读、英语精读。
🔍 {'、'.join(r + '中考英语' for r in st['regions'])}"""
    tags = ['中考英语', '中考英语阅读', '中考阅读理解', '中考单词', '中考词汇', '中考真题', '初中英语', f'{y1 + 1}中考', '英语阅读精读', '背单词']
    parts = [f"P{k} {p['year']}{p['region']}中考英语 {p['passage']}｜{p.get('title') or ''}" for k, p in enumerate(release_order(P), 1)]
    errs = []
    for name, t in (('标题', title), ('备选标题', alt)):
        if len(t) > TITLE_MAX:
            errs.append(f'{name} {len(t)} 字，超过 {TITLE_MAX}')
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
