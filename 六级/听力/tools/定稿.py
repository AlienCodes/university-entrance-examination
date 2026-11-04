"""六级听力文字定稿：transcripts（otter）当底稿，解析里的听力原文给它挑错（老师 2026-11-04），parakeet 识别当第三方 + 给每个词时间。

三方逐词对齐（difflib，小写去标点比较）。transcripts 与原文不一致的每一处：
  · 原文 = 识别            → 按原文改（transcripts 识别错）            分类「按原文改」
  · transcripts = 识别     → 保留（原文 OCR 错或排版差异）            分类「原文OCR错」
  · 三方都不同             → 待核（列出上下文，人看）                  分类「待核」
原文漏的部分（说明、念题——解析里只有题干）不比，照 transcripts。
人看过的待核处登记在 <套>/待核裁定.json：{"<位置键>": "采用的文字"}，键是 待核 里的 key；没裁定的待核一律退出码 1。

用法：python 定稿.py <套号>        读 <套>/识别.json、解析原文.txt、Release 材料里的 otter（scratch 下载）或 <套>/otter.txt
输出：<套>/定稿.json  {"词": [[文字, 开始, 结束, 段号]], "段": [[说话人, 开始秒]], "差异": {...分类计数}, "改动": [...], "待核": [...]}
"""
import difflib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE.parent
NUM = {w: str(i) for i, w in enumerate('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen '
                                       'fifteen sixteen seventeen eighteen nineteen twenty'.split())}


EQ = {"okay": "ok", "were": "were"}
CONTR = {"we're": "we are", "you're": "you are", "they're": "they are", "i'm": "i am", "it's": "it is", "that's": "that is",
         "don't": "do not", "doesn't": "does not", "can't": "cannot", "won't": "will not", "isn't": "is not", "aren't": "are not",
         "i've": "i have", "we've": "we have", "you've": "you have", "they've": "they have", "i'll": "i will", "we'll": "we will",
         "there's": "there is", "what's": "what is", "let's": "let us", "didn't": "did not", "wasn't": "was not", "i'd": "i would"}
DICT = set(l.strip().lower() for l in open('/usr/share/dict/american-english', encoding='utf-8', errors='ignore')) \
    if Path('/usr/share/dict/american-english').exists() else None


def realword(w):
    w = re.sub(r"^[^A-Za-z]+|[^A-Za-z']+$", '', w.replace('’', "'")).lower()
    return bool(w) and (w in DICT or w.rstrip('s') in DICT or w.replace("'", '') in DICT)


def n(w):
    k = re.sub(r"[^a-z']", '', w.lower().replace('’', "'"))
    if k in CONTR: return CONTR[k].replace(' ', '')
    w = EQ.get(k, w)
    w = re.sub(r"[^a-z0-9]", '', w.lower().replace('’', "'").replace('&', 'and').replace('%', 'percent'))
    return NUM.get(w, w)


def otter(txt):
    """otter transcript.txt → [(说话人, 秒, [词...])]"""
    out = []
    for m in re.finditer(r'^(Speaker \d+)\s+(\d+):(\d+)\n(.*?)(?=\n\n|\Z)', txt, re.M | re.S):
        out.append((m.group(1), int(m.group(2)) * 60 + int(m.group(3)), m.group(4).split()))
    return out


def ocr_words(txt):
    """解析原文 → 英文词序列（去掉中文、[n] 题号标记、W:/M: 说话人标记、页眉）"""
    ws = []
    for line in txt.splitlines():
        if line.startswith('===') or re.search(r'[\u4e00-\u9fff]{3,}.*', line) and not re.search(r'[A-Za-z]{3,}.*[A-Za-z]{3,}', line):
            continue
        line = re.sub(r'[\u4e00-\u9fff，。？！：；、“”（）]+', ' ', line)
        line = re.sub(r'\[\d+\]|^\s*[WM]\s*[:：]', ' ', line)
        ws += [w for w in line.split() if re.search(r'[A-Za-z0-9]', w) and not re.fullmatch(r'[A-D]\)?|[A-D]\)\S*|\d+\.|\(\d+(-\w+)?\)\S*|[IVXJ]{1,4}|\[\d+\]?', w)]   # 详解里的选项标记、题号
    return ws


def sim(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def mapping(a, b):
    """a 的每个下标 → b 的下标（相等块与等长替换块 1:1），没有的 None"""
    m = [None] * len(a)
    sm = difflib.SequenceMatcher(None, [n(x) for x in a], [n(x) for x in b], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal' or (op == 'replace' and i2 - i1 == j2 - j1):
            for k in range(i2 - i1): m[i1 + k] = j1 + k
    return m, sm


def run(sid):
    sd = D / sid
    paras = otter((sd / 'otter.txt').read_text('utf-8'))
    W = [w for _, _, ws in paras for w in ws]
    seg = [k for k, (_, _, ws) in enumerate(paras) for _ in ws]
    A = json.loads((sd / '识别.json').read_text('utf-8'))
    R = ocr_words((sd / '解析原文.txt').read_text('utf-8'))
    amap, _ = mapping(W, [x[0] for x in A])
    global LAYER
    LAYER = json.loads((sd / '解析OCR.json').read_text('utf-8'))['方式'] == 'text'
    if DICT is None: sys.exit('停止：缺英文词典 /usr/share/dict/american-english（apt install wamerican）')
    rule = {k: v for k, v in json.loads((sd / '待核裁定.json').read_text('utf-8')).items() if not k.startswith('_')} if (sd / '待核裁定.json').exists() else {}

    def aspan(i1, i2):
        """otter[i1:i2] 对应的识别词（按两端最近的已对齐词夹出来）"""
        lo = next((amap[k] + 1 for k in range(i1 - 1, -1, -1) if amap[k] is not None), 0)
        hi = next((amap[k] for k in range(i2, len(W)) if amap[k] is not None), len(A))
        return [x[0] for x in A[lo:hi]]

    sm = difflib.SequenceMatcher(None, [n(x) for x in W], [n(x) for x in R], autojunk=False)
    edits, todo, kept, cnt = {}, [], [], {'按原文改': 0, '原文OCR错': 0, '待核': 0, '已裁定': 0}
    J = lambda ws: ''.join(n(x) for x in ws)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal' or max(i2 - i1, j2 - j1) > 6:     # 长段不一致 = 原文没有的部分（说明、念题）或中文残留，不比
            continue
        O, Rr, Aa = W[i1:i2], R[j1:j2], aspan(i1, i2)
        if J(O) == J(Rr):            # 只是拆分 / 标点不同
            continue
        key = f'{i1}:{i2}'
        ctx = ' '.join(W[max(0, i1 - 6):i1]) + ' 【' + ' '.join(O) + '】 ' + ' '.join(W[i2:i2 + 6])
        if any(k.startswith('改 ') and int(k[2:].split(':')[0]) <= i1 and i2 <= int(k.split(':')[1]) for k in rule):
            cnt['已裁定'] += 1; continue          # 落在整段改写里
        if key in rule:
            edits[(i1, i2)] = rule[key].split(); cnt['已裁定'] += 1
        elif J(Rr) == J(Aa) and Rr:
            edits[(i1, i2)] = Rr; cnt['按原文改'] += 1
        elif J(O) == J(Aa) and Rr and (LAYER or (DICT is not None and all(realword(x) for x in Rr) and sim(J(Rr), J(Aa)) >= 0.6)):
            # 两个识别器常犯同一种错（同音词、单复数、专名拼写）：原文是真词且拼写很近、或原文是文字层（没有 OCR 错）→ 不自动判，待核
            todo.append({'key': key, 'transcripts': ' '.join(O), '原文': ' '.join(Rr), '识别': ' '.join(Aa), '上下文': ctx, '类': '二识别同原文异'}); cnt['待核'] += 1
        elif J(O) == J(Aa):
            cnt['原文OCR错'] += 1; kept.append({'transcripts': ' '.join(O), '原文': ' '.join(Rr)})
        elif Rr and Aa and sim(J(Rr), J(Aa)) >= 0.75 and sim(J(Rr), J(Aa)) > sim(J(O), J(Aa)) + 0.2:
            edits[(i1, i2)] = Rr; cnt['按原文改'] += 1        # 识别明显更接近原文（专名拼写：Winnipeg / 原文 Winopia / 识别 Winnopia）
        elif op == 'delete' and not Aa and i2 - i1 <= 2:
            edits[(i1, i2)] = []; cnt['按原文改'] += 1        # transcripts 多出来、原文和录音里都没有
        else:
            todo.append({'key': key, 'transcripts': ' '.join(O), '原文': ' '.join(Rr), '识别': ' '.join(Aa), '上下文': ctx}); cnt['待核'] += 1
    # 整段改写（裁定文件里 "改 a:b": "文字"）：理顺待核裁定后前后词的标点、大小写；与别的改动重叠就停
    for k, v in rule.items():
        if k.startswith('改 '):
            i1, i2 = map(int, k[2:].split(':'))
            hit = [e for e in edits if e[0] < i2 and i1 < e[1] or e[0] == e[1] and i1 <= e[0] < i2]
            for e in hit:
                del edits[e]
            print(f'  改写 {k}：「{" ".join(W[i1:i2])}」→「{v}」' + (f'（覆盖 {hit}）' if hit else ''))
            edits[(i1, i2)] = v.split()
    same = {J(W[i1:i2]): v for (i1, i2), v in edits.items() if i2 > i1}
    for t in todo[:]:
        i1, i2 = map(int, t['key'].split(':'))
        if i2 > i1 and J(W[i1:i2]) in same and J(same[J(W[i1:i2])]) == J(t['原文'].split()):
            edits[(i1, i2)] = same[J(W[i1:i2])]; todo.remove(t); cnt['待核'] -= 1; cnt['按原文改'] += 1
    # 应用改动：改后的词继承原位置的时间（等长 1:1，否则平均分）
    out, changes = [], []
    i = 0
    starts = {k[0]: k for k in edits}
    while i < len(W):
        if i in starts:
            i1, i2 = starts[i]
            new = edits[(i1, i2)]
            changes.append({'位置': f'{i1}:{i2}', '原': ' '.join(W[i1:i2]), '改为': ' '.join(new)})
            if len(new) == i2 - i1:      # 1:1 换词：保留 transcripts 原词前后的标点（Winnipeg. → Winopia.）
                new = [re.match(r'^\W*', W[i1 + k]).group() + re.sub(r'^\W+|\W+$', '', w) + re.search(r'\W*$', W[i1 + k]).group() for k, w in enumerate(new)]
            for k, w in enumerate(new):
                src = i1 + min(k, max(i2 - i1 - 1, 0)) if i2 > i1 else max(i1 - 1, 0)
                out.append((w, src))
            i = max(i2, i + 1) if i2 > i1 else i
            if i2 == i1:          # 插入：插在 i1 之前，原词照常
                out.append((W[i], i)); i += 1
            continue
        out.append((W[i], i)); i += 1
    words = []
    for w, src in out:
        a = amap[src]
        words.append([w, A[a][1] if a is not None else None, A[a][2] if a is not None else None, seg[src]])
    res = {'词': words, '段': [[s, t] for s, t, _ in paras], '差异': cnt, '改动': changes, '保留': kept, '待核': todo,
           '对齐': {'transcripts词': len(W), '识别词': len(A), '原文词': len(R),
                  '有时间的词': sum(1 for x in words if x[1] is not None)}}
    (sd / '定稿.json').write_text(json.dumps(res, ensure_ascii=False, indent=0), 'utf-8')
    print(sid, cnt, res['对齐'])
    for t in todo:
        print('  待核', t['key'], '| T:', t['transcripts'], '| 原:', t['原文'], '| 识:', t['识别'], '|', t['上下文'])
    return 1 if todo else 0


if __name__ == '__main__':
    sys.exit(run(sys.argv[1]))
