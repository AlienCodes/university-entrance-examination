"""排版引擎（专八/tools/make_video.py）与排版检查（layoutcheck.py）共用的“不许拆开”的片段（考研截图盲审 2026-10-21）。

引擎用它决定哪里不断行，检查程序用它逐屏量实际断行位置：规则只写在这一处，两边不会不一致。

zh_spans(s, jieba)：中文里不许断开的片段 [(起, 止)]
  ① 名词性复合词：相邻两个词都是 2 个字以上、后一个是名词性（n、vn、nz、ns、nt、nr、ng、an、j），前一个是名词性 / 动词 / 形容词 / 区别词，
     合起来不超过 6 个字（服务人员、会员资格、保障措施、再生农业、非营利组织、联邦通信委员会、千禧技术奖）；
  ② 前缀词与后面的词：不、可、非、这一、每一、这些……（不稳定、可持续、这一威胁）；
  ③ 单字后缀与前面的词：们、型、性、化、者、家、式、级、类（父母们、气候友好型）；“得多”“得很”与前面的词；
  ④ 单字介词、连词与后面不超过 3 个字的词：以、与、和、把、被、在、为、对……（以 / 医院为中心、与 / 空间科学）；
  ⑤ 数字与后面不超过 3 个字的词（20世纪90 / 年代）。
  一串连起来的片段超过 8 个字就不再往上接（防止一大块不断行、上一行空出一截）。
en_spans(t)：英文里不许断开的片段 [(起, 止)]
  ① 专名：连续 2—4 个首字母大写的词（去掉开头的 The、When、In 这类普通词），总长不超过 32 个字符
     （Brett Kavanaugh、West Virginia、San Francisco、Apple TV.、California Attorney General）；
  ② 数字 or/to/and 数字（18 or 21）。
"""
import re

NOUN = {'n', 'vn', 'nz', 'ns', 'nt', 'nr', 'ng', 'an', 'j', 'nrt', 'nrfg', 'nw'}
HEAD = NOUN | {'v', 'a', 'b', 'vd', 'ad'}
PREFIX = {'不', '可', '非', '这', '那', '每', '各', '该', '某', '此', '这一', '那一', '每一', '同一', '这些', '那些', '这个', '那个', '这种', '那种',
          '这项', '这场', '这位', '这次', '这样', '那样'}
SUFFIX1 = set('们型性化者家式级类')
TAIL = {'得多', '得很'}
FUNC1 = set('以与和及把被将对向从在为让使给跟同由')
MAXLEN = 8
han = lambda w: bool(w) and all('一' <= c <= '鿿' for c in w)


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
        if han(x) and len(x) >= 2 and len(y) >= 2 and fy in NOUN and fx in HEAD and b - a <= 6:
            pairs.append((a, b))
        elif x in PREFIX and len(y) <= 4:
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
    return out


STOP = {'The', 'A', 'An', 'In', 'On', 'At', 'But', 'And', 'If', 'When', 'As', 'For', 'So', 'This', 'That', 'These', 'Those', 'It', 'Its',
        'We', 'They', 'He', 'She', 'I', 'You', 'Yet', 'Or', 'Though', 'Although', 'While', 'After', 'Before', 'Since', 'Because', 'With',
        'Without', 'From', 'By', 'To', 'Of', 'Our', 'Their', 'His', 'Her', 'My', 'Your', 'What', 'Why', 'How', 'Where', 'Who', 'Which',
        'There', 'Here', 'Now', 'Then', 'Still', 'Even', 'Many', 'Most', 'Some', 'All', 'Such', 'One', 'Two', 'Like', 'Unlike', 'Under',
        'Over', 'According', 'Despite', 'During', 'Last', 'Next', 'Each', 'Every', 'Both', 'No', 'Not', 'Only', 'Just', 'Also', 'Yes'}
CAP = r"[A-Z][A-Za-z’'.&-]*"


def en_spans(t):
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
            if e - st <= 32:
                out.append((st, e))
    out += [m.span() for m in re.finditer(r'\b\d+ (?:or|to|and) \d+\b', t)]
    return out
