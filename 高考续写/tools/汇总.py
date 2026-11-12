"""读后续写汇总：读 extract.py 的 found.json → 定来源 → 按开头语去重 → 检查 → 写 json / md。
用法: python3 -I 汇总.py found.json 输出目录"""
import sys, os, re, json, difflib, collections

FOUND, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
# 人工补录（扫描件 OCR 校对后的题目、来源修正），见 补录.json
PATCH = json.load(open(os.path.join(HERE, '补录.json'))) if os.path.exists(os.path.join(HERE, '补录.json')) else {}

NUM = {'1': 'Ⅰ', '一': 'Ⅰ', 'Ⅰ': 'Ⅰ', 'I': 'Ⅰ', '2': 'Ⅱ', '二': 'Ⅱ', 'Ⅱ': 'Ⅱ', 'II': 'Ⅱ'}

def source(path):
    """按文件路径定来源。返回 (年份, 考试全称, 类别, 适用省份, 排序键) 或 None（不认识就报错）。"""
    p = path.replace('（', '(').replace('）', ')')
    fn = os.path.basename(p)
    m = re.search(r'(20\d\d)年(?:高考英语试卷|全国高考|高考全国|浙江省)', fn) or re.search(r'(20\d\d)年', fn)
    y = int(m.group(1)) if m else None
    gk = '普通高等学校招生全国统一考试'
    if re.search(r'高考英语真题/', p) and y:
        m = re.search(r'新高考(Ⅰ|Ⅱ)卷|新课标(Ⅰ|Ⅱ)卷|全国(一|二|1|2)卷|高考(一|二)卷', fn)
        if m:
            n = NUM[next(g for g in m.groups() if g)]
            name = ('新高考' if y <= 2022 else '新课标') + n + '卷'
            prov = ''
            m2 = re.search(r'\((山东|海南)\)', fn)
            if m2:
                prov = m2.group(1)
            return y, f'{y}年{gk}（{name}）', '高考', prov, (y, 1 if n == 'Ⅰ' else 2)
        m = re.search(r'浙江\)?\(?(1|6|7)月|浙江省(1)月', fn)
        if m:
            mo = m.group(1) or m.group(2)
            return y, f'{y}年{mo}月浙江省普通高校招生考试（浙江卷·{mo}月）', '高考', '浙江', (y, 3 if mo == '1' else 4)
    if '九省联考' in p and '2024' in p:
        return 2024, '2024年1月九省联考（普通高等学校招生全国统一考试适应性测试，2024届）', '九省联考', '', (2024, 5)
    if re.search(r'2025年1月.*适应性测试.*八省联考|2025.1.3-八省联考|八省联考\(2\)', p):
        return 2025, '2025年1月八省联考（普通高等学校招生全国统一考试适应性测试，2025届）', 'T8联考', '云南、内蒙古、四川、河南、陕西、山西、宁夏、青海', (2025, 5)
    if re.search(r'2021年1月.*八省联考', p):
        return 2021, '2021年1月八省联考（普通高等学校招生全国统一考试适应性测试，2021届）', 'T8联考', '', (2021, 5)
    if 'T8' in p:
        for pat, y, name in [
            (r'2021-2022学年.*第一次联考', 2022, '2022届八省八校T8联考 高三第一次联考（2021—2022学年上学期）'),
            (r'2023届高三T8联考', 2023, '2023届八省八校T8联考 高三第一次学业质量评价'),
            (r'2024届.*第一次学业质量评价', 2024, '2024届八省八校T8联考 高三第一次学业质量评价'),
            (r'2024届.*第二次学业质量评价', 2024, '2024届八省八校T8联考 高三第二次学业质量评价（2024年3月）'),
            (r'2025届高三(第一次|12月)|2025届高三T8联考12月', 2025, '2025届八省八校T8联考 高三第一次联考（2024年12月）'),
            (r'2026届', 2026, '2026届八省八校T8联考 高三12月检测训练（2025年12月）'),
        ]:
            if re.search(pat, p):
                return y, name, 'T8联考', '', (y, 6)
    if path in PATCH.get('来源', {}):
        s = PATCH['来源'][path]
        return s['年份'], s['考试'], s['类别'].replace('其他（T8 等联考）', 'T8联考'), s.get('省份', ''), (s['年份'], s.get('序', 7))
    return None

def key(s):
    return re.sub(r'[^a-z]', '', s.lower())

def same(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio() > 0.85

def wc(s):
    return len(re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", s))

found = json.load(open(FOUND))
for p, hit in PATCH.get('题目', {}).items():
    for o in found:
        if o['path'] == p:
            o['hit'] = hit
problems, unknown = [], []
items = []
for o in found:
    h = o['hit']
    if not h:
        continue
    src = source(o['path'])
    if 'error' in h or len(h.get('openings') or []) != 2:
        items.append(dict(o, src=src, bad=True))
        continue
    items.append(dict(o, src=src, bad=False, k=key(h['openings'][0])[:60] + '|' + key(h['openings'][1])[:60]))

# 按开头语聚类
groups = []
for it in [i for i in items if not i['bad']]:
    for g in groups:
        if same(g[0]['k'], it['k']):
            g.append(it); break
    else:
        groups.append([it])
# 开头语抽不出的文件，只要同一来源已有完整的版本就并进去，否则单独成组报问题
for it in [i for i in items if i['bad']]:
    g = next((g for g in groups if it['src'] and any(x['src'] and x['src'][1] == it['src'][1] for x in g)), None)
    if g:
        g.append(it)
    else:
        groups.append([it])

def ocr_err(x):
    """OCR 质量粗估：句号认成逗号（“, For”）、开头语以逗号结尾、乱码字符。非 OCR 记 0。"""
    if not x['hit'].get('ocr'):
        return 0
    p = ' '.join(x['hit']['passage'])
    return len(re.findall(r', [A-Z]', p)) + 5 * sum(o.endswith(',') for o in x['hit']['openings']) + p.count('�')

def best(g, want):
    """挑代表：原文挑段数多、非 OCR 的；范文挑有范文的解析卷。"""
    ok = [x for x in g if not x['bad']]
    if want == 'essay':
        c = [x for x in ok if x['hit'].get('essay')]
        c.sort(key=lambda x: (bool(x['hit'].get('ocr')), x['path'].endswith('.pdf'), -wc(' '.join(x['hit']['essay']))))
        return c[0] if c else None
    ok.sort(key=lambda x: (bool(x['hit'].get('ocr')), ocr_err(x), x['path'].endswith('.pdf'), '解析' in x['path'] or '答案' in x['path'], len(x['path'])))
    return ok[0] if ok else None

recs = []
verify = list(PATCH.get('需核实', []))
for g in groups:
    known = [x['src'] for x in g if x['src']]
    for x in g:
        if not x['src']:
            if known:
                x['src'] = sorted(known, key=lambda s: s[4])[0]
                x['src_by'] = 'content'
                verify.append(f"按内容归入（文件名/路径认不出或不符）：{x['path']} → {x['src'][1]}")
            else:
                unknown.append(x['path'])
    if any(not x['src'] for x in g):
        continue
    srcs = sorted({x['src'] for x in g}, key=lambda s: s[4])
    rep, es = best(g, 'text'), best(g, 'essay')
    note = ''
    if rep is None:
        sup = [x for x in g if x['path'] in PATCH.get('补开头语', {})]
        if sup:
            x = sup[0]
            x['hit'] = dict(x['hit'], openings=PATCH['补开头语'][x['path']]['开头语'])
            x['bad'] = False
            rep = x
            note = PATCH['补开头语'][x['path']]['备注']
    if rep is None:
        known = [x for x in g if x['path'] in PATCH.get('已知缺开头语', {})]
        if not known or 'error' in known[0]['hit']:
            problems.append(f"{srcs[0][1]}：没有一个文件抽得出两段开头语（{g[0]['path']}）")
            continue
        rep = known[0]
        note = PATCH['已知缺开头语'][rep['path']]
        verify.append(f"{srcs[0][1]}：{note}")
    h = dict(rep['hit'])
    fix = PATCH.get('校对', {}).get(rep['path'], {})
    h['openings'] = [fix.get(o, o) for o in h['openings']]
    h['passage'] = [fix.get(x, x) for x in h['passage']]
    if h.get('ocr'):
        note = (note + '；' if note else '') + '题目由扫描件 OCR 识别，个别字词（尤其括号里的中文注释）可能有误，需对照原卷' + ('；开头语已人工校对' if fix else '')
        verify.append(f"{srcs[0][1]}：题目只有扫描件，OCR 识别（{rep['path']}），需对照原卷校字")
    cats = sorted({s[2] for s in srcs})
    exams = [{'考试': s[1], '年份': s[0], '类别': s[2], '适用省份': s[3]} for s in srcs]
    recs.append({
        '编号': None,
        '年份': srcs[0][0],
        '来源': srcs[0][1] if len(srcs) == 1 else '；'.join(s[1] for s in srcs),
        '类别': cats[0] if len(cats) == 1 else '/'.join(cats),
        '试卷': exams,
        '题号': h.get('qno') or next((x['hit'].get('qno') for x in g if not x['bad'] and x['hit'].get('qno')), None),
        '分值': h.get('score') or next((x['hit'].get('score') for x in g if not x['bad'] and x['hit'].get('score')), None),
        '说明': h['instr'],
        '原文': h['passage'],
        '注意': h['note'],
        '开头语': h['openings'],
        '原文首句': re.split(r'(?<=[.!?])\s', h['passage'][0] if h['passage'] else '')[0],
        '原文词数': wc(' '.join(h['passage'])),
        '范文': es['hit']['essay'] if es else None,
        '范文来源': es['path'] if es else None,
        '题目来源文件': rep['path'],
        '备注': note,
        '原始文件': sorted({x['path'] for x in g}),
        '卷首标题': sorted({x['title'] for x in g if x['title']}),
    })
def is_en(x, k=4):
    return len(re.findall(r"[A-Za-z]+", x)) >= k and len(re.findall(r'[\u4e00-\u9fff]', x)) <= 2

def locate(text, op, start=0):
    w = re.findall(r"[A-Za-z]+", op)
    for a in range(0, max(1, len(w) - 3)):
        pat = r'[^A-Za-z]{0,6}'.join(map(re.escape, w[a:a + 4]))
        m = re.compile(pat, re.I).search(text, start)
        if m:
            # 往回退到这一句的开头（a 个词）
            st = m.start()
            if a:
                back = re.search(r'(?:[A-Za-z]+[^A-Za-z]{1,6}){%d}$' % a, text[max(0, st - 120):st])
                st = st - len(back.group(0)) if back else st
            return st, m.end()
    return -1, -1

def essay_in(text, ops):
    """在答案文本里找“开头语 1 … 开头语 2 …”：两句之间至少 40 个英文词（题目里两句之间只有横线）。"""
    pos = 0
    while True:
        a, a_end = locate(text, ops[0], pos)
        if a < 0:
            return None
        b, _ = locate(text, ops[1], a_end)
        if b < 0:
            return None
        p1 = text[a:b]
        if wc(p1) >= 40 and b - a < 4000:
            lines = text[b:].split('\n')
            p2 = [lines[0]]
            for l in lines[1:]:
                if l.strip() and not is_en(l, 3):
                    break
                p2.append(l)
            p2 = ' '.join(x.strip() for x in p2 if x.strip())
            p1 = ' '.join(x.strip() for x in p1.split('\n') if x.strip() and not re.fullmatch(r'[_\s]+', x))
            p2 = re.sub(r'\s*\S{0,6}\s*(第\s*)?\d+\s*页.*$', '', p2)
            if a and text[a - 1] in '“"':
                p1 = text[a - 1] + p1
            return [p1, p2] if wc(p2) >= 30 else None
        pos = a_end

bydir = collections.defaultdict(list)
for o in found:
    bydir[os.path.dirname(o['path'])].append(o)
for r in recs:
    if r['范文'] or len(r['开头语']) != 2:
        continue
    cands = []
    for pth in r['原始文件']:
        cands += bydir[os.path.dirname(pth)]
    for o in sorted({id(o): o for o in cands}.values(), key=lambda o: ('答案' not in o['path'], o['path'])):
        e = essay_in(o.get('tail') or '', r['开头语'])
        if e:
            r['范文'], r['范文来源'] = e, o['path']
            if o['path'] not in r['原始文件']:
                r['原始文件'].append(o['path'])
            break

recs.sort(key=lambda r: (-r['年份'], min(e['年份'] * 0 + s for e in r['试卷'] for s in [0]), r['来源']))
order = {'高考': 0, 'T8联考': 1, '九省联考': 2}
# 标题、原卷标题、考试年月；OCR 错字校对
def short(full):
    m = re.search(r'（((?:新高考|新课标)[ⅠⅡ]卷)）', full)
    if m:
        return m.group(1)
    m = re.search(r'浙江卷·(\d+)月', full)
    return f'浙江卷（{m.group(1)}月）' if m else full

def fixtext(x):
    for a, b in PATCH.get('OCR校对', []):
        x = x.replace(a, b)
    return re.sub(r'\(\s*([\u4e00-\u9fff，、]+)\s*\)', r'(\1)', x)

for r in recs:
    t8 = PATCH.get('T8标题', {}).get(r['来源'])
    if t8:
        r['标题'], r['原卷标题'] = t8['标题'], t8['原卷标题']
        r['年份'], r['考试月份'] = t8['年'], t8['月']
    else:
        if r['类别'] != '高考':
            problems.append(f"{r['来源']}：联考没有登记统一标题（补录.json 的 T8标题）")
        r['标题'] = f"{r['年份']}年 " + '；'.join(short(e['考试']) for e in r['试卷'])
        r['原卷标题'] = '；'.join(e['考试'] for e in r['试卷'])
        r['考试月份'] = 1 if '1月' in r['标题'] else 6
    for k in ('原文', '开头语'):
        r[k] = [fixtext(x) for x in r[k]]
    # 英文里夹的全角标点改半角（中文注释不动）
    en0 = lambda x: re.sub(r'．\s*$', '.', re.sub(r'(?<=[A-Za-z])．(?=[a-z])', ', ', x))
    en1 = lambda x: re.sub(r'(?<=[A-Za-z0-9’”"])\s*([．，；：])\s*(?=[A-Za-z“"‘$])', lambda m: {'．': '. ', '，': ', ', '；': '; ', '：': ': '}[m.group(1)], x)
    en = lambda x: en1(en0(x))
    r['原文'] = [en(x) for x in r['原文'] if not (re.search('英语试题|试卷第|第.{0,3}页', x) and len(x) < 40)]
    r['开头语'] = [en(x) for x in r['开头语']]
    if r['范文']:
        r['范文'] = [en(x) for x in r['范文']]
    merged = []  # 换页处被拆开的段落接回去：上一段没以句末标点结束，下一段小写开头、或上一段以小写词 / 逗号结尾
    for x in r['原文']:
        if merged and len(merged[-1].split()) > 8 and not re.search(r'[.!?"”’)]\s*$', merged[-1]) and (re.match(r'[a-z]', x) or re.search(r'[a-z,]\s*$', merged[-1])):
            merged[-1] += ' ' + x
        else:
            merged.append(x)
    r['原文'] = merged
    if r['范文']:
        r['范文'] = [fixtext(x) for x in r['范文']]
    r['原文首句'] = fixtext(r['原文首句'])
recs.sort(key=lambda r: (-r['年份'], order.get(r['类别'], 3), -r['考试月份'], r['来源']))
for i, r in enumerate(recs, 1):
    r['编号'] = i

# ---------- 检查（全部列出，一次查完） ----------
for r in recs:
    tag = f"#{r['编号']} {r['来源']}"
    if not r['原文'] or r['原文词数'] < 150:
        problems.append(f'{tag}：原文过短（{r["原文词数"]} 词）')
    if r['备注'] and not r['开头语']:
        continue
    if len(r['开头语']) != 2 or any(wc(o) < 3 for o in r['开头语']):
        problems.append(f'{tag}：开头语不是两句')
    body = key(' '.join(r['原文']))
    for o in r['开头语']:
        if key(o) and key(o) in body:
            problems.append(f'{tag}：开头语与原文重复：{o}')
    if not r['年份'] or not r['来源']:
        problems.append(f'{tag}：年份或来源为空')
    if r['范文'] and (len(r['范文']) != 2 or not same(key(r['范文'][1][:len(r['开头语'][1]) + 5])[:40], key(r['开头语'][1])[:40])):
        problems.append(f'{tag}：范文第二段开头与开头语对不上')
covered = {p for r in recs for p in r['原始文件']}
dirs = {}
for r in recs:
    for q in r['原始文件']:
        dirs.setdefault(os.path.dirname(q), r)
for o in found:
    if o.get('mention') and o['path'] not in covered and os.path.dirname(o['path']) in dirs:
        r = dirs[os.path.dirname(o['path'])]
        r.setdefault('同套其他文件', []).append(o['path'])
        covered.add(o['path'])
for o in found:
    if o.get('mention') and o['path'] not in covered:
        verify.append(f"含“续写”字样、没抽出题目（多为只有答案或只提到续写）：{o['path']}")
for u in unknown:
    problems.append(f'认不出来源（没有规则）：{u}')
ks = [''.join(r['开头语']) or r['来源'] for r in recs]
for i in range(len(recs)):
    for j in range(i + 1, len(recs)):
        if same(key(ks[i]), key(ks[j])):
            problems.append(f"#{recs[i]['编号']} 与 #{recs[j]['编号']} 开头语相同却没合并")

for r in recs:
    for t in r['卷首标题']:
        ys = set(re.findall(r'(20\d\d)', t))
        if ys and not any(y in r['来源'] for y in ys):
            verify.append(f"#{r['编号']} {r['来源']}：卷首标题年份不一致「{t}」")
    if any(x.endswith('.pdf') for x in [r['题目来源文件']]) and r['题目来源文件'] not in PATCH.get('题目', {}):
        pass

# ---------- 统计 ----------
paper_cnt = collections.Counter()
by_year = collections.defaultdict(collections.Counter)
for r in recs:
    by_year[r['年份']][r['类别']] += 1
    for e in r['试卷']:
        paper_cnt[e['类别']] += 1
stat = {
    '续写题（去重后）': len(recs),
    '按类别': dict(collections.Counter(r['类别'] for r in recs)),
    '试卷套数（共用同一篇续写的试卷分别计）': dict(paper_cnt),
    '按年份': {str(y): dict(c) for y, c in sorted(by_year.items(), reverse=True)},
    '有范文': sum(1 for r in recs if r['范文']),
}
for r in recs:  # 范文第一段前的“One possible version:”之类去掉（只去开头语之前 80 字以内的部分）
    if r['范文'] and r['开头语']:
        a, _ = locate(r['范文'][0], r['开头语'][0])
        if 0 < a <= 80:
            r['范文'][0] = r['范文'][0][a - 1 if r['范文'][0][a - 1] in '“"' else a:]
os.makedirs(OUT, exist_ok=True)
json.dump({'统计': stat, '检查问题': problems, '需人工核实': verify, '续写题': recs},
          open(os.path.join(OUT, '续写题汇总.json'), 'w'), ensure_ascii=False, indent=1)

# ---------- md ----------
cats = ['高考', 'T8联考', '九省联考']
L = ['# 高考英语读后续写汇总', '',
     f"去重后共 **{len(recs)} 篇**续写题（同一篇被几套试卷共用只算一篇），"
     + '、'.join(f"{c} {stat['按类别'].get(c, 0)} 篇" for c in cats) + f"；其中 {stat['有范文']} 篇有原解析卷的参考范文。", '',
     '## 总数表', '', '| 年份 | ' + ' | '.join(cats) + ' | 合计 |', '|---|' + '---|' * (len(cats) + 1)]
for y, c in stat['按年份'].items():
    L.append(f'| {y} | ' + ' | '.join(str(c.get(k, 0)) for k in cats) + f' | {sum(c.values())} |')
L.append('| **合计** | ' + ' | '.join(f"**{stat['按类别'].get(k, 0)}**" for k in cats) + f' | **{len(recs)}** |')
L += ['', '试卷套数（共用同一篇续写的试卷分别计）：' + '、'.join(f'{k} {v} 套' for k, v in paper_cnt.items()), '']
if problems:
    L += ['## 程序检查发现的问题', ''] + [f'- {p}' for p in problems] + ['']
if verify:
    L += ['## 需人工核实', ''] + [f'- {p}' for p in verify] + ['']
L += ['## 清单', '', '| # | 年份 | 类别 | 来源 | 题号 | 原文首句 | 开头语 1 | 开头语 2 | 范文 |', '|---|---|---|---|---|---|---|---|---|']
for r in recs:
    L.append(f"| {r['编号']} | {r['年份']} | {r['类别']} | {r['标题']}<br>原卷：{r['原卷标题']} | {r['题号'] or ''} | {r['原文首句']} | {(r['开头语'] or ['（缺）'])[0]} | {(r['开头语'] or ['', '（缺）'])[1]} | {'有' if r['范文'] else '—'} |")
L += ['', '## 原始文件', '']
for r in recs:
    L.append(f"- #{r['编号']} {r['来源']}：" + '；'.join(f'`{p}`' for p in r['原始文件'])
             + (('；同套答案等：' + '；'.join(f'`{p}`' for p in r['同套其他文件'])) if r.get('同套其他文件') else ''))
open(os.path.join(OUT, '续写题汇总.md'), 'w').write('\n'.join(L) + '\n')
print(json.dumps(stat, ensure_ascii=False, indent=1))
print('检查问题', len(problems)); [print(' ', p) for p in problems]
print('需核实', len(verify)); [print(' ', p) for p in verify]
sys.exit(1 if problems else 0)
