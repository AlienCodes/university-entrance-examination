"""四级听力题目（关卡 3：题 ↔ 原文；关卡 4 的程序一半）：25 题 × [题干, [A, B, C, D], 答案]。
四级结构：Section A 新闻 3 段（1—2、3—4、5—7），B 长对话 2 段（8—11、12—15），C 短文 3 段（16—18、19—21、22—25）。
  · 选项：四级/听力/试卷/<套>.txt（第一来源）；第二来源 = 仓库 四级/真题/ 里同一套试卷 PDF 的文字层（与第一来源不是同一个文件时），
    逐个选项比，相似度 < 0.9 报出。扫描版、没有第二个文件的套记“只有一个来源”（靠内容配对 + 做题兜底）。
    人工整理过的选项写 <套>/选项.json {"题号": [A, B, C, D]}（与试卷文字比，防改写）。
  · 题干：定稿.json 里念题那句（Question N: …?）；解析里的英文题干与之不同（且多出的都是真词）就报。
  · 答案：只认 <套>/答案裁定.json（{"题号": "字母"}，程序抽的 × 子代理做题两边一致才写，见 答案.py）。
    程序抽：解析每题讲解里说“X 是正确答案 / 答案为 X / X 与原文一致”是肯定、“排除 / 未提及 / 不符”是否定（judge，照六级）。
  · 内容配对：每题 4 个选项的实词在本段原文里出现的比例，中位数 < 0.3 报（配错套）；题干念题顺序与题号一致。
出错一律列全、退出码 1。用法：python3 题目.py <套> … | ALL     输出 <套>/题目.json
"""
import difflib, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
H = HERE.parent
ROOT = HERE.parents[2]
SEC = [(1, 2), (3, 4), (5, 7), (8, 11), (12, 15), (16, 18), (19, 21), (22, 25)]      # 四级听力固定 8 段
DICT = set(l.strip().lower() for l in open('/usr/share/dict/american-english', encoding='utf-8', errors='ignore'))
PRINTED = {'advertizing'}          # 原卷就这么印（201812-2 第 13 题，两个来源相同）
STOP = set('the a an of to and in is for on that what does do did be by with as it at from are was this his her their its about'.split())
NUMW = {w: i + 1 for i, w in enumerate('one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen '
                                       'eighteen nineteen twenty twenty-one twenty-two twenty-three twenty-four twenty-five'.split())}


def paper_txt(sid):
    return (H / '试卷' / f'{sid}.txt').read_text('utf-8')


def second_txt(sid):
    """同一套试卷的另一个文件（仓库 四级/真题/ 的 PDF 文字层）；与第一来源同一个文件、或没有文字层 → None"""
    y, m, k = sid[:4], sid[4:6], sid[-1]
    src = paper_txt(sid).splitlines()[0]
    for f in sorted((ROOT / '四级/真题' / y / f'{y}年{m}月').glob(f'*第{k}套.pdf')):
        if f.stem in src: continue                      # 第一来源就是它（或它的 .txt）
        t = subprocess.run(['pdftotext', '-layout', str(f), '-'], capture_output=True, text=True).stdout
        if len(re.findall(r'\bA[.)]', t)) >= 20: return t, f.name
    return None, None


def parse_options(txt):
    i = txt.find('Listening Comprehension')
    part = txt[i if i >= 0 else txt.find('Section A'):]
    m = re.search(r'Part\s*(III|Ⅲ)\b|Reading\s*Comprehension', part)
    part = part[:m.start()] if m else part
    part = '\n'.join(re.sub(r'\b([A-D])\s+[.)]', r'\1)', re.sub(r'^(\s*\d{1,2})\s+\.', r'\1.', re.sub(r'^(\s*)(\d)\s(\d)\s*\.', r'\1\2\3.', ln)))
                     for ln in part.splitlines())
    instr = {}
    for s in 'ABC':
        mm = re.search(rf'Section {s}\s*\n(?:[^\n]*\n)?\s*Directions\s*[:：,，.]\s*(.*?)(?=\n\s*(Questions|News|Conversation|Passage|1\.))', part, re.S)
        instr[s] = re.sub(r'\s+([.,])', r'\1', re.sub(r'\s+', ' ', 'Directions: ' + mm.group(1))).strip() if mm else None
        if instr[s]:
            e = re.search(r'cent(?:re|er)\.', instr[s]); instr[s] = instr[s][:e.end()] if e else instr[s]
    Q, cur, last = {}, None, None
    for line in part.splitlines():
        line = line.replace('\f', '')
        if 'burningvocabulary' in line or re.fullmatch(r'\s*\d*\s*', line) or re.search(r'[\u4e00-\u9fff]', line): continue
        mm = re.match(r'\s*(\d{1,2})\s*[.．]\s*(A\s*[.)].*)', line)
        if mm and 1 <= int(mm.group(1)) <= 25 and re.match(r'A\s*[.)]', mm.group(2)):
            cur = int(mm.group(1)); Q[cur] = {}; line = mm.group(2)
        if re.match(r'\s*(Questions|Section|Directions|Part)\b', line): cur = None
        if cur is None: continue
        for c in re.split(r'\s{3,}', line.strip()):
            mm = re.match(r'([A-D])\s*[.)]\s*(.*)', c)
            if mm: Q[cur][mm.group(1)] = mm.group(2).strip(); last = mm.group(1)
            elif c and Q[cur] and not re.search(r'[.?!]$', Q[cur][last]): Q[cur][last] += ' ' + c.strip()
            elif c: cur = None; break
    return Q, instr


def nz(x):
    return re.findall(r'[a-z0-9]+', x.lower().replace('&', ' and ').replace('’', "'").replace("'s", ' s'))


def judge(blk):
    """讲解段 → 答案字母（照六级）：说正确 / 相符 / 答案为的字母是肯定，说排除 / 不符 / 未提及的是否定"""
    blk = re.sub(r'[A-D]\s*[)）]', '', blk)
    blk = re.sub(r'[A-Za-z]{2,}', ' ', blk)
    pos, neg = set(), set()
    for sen in re.split(r'[。；;]', blk):
        ls = set(re.findall(r'[A-D]', sen))
        if not ls: continue
        if re.search(r'排除|不符|不正确|错误|无中生有|未提及|没有提及|并未|曲解|偷换|干扰|不是|均未', sen): neg |= ls
        elif re.search(r'正确|相符|答案|符合|吻合|一致|对应|故|由此|可知|因此|所以', sen): pos |= ls
    pos -= neg if len(pos - neg) == 1 else set()
    if len(pos) == 1: return pos.pop()
    rest = set('ABCD') - neg
    return rest.pop() if not pos and len(rest) == 1 else ''


def jx_blocks(sid):
    """解析听力部分按题切块：每题的英文题干（n. What …）起，到下一题题干止；中文 OCR 的字间空格去掉"""
    t = (H / '解析文字' / f'{sid}.txt').read_text('utf-8', 'ignore')
    i = t.find('Listening'); j = re.search(r'Reading\s*Comprehension|Part\s*(III|Ⅲ)', t[i + 400:]) if i >= 0 else None
    t = t[i: i + 400 + j.start()] if j else t
    t = re.sub(r'(?<=[一-鿿，。：；、“”（）])\s+(?=[一-鿿，。：；、“”（）A-D])|(?<=[A-D])\s+(?=[一-鿿])', '', t)
    pos = []
    for n in range(1, 26):
        lo = next((q + 1 for _, q in reversed(pos) if q is not None), 0)
        m = re.search(rf'(?<![\d\[(]){n}\s*[.．]\s*(?=What|Why|How|Who|Which|When|Where|According|In |For |On |Accor)', t[lo:])
        pos.append((n, lo + m.start() if m else None))
    out = {}
    for k, (n, p) in enumerate(pos):
        if p is None: continue
        nxt = next((q for _, q in pos[k + 1:] if q is not None), len(t))
        out[n] = t[p:nxt]
    return out


def col_answers(sid):
    """两栏版式：题干行（n. What …）下面 1—4 行内、与题号同一栏位（列差 ≤ 14）的第一个“X)”/“X）”就是答案字母"""
    t = (H / '解析文字' / f'{sid}.txt').read_text('utf-8', 'ignore')
    i = t.find('Listening'); j = re.search(r'Reading\s*Comprehension|Part\s*(III|Ⅲ)', t[i + 400:]) if i >= 0 else None
    L = (t[i: i + 400 + j.start()] if j else t).splitlines()
    out = {}
    for k, line in enumerate(L):
        for m in re.finditer(r'(?:(?<=\s)|^)(\d{1,2})\s*[.．]\s*(?=What|Why|How|Who|Which|When|Where|According|In |For |On )', line):
            n = int(m.group(1))
            if not 1 <= n <= 25 or n in out: continue
            c = m.start(1)
            for line2 in L[k + 1:k + 5]:
                if re.search(r'(?:^|\s)\d{1,2}\s*[.．]\s*(?:What|Why|How|Who)', line2): break
                hit = [mm for mm in re.finditer(r'(?:(?<=\s)|^)([A-D])\s*[)）](?!\s*[A-Z]?[a-z]+[ ,.][a-z]*)(?=\s*\S)', line2) if abs(mm.start(1) - c) <= 14]   # 后面是英文句子 = 重印的选项，不是答案
                if hit: out[n] = hit[0].group(1); break
    return out


def jx_stem(blk):
    m = re.match(r'\d+\s*[.．]\s*([A-Z][^一-鿿?]*\?)', blk, re.S)
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''


def toks(s):
    return {w for w in re.findall(r"[a-z]+", s.lower()) if w not in STOP and len(w) > 2}


NUMRE = r'(?:\d{1,2}|(?:twenty[- ])?(?:one|two|three|four|five)|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)'
STOPRE = r'(?=\s+(?:[Qq]uestions?\s+' + NUMRE + r'\b|Section [ABC]\b|News [Rr]eport|Conversation (?:one|two|One|Two)|Passage (?:one|two|three|One|Two|Three)|(?:That|This) is the end|$))'


def stems_from(text):
    """念题：Question N[.:] 题干 —— 到第一个问号；没有问号的到下一个念题 / 段标题为止"""
    st = {}
    for m in re.finditer(r'\b[Qq]uestion (' + NUMRE + r')\b[.:,]?\s+(?!(?:and|to) )', text):
        num = m.group(1).replace(' ', '-').lower()
        num = int(num) if num.isdigit() else NUMW.get(num)
        rest = text[m.end():]
        e = re.search(STOPRE, rest)
        body = rest[:e.start()] if e else rest
        q = body.find('?')
        body = body[:q + 1] if q >= 0 else body
        if num and num not in st: st[num] = (m.start(), body.strip())
    return st


_CI = {}


def instr_junk(v):
    """OCR 残损（202206-1 说明“ne^s reports”“o f each”、选项“far m”“.dogs”“ ,to”“impracticable .”逐词查不出——都被切成“认识的词”）：
    字母之间夹符号；单个小写字母成词（a、i、数字后的 s 除外；大写单字母是缩写 U.S.、360°C）；标点前有空格；词首贴着 . ,"""
    j = re.findall(r'[A-Za-z][\^~|\\{}<>@#*_=+`][A-Za-z]', v)
    j += [m.group(0) for m in re.finditer(r'(?<![A-Za-z0-9’\'-])[b-hj-z](?![A-Za-z’\')-])', v)]
    j += re.findall(r'\S\s+[,.;:?!]', v) + re.findall(r'(?:^|\s)[.,][A-Za-z]+', v)
    return j


def clean_instr(sec):
    """所有试卷里这一节说明的干净版本（每个词都认识、以 centre. 结尾）"""
    if sec not in _CI:
        out = set()
        for f in sorted((H / '试卷').glob('*.txt')):
            v = parse_options(f.read_text('utf-8'))[1].get(sec)
            if v:
                v = re.sub(r'\s+([.,])', r'\1', v); e = re.search(r'cent(?:re|er)\.', v); v = v[:e.end()] if e else v
                if re.search(r'cent(?:re|er)\.$', v) and not re.search(r'[^\x20-\x7e]', v) and not instr_junk(v) and all(w.lower() in DICT or w in ('A', 'B', 'C', 'D') or w.isdigit()
                        for w in re.findall(r"[A-Za-z]+|\d+", v.replace("'ll", ''))):
                    out.add(v)
        _CI[sec] = sorted(out)
    return _CI[sec]


def run(sid, quiet=False, words=None, Qover=None):
    sd = H / sid
    bad, notes = [], []
    Q, instr = parse_options(paper_txt(sid))
    if Qover: Q = Qover
    if (sd / '选项.json').exists():
        raw = re.sub(r'\s+', ' ', paper_txt(sid)).lower()
        fixd = json.loads((sd / '选项.json').read_text('utf-8'))
        for k, v in fixd.items():
            if k.startswith('_'): continue
            Q[int(k)] = dict(zip('ABCD', v))
            for c, o in zip('ABCD', v):
                ol = o.lower().replace('’', "'")
                rw = raw.replace('’', "'")
                best = max((difflib.SequenceMatcher(None, ol, rw[max(0, m.start() - ol.find(lw) + d): m.start() - ol.find(lw) + d + len(ol)]).ratio()
                            for lw in {w.strip(".,?!'") for w in ol.split() if len(w.strip(".,?!'")) >= 3}
                            for m in re.finditer(re.escape(lw), rw) for d in (-3, 0, 3)), default=0)
                if best < 0.8 and f'{k}{c}' not in fixd.get('_核图', []): bad.append(f'第 {k} 题 {c} 选项「{o}」在试卷文字里找不到相近的（{best:.2f}）')
    if words is None:
        wl = [w[0] for w in json.loads((sd / '定稿.json').read_text('utf-8'))['词']]
    else:
        wl = words
    vocab = set(nz(' '.join(wl)))

    def known(w):
        w = w.lower().replace('’', "'").strip("'")
        cands = {w, re.sub(r"'s$", '', w), w.rstrip('s'), re.sub(r'(ed|ing|er|ers)$', '', w), w[:-1], re.sub(r'^(re|un|over|non)', '', w)}
        cands |= {re.sub(r'^(re|un)', '', c) for c in list(cands)}
        for a, b in ((r'our', 'or'), (r'is(e|ed|es|ing)$', r'iz\1'), (r'tre$', 'ter'), (r'lling$', 'ling'), (r'elled$', 'eled'), (r'ising$', 'izing')):
            cands.add(re.sub(a, b, w))
        if any(c in DICT or c in vocab or c in PRINTED for c in cands): return True
        if "'" in w and w.split("'")[0] in DICT | {'didn', 'doesn', 'don', 'couldn', 'wouldn', 'isn', 'aren', 'wasn', 'weren', 'shouldn', 'haven', 'hasn', 'won', 'can'}: return True
        return any(w[:k] in DICT and w[k:] in DICT and k >= 3 and len(w) - k >= 3 for k in range(3, len(w) - 2))     # 复合词 bushfire / wellbeing

    def clean(o):
        """选项文字像不像真的：每个词是词典词（含英式拼写、复合词）/ 本套原文里出现过；返回不认识的词"""
        if re.search(r'[^\x20-\x7e’‘“”—–é°£Ⅰ]|[·]|[a-z][.:][a-z]{2,}|[a-z]\.[A-Z][a-z]|\d[A-Za-z]{3,}|[a-z]\d', o): return ['（有乱码字符）']
        ws = re.findall(r"[A-Za-z’']+(?:-[A-Za-z]+)*", o)
        return [w for k, w in enumerate(ws) if not (all(known(x) for x in w.split('-') if x) or (k > 0 and w[0].isupper()))]      # 句中大写 = 人名
    # 第二来源逐个比；第一来源缺 / 有不认识的词、第二来源干净 → 用第二来源（记下）
    t2, f2 = second_txt(sid)
    fixed2 = []
    if t2:
        Q2, _ = parse_options(t2)
        nd = 0
        for q in range(1, 26):
            for c in 'ABCD':
                a, b = Q.get(q, {}).get(c, ''), Q2.get(q, {}).get(c, '')
                if not b: continue
                if (not a or clean(a)) and not clean(b) and not re.search(r'\b[A-D]\)', b):
                    Q.setdefault(q, {})[c] = b; fixed2.append(f'{q}{c}'); nd += 1; continue
                r = difflib.SequenceMatcher(None, ' '.join(nz(a)), ' '.join(nz(b))).ratio()
                if r < 0.9 and not re.search(r'\b[A-D]\)', b): bad.append(f'第 {q} 题 {c} 两个来源不同：「{a}」 / {f2}「{b}」（{r:.2f}）')
                else: nd += 1
        notes.append(f'选项第二来源 {f2}：{nd}/100 一致' + (f'（第一来源坏了改用第二来源：{fixed2}）' if fixed2 else ''))
        if nd < 60: bad.append(f'第二来源只比上 {nd}/100 个选项')
    else:
        notes.append('选项只有一个来源（第二来源：内容配对 + 子代理做题）')
    for q in range(1, 26):
        for c in 'ABCD':
            u = clean(Q.get(q, {}).get(c, '')) + instr_junk(Q.get(q, {}).get(c, ''))
            if u: bad.append(f'第 {q} 题 {c} 选项有不认识的词 {u}：「{Q[q][c]}」')
    save = words is None
    if words is None:
        words = [w[0] for w in json.loads((sd / '定稿.json').read_text('utf-8'))['词']]
    text = ' '.join(words)
    st = stems_from(text)
    order = [st[q][0] for q in range(1, 26) if q in st]
    if order != sorted(order): bad.append('念题顺序与题号不一致：' + str([q for q in range(1, 26) if q in st]))
    blocks = jx_blocks(sid)
    cols = col_answers(sid)
    rule = json.loads((sd / '答案裁定.json').read_text('utf-8')) if (sd / '答案裁定.json').exists() else {}
    out, prog = [], {}
    for n in range(1, 26):
        o = Q.get(n, {})
        if sorted(o) != list('ABCD'): bad.append(f'第 {n} 题选项 {sorted(o)}'); o = {c: o.get(c, '') for c in 'ABCD'}
        if any(not o[c].strip() for c in 'ABCD'): bad.append(f'第 {n} 题有空选项')
        stem = rule.get('题干', {}).get(str(n)) or (st[n][1] if n in st else '')
        if not stem: bad.append(f'第 {n} 题题干（念题）找不到')
        js = jx_stem(blocks.get(n, ''))
        if stem and js and nz(js) != nz(stem) and n not in rule.get('题干已核', []):
            diff = set(nz(js)) ^ set(nz(stem))
            if (set(nz(js)) - set(nz(stem))) and len(diff) <= 4 and all(len(w) > 1 and w in DICT for w in set(nz(js)) - set(nz(stem))):
                bad.append(f'第 {n} 题题干 解析「{js}」≠ 念题「{stem}」（{sorted(diff)}）')
        if stem and not stem.endswith('?'): stem = re.sub(r'[.,;:]?\s*$', '?', stem)
        if stem and len(stem.split()) > 40: bad.append(f'第 {n} 题题干 {len(stem.split())} 词，截进了后面的录音：{stem[:80]}…')
        prog[n] = cols.get(n) or judge(blocks.get(n, ''))
        ans = str(rule.get(str(n), ''))
        ans = ans if len(ans) == 1 and ans in 'ABCD' else ''
        if not ans: bad.append(f'第 {n} 题答案没有裁定（答案裁定.json）')
        out.append([stem, [o[c] for c in 'ABCD'], ans])
    # 内容配对：每段原文 = 上一段“Questions … based on”之后到本段“Questions … based on”
    marks = [m.start() for m in re.finditer(r'Questions? ' + NUMRE + r',? (?:and|to) ' + NUMRE + r',? (?:are|is) based', text, re.I)]
    if len(marks) != 8: bad.append(f'“Questions … are based on” 找到 {len(marks)} 处（应 8）')
    score = []
    for b, (q1, q2) in enumerate(SEC):
        if len(marks) != 8: break
        seg = toks(text[(marks[b - 1] if b else 0):marks[b]])
        for q in range(q1, q2 + 1):
            w = set().union(*(toks(x) for x in out[q - 1][1]))
            score.append(round(len(w & seg) / max(len(w), 1), 2))
    med = sorted(score)[len(score) // 2] if score else 0
    if med < 0.3: bad.append(f'选项实词在本段原文里出现的比例中位数 {med}（< 0.3，可能配错套 / 错位）：{score}')
    for k, v in list(instr.items()):        # OCR 脏的说明：换成别的试卷里最接近的干净版本（四级说明各年只有几种措辞），相似度 ≥ 0.85
        if v and (clean(v) or instr_junk(v) or not re.search(r'cent(?:re|er)\.$', v)):
            cands = clean_instr(k)
            best = max(cands, key=lambda c: difflib.SequenceMatcher(None, c, v).ratio(), default=None)
            r = difflib.SequenceMatcher(None, best, v).ratio() if best else 0
            if r >= 0.85: instr[k] = best; notes.append(f'说明 {k} OCR 脏，换成干净版本（{r:.2f}）')
    for k, v in instr.items():
        if v and (clean(v) or instr_junk(v) or not re.search(r'cent(?:re|er)\.$', v)): bad.append(f'说明 {k} 有不认识的词 {clean(v) + instr_junk(v)} 或结尾不对：…{v[-40:]}')
    if any(v is None for v in instr.values()): bad.append(f'说明缺 {[k for k, v in instr.items() if v is None]}')
    res = {'说明': instr, 'sections': SEC, 'questions': out, '答案_程序': prog, '内容配对': score, '备注': notes}
    if save and Qover is None:
        (sd / '题目.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), 'utf-8')
    if not quiet:
        print(sid, f'内容配对中位数 {med}', '程序抽答案', ''.join(prog[n] or '?' for n in range(1, 26)), '|', '；'.join(notes))
        for b in bad: print('  ', b)
    return bad, res


if __name__ == '__main__':
    ids = sys.argv[1:]
    if ids == ['ALL']: ids = sorted(json.loads((H / '对照.json').read_text('utf-8'))['choice'])
    nb = 0
    for s in ids:
        b, _ = run(s); nb += len(b)
    print(f'合计 {nb} 处')
    sys.exit(1 if nb else 0)
