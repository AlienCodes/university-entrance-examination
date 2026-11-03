"""各项目共用的文字规则（只写在这一处，踩坑 30、41、60a、73）。

word_count：片头“全文 N 词”。按空白、破折号（— –）、省略号切分，只数含英文字母或数字的片段：
  中文注释“(防水布)”不算词（踩坑 30，中考）；villages—just 算两个词（踩坑 41，中考 / 考研）。
  专八、四级、六级的提取程序当年用的是 len(text.split())，中文注释算成一个词、破折号连着的两个词算一个
  （专八 t09 片头 1079 词，应为 1094；防复发审计 2026-10-23 查出）。build_vocab 一律从定稿句子用这里重算，不用提取时存的数。"""
import re


def word_count(text):
    return len([w for w in re.split(r'[\s—–…]+', text) if re.search(r'[A-Za-z0-9]', w)])



# 已人工核过的旧标注（2026-11-03 加检查时全项目扫出 4 处）：并列的 so…, so…, that 两个 so 都可以作前一段，保留；
# 四级 c01 第 12 句 build…up 落在远处的 building something（应为 building it up），视频已发布，不追溯，只登记（只许减少）。
SLOT_REVIEWED = {
    ('so…that', 'I was feeling a deep, strong lo'[:30]),
    ('so…that', 'National service opportunities'[:30]),
    ('so…that', 'At last, the problem became so'[:30]),
    ('build…up', 'There are cognitive (认知的) bene'[:30]),
}


def slot_gap_problem(entry, sent, spans, find):
    """带空位的短语（have…in order）：前一段高亮落到了远处别的分句里的词，而空位里还有离后一段更近的同一个词（形）。
    高考续写精读 x05：“She had prepared lots of snacks, while my job was to have the backyard in order.”
    have…in order 的 have 落到了前一分句的 had，正确的是后面的 have（踩坑 103）。
    find = 该项目 ann_lib 的 find；做法：从前一段之后重新找一次，如果找到的落点与原来同一个结尾、开头更靠后，就是落远了。返回问题描述或 None。"""
    if entry.get('t') != 'phr' or '…' not in entry.get('h', '') or not spans or len(spans) < 2:
        return None
    sp = sorted(spans)
    off = sp[0][1]
    if not re.search(r'[,;:—–]', sent[off:sp[-1][0]]):      # 空位不跨分句（using the “fair use” clause as：远处的 using 才对），不管
        return None
    if (entry['h'], sent[:30]) in SLOT_REVIEWED:
        return None
    sub = find(entry, sent[off:], [])
    if sub and len(sub) >= 2 and max(b for _, b in sub) + off == sp[-1][1]:
        a0 = min(a for a, _ in sub) + off
        return (f'短语 {entry["h"]} 的前一段落到了远处的“{sent[sp[0][0]:sp[0][1]]}”，'
                f'后面还有更近的“{sent[a0:a0 + (sorted(sub)[0][1] - sorted(sub)[0][0])]}”：用 {{原文词形}} 指定同一分句里的那一处')
    return None
