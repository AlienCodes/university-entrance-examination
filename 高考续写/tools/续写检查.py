"""读后续写讲解的程序检查（有一处就退出码 1）。规则只写一处，引擎、流水线都调它。
① 范文词数：tools/作文规则（铁律 20）“约 150 词”→ [165, 180]，不含两句给定开头语；拼写、标点同 作文规则.check；
② 开头语：题目.json 的开头语 = 范文每段第一句（逐字）= 续写题汇编_高考真题.docx 里的那一句；题目原文每段与 docx 逐字相同；
③ 引用原文：原文屏 mark 的每个短语、伏笔表 row[0] 都在原文里（逐字）；row[1] 在范文里；
   中文段配音文字里成句的英文（≥ 2 个词）必须出自原文、范文，或写在本段的 替换（可替换表达）/ 例（反例、泛例）里；
   替换、例 里的不许就是范文原句；原文屏（p1—p4）上引的英文只许出自原文；
④ 范文每一句（开头语除外）都有逐句讲解：读句（英文段 = 范文句去掉引号，逐字）→ 意思与作用 → 得分点（hl 都在这句里）→ 怎么写与可替换，
   顺序不乱；意思卡 = 范文.json 的中文意思；全文通读按顺序读完全部句子；
⑤ 朗读文本：不许有 blank（用户 2026-11-03）；中文段没有阿拉伯数字（防止读成英文数字）；英文段没有引号、括号、中文；
   问句干脆：？ 前不带 呢 / 吧 / 啊，问句后是 ‖ 或段尾（踩坑 93，同 高考语法填空/tools/稿检查.py ⑥）；
⑥ 合成用的副本（高考语法填空/tts/ 下，Actions 只检出那里，踩坑 84）与原稿逐字相同。
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

DOCX = ROOT / '高考续写/续写题汇编_高考真题.docx'
EN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9 ,;:'’.-]*[A-Za-z]")
PHASES = ['read', 'mean', 'pt', 'how']


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
        for m in s.get('mark', []):
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
    # ④ 逐句讲解
    own = own_sents(fw)
    for k, sen in enumerate(own, 1):
        ss = [s for s in segs if s['screen'] == f's{k}']
        if not ss:
            E.append(f'④ 范文第 {k} 句没有讲解：{sen["en"][:30]}')
            continue
        ph = [s.get('ph') for s in ss]
        if [p for i, p in enumerate(ph) if i == 0 or p != ph[i - 1]] != PHASES:
            E.append(f'④ s{k}：阶段顺序 {ph} ≠ 读句→意思与作用→得分点→怎么写')
        rd = [s for s in ss if s['lang'] == 'English']
        if len(rd) != 1 or rd[0]['text'] != noq(sen['en']):
            E.append(f'④ s{k}：英文朗读与范文句不一致')
        mean = [s.get('ln') for s in ss if s.get('ph') == 'mean']
        if not mean or mean[0] != '意思：' + sen['zh']:
            E.append(f'④ s{k}：意思卡与范文中文意思不一致')
        for s in ss:
            if s.get('ph') == 'pt' and (not s.get('hl') or s['hl'] not in sen['en']):
                E.append(f"④ {s['id']}：得分点短语“{s.get('hl')}”不在这句里")
            if s.get('ph') in ('mean', 'pt', 'how') and not s.get('ln'):
                E.append(f"④ {s['id']}：没有画面文字")
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


def check_dir(d, copy_path=None):
    d = Path(d)
    t = json.loads((d / '题目.json').read_text('utf-8'))
    fw = json.loads((d / '范文.json').read_text('utf-8'))
    doc = json.loads((d / '稿.json').read_text('utf-8'))
    E = problems(t, fw, doc, docx_paras())
    if copy_path and Path(copy_path).read_text('utf-8') != (d / '稿.json').read_text('utf-8'):
        E.append(f'⑥ 合成副本 {copy_path} 与原稿不一致（重新复制）')
    return E, (t, fw, doc)


def selftest():
    d = ROOT / '高考续写/讲解/2026_新课标Ⅰ卷'
    E0, (t, fw, doc) = check_dir(d)
    docx = docx_paras()

    def mine(f):
        a, b, c = copy.deepcopy(t), copy.deepcopy(fw), copy.deepcopy(doc)
        f(a, b, c)
        return problems(a, b, c, docx)

    seg = lambda c, i: next(s for s in c['segments'] if s['id'] == i)  # noqa: E731
    mines = {
        '词数超出': (lambda a, b, c: b['paragraphs'][1][4].update(en=b['paragraphs'][1][4]['en'][:-1] + ' that she would never forget in her whole life.'), '① 范文词数'),
        '开头语改字': (lambda a, b, c: b['paragraphs'][1][0].update(en='Three days later, Emily came back to get her car.'), '② 范文开头语'),
        '原文改字': (lambda a, b, c: a['原文'].__setitem__(0, a['原文'][0].replace('high hopes', 'great hopes')), '② 原文第 1 段'),
        '高亮不在原文': (lambda a, b, c: seg(c, 'r03')['mark'].__setitem__(0, 'she didn’t give it any thought'), '③ r03'),
        '引用编造原文': (lambda a, b, c: seg(c, 'r08').update(text=seg(c, 'r08')['text'].replace('genuine warmth', 'true warmth')), '③ r08'),
        '漏讲一句': (lambda a, b, c: c.__setitem__('segments', [s for s in c['segments'] if s['screen'] != 's6']), '④ 范文第 6 句'),
        '得分点不在句中': (lambda a, b, c: seg(c, 's3p2').update(hl='was taken'), '④ s3p2'),
        '朗读念 blank': (lambda a, b, c: seg(c, 't02').update(text=seg(c, 't02')['text'] + 'blank'), '⑤ t02'),
        '阿拉伯数字': (lambda a, b, c: seg(c, 't01').update(text=seg(c, 't01')['text'].replace('二十五分', '25分')), '⑤ t01'),
        '问句带呢': (lambda a, b, c: seg(c, 'o03').update(text=seg(c, 'o03')['text'].replace('衔接？', '衔接呢？')), '⑤ o03'),
        '英文段有引号': (lambda a, b, c: seg(c, 's1b').update(text='“' + seg(c, 's1b')['text']), '⑤ s1b'),
        '英式拼写': (lambda a, b, c: b['paragraphs'][1][1].update(en=b['paragraphs'][1][1]['en'].replace('house', 'neighbour’s house')), '① 英式拼写'),
    }
    ok = not E0
    print(f'  原稿：{len(E0)} 处' + (f'（{E0[:3]}）' if E0 else ''))
    for k, (f, want) in mines.items():
        e = [x for x in mine(f) if x.startswith(want)]
        print(f'  {k}：{len(e)} 处' + (f'（{e[0][:50]}）' if e else '（漏报）'))
        ok &= bool(e)
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
