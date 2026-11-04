"""读后续写讲解的程序检查（有一处就退出码 1）。规则只写一处，引擎、流水线都调它。
① 范文词数：每段 80—90 词（硬上限 95），两段合计 165—180（用户 2026-11-03），都不含给定开头语；拼写、标点同 作文规则.check；
② 开头语：题目.json 的开头语 = 范文每段第一句（逐字）= 续写题汇编_高考真题.docx 里的那一句；题目原文每段与 docx 逐字相同；
③ 引用原文：原文屏 mark 的每个短语、伏笔表 row[0] 都在原文里（逐字）；row[1] 在范文里；
   中文段配音文字里成句的英文（≥ 2 个词）必须出自原文、范文，或写在本段的 替换（可替换表达）/ 例 里；替换、例 不许就是范文原句；原文屏上引的英文只许出自原文；
④ 逐句讲（用户 2026-11-03 第二版：一块一块翻、一气呵成）：每个范文句（开头语除外）都有 zh 中文构思 → chunk 逐块翻（≥ 1 块）→ join 连成一句
   → read 读整句 → pt 得分点（≥ 1）→ alt 可替换，顺序不乱；chunk 的 show 依次 = 1..N，hl 是中文句的子串，en / note 非空，en 没有英式拼写；
   join：有 base（保底版）就是 step=base、step=fan 两段，否则只有 fan 一段；marks 每个都按整词在范文句里（and 以外只出现一次）；
   旧讲法（v/s/r、范文.json 的“块”）出现就报；read = 原句去引号；
   得分点：hl 在这句里、档 ⊆ ①②③④、src 是原文或开头语里的原句片段、mark 在 src 里、有画面文字；可替换有 替换 列表；
   每段讲完整段连读（para1 / para2 = 整段去引号）；全文通读按顺序读完全部句子；
⑤ 朗读文本：不许有 blank；中文段没有阿拉伯数字；英文段没有引号、括号、中文；问句干脆（不带 呢/吧/啊，后面接 ‖ 或段尾，踩坑 93）；
⑥ 合成用的副本（高考语法填空/tts/ 下，Actions 只检出那里，踩坑 84）与原稿逐字相同；
⑦ 新范文与旧范文（续写题汇总.json 同一题的“范文”，只由本程序读，只报百分比，不打印内容）5 词片段重合 > 3% 报错；
⑧ 不读旧范文：题目.json 不许有 范文 键；稿源.py、续写视频.py 的源码里不许出现 续写题汇总（生成稿子和画面只读 题目.json）；
⑨ 不念题号、满分、分值、范文词数（用户 2026-11-03 看开头预览：“不用说我们的范文多少个词……不用说第多少个题……也不用说满分多少分”）：
   配音文字里不许有“第 N 题”“满分”“N 分”（得分点等除外）“范文 / 每段 / 合计 … N 个词”；画面引擎不许把题目.json 的 no、score 排到画面上（原题照原卷的文字不算）。
⑩ 口语（用户 2026-11-04 第 16 条：自然、不要过多语气词、该停就停、不要一口气说完）：高考语法填空/tools/稿检查.talk_problems（阈值取自老师录音）；
用法：python3 续写检查.py 讲解目录 [--副本 高考语法填空/tts/稿_xxx.json]   |   --自检（双向验证：每颗雷必须报出，原稿 0 处）"""
import copy
import html
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import 作文规则 as R  # noqa: E402
sys.path.insert(0, str(ROOT / '高考语法填空/tools'))
import 稿检查 as GK  # noqa: E402

DOCX = ROOT / '高考续写/续写题汇编_高考真题.docx'
EN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9 ,;:'’.-]*[A-Za-z]")
PHASES = ['zh', 'chunk', 'join', 'read', 'pt', 'alt']
DANG = set('①②③④')
OLD = ROOT / '高考续写/续写题汇总.json'
OVERLAP_MAX = 0.03


def norm(s):
    return re.sub(r'\s+', ' ', s.replace('’', "'").replace('“', '"').replace('”', '"')).strip().lower()


def noq(s):
    return s.replace('“', '').replace('”', '')


def docx_paras():
    x = zipfile.ZipFile(DOCX).read('word/document.xml').decode()
    ps = [html.unescape(re.sub(r'<[^>]+>', '', p)) for p in re.findall(r'<w:p[ >].*?</w:p>', x, flags=re.S)]
    return [p for p in ps if p.strip()]


def own_sents(fw):
    return [s for p in fw['paragraphs'] for s in p if not s.get('given')]


def problems(t, fw, doc, docx=None):
    E = []
    # ① 词数、拼写、标点
    given = [p[0]['en'] for p in fw['paragraphs']]
    body = [' '.join(s['en'] for s in p) for p in fw['paragraphs']]
    lo, hi = R.word_range('about 150')
    n = R.wc(' '.join(body)) - R.wc(' '.join(given))
    if not lo <= n <= hi:
        E.append(f'① 范文词数 {n}（不含开头语）不在 {lo}—{hi}')
    for k, p in enumerate(fw['paragraphs'], 1):
        m = R.wc(' '.join(x['en'] for x in p)) - R.wc(p[0]['en'])
        if not 80 <= m <= 90:
            E.append(f'① 第 {k} 段 {m} 词（不含开头语）不在 80—90')
    for b in body:
        E += ['① ' + x for x in R.punct(b)]
    E += [f'① 英式拼写：{w}' for w in R.spelling(' '.join(body))]
    if any(not p[0].get('given') for p in fw['paragraphs']) or any(s.get('given') for p in fw['paragraphs'] for s in p[1:]):
        E.append('① 每段第一句才是给定开头语')
    # ② 开头语、原文与 docx 逐字
    if given != t['开头语']:
        E.append(f'② 范文开头语与题目不一致：{given} ≠ {t["开头语"]}')
    if docx is not None:
        for g in t['开头语']:
            if g not in docx:
                E.append(f'② 开头语在 docx 里找不到：{g}')
        for k, p in enumerate(t['原文'], 1):
            if p not in docx:
                E.append(f'② 原文第 {k} 段与 docx 不一致：{p[:40]}…')
    # ③ 引用原文
    src = norm(' '.join(t['原文']))
    fan = norm(' '.join(s['en'] for p in fw['paragraphs'] for s in p))
    segs = doc['segments']
    for s in segs:
        for m in (s.get('mark', []) if s['screen'] in ('p1', 'p2', 'p3', 'p4') else []):
            if m not in ' '.join(t['原文']):
                E.append(f"③ {s['id']}：高亮的“{m}”不在原文里")
        if 'row' in s:
            if norm(s['row'][0]) not in src:
                E.append(f"③ {s['id']}：伏笔“{s['row'][0]}”不在原文里")
            if norm(s['row'][1]) not in fan:
                E.append(f"③ {s['id']}：呼应“{s['row'][1]}”不在范文里")
        alt = [norm(x) for x in s.get('替换', []) + s.get('例', [])]
        for x in alt:
            if x in fan:
                E.append(f"③ {s['id']}：替换 / 例“{x}”就是范文原句")
        if s['lang'] == 'Chinese':
            for m in EN_RUN.finditer(s['text']):
                w = m.group().strip(' ,;:.')
                if len(w.split()) < 2:
                    continue
                if s['screen'] in ('p1', 'p2', 'p3', 'p4'):
                    if norm(w) not in src:
                        E.append(f"③ {s['id']}：原文屏引的英文“{w}”不在原文里")
                elif norm(w) not in src and norm(w) not in fan and not any(norm(w) in a or a in norm(w) for a in alt):
                    E.append(f"③ {s['id']}：英文“{w}”不在原文、范文里，也没写进 替换 / 例")
    # ④ 逐句五步
    own = own_sents(fw)
    src_all = ' '.join(t['原文'] + t['开头语'])
    for k, sen in enumerate(own, 1):
        ss = [s for s in segs if s['screen'] == f's{k}']
        if not ss:
            E.append(f'④ 范文第 {k} 句没有讲解：{sen["en"][:30]}')
            continue
        ph = [s.get('ph') for s in ss]
        if [p for i, p in enumerate(ph) if i == 0 or p != ph[i - 1]] != PHASES:
            E.append(f'④ s{k}：步骤顺序 {ph} ≠ 中文构思→逐块翻→连成一句→读句→得分点→可替换')
        if ph.count('zh') != 1 or ph.count('read') != 1 or ph.count('alt') != 1:
            E.append(f'④ s{k}：中文构思、读句、可替换各要恰好一段')
        if '块' in sen:
            E.append(f'④ s{k}：范文.json 还有旧讲法的“块”')
        ck = [s for s in ss if s.get('ph') == 'chunk']
        if [s.get('show') for s in ck] != list(range(1, len(ck) + 1)) or not ck:
            E.append(f"④ s{k}：逐块翻的 show {[s.get('show') for s in ck]} 不是 1..N（N ≥ 1）")
        for s in ck:
            if not s.get('hl') or s['hl'] not in sen['zh']:
                E.append(f"④ {s['id']}：顶部高亮“{s.get('hl')}”不在中文句里")
            if not s.get('zh') or not s.get('en', '').strip() or not s.get('note'):
                E.append(f"④ {s['id']}：逐块翻缺 zh / en / note")
            E += [f"④ {s['id']}：英式拼写 {w}" for w in R.spelling(s.get('en', ''))]
        jn = [s for s in ss if s.get('ph') == 'join']
        want = ['base', 'fan'] if jn and jn[0].get('base') else ['fan']
        if [s.get('step') for s in jn] != want:
            E.append(f"④ s{k}：连成一句的步骤 {[s.get('step') for s in jn]} ≠ {want}")
        for s in jn:
            for m in s.get('marks') or []:
                n = len(re.findall(rf'(?<![A-Za-z’]){re.escape(m)}(?![A-Za-z’])', sen['en']))
                if n == 0 or (n > 1 and m != 'and'):
                    E.append(f"④ {s['id']}：连接处“{m}”在范文句里出现 {n} 次（应恰好 1 次，and 除外）")
            if not s.get('marks'):
                E.append(f"④ {s['id']}：连成一句没写 marks")
            if s.get('base'):
                if R.spelling(s['base']) or not re.fullmatch(r'[A-Z].*[.?!”]', s['base']):
                    E.append(f"④ {s['id']}：保底版拼写 / 句首大写 / 句末标点不对：{s['base'][:30]}")
                if noq(s['base']) == noq(sen['en']):
                    E.append(f"④ {s['id']}：保底版就是范文句（不用分两步）")
        rd = [s for s in ss if s['lang'] == 'English']
        if len(rd) != 1 or rd[0]['text'] != noq(sen['en']) or rd[0].get('ph') != 'read':
            E.append(f'④ s{k}：读句（英文段）与范文句不一致')
        for s in ss:
            if s.get('ph') in ('zh', 'chunk', 'join', 'pt', 'alt') and not s.get('ln'):
                E.append(f"④ {s['id']}：没有画面文字")
            if s.get('ph') == 'pt':
                if not s.get('hl') or s['hl'] not in sen['en']:
                    E.append(f"④ {s['id']}：得分点短语“{s.get('hl')}”不在这句里")
                if not s.get('dang') or not set(s['dang']) <= DANG:
                    E.append(f"④ {s['id']}：没写对应第五档哪一条（{s.get('dang')}）")
                said = {'①②③④'['一二三四'.index(c)] for m in re.finditer(r'对应第([一二三四])条(?:和第([一二三四])条)?', s['text']) for c in m.groups() if c}
                if said != set(s.get('dang') or []):
                    E.append(f"④ {s['id']}：配音说的“对应第几条”{sorted(said)} ≠ 画面的档 {s.get('dang')}")
                if not s.get('src') or s['src'] not in src_all:
                    E.append(f"④ {s['id']}：原文出处不是原文 / 开头语里的原句")
                elif not s.get('mark') or any(m not in s['src'] for m in s['mark']):
                    E.append(f"④ {s['id']}：出处高亮不在出处句里")
            if s.get('ph') == 'alt' and not s.get('替换'):
                E.append(f"④ {s['id']}：可替换表达没有 替换 列表")
    for k, p in enumerate(fw['paragraphs'], 1):
        pr = [s['text'] for s in segs if s['screen'] == f'para{k}' and s['lang'] == 'English']
        if pr != [' '.join(noq(x['en']) for x in p)]:
            E.append(f'④ 第 {k} 段讲完没有整段连读（para{k}）')
    allsent = [noq(s['en']) for p in fw['paragraphs'] for s in p]
    full = [s['text'] for s in segs if s['screen'] == 'full' and s['lang'] == 'English']
    if full != allsent:
        E.append('④ 全文通读没有按顺序读完全部句子')
    # ⑤ 朗读文本
    for s in segs:
        x = s['text']
        if re.search(r'blank', x, re.I):
            E.append(f"⑤ {s['id']}：朗读文本里有 blank")
        if s['lang'] == 'Chinese' and re.search(r'\d', x):
            E.append(f"⑤ {s['id']}：中文段配音文字有阿拉伯数字：{x[:20]}")
        if s['lang'] == 'English' and re.search(r'[“”"()（）一-鿿]', x):
            E.append(f"⑤ {s['id']}：英文段有引号、括号或中文")
        for m in re.finditer(r'(.)？', x):
            if m.group(1) in '呢吧啊':
                E.append(f"⑤ {s['id']}：问句带“{m.group(1)}”")
            rest = x[m.end():]
            if rest and not rest.startswith('‖'):
                E.append(f"⑤ {s['id']}：问句后面没有 ‖ 停顿")
    ids = [s['id'] for s in segs]
    if len(set(ids)) != len(ids):
        E.append('⑤ 段 id 重复')
    return E


def _flat(x):
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [y for v in x.values() for y in _flat(v)]
    if isinstance(x, list):
        return [y for v in x for y in _flat(v)]
    return []


def grams(s, n=5):
    w = re.findall(r"[a-z]+(?:'[a-z]+)?", s.replace('’', "'").lower())
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def old_essay(t):
    """旧范文（汇总里同一年、同一试卷、同一题号的“范文”）。只给 overlap 用，不打印、不返回给别处。"""
    for e in json.loads(OLD.read_text('utf-8'))['续写题']:
        if e.get('年份') == t['year'] and e.get('题号') == t['no'] and any(t['paper'] in x.get('考试', '') for x in e.get('试卷', [])):
            return ' '.join(_flat(e.get('范文', [])))
    raise SystemExit('⑦ 汇总里找不到这道题（无法做重合检查）')


def overlap(fw, old):
    new = ' '.join(s['en'] for s in own_sents(fw))
    g = grams(new)
    return len(g & grams(old)) / max(len(g), 1)


def leak_problems(d, t):
    E = []
    if '范文' in t:
        E.append('⑧ 题目.json 里有 范文 键（生成稿子和画面的程序只许读 说明、原文、开头语）')
    for f in [Path(d) / '稿源.py', ROOT / '高考续写/tools/续写视频.py']:
        if f.exists() and '续写题汇总' in f.read_text('utf-8'):
            E.append(f'⑧ {f.name} 的源码里出现了 续写题汇总（不许读旧范文）')
    return E


TALK_BAD = [(re.compile(r'第[零一二三四五六七八九十百\d]+题'), '题号'), (re.compile(r'满分'), '满分'),
            (re.compile(r'[零一二三四五六七八九十百\d]+分(?![点析清别开成钟号句段数])'), '分值'),
            (re.compile(r'(范文|每段|合计|一共|共)[^。‖]{0,8}[零一二三四五六七八九十百\d]+个?词'), '范文词数')]


def talk_problems(doc, engine_src):
    E = []
    for s in doc['segments']:
        for rx, what in TALK_BAD:
            m = rx.search(s['text'])
            if m:
                E.append(f"⑨ {s['id']}：配音念了{what}“{m.group(0)}”（用户：不用说题号、满分、范文词数）")
    for k in ('no', 'score'):
        if re.search(rf"t\[[\'\"]{k}[\'\"]\]", engine_src):
            E.append(f'⑨ 续写视频.py 把题目.json 的 {k} 排到了画面上（不显示题号、分值）')
    return E


def check_dir(d, copy_path=None):
    d = Path(d)
    t = json.loads((d / '题目.json').read_text('utf-8'))
    fw = json.loads((d / '范文.json').read_text('utf-8'))
    doc = json.loads((d / '稿.json').read_text('utf-8'))
    E = problems(t, fw, doc, docx_paras())
    r = overlap(fw, old_essay(t))
    if r > OVERLAP_MAX:
        E.append(f'⑦ 与旧范文 5 词片段重合 {r:.1%} > {OVERLAP_MAX:.0%}')
    E += leak_problems(d, t)
    E += talk_problems(doc, (ROOT / '高考续写/tools/续写视频.py').read_text('utf-8'))
    E += GK.talk_problems(doc)
    if copy_path and Path(copy_path).read_text('utf-8') != (d / '稿.json').read_text('utf-8'):
        E.append(f'⑥ 合成副本 {copy_path} 与原稿不一致（重新复制）')
    return E, (t, fw, doc)


def selftest():
    d = ROOT / '高考续写/讲解/2026_新课标Ⅰ卷'
    E0, (t, fw, doc) = check_dir(d)
    docx = docx_paras()
    old = old_essay(t)

    def mine(f):
        a, b, c = copy.deepcopy(t), copy.deepcopy(fw), copy.deepcopy(doc)
        f(a, b, c)
        return problems(a, b, c, docx) + talk_problems(c, '')

    seg = lambda c, i: next(s for s in c['segments'] if s['id'] == i)  # noqa: E731
    sen = lambda b, k: own_sents(b)[k - 1]  # noqa: E731

    def widen(b):
        x = b['paragraphs'][0][1]
        x['en'] = x['en'][:-1] + ' after a short wait at the station.'
    mines = {
        '段词数超 90': (lambda a, b, c: widen(b), '① 第 1 段'),
        '开头语改字': (lambda a, b, c: b['paragraphs'][1][0].update(en='Three days later, Emily came back to get her car.'), '② 范文开头语'),
        '原文改字': (lambda a, b, c: a['原文'].__setitem__(0, a['原文'][0].replace('high hopes', 'great hopes')), '② 原文第 1 段'),
        '高亮不在原文': (lambda a, b, c: seg(c, 'a02')['mark'].__setitem__(0, 'she didn’t give it any thought'), '③ a02'),
        '引用编造原文': (lambda a, b, c: seg(c, 'a05').update(text=seg(c, 'a05')['text'].replace('genuine warmth', 'true warmth')), '③ a05'),
        '漏讲一句': (lambda a, b, c: c.__setitem__('segments', [s for s in c['segments'] if s['screen'] != 's6']), '④ 范文第 6 句'),
        '缺一块': (lambda a, b, c: c.__setitem__('segments', [s for s in c['segments'] if s['id'] != 's3b1']), '④ s3：逐块翻的 show'),
        '逐块顺序乱': (lambda a, b, c: (seg(c, 's3b2').update(show=3), seg(c, 's3b3').update(show=2)), '④ s3：逐块翻的 show'),
        '顶部高亮不在中文句': (lambda a, b, c: seg(c, 's7b2').update(hl='那条路静静地躺在阳光里'), '④ s7b2：顶部高亮'),
        '连接处不在范文句': (lambda a, b, c: seg(c, 's9bf').update(marks=['which read']), '④ s9bf：连接处'),
        '连接处出现两次': (lambda a, b, c: seg(c, 's11bf').update(marks=['her']), '④ s11bf：连接处'),
        '保底版拼错': (lambda a, b, c: seg(c, 's5bj').update(base=seg(c, 's5bj')['base'].replace('window', 'windw').rstrip('.')), '④ s5bj：保底版'),
        '保底版缺范文一步': (lambda a, b, c: c.__setitem__('segments', [s for s in c['segments'] if s['id'] != 's8bf']), '④ s8：连成一句的步骤'),
        '旧讲法（谓语一步）': (lambda a, b, c: seg(c, 's3b1').update(ph='v'), '④ s3：步骤顺序'),
        '旧讲法（范文还有块）': (lambda a, b, c: sen(b, 3).__setitem__('块', [['Daniel ', 2]]), '④ s3：范文.json 还有旧讲法'),
        '得分点不在句中': (lambda a, b, c: seg(c, 's3p2').update(hl='was taken'), '④ s3p2'),
        '得分点没写档': (lambda a, b, c: seg(c, 's5p1').update(dang=['⑤']), '④ s5p1'),
        '配音的条与档不一致': (lambda a, b, c: seg(c, 's6p2').update(dang=['②']), '④ s6p2'),
        '配音没说第几条': (lambda a, b, c: seg(c, 's9p2').update(text=seg(c, 's9p2')['text'].replace('对应第三条和第一条', '')), '④ s9p2'),
        '出处不是原文': (lambda a, b, c: seg(c, 's7p2').update(src='The heavy snow made driving impossible.'), '④ s7p2'),
        '缺可替换': (lambda a, b, c: c.__setitem__('segments', [s for s in c['segments'] if s['id'] != 's4h']), '④ s4'),
        '段落连读不全': (lambda a, b, c: seg(c, 'r2b').update(text=seg(c, 'r2b')['text'].rsplit('. ', 1)[0] + '.'), '④ 第 2 段'),
        '朗读念 blank': (lambda a, b, c: seg(c, 't02').update(text=seg(c, 't02')['text'] + 'blank'), '⑤ t02'),
        '阿拉伯数字': (lambda a, b, c: seg(c, 't02').update(text=seg(c, 't02')['text'].replace('一百五十', '150')), '⑤ t02'),
        '念题号': (lambda a, b, c: seg(c, 't01').update(text=seg(c, 't01')['text'] + '第六十七题。'), '⑨ t01'),
        '念满分': (lambda a, b, c: seg(c, 'g01').update(text=seg(c, 'g01')['text'] + '满分二十五分。'), '⑨ g01'),
        '念范文词数': (lambda a, b, c: seg(c, 't02').update(text=seg(c, 't02')['text'] + '我们的范文，合计一百七十六个词。'), '⑨ t02'),
        '问句带呢': (lambda a, b, c: seg(c, 'a02').update(text=seg(c, 'a02')['text'].replace('哪里来？', '哪里来呢？')), '⑤ a02'),
        '英文段有引号': (lambda a, b, c: seg(c, 's2e').update(text='“' + seg(c, 's2e')['text']), '⑤ s2e'),
        '英式拼写': (lambda a, b, c: b['paragraphs'][1][2].update(en=b['paragraphs'][1][2]['en'].replace('garage', 'neighbour’s garage')), '① 英式拼写'),
    }
    ok = not E0
    print(f'  原稿：{len(E0)} 处' + (f'（{E0[:3]}）' if E0 else ''))
    for k, (f, want) in mines.items():
        e = [x for x in mine(f) if x.startswith(want)]
        print(f'  {k}：{len(e)} 处' + (f'（{e[0][:50]}）' if e else '（漏报）'))
        ok &= bool(e)
    # ⑦ 旧范文冒充新范文必须报；新范文不报（只打印百分比）
    fake = {'paragraphs': [[{'en': g, 'given': True}, {'en': old}] for g in t['开头语'][:1]]}
    r_old, r_new = overlap(fake, old), overlap(fw, old)
    print(f'  旧范文冒充新范文：重合 {r_old:.1%}（必须 > {OVERLAP_MAX:.0%}）；新范文 {r_new:.1%}（必须 ≤ {OVERLAP_MAX:.0%}）')
    ok &= r_old > OVERLAP_MAX >= r_new
    # ⑧ 题目.json 混进范文、源码读汇总都要报
    e1 = leak_problems(d, dict(t, 范文=['x']))
    tmp = Path(__import__('tempfile').mkdtemp())
    (tmp / '稿源.py').write_text("json.load(open('高考续写/续写题汇总.json'))", 'utf-8')
    e2 = leak_problems(tmp, t)
    print(f'  题目.json 有范文键：{len(e1)} 处；稿源读汇总：{len(e2)} 处；现稿：{len(leak_problems(d, t))} 处')
    ok &= bool(e1) and bool(e2) and not leak_problems(d, t)
    e3 = talk_problems({'segments': []}, 'f"第 {t[\"no\"]} 题 · {t[\"score\"]} 分"')
    print(f'  画面排题号分值：{len(e3)} 处（应 2）')
    ok &= len(e3) == 2
    print('自检', '通过' if ok else '失败')
    return ok


def main():
    if '--自检' in sys.argv:
        sys.exit(0 if selftest() else 1)
    d = sys.argv[1]
    cp = sys.argv[sys.argv.index('--副本') + 1] if '--副本' in sys.argv else None
    E, (t, fw, doc) = check_dir(d, cp)
    n = R.wc(' '.join(s['en'] for p in fw['paragraphs'] for s in p)) - R.wc(' '.join(p[0]['en'] for p in fw['paragraphs']))
    print(f'续写检查：范文 {n} 词，讲解 {len(doc["segments"])} 段，问题 {len(E)} 处')
    for x in E:
        print('  ✗', x)
    sys.exit(1 if E else 0)


if __name__ == '__main__':
    main()
