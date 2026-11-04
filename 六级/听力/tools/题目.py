"""六级听力题目：25 题 × [题干, [A, B, C, D], 答案]。
  · 选项：试卷文字（2021-06 起用仓库 六级/真题/<年>/<年月>/… 第N套.txt，已校对；更早的用 Release 里试卷 PDF 的文字层，存成 <套>/试卷.txt 后人工核过）
  · 题干：定稿.json 里念题那句（Question N: …?）
  · 答案：解析原文每题讲解里“由此可知 / 故 / 因此 … X项”；交叉核对：解析原文 [n] 标出的答案句与四个选项比用词重合，
    抽到的答案不是重合最高的就列出（人看原图后登记 <套>/答案裁定.json {"题号": "字母"}）
  · 说明（Directions）：试卷文字
出错（不是 25 题、选项不是 4 个、题干缺、答案缺或待核）一律列全、退出码 1。
用法：python 题目.py <套号>     输出 <套>/题目.json
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE.parent
ROOT = HERE.parents[2]
SEC = [(1, 4), (5, 8), (9, 11), (12, 15), (16, 18), (19, 21), (22, 25)]      # 六级听力固定 7 段
STOP = set('the a an of to and in is for on that what does do did be by with as it at from are was this his her their its about'.split())


def paper_txt(sid):
    y, m, k = sid[:4], sid[4:6], sid[-1]
    f = ROOT / '六级/真题' / y / f'{y}年{m}月' / f'{y}年{int(m)}月 英语六级真题 第{k}套.txt'
    if f.exists(): return f.read_text('utf-8')
    f = D / sid / '试卷.txt'
    if f.exists(): return f.read_text('utf-8')
    sys.exit(f'停止：{sid} 没有试卷文字（{f}）')


def parse_options(txt):
    i = txt.find('Listening Comprehension')
    part = txt[i if i >= 0 else txt.index('Section A'):]          # 扫描版 OCR 标题可能是乱码（Li&iening）
    part = part[:re.search(r'Part\s*(III|Ⅲ)\b|Reading\s*Comprehension', part).start()]
    # 扫描版 OCR：“1 7 . A)”“8 . A)”“C ) They”
    part = '\n'.join(re.sub(r'\b([A-D])\s+\)', r'\1)', re.sub(r'^(\s*\d{1,2})\s+\.', r'\1.', re.sub(r'^(\s*)(\d)\s(\d)\s*\.', r'\1\2\3.', ln)))
                     for ln in part.splitlines())
    instr = {}
    for s in 'ABC':
        m = re.search(rf'Section {s}\s*\n\s*Directions\s*:(.*?)(?=\n\s*(Questions|Conversation|Passage|Recording|1\.))', part, re.S)
        instr[s] = re.sub(r'\s+', ' ', 'Directions:' + m.group(1)).strip() if m else None
    Q = {}
    cur = None
    for line in part.splitlines():
        line = line.replace('\f', '')
        if 'burningvocabulary' in line or re.fullmatch(r'\s*\d*\s*', line): continue     # 页脚、分页
        m = re.match(r'\s*(\d{1,2})\.\s+(.*)', line)
        if m and 1 <= int(m.group(1)) <= 25 and re.match(r'A[.)]', m.group(2)):
            cur = int(m.group(1)); Q[cur] = {}; line = m.group(2)
        if re.match(r'\s*(Questions|Section|Directions|Part)\b', line): cur = None
        if cur is None: continue
        for c in re.split(r'\s{3,}', line.strip()):
            mm = re.match(r'([A-D])[.)]\s*(.*)', c)
            if mm: Q[cur][mm.group(1)] = mm.group(2).strip(); last = mm.group(1)
            elif c and Q[cur] and not re.search(r'[.?!]$', Q[cur][last]): Q[cur][last] += ' ' + c.strip()      # 选项折行（上一行没写完才接）
            elif c: cur = None; break
    return Q, instr


def ocr_stem(ocr, n):
    """解析里第 n 题的英文题干：行首“n. What …”，跨行接到问号为止，遇到中文停"""
    m = re.search(rf'(?m)^\s*{n}\s*[.．]\s*([A-Z][^\u4e00-\u9fff]*?\?)', ocr) or \
        re.search(rf'(?m)^\s*{n}\s*[.．]\s*([A-Z][^\u4e00-\u9fff?]*\n(?:\s*\n)*[^\u4e00-\u9fff?]*\?)', ocr)
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''


def judge(blk):
    """讲解段 → 答案字母：句子里说正确 / 相符 / 答案为的字母是肯定，说排除 / 不符 / 无中生有的是否定"""
    blk = re.sub(r'[A-D]\)', '', blk)                       # 去掉选项列表本身
    blk = re.sub(r'[A-Za-z]{2,}', ' ', blk)                   # 去掉英文单词（里面的大写字母不是选项）
    pos, neg = set(), set()
    for sen in re.split(r'[。；]', blk):
        ls = set(re.findall(r'[A-D]', sen))
        if not ls: continue
        if re.search(r'排除|不符|不正确|错误|无中生有|未提及|曲解|偷换|干扰', sen): neg |= ls
        elif re.search(r'正确|相符|答案|符合|吻合|一致|对应|故|由此|可知|因此', sen): pos |= ls
    pos -= neg if len(pos - neg) == 1 else set()
    if len(pos) == 1: return pos.pop()
    rest = set('ABCD') - neg
    return rest.pop() if not pos and len(rest) == 1 else ''
                       

def toks(s):
    return {w for w in re.findall(r"[a-z]+", s.lower()) if w not in STOP and len(w) > 2}


def run(sid):
    sd = D / sid
    bad = []
    Q, instr = parse_options(paper_txt(sid))
    words = [w[0] for w in json.loads((sd / '定稿.json').read_text('utf-8'))['词']]
    text = ' '.join(words)
    stems = {}
    for m in re.finditer(r'[Qq]uestion (\d{1,2}|[a-z]+(?:-[a-z]+)?)[.:,]?\s+(.*?[?.])(?=\s+(?:[Qq]uestions?\b|Section|Passage|Recording|Conversation|That.s the end|$))', text):
        num = m.group(1)
        num = int(num) if num.isdigit() else {w: i + 1 for i, w in enumerate('one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty twenty-one twenty-two twenty-three twenty-four twenty-five'.split())}.get(num.lower())
        if num and num not in stems: stems[num] = m.group(2).strip()
    ocr = (sd / '解析原文.txt').read_text('utf-8')
    flat = re.sub(r'\s+', '', ocr)
    # 讲解段：题号 + 英文题干开头 → 下一题
    starts = []
    for n in range(1, 26):
        m = re.search(rf'(?<![\d\[]){n}[.．](?=What|Why|How|Who|Which|When|Where|According|In|Accor)', flat[starts[-1][1] if starts else 0:])
        starts.append((n, (starts[-1][1] if starts else 0) + m.start()) if m else (n, starts[-1][1] if starts else 0))
    rule = json.loads((sd / '答案裁定.json').read_text('utf-8')) if (sd / '答案裁定.json').exists() else {}
    # [n] 答案句
    raw = re.sub(r'\s+', ' ', ocr)
    marks = {}
    for m in re.finditer(r'\[(\d{1,2})\](.{0,400}?)(?=\[\d{1,2}\]|$)', raw):
        marks.setdefault(int(m.group(1)), '')
        marks[int(m.group(1))] += ' ' + re.sub(r'[一-鿿].*', '', m.group(2))
    out, review = [], []
    for i, (n, p) in enumerate(starts):
        o = Q.get(n, {})
        if sorted(o) != list('ABCD'): bad.append(f'第 {n} 题选项 {sorted(o)}'); continue
        js = ocr_stem(ocr, n)
        nz = lambda x: re.sub(r'[^a-z0-9]', '', x.lower())
        if not js: bad.append(f'第 {n} 题题干（解析）找不到')
        elif n not in stems: bad.append(f'第 {n} 题题干（念题）找不到')
        elif nz(js) != nz(stems[n]) and str(n) not in rule.get('题干', {}):
            bad.append(f'第 {n} 题题干 解析「{js}」≠ 念题「{stems[n]}」')
        stems[n] = rule.get('题干', {}).get(str(n), js or stems.get(n, ''))
        blk = flat[p:starts[i + 1][1]] if i + 1 < len(starts) else flat[p:p + 1500]
        m = judge(blk)
        ans = str(rule.get(str(n), m))
        ans = ans if ans in 'ABCD' else ''
        sc = {c: len(toks(o[c]) & toks(marks.get(n, ''))) for c in 'ABCD'}
        best = max(sc.values())
        if not ans: bad.append(f'第 {n} 题答案找不到')
        elif str(n) not in rule and best > 0 and sc[ans] < best:
            review.append(f'第 {n} 题 抽到 {ans}，答案句重合 {sc}：[{n}]{marks.get(n, "")[:120]}')
        out.append([stems.get(n, ''), [o[c] for c in 'ABCD'], ans])
    if len(out) != 25: bad.append(f'题数 {len(out)}')
    # 套与音频按内容核（协调会话审 4）：每题 4 个选项的实词在本段原文里出现的比例；配错套时整套接近 0
    blk_txt = {}
    for b, (q1, q2) in enumerate(SEC):
        lo = text.find(f'Questions {q1} to') if b == 0 else text.find(f'Questions {SEC[b - 1][0]} to')
        hi = text.find(f'Questions {q1} to')
        blk_txt[b] = toks(text[max(lo, 0) if b else 0:hi if hi > 0 else None])
    score = []
    for b, (q1, q2) in enumerate(SEC):
        for q in range(q1, min(q2, len(out)) + 1):
            w = set().union(*(toks(x) for x in out[q - 1][1]))
            score.append(round(len(w & blk_txt[b]) / max(len(w), 1), 2))
    med = sorted(score)[len(score) // 2] if score else 0
    if med < 0.3: bad.append(f'选项实词在原文里出现的比例中位数 {med}（< 0.3，可能配错套）：{score}')
    bad += [f'待核答案 {r}' for r in review]
    if any(v is None for v in instr.values()): bad.append(f'说明缺 {instr}')
    (sd / '题目.json').write_text(json.dumps({'说明': {k: v for k, v in instr.items()}, 'sections': SEC, 'questions': out},
                                            ensure_ascii=False, indent=1), 'utf-8')
    print(sid, f'内容配对中位数 {med}', '25 题' if not bad else '', f'{sum(1 for q in out if q[2])} 个答案', ''.join(q[2] for q in out))
    for b in bad: print('  ', b)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(run(sys.argv[1]))
