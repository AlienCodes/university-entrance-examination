"""从每个文本里找“读后续写”，抽题目、开头语、范文。输出 found.json（每个文件一条或零条）。
用法: python3 -I extract.py work目录"""
import sys, os, re, json

W = sys.argv[1]
T = os.path.join(W, 'T')
SKIP = re.compile('数学|语文|物理|化学|生物|历史|地理|政治|日语|俄语|答题卡|听力试题')

def is_en(s, k=4):
    words = re.findall(r"[A-Za-z][A-Za-z'’]*", s)
    cjk = len(re.findall(r'[一-鿿]', s))
    return len(words) >= k and cjk <= 2

def clean(s):
    return re.sub(r'\s+', ' ', s.replace('　', ' ')).strip()

FOOT = re.compile(r'(英语|试题|试卷).{0,6}第\s*\d+\s*页|第\s*\d+\s*页\s*[,，]?\s*共\s*\d+\s*页')
UND = re.compile(r'^[\s_＿—\-·.…]{6,}$')
PARA = re.compile(r'^\s*(Para(?:graph)?\s*\.?\s*[12一二]|第[一二12]段)\s*[:：.]?\s*', re.I)

def key(s):
    return re.sub(r'[^a-z]', '', s.lower())

def split2(text, op2):
    """范文按第二段开头语切成两段；切不开返回 None（不硬切）。"""
    if len(text.split()) < 60:
        return None
    w = re.findall(r"[A-Za-z]+", op2)[:6]
    if not w:
        return None
    m = re.search(r'[^A-Za-z]*'.join(map(re.escape, w)), text, re.I)
    if not m or m.start() < 100:
        return None
    return [text[:m.start()].strip(), text[m.start():].strip()]

def find(t):
    lines = [l.rstrip() for l in t.replace('\f', '\n').split('\n')]
    # 1. 题目说明行：含“续写”且含“阅读/材料/开头语/段落”
    starts = [i for i, l in enumerate(lines)
              if '续写' in l and re.search('阅读|材料|开头语|开头|段首|短文', l) and '所续写' not in l and not re.match(r'\s*\d\s*[.．、]\s*续写', l) and len(l) < 250]
    if not starts:
        return None
    i0 = starts[0]
    head = ''
    for j in range(max(0, i0 - 3), i0 + 1):
        if re.search(r'第[二三四]节|读后续写|写作', lines[j]):
            head = clean(lines[j]) if j != i0 else head
    instr = clean(lines[i0])
    m = re.search(r'满分\s*(\d+)\s*分', head + instr)
    score = int(m.group(1)) if m else None
    m = re.match(r'\s*(\d{1,3})\s*[.．、]', lines[i0])
    qno = int(m.group(1)) if m else None
    # 2. 原文：说明行之后到“注意”
    k = i0 + 1
    passage = []
    NOTE1 = re.compile(r'\s*[(（]?1[)）]?\s*[.．、]?\s*(所)?续写')
    while k < len(lines) and not re.match(r'\s*注意', lines[k]) and not PARA.match(lines[k]) and not NOTE1.match(lines[k]):
        if NOTE1.match(lines[k + 1] if k + 1 < len(lines) else '') and not is_en(lines[k], 6):
            k += 1  # “注意”被 OCR 认成别的字（如 TEE:）
            break
        if lines[k].strip() and not FOOT.search(lines[k]):
            passage.append(clean(lines[k]))
        k += 1
        if k - i0 > 200:
            return {'error': '没找到“注意”', 'instr': instr}
    note = []
    if k < len(lines) and re.match(r'\s*注意', lines[k]):
        note.append(clean(lines[k])); k += 1
    # 3. 注意事项 + 两段开头语
    openings = []
    while k < len(lines) and len(openings) < 2:
        l = lines[k]
        s = clean(l)
        k += 1
        if not s or UND.match(s):
            continue
        if re.match(r'^[(（]?\d[)）.．、]', s) or ('续写' in s or '词数' in s or '格式' in s or '答题' in s):
            note.append(s); continue
        s2 = PARA.sub('', s)
        if not s2:  # “Paragraph 1:” 单独一行
            continue
        if is_en(s2, 3):
            openings.append(re.sub(r'[_＿]{3,}.*$', '', s2).strip().lstrip(';；,，:：.·•-—_ '))
        elif re.search(r'[【\[](参考)?答案[】\]]|[【\[]解析|参考范文|One possible', s):
            break
    # 4. 范文：【答案】之后到【解析】/【分析】/【导语】
    rest = '\n'.join(lines[k:])
    essay = None
    m = re.search(r'[【\[](?:参考)?答案[】\]](.*?)(?=[【\[](?:解析|分析|导语|详解|点睛|思路)|\Z)', rest, re.S)
    if not m:
        m = re.search(r'^\s*(?:参考)?范文[:：]?\s*$(.*?)(?=^\s*(?:译文|参考答案)|[【\[]|\Z)', rest, re.S | re.M)
    if m and len(openings) == 2:
        body = [PARA.sub('', clean(x)) for x in m.group(1).split('\n') if clean(x) and not UND.match(clean(x))]
        essay = split2(' '.join(body), openings[1])
    return {'head': head, 'instr': instr, 'qno': qno, 'score': score, 'passage': passage,
            'note': note, 'openings': openings, 'essay': essay}

def title(t):
    for l in t.split('\n')[:40]:
        s = clean(l)
        if re.search(r'(19|20)\d\d', s) and re.search('考试|试卷|高考|联考|测试|评价|演练|检测|英语', s) and len(s) < 90:
            return s
    return ''

OCR = set()
for fn in ('ocr1.tsv', 'ocr2.tsv', 'ocr3.tsv'):
    fp = os.path.join(T, fn)
    if os.path.exists(fp):
        OCR |= {l.split('\t')[0] for l in open(fp) if l.strip()}

def deocr(t):
    """OCR 文本：去汉字之间的空格；英文折行并回段落（上一行不以句末标点结尾、或下一行小写开头就接上）。"""
    t = re.sub(r'(?<=[\u4e00-\u9fff\uff08-\uff1f\u3001\u3002]) +(?=[\u4e00-\u9fff\uff08-\uff1f\u3001\u3002])', '', t)
    out = []
    for l in t.split('\n'):
        s = l.strip()
        if not s:
            continue
        if out and is_en(out[-1], 3) and re.match(r"[a-z(“\"'’,]", s) or (out and is_en(out[-1], 6) and is_en(s, 1)
                and not re.search(r'[.!?"”’]$', out[-1]) and not PARA.match(s)):
            out[-1] += ' ' + s
        else:
            out.append(s)
    return '\n'.join(out)

rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(T, 'files.tsv'))]
out = []
for h, ext, size, path, n in rows:
    rel = path.split('/work/', 1)[1]
    if SKIP.search(rel):
        continue
    t = open(os.path.join(T, h + '.txt'), errors='replace').read()
    if h in OCR:
        t = deocr(t)
    r = find(t)
    if r is not None:
        r['ocr'] = h in OCR
    # 供汇总在答案卷 / 卷末参考答案里找范文：从第一次出现“续写”起的全文
    i = t.find('续写')
    tail = t[i:] if i >= 0 else ''
    out.append({'sha': h, 'path': rel, 'title': title(t), 'chars': len(t.strip()), 'hit': r, 'mention': '续写' in t, 'tail': tail})
json.dump(out, open(os.path.join(W, 'found.json'), 'w'), ensure_ascii=False, indent=1)
for o in out:
    r = o['hit']
    if r is None:
        continue
    flag = 'ERR' if 'error' in r else f"op={len(r['openings'])} es={'Y' if r['essay'] else '-'} q={r['qno']} s={r['score']} p={len(r['passage'])}"
    print(flag, o['path'][-70:])
