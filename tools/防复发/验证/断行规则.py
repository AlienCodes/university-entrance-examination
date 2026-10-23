"""双向验证：“不许拆开”的断行规则 zh_bind（踩坑 60、62、71；引擎与 layoutcheck 共用这一份，规则被改松两边会一起失效、什么也不报）。
每条用例都是盲审真查出过的断行：①证明“雷”是真的——不用规则时 jieba / 空格在词中间有断点；②规则打开后这一段整体不断开。
    python3 tools/防复发/验证/断行规则.py"""
import logging
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / '中考' / 'tools' / '画面核查'))
import jieba  # noqa: E402
import jieba.posseg as pseg  # noqa: E402
import zh_bind  # noqa: E402

jieba.setLogLevel(logging.WARNING)
bad = []


def raw_cuts(s):
    cuts, p = set(), 0
    for w, _ in pseg.lcut(s):
        p += len(w)
        cuts.add(p)
    return cuts


def covered(spans, a, b):
    return any(x <= a and b <= y for x, y in spans)


def zh_case(src, sent, word):
    a = sent.index(word)
    b = a + len(word)
    inside = {c for c in raw_cuts(sent) if a < c < b}
    ok = bool(inside) and covered(zh_bind.zh_spans(sent, jieba), a, b)
    print(f"  {'✅' if ok else '❌'} {src}：“{word}”（jieba 在词中断 {sorted(c - a for c in inside)}，规则{'绑住' if ok else '没绑住'}）")
    if not ok:
        bad.append(f'{src} {word}：' + ('jieba 已经不在词中断开，用例要换' if not inside else '规则没把它绑住'))


def en_case(src, sent, part):
    a = sent.index(part)
    b = a + len(part)
    ok = ' ' in part and covered(zh_bind.en_spans(sent), a, b)
    print(f"  {'✅' if ok else '❌'} {src}：“{part}”")
    if not ok:
        bad.append(f'{src} {part}：规则没把它绑住')


# ① 名词性复合词 ② 前缀 ③ 后缀 ④ 单字介词 ⑦ 数字范围（考研截图盲审、专八水墨）
zh_case('踩坑 60 复合词', '我们需要更多的服务人员来帮忙。', '服务人员')
zh_case('踩坑 60 前缀', '这是一种可持续的做法。', '可持续')
zh_case('踩坑 60 数词', '这一威胁正在扩大。', '这一威胁')
zh_case('踩坑 60 后缀', '孩子的父母们都来了。', '父母们')
zh_case('踩坑 60 介词', '这家机构以医院为中心展开工作。', '以医院')
zh_case('踩坑 71 数字范围', '莫扎特（1756—1791）是作曲家。', '1756—1791')
# ⑥ 补充词典（踩坑 62、71）：先证明不加载时 jieba 切错，再加载补充词典
pre = {w: raw_cuts(s) for w, s in [('网络中立', '他们讨论了网络中立法的影响。'), ('吧台', '他把杯子放在吧台上。')]}
for w in zh_bind.supp_words():
    jieba.add_word(w)
jieba._zb_dict = True
for w, s in [('网络中立', '他们讨论了网络中立法的影响。'), ('吧台', '他把杯子放在吧台上。')]:
    a = s.index(w)
    inside = {c for c in pre[w] | raw_cuts(s) if a < c < a + len(w)}
    ok = bool(inside) and covered(zh_bind.zh_spans(s, jieba), a, a + len(w))
    print(f"  {'✅' if ok else '❌'} 踩坑 62 补充词典：“{w}”（加载前后 jieba 在词中断 {sorted(c - a for c in inside)}，规则{'绑住' if ok else '没绑住'}）")
    if not ok:
        bad.append(f'补充词典 {w}：' + ('jieba 已不切错，用例要换' if not inside else '规则 ⑥ 没把它绑住'))
jieba._zb_dict = False
# 英文：专名、数字 + 名词、日期、数字 or 数字（考研 k、专八水墨 t05）
en_case('踩坑 60 专名', 'The opinion was written by Brett Kavanaugh last week.', 'Brett Kavanaugh')
en_case('踩坑 71 数字+名词', 'The study was done in 26 countries last year.', '26 countries')
en_case('踩坑 71 日期', 'It opened on June 3, 1853, in London.', 'June 3, 1853')
en_case('踩坑 60 数字范围', 'Drivers aged 18 or 21 may apply.', '18 or 21')
print('断行规则双向验证：' + ('全部通过' if not bad else f'{len(bad)} 处失败\n  ' + '\n  '.join(bad)))
sys.exit(1 if bad else 0)
