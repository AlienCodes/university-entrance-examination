"""讲解稿的程序检查（有一处就退出码 1）：
① 稿里的答案表 = 答案文件（官方答案，原文目录）；每题“答案”段的配音文字里含答案（63 题 that、which 都要有；62 题 Drawn 大写）；
② 朗读段 en 是原文里连续的一段（逐字相同）；配音文字 = en 去掉中文注释、去掉空格（只比单词）；配音文字里不许有 blank
   （用户 2026-11-03：读原句时空格处不要念 blank，只留短停顿——空格处写逗号，画面照旧）；
③ 每题的步骤 读句→提示→词性→成分→形式→答案→口诀 全部出现且顺序不乱；答案段之前空格不显示答案；
④ 全文通读 = 原文填上答案、去掉中文注释（逐词相同）；
⑤ 中文段的配音文字里没有阿拉伯数字（题号写汉字，防止读成 five six）；
⑥ 问句干脆（用户 2026-10-30：“是不是谓语呢？”尾音轻飘）：？ 前不带 呢 / 吧 / 啊，问句后面是 ‖ 或段尾（停一下）；
⑦ 给了词的题：“提示”段里先单独说出词义，“X 的意思……。‖”自成一句（用户 2026-10-30：先说 hold 的意思是举办，停一下，再推理）；
   答案段的“答案”前面有 ‖ 或在段首。
⑧ 口语（用户 2026-11-04：自然、不要过多语气词；该停就停、该连就连，不要一口气说完）——`talk_problems`，讲解稿通用（续写检查调用）：
   语气词（呢 啊 吧 嘛 哦 呀 啦 嗯）每段最多 1 个，全稿每千音节最多 3 个；
   一口气：阈值取自老师本人讲课录音 05.wav（挑参考.utterances 切停顿、按实测语速 5.607 音节/秒折算，见 BREATH 注释）——
     标点（，。；：？！、—）或 ‖ 之间 ≤ CLAUSE_MAX 音节（录音 0.12 秒以上停顿之间的 95% 分位）；
     两个 ‖ 之间（段首段尾也算）≤ UNIT_MAX 音节（录音 0.40 秒以上停顿之间的中位数：讲解比聊天密，至少像老师一半时间那样常停）；
     一段 ≤ SEG_MAX 音节（0.40 秒停顿之间的 90% 分位）；
   ‖ 只放在标点后面（停在意思的边界，不切开意群）；两个 ‖ 之间不少于 UNIT_MIN 音节（问句、“英文是：……”答案除外，防一顿一顿）；
   “英文是：”（答案）前面有 ‖ 或在段首。--口语 同时跑 tools/中文地道（忍泪、挥别、翻译腔……，用户 2026-11-04）和 tools/讲解推理（因为……所以……说完整，用户 2026-11-04）。音节 = 汉字 + 英文词（与 语速语调.py 同一数法）。
用法：python 稿检查.py 稿.json [--自检]；python 稿检查.py --口语 稿.json [--自检 旧稿.json]"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEPS = ['读句', '提示', '词性', '成分', '形式', '答案', '口诀']
NOTE = re.compile(r'\s*\([^()]*[一-鿿][^()]*\)')


# 老师录音 05.wav 实测（2026-11-04，停顿 ≥ 0.12 / 0.25 / 0.40 秒切开后每段音节数）：
#   ≥0.12 秒：p50 10、p90 19、p95 23.5；≥0.25 秒：p50 20.6、p95 43；≥0.40 秒：p50 69.5、p90 150、p95 196
BREATH = {'CLAUSE_MAX': 24, 'UNIT_MAX': 70, 'SEG_MAX': 150, 'UNIT_MIN': 7}
FILLERS = '呢啊吧嘛哦呀啦嗯'
FILLER_PER_SEG, FILLER_PER_K = 1, 3
TALK_EXEMPT = {('t01', '那接下来我们就开始讲一下这篇二零二六年新课标一卷的续写')}   # 老师原话（续写意见第 2 条），照念


def syl(t):
    return len(re.findall(r"[一-鿿]|[A-Za-z]+(?:[’'][A-Za-z]+)?", t))


def talk_problems(doc):
    E, tot, nf = [], 0, 0
    for s in doc['segments']:
        if s['lang'] != 'Chinese':
            continue
        t = s['text']
        n = syl(t)
        tot += n
        f = sum(t.count(c) for c in FILLERS)
        nf += f
        if f > FILLER_PER_SEG:
            E.append(f"⑧ {s['id']} 语气词 {f} 个（每段最多 {FILLER_PER_SEG}）：{t[:30]}")
        if n > BREATH['SEG_MAX']:
            E.append(f"⑧ {s['id']} 一段 {n} 音节 > {BREATH['SEG_MAX']}（拆段）")
        for c in re.split(r'[，。；：？！、—‖]+', t):
            c = c.strip(' （）“”')
            if syl(c) > BREATH['CLAUSE_MAX'] and (s['id'], c) not in TALK_EXEMPT:
                E.append(f"⑧ {s['id']} 一口气 {syl(c)} 音节没有标点 > {BREATH['CLAUSE_MAX']}：{c}")
        units = t.split('‖')
        for u in units:
            if syl(u) > BREATH['UNIT_MAX']:
                E.append(f"⑧ {s['id']} 两个停顿 ‖ 之间 {syl(u)} 音节 > {BREATH['UNIT_MAX']}：{u[:24]}……")
            if len(units) > 1 and syl(u) < BREATH['UNIT_MIN'] and not u.rstrip().endswith('？') and not u.startswith('英文是'):
                E.append(f"⑧ {s['id']} 两个 ‖ 之间只有 {syl(u)} 音节（太碎，一顿一顿）：{u}")
        for m in re.finditer('‖', t):
            if m.start() == 0 or t[m.start() - 1] not in '，。；：？！—':
                E.append(f"⑧ {s['id']} ‖ 不在标点后面（切开了意群）：{t[max(0, m.start() - 10):m.start() + 6]}")
        for m in re.finditer('英文是：', t):
            if m.start() > 0 and t[m.start() - 1] != '‖':
                E.append(f"⑧ {s['id']} 答案“英文是”前面没有 ‖：{t[max(0, m.start() - 10):m.start() + 6]}")
    if tot and nf * 1000 / tot > FILLER_PER_K:
        E.append(f'⑧ 全稿语气词每千音节 {nf * 1000 / tot:.1f} 个 > {FILLER_PER_K}')
    return E


def talk_selftest(doc, old):
    """双向验证：旧稿必须报一口气；新稿 0；再放进多余语气词、‖ 切开意群、太碎、答案前没停各一颗雷。"""
    import copy
    ok = not talk_problems(doc)
    print(f"  新稿：{len(talk_problems(doc))} 处")
    e = talk_problems(old)
    print(f"  旧稿：{len(e)} 处（应 > 0，含一口气）")
    ok &= any('一口气' in x or '之间' in x for x in e)
    zs = [s for s in doc['segments'] if s['lang'] == 'Chinese' and '英文是：' in s['text']]
    seg0 = zs[0]['id']
    mines = [('语气词', lambda t: '好啊，我们来看一下吧。' + t),
             ('全稿语气词', None),
             ('一口气长句', lambda t: '我们现在要把这几块中文按照原来的顺序一块一块地全部翻成简单准确的英文句子。' + t),
             ('‖ 切开意群', lambda t: t.replace('英文是', '英文‖是', 1)),
             ('太碎', lambda t: '先看。‖' + t),
             ('答案前没停', lambda t: t.replace('‖英文是', '英文是', 1))]
    for name, f in mines:
        d = copy.deepcopy(doc)
        if f is None:
            for s in d['segments']:
                if s['lang'] == 'Chinese':
                    s['text'] = '对吧，' + s['text']
        else:
            s = next(x for x in d['segments'] if x['id'] == seg0)
            s['text'] = f(s['text'])
        e = talk_problems(d)
        hit = bool(e)
        print(f'  雷 {name}：{"报出" if hit else "漏查"}')
        ok &= hit
    print('口语自检', '通过' if ok else '失败')
    return ok


def words(s):
    return re.findall(r"[a-z]+(?:'[a-z]+)?", s.lower().replace('’', "'"))


def problems(doc):
    src = json.loads((ROOT / doc['原文']).read_text('utf-8'))
    ans_file = json.loads((ROOT / doc['原文']).with_name('答案_' + Path(doc['原文']).name).read_text('utf-8'))['answers']
    P, errs = src['paragraphs'], []
    if doc['answers'] != ans_file:
        errs.append(f'答案表与答案文件不同：{doc["answers"]} ≠ {ans_file}')
    segs = doc['segments']
    by_q = {}
    for s in segs:
        if s.get('q'):
            by_q.setdefault(s['q'], []).append(s)
        if re.search(r'\bblank\b', s['text'], re.I):
            errs.append(f"{s['id']} 配音文字里念了 blank（空格处只停顿、不念词）：{s['text'][:50]}")
        if s['lang'] == 'Chinese' and re.search(r'[0-9]', s['text']):
            errs.append(f"{s['id']} 中文配音文字里有阿拉伯数字：{s['text'][:30]}")
        if 'en' in s:
            if not any(s['en'] in p for p in P):
                errs.append(f"{s['id']} 朗读的原句不是原文里连续的一段：{s['en'][:50]}")
            exp = words(re.sub(r'___\d+___(\s*\([^()]*\))?', ' ', NOTE.sub('', s['en'])))
            if words(s['text']) != exp:
                errs.append(f"{s['id']} 配音文字与原句不一致：{' '.join(words(s['text']))} ≠ {' '.join(exp)}")
    for q in range(56, 66):
        ss = by_q.get(q, [])
        seq = [st for s in ss for st in s.get('steps', [])]
        if seq != STEPS:
            errs.append(f'{q} 题步骤不全或顺序不对：{seq}')
        if not any('en' in s for s in ss):
            errs.append(f'{q} 题没有朗读原句')
        a = [s for s in ss if '答案' in s.get('steps', [])]
        if a:
            if not a[0].get('answer'):
                errs.append(f'{q} 题答案段没有让空格显示答案')
            for w in doc['answers'][str(q)].split(' / '):
                if w not in a[0]['text']:
                    errs.append(f"{q} 题答案段没说出答案 {w}：{a[0]['text']}")
            first = next(i for i, s in enumerate(ss) if s.get('answer'))
            if ss[first] is not a[0]:
                errs.append(f'{q} 题答案在“答案”段之前就显示了')
    full = ' '.join(s['text'] for s in segs if s.get('full'))
    filled = ' '.join(NOTE.sub('', re.sub(r'___(\d+)___(\s*\([^()]*\))?',
                                          lambda m: doc['answers'][m.group(1)].split(' / ')[0], p)) for p in P)
    if words(full) != words(filled):
        errs.append('全文通读与原文（填上答案）不一致')
    for s in segs:
        if s['lang'] != 'Chinese':
            continue
        for m in re.finditer('？', s['text']):
            if re.search('[呢吧啊]$', s['text'][:m.start()]):
                errs.append(f"{s['id']} 问句带“{s['text'][m.start() - 1]}”：{s['text'][max(0, m.start() - 12):m.end()]}")
            rest = s['text'][m.end():]
            if rest and not rest.startswith('‖'):
                errs.append(f"{s['id']} 问句后面没有停顿标记 ‖：{s['text'][max(0, m.start() - 12):m.end() + 6]}")
        if '提示' in s.get('steps', []) and '给' in s['text'] and '没' not in s['text']:
            if not re.search(r"‖[A-Za-z]+ (?:在这里)?的意思[^。‖，]*。‖", s['text']):
                errs.append(f"{s['id']} 给了词，却没先单独说出词义（“‖X 的意思是……。‖”，中间不带逗号）：{s['text'][:40]}")
        if '答案' in s.get('steps', []):
            i = s['text'].find('答案')
            if i > 0 and s['text'][:i] != '所以' and '‖' not in s['text'][:i]:
                errs.append(f"{s['id']} “答案”前面没有停顿标记 ‖：{s['text'][:40]}")
    ids = [s['id'] for s in segs]
    if len(set(ids)) != len(ids):
        errs.append('段落 id 重复')
    return errs


def selftest(doc):
    import copy
    mines = []
    d = copy.deepcopy(doc); d['answers']['59'] = 'was'; mines.append(('答案表', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q62f')['text'] = '答案：drawn。'; mines.append(('大写', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q57b')['en'] = 'The exact date and ___57___ (frequent) of daji vary from region to region.'; mines.append(('原句', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q64d')['steps'] = []; mines.append(('步骤', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'f05')['text'] = 'As transportation and communication was underdeveloped at that time, it was very difficult for households to obtain daily necessities.'; mines.append(('通读', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q58a')['text'] = '第58题。'; mines.append(('数字', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q65e')['answer'] = True; mines.append(('答案提前显示', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q56d')['text'] = '那它在这句话里是不是谓语呢？我们找一下主干。'; mines.append(('问句带呢、问句后没停顿', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q56c')['text'] = '括号里给了一个词，hold，举办。给了词，一般都要变形。hold 是个动词。'; mines.append(('词义没单独成句', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q59f')['text'] = '过去时，再加上复数，就是 were。答案：were。'; mines.append(('答案前没停顿', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q56b')['text'] = 'It is also common for them, blank, during traditional Chinese holidays, such as the Spring Festival and the Mid-Autumn Festival.'; mines.append(('念 blank', d))
    ok = not problems(doc)
    for name, d in mines:
        e = problems(d)
        print(f'  雷 {name}：{"报出" if e else "漏查"}')
        ok &= bool(e)
    print('自检', '通过' if ok else '失败')
    return ok


if __name__ == '__main__':
    if sys.argv[1] == '--口语':
        doc = json.loads(Path(sys.argv[2]).read_text('utf-8'))
        if '--自检' in sys.argv:
            old = json.loads(Path(sys.argv[sys.argv.index('--自检') + 1]).read_text('utf-8'))
            sys.exit(0 if talk_selftest(doc, old) else 1)
        sys.path.insert(0, str(ROOT / 'tools'))
        import 中文地道 as ZD
        import 讲解推理 as TL
        e = talk_problems(doc) + ZD.problems(ZD.doc_items(doc)) + TL.problems(doc)
        for x in e:
            print('✗', x)
        print(f'口语检查：{len(e)} 处')
        sys.exit(1 if e else 0)
    doc = json.loads(Path(sys.argv[1]).read_text('utf-8'))
    if '--自检' in sys.argv:
        sys.exit(0 if selftest(doc) else 1)
    e = problems(doc)
    for x in e:
        print('✗', x)
    print(f'稿检查：{len(e)} 处')
    sys.exit(1 if e else 0)
