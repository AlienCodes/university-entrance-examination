"""排版引擎（专八/tools/make_video.py）与排版检查（layoutcheck.py）共用的“不许拆开”的片段（考研截图盲审 2026-10-21）。

引擎用它决定哪里不断行，检查程序用它逐屏量实际断行位置：规则只写在这一处，两边不会不一致。

zh_spans(s, jieba)：中文里不许断开的片段 [(起, 止)]
  ① 名词性复合词：相邻两个词都是 2 个字以上、后一个是名词性（n、vn、nz、ns、nt、nr、ng、an、j），前一个是名词性 / 动词 / 形容词 / 区别词，
     合起来不超过 4 个字（服务人员、会员资格、保障措施、再生农业、非营利组织、联邦通信委员会、千禧技术奖）；
  ② 前缀词、单字数词与后面的词：不、可、非、最、这一、每一、这些、一、两……（不稳定、可持续、这一威胁、最富裕）；
  ③ 单字后缀与前面的词：们、型、性、化、者、家、式、级、类、了（父母们、气候友好型、进入了）；“得多”“得很”与前面的词；
  ④ 单字介词、连词与后面不超过 3 个字的词：以、与、和、把、被、在、为、对……（以 / 医院为中心、与 / 空间科学）；
  ⑤ 数字与后面不超过 3 个字的词（20世纪90 / 年代）。
  一串连起来的片段超过 5 个字就不再往上接（防止一大块不断行、上一行空出一截）。
  ⑥ 分词补充.txt 里的词（jieba 切错的词：吧台、名目、而非……）出现在哪里都整体不断开——只在已加载补充词典时（专八 / 六级引擎、layoutcheck z8；中考不加载，结果不变）。
     不靠改 jieba 词频（踩坑 62：suggest_freq 强制成词仍敌不过上下文里更强的词，“在吧台上”照样切成 在 / 吧 / 台上，还会把“然而非常”切成 然 / 而非 / 常）。
en_spans(t)：英文里不许断开的片段 [(起, 止)]
  ① 专名：连续 2—4 个首字母大写的词（去掉开头的 The、When、In 这类普通词），总长不超过 32 个字符
     （Brett Kavanaugh、West Virginia、San Francisco、Apple TV.、California Attorney General）；
  ② 数字 or/to/and 数字（18 or 21）；
  ③ 数字与后面的小写词（in 26 / countries、the 10 / highest：专八书卷水墨截图盲审），日期“June 3, 1853”整体不断开（t05 “on June 3, / 1853.”）；
  ④ 句首的长专名（只隔着 The、A 这类词、22 个字符以上）不绑：一行放不下“The + 专名”时 The 会单独占一行（水墨 t07 “The / Australian Beverages Council,”）。
"""
import re

NOUN = {'n', 'vn', 'nz', 'ns', 'nt', 'nr', 'ng', 'an', 'j', 'nrt', 'nrfg', 'nw'}
HEAD = NOUN | {'v', 'a', 'b', 'vd', 'ad'}
PREFIX = {'不', '可', '非', '这', '那', '每', '各', '该', '某', '此', '这一', '那一', '每一', '同一', '这些', '那些', '这个', '那个', '这种', '那种',
          '这项', '这场', '这位', '这次', '这样', '那样', '最'}      # 最：与后面的形容词（专八水墨复审 t07 “最 / 富裕”）
SUFFIX1 = set('们型性化者家式级类了')      # 了：动态助词跟前面的动词（专八水墨复审 t06 “进入 / 了死母鸡期”）
NUM1 = set('一二两三四五六七八九十几半')      # 单独成词的数词与后面的词（这 / 一 / 威胁：jieba 有时切成三段）
TAIL = {'得多', '得很'}
FUNC1 = set('以与和及把被将对向从在为让使给跟同由')
MAXLEN = 5          # 绑得太长会整块推到下一行、上一行空出一截（考研第一版 6—8 字，layoutcheck 译文短行查出 63 处）
han = lambda w: bool(w) and all('一' <= c <= '鿿' for c in w)


_SUPP = None


def supp_words():
    """分词补充.txt 里的词（与 make_video.jb、layoutcheck.jb 读同一个文件）。"""
    global _SUPP
    if _SUPP is None:
        from pathlib import Path
        _SUPP = [w.strip() for w in (Path(__file__).resolve().parent / '分词补充.txt').read_text('utf-8').splitlines() if w.strip() and not w.startswith('#')]
    return _SUPP


def zh_spans(s, jieba):
    import jieba.posseg as pseg
    ws, pos = [], 0
    for w, f in pseg.lcut(s):
        ws.append((pos, pos + len(w), w, f))
        pos += len(w)
    pairs = []
    for (a, _, x, fx), (_, b, y, fy) in zip(ws, ws[1:]):
        if not han(y):
            continue
        if han(x) and len(x) >= 2 and len(y) >= 2 and fy in NOUN and fx in HEAD and b - a <= 4:
            pairs.append((a, b))
        elif (x in PREFIX or x in NUM1) and len(y) <= 4:
            pairs.append((a, b))
        elif han(x) and (len(y) == 1 and y in SUFFIX1 or y in TAIL):
            pairs.append((a, b))
        elif x in FUNC1 and len(y) <= 3:
            pairs.append((a, b))
        elif re.fullmatch(r'\d+', x) and len(y) <= 3:
            pairs.append((a, b))
    out = []
    for a, b in pairs:                     # 连成串；超过 MAXLEN 个字就不再接上去
        if out and a < out[-1][1]:
            if max(b, out[-1][1]) - out[-1][0] <= MAXLEN:
                out[-1] = (out[-1][0], max(b, out[-1][1]))
        else:
            out.append((a, b))
    if getattr(jieba, '_zb_dict', False):      # ⑥ 补充词典里的词整体不断开（已加载补充词典时）
        out += [m.span() for w in supp_words() for m in re.finditer(re.escape(w), s)]
    return sorted(out)


STOP = {'The', 'A', 'An', 'In', 'On', 'At', 'But', 'And', 'If', 'When', 'As', 'For', 'So', 'This', 'That', 'These', 'Those', 'It', 'Its',
        'We', 'They', 'He', 'She', 'I', 'You', 'Yet', 'Or', 'Though', 'Although', 'While', 'After', 'Before', 'Since', 'Because', 'With',
        'Without', 'From', 'By', 'To', 'Of', 'Our', 'Their', 'His', 'Her', 'My', 'Your', 'What', 'Why', 'How', 'Where', 'Who', 'Which',
        'There', 'Here', 'Now', 'Then', 'Still', 'Even', 'Many', 'Most', 'Some', 'All', 'Such', 'One', 'Two', 'Like', 'Unlike', 'Under',
        'Over', 'According', 'Despite', 'During', 'Last', 'Next', 'Each', 'Every', 'Both', 'No', 'Not', 'Only', 'Just', 'Also', 'Yes'}
CAP = r"[A-Z][A-Za-z’'.&-]*"


def en_spans(t, hl=()):
    """hl：高亮词、短语在 t 里的位置（整体不断行）。专名与跨进去的高亮连起来超过 28 个字符就不绑（考研 k35：Massachusetts + 高亮 Institute of Technology
    共 37 个字符，连成一整块比一行还宽，伸出右边界）。"""
    out = []
    for m in re.finditer(rf"{CAP}(?: {CAP})+", t):
        ws = m.group(0).split(' ')
        st = m.start()
        while ws and ws[0] in STOP:
            st += len(ws[0]) + 1
            ws = ws[1:]
        while len(ws) > 4:                 # 太长：只绑前 4 个词
            ws = ws[:4]
        if len(ws) >= 2:
            e = st + len(' '.join(ws))
            a2 = min([st] + [x for x, y in hl if x < e and y > st])
            b2 = max([e] + [y for x, y in hl if x < e and y > st])
            if e - st <= 32 and b2 - a2 <= 28 and not (st <= 4 and e - st >= 22):      # ④ 句首长专名不绑
                out.append((st, e))
    out += [m.span() for m in re.finditer(r'\b\d+ (?:or|to|and) \d+\b', t)]
    out += [m.span() for m in re.finditer(r'(?<![\w.,-])\d+(?:[.,]\d+)*%? [a-z][a-z’\'-]*', t)]       # ③ 数字 + 小写词
    out += [m.span() for m in re.finditer(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}\b', t)]
    return out
