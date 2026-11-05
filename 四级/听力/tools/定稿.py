"""四级听力文字定稿（关卡 2：原文三方互核）。底稿 = parakeet 识别（每个词都有时刻，45 段录音都有），
解析里的官方听力原文 + otter 转写（老师给的 30 段才有）给它挑错。规则照六级 定稿.py，只是底稿换成识别：

逐词对齐（difflib，小写去标点比较），识别与原文不一致的每一处（≤ 6 词；更长的是原文没有的说明、念题、解析讲解，不比）：
  · 原文 = otter                         → 按原文改（识别错）                       「按原文改」
  · 识别 = otter，原文不同                 → 原文是真词且拼写接近 / 原文来自文字层 → 待核（两个识别器常犯同一种错）
                                            否则 → 原文 OCR 错，保留识别            「原文OCR错」
  · 没有 otter（合集 5 段、otter 缺的那段） → 原文全是真词 → 待核；原文有非词 → OCR 错，保留
  · 三方都不同                            → 识别明显更接近原文（专名拼写）→ 按原文改；否则待核
没有官方原文的 6 套（2023-06、2023-12、2024-06）：识别 × otter 两个机器转写互核，不一致的（两边都是真词、规范化后不同）一律待核，
  汇报写明「两个识别器互核 + 人核」（老师补原文后重跑，自动换成三方互核）。
人核结论登记 <套>/待核裁定.json：{"<key>": "采用的文字"}（key 见 待核；"" = 删掉这几个识别词），没裁定的待核退出码 1。
用法：python3 定稿.py <套> [<套> …] | ALL       输出 四级/听力/<套>/定稿.json
  {"词": [[文字, 开始, 结束, 0]], "差异": {...}, "改动": [...], "保留": [...], "待核": [...], "来源": "三方" | "二方"}
"""
import difflib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
H = HERE.parent
NUM = {w: str(i) for i, w in enumerate('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen '
                                       'fifteen sixteen seventeen eighteen nineteen twenty'.split())}
CONTR = {"we're": "we are", "you're": "you are", "they're": "they are", "i'm": "i am", "it's": "it is", "that's": "that is",
         "don't": "do not", "doesn't": "does not", "can't": "cannot", "won't": "will not", "isn't": "is not", "aren't": "are not",
         "i've": "i have", "we've": "we have", "you've": "you have", "they've": "they have", "i'll": "i will", "we'll": "we will",
         "there's": "there is", "what's": "what is", "let's": "let us", "didn't": "did not", "wasn't": "was not", "i'd": "i would",
         "he's": "he is", "she's": "she is", "couldn't": "could not", "wouldn't": "would not", "haven't": "have not"}
EQ = {'okay': 'ok', 'centre': 'center', 'percent': 'percent'}
DICTF = Path('/usr/share/dict/american-english')
if not DICTF.exists(): sys.exit('停止：缺英文词典 /usr/share/dict/american-english（apt install wamerican，踩坑 114）')
DICT = set(l.strip().lower() for l in DICTF.open(encoding='utf-8', errors='ignore'))


def realword(w):
    w = re.sub(r"^[^A-Za-z]+|[^A-Za-z']+$", '', w.replace('’', "'")).lower()
    if len(w) < 2 and w not in ('a', 'i'): return False
    return bool(w) and (w in DICT or w.rstrip('s') in DICT or w.replace("'", '') in DICT or re.sub(r"'s$", '', w) in DICT
                        or (w.endswith('ed') and (w[:-2] in DICT or w[:-1] in DICT)) or (w.endswith('ing') and w[:-3] in DICT))


def n(w):
    k = re.sub(r"[^a-z']", '', w.lower().replace('’', "'"))
    if k in CONTR: return CONTR[k].replace(' ', '')
    w = EQ.get(k, w)
    w = re.sub(r"[^a-z0-9]", '', w.lower().replace('’', "'").replace('&', 'and').replace('%', 'percent'))
    return NUM.get(w, w)


BRIT = [(r'our\b', 'or'), (r'ise(s|d)?\b', r'ize\1'), (r'isation', 'ization'), (r'yse(s|d)?\b', r'yze\1'), (r'tre\b', 'ter'),
        (r'lled\b', 'led'), (r'lling\b', 'ling'), (r'^mum', 'mom'), (r'ogue\b', 'og'), (r'^grey', 'gray')]
ONES = {w: i for i, w in enumerate('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split())}
TENS = {w: 10 * i for i, w in enumerate('_ _ twenty thirty forty fifty sixty seventy eighty ninety'.split()) if w != '_'}


def canon(ws):
    """比较用：英美拼写、数字读法（one thousand dollar = $1,000，nineteen ninety six = 1996，twenty eighth = 28th）、货币和百分号统一"""
    t = []
    for w in ws:
        w = w.lower().replace('’', "'")
        w = re.sub(r'(?<=\d),(?=\d{3})', '', w)
        t += [x for x in re.split(r"[^a-z0-9']+", w.replace('-', ' ')) if x]
    out, i = [], 0
    while i < len(t):
        x = t[i]
        if x in ONES or x in TENS or x in ('hundred', 'thousand', 'million'):
            val, cur, j, parts = 0, 0, i, []
            while j < len(t) and (t[j] in ONES or t[j] in TENS or t[j] in ('hundred', 'thousand', 'million', 'and') or re.fullmatch(r'(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|twentieth|thirtieth)', t[j])):
                if t[j] == 'and' and not (j + 1 < len(t) and (t[j + 1] in ONES or t[j + 1] in TENS) and parts and parts[-1] in ('hundred', 'thousand')): break
                parts.append(t[j]); j += 1
            # 年份读法：nineteen ninety six → 1996（两组各 < 100）
            nums, k = [], 0
            ORD = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10, 'twentieth': 20, 'thirtieth': 30}
            for p_ in parts:
                v = ONES.get(p_, TENS.get(p_, ORD.get(p_)))
                if p_ == 'and': continue
                if p_ == 'hundred': cur = max(cur, 1) * 100
                elif p_ in ('thousand', 'million'): val += max(cur, 1) * (1000 if p_ == 'thousand' else 10 ** 6); cur = 0
                elif cur and cur % 100 and cur >= 10 and v < 100 and (cur % 10 == 0 and v < 10) is False and cur < 100 and v >= 10:
                    nums.append(val + cur); val, cur = 0, v           # 两组：nineteen | ninety …
                else: cur += v
            nums.append(val + cur)
            out.append(''.join(str(z) for z in nums)); i = j
            if parts and re.fullmatch(r'first|second|third|\w+th', parts[-1]) and parts[-1] not in ONES: pass
            continue
        x = re.sub(r'^(\d+)(st|nd|rd|th)$', r'\1', x)
        if x in ('dollar', 'dollars', 'percent', 'per', 'cent'): i += 1; continue
        k = CONTR.get(x)
        if k: out.append(k.replace(' ', '')); i += 1; continue
        x = x.replace("'", '')
        x = EQ.get(x, x)
        for a, b in BRIT: x = re.sub(a, b, x)
        out.append(x); i += 1
    return ''.join(out)


J = canon
sim = lambda a, b: difflib.SequenceMatcher(None, a, b).ratio()


def otter(txt):
    return [w for m in re.finditer(r'^Speaker \d+\s+\d+:\d+\n(.*?)(?=\n\n|\Z)', txt, re.M | re.S) for w in m.group(1).split()]


def ref_words(txt):
    """解析 → 听力部分（Listening Comprehension 到 Reading Comprehension）的英文词序列；去掉中文、(3-1) / [1] 题号标记、W:/M:、选项标记"""
    i = txt.find('Listening Comprehension')
    if i < 0: i = 0
    m = re.search(r'Reading\s+Comprehension', txt[i + 50:])
    part = txt[i: i + 50 + m.start()] if m else txt[i:]
    ws = []
    for line in part.splitlines():
        if re.search(r'[\u4e00-\u9fff]{3,}', line) and not re.search(r'[A-Za-z]{3,}.*[A-Za-z]{3,}', line):
            continue
        line = re.sub(r'[\u4e00-\u9fff，。？！：；、“”（）【】]+', ' ', line)
        line = re.sub(r"(\w)\s?['’]\s+(s|m|re|ve|ll|d|t)\b", r"\1'\2", line)          # OCR 把 it's 拆成 it' s
        line = re.sub(r'\(\s*[\dlI]{1,2}(?:\s*-\s*\d)?\s*\)|\[\s*\d{1,2}\s*\]|(?:^|\s)[WM]\s*[:：]', ' ', line)
        ws += [w for w in line.split() if re.search(r'[A-Za-z0-9]', w) and not re.fullmatch(r'[A-D]\)\S*|\d+\.', w)]
    return ws


def mapping(a, b):
    m = [None] * len(a)
    sm = difflib.SequenceMatcher(None, [n(x) for x in a], [n(x) for x in b], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal' or (op == 'replace' and i2 - i1 == j2 - j1):
            for k in range(i2 - i1): m[i1 + k] = j1 + k
    return m


def sources(sid):
    dz = json.loads((H / '对照.json').read_text('utf-8'))
    rid = dz['choice'][sid]
    P = json.loads((H / '识别' / rid / '识别.json').read_text('utf-8'))
    of = H / 'otter' / f'{rid}.txt'
    O = otter(of.read_text('utf-8')) if of.exists() else None
    info = json.loads((H / '原始材料/解析内容.json').read_text('utf-8'))[sid]
    R = ref_words((H / '解析文字' / f'{sid}.txt').read_text('utf-8')) if info['听力原文'] == '有' else None
    return rid, P, O, R, info['文字来源'] == '文字层'


def run(sid, quiet=False, R_override=None, P_override=None):
    rid, P, O, R, layer = sources(sid)
    if R_override is not None: R = R_override
    if P_override is not None: P = P_override
    W = [x[0] for x in P]
    sd = H / sid; sd.mkdir(exist_ok=True)
    rf = sd / '待核裁定.json'
    rule = {k: v for k, v in json.loads(rf.read_text('utf-8')).items() if not k.startswith('_')} if rf.exists() else {}
    omap = mapping(W, O) if O else [None] * len(W)

    def ospan(i1, i2):
        """识别 W[i1:i2] 对应的 otter 词（两端最近的已对齐词夹出来）；两端都没对上（otter 缺这一段）→ None"""
        if not O: return None
        lo = next((omap[k] + 1 for k in range(i1 - 1, max(-1, i1 - 12), -1) if omap[k] is not None), None)
        hi = next((omap[k] for k in range(i2, min(len(W), i2 + 12)) if omap[k] is not None), None)
        if lo is None or hi is None or hi < lo or hi - lo > 12: return None
        return O[lo:hi]

    ref = R if R is not None else O
    two = R is None
    sm = difflib.SequenceMatcher(None, [n(x) for x in W], [n(x) for x in ref], autojunk=False)
    edits, todo, kept = {}, [], []
    cnt = {'按原文改': 0, '原文OCR错': 0, '待核': 0, '已裁定': 0}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal' or max(i2 - i1, j2 - j1) > 6: continue
        A, Rr = W[i1:i2], ref[j1:j2]
        if J(A) == J(Rr): continue
        key = f'{i1}:{i2}'
        ctx = ' '.join(W[max(0, i1 - 8):i1]) + ' 【' + ' '.join(A) + '】 ' + ' '.join(W[i2:i2 + 8])
        item = {'key': key, '识别': ' '.join(A), ('otter' if two else '原文'): ' '.join(Rr), '上下文': ctx}
        if key in rule:
            edits[(i1, i2)] = rule[key].split(); cnt['已裁定'] += 1; continue
        if two:                                       # 识别 × otter：只有两边都像真词才可能是实质差异
            if A and Rr and (all(realword(x) for x in A + Rr) or any(c.isdigit() for c in ' '.join(A + Rr))):
                todo.append(item); cnt['待核'] += 1
            else:
                cnt['原文OCR错'] += 1; kept.append(item)
            continue
        Os = ospan(i1, i2)
        item['otter'] = ' '.join(Os) if Os is not None else None
        real = bool(Rr) and all(realword(x) for x in Rr)
        if Os is not None and J(Rr) == J(Os):
            edits[(i1, i2)] = Rr; cnt['按原文改'] += 1
        elif not Rr and (Os is None or J(Os) == J(A)):      # 原文省掉的（说明、念题、语气词）：识别有、otter 也有 / 没有 otter → 照识别
            cnt['原文OCR错'] += 1; kept.append(item)
        elif not A and (Os is None or not Os):              # 原文多出来的、两个识别器都没有：解析讲解的残片 → 不加
            cnt['原文OCR错'] += 1; kept.append(item)
        elif Os is not None and J(A) == J(Os):
            if real and sim(J(Rr), J(A)) >= 0.6:
                item['类'] = '二识别同原文异'; todo.append(item); cnt['待核'] += 1
            else:
                cnt['原文OCR错'] += 1; kept.append(item)
        elif not real and Rr:                              # 原文有非词：OCR 错
            cnt['原文OCR错'] += 1; kept.append(item)
        elif Rr and A and Os is not None and sim(J(Rr), J(A)) >= 0.75 and sim(J(Rr), J(A)) > sim(J(Os), J(A)) + 0.2:
            edits[(i1, i2)] = Rr; cnt['按原文改'] += 1
        else:
            todo.append(item); cnt['待核'] += 1
    # 整段改写（裁定文件 "改 a:b": "文字"，a:b 是识别词下标）：念题漏词、听错题号等；与别的改动重叠就覆盖（打印出来）
    for k, v in rule.items():
        if not k.startswith('改 '): continue
        i1, i2 = map(int, k[2:].split(':'))
        hit = [e for e in edits if e[0] < i2 and i1 < e[1] or e[0] == e[1] and i1 <= e[0] < i2]
        for e in hit: del edits[e]
        edits[(i1, i2)] = v.split(); cnt['已裁定'] += 1
        if not quiet: print(f'  改写 {k}：「{" ".join(W[i1:i2])}」→「{v}」' + (f'（覆盖 {hit}）' if hit else ''))
    todo = [t for t in todo if not any(k.startswith('改 ') and int(k[2:].split(':')[0]) <= int(t['key'].split(':')[0]) and int(t['key'].split(':')[1]) <= int(k.split(':')[1]) for k in rule)]
    cnt['待核'] = len(todo)
    whole = {tuple(map(int, k[2:].split(':'))) for k in rule if k.startswith('改 ')}
    # 应用改动：1:1 换词继承原词时刻与前后标点；其余新词时刻留空（引擎在前后已知时刻之间插值）
    words, changes, i = [], [], 0
    starts = {k[0]: k for k in edits}
    while i < len(P):
        if i in starts:
            i1, i2 = starts[i]; new = edits[(i1, i2)]
            changes.append({'位置': f'{i1}:{i2}', '原': ' '.join(W[i1:i2]), '改为': ' '.join(new)})
            if len(new) == i2 - i1 and (i1, i2) not in whole:
                for k, w in enumerate(new):
                    src = P[i1 + k][0]
                    w = re.match(r'^\W*', src).group() + re.sub(r'^\W+|\W+$', '', w) + re.search(r'\W*$', src).group()
                    words.append([w, P[i1 + k][1], P[i1 + k][2], 0])
            elif len(new) == i2 - i1:
                words += [[w, P[i1 + k][1], P[i1 + k][2], 0] for k, w in enumerate(new)]
            else:
                if new and i2 > i1 and (i1, i2) not in whole:              # 保留尾标点（整段改写照写的，不套）
                    new = new[:-1] + [re.sub(r'\W+$', '', new[-1]) + re.search(r'\W*$', W[i2 - 1]).group()]
                words += [[w, None, None, 0] for w in new]
            if i2 == i1:
                words.append(list(P[i]) + [0]); i += 1
            else:
                i = i2
            continue
        words.append(list(P[i]) + [0]); i += 1
    res = {'来源': '二方' if two else '三方', '录音': rid, '词': words, '差异': cnt, '改动': changes, '保留': kept, '待核': todo,
           '对齐': {'识别词': len(W), '原文词': len(R) if R else 0, 'otter词': len(O) if O else 0,
                  '有时间的词': sum(1 for x in words if x[1] is not None)}}
    if R_override is None and P_override is None:
        (sd / '定稿.json').write_text(json.dumps(res, ensure_ascii=False, indent=0), 'utf-8')
    if not quiet:
        print(sid, res['来源'], cnt, res['对齐'])
    return res


if __name__ == '__main__':
    ids = sys.argv[1:]
    if ids == ['ALL']: ids = sorted(json.loads((H / '对照.json').read_text('utf-8'))['choice'])
    bad = 0
    for s in ids:
        r = run(s)
        bad += len(r['待核'])
    print(f'待核合计 {bad} 处')
    sys.exit(1 if bad else 0)
