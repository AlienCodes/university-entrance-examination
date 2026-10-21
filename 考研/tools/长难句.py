"""考研长难句分析（用户 2026-10-21：和六级一样，但要讲得更细——怎么拆分句子、怎么一步步读懂，挨个句子拆开讲）。

    /opt/ttsenv/bin/python 考研/tools/长难句.py select [k01 …]   # ① 程序挑句 → 考研/长难句/挑句.json（不花 token）
    /opt/ttsenv/bin/python 考研/tools/长难句.py check  [k01 …]   # ② 程序检查模型写的分析 考研/长难句/<篇目>.json
    /opt/ttsenv/bin/python 考研/tools/长难句.py pdf    [k01 …]   # ③ 程序排版 → 考研/听写卡/<文件夹>/… - 4 长难句分析.pdf
    /opt/ttsenv/bin/python 考研/tools/长难句.py plant <输出目录> k01 k02 …   # 复核埋雷（每 6 篇一批，答案在 <输出目录>_key.json）

分工（虹吸）：挑句、检查、排版、参考译文都由程序做；模型只写程序做不了的分析。与六级（六级/tools/长难句.py）相比每句多三项，讲得更细：
  意群：把整句按意群切开（切块），每块标层级（1 = 主干所在的块，2 = 修饰主干的成分，3 = 修饰修饰语的成分……）和顺着英文语序的意思；
        程序核对：各块按顺序拼起来必须与原句一字不差（只忽略空格），主干的谓语必须落在第 1 层的块里；
  易错点：考生最容易读错的地方（误读 → 正解）；
  顺译：按意群顺序直接译出来的“草稿”，再说明怎么调整成通顺的中文（参考译文用已复核定稿的译文，不让模型写）。
挑句：每句按 词数 + 6 × 从句与非谓语结构数（spaCy 依存：relcl、advcl、ccomp、csubj、acl、xcomp、appos、并列谓语）打分，
      词数 ≥ 25 且结构数 ≥ 2 的句子全部入选（每篇最多 8 句，按分数取），不够 3 句就放宽到词数 ≥ 20，按原文顺序排列。
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KY = HERE.parent
DIR = KY / '长难句'
P = {p['id']: p for p in json.loads((KY / 'data' / 'vocab.json').read_text('utf-8'))['passages'] if p.get('done')}
LONG, LONG2, MINN, MAXN = 25, 20, 3, 8
SENTS = {pid: [s for pa in p['paras'] for s in pa] for pid, p in P.items()}
PARTS = ['主句', '主语', '谓语', '宾语', '表语', '宾语补足语', '主语从句', '宾语从句', '表语从句', '同位语从句', '定语从句', '非限制性定语从句',
         '时间状语从句', '原因状语从句', '条件状语从句', '让步状语从句', '目的状语从句', '结果状语从句', '比较状语从句', '方式状语从句', '地点状语从句',
         '现在分词短语', '过去分词短语', '不定式短语', '动名词短语', '介词短语', '形容词短语', '副词短语', '同位语', '插入语', '并列结构', '并列谓语',
         '并列分句', '独立主格结构', '比较结构', '倒装结构', '强调句', '省略结构', 'there be 句型', '形式主语', '形式宾语', '引语', '状语', '定语', '后置定语']
POINTS = PARTS + ['固定搭配', '虚拟语气', '被动语态', '时态', '情态动词', '代词指代', '平行结构', '否定结构', '双重否定', '部分否定', '比较级', '最高级',
                  '名词化', '介词 + which/whom', '关系副词', 'what 从句', 'whether 从句', '分隔结构', '多重定语', '长主语', '破折号', '冒号', '分号']
METHODS = ['顺译', '逆序译', '拆分译', '合并译', '定语前置', '定语后置拆译', '词性转换', '增译', '省译', '被动转主动', '名词动词化', '正反译', '插入语处理']
SEL = DIR / '挑句.json'
CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'


def words(s):
    return len(re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", s))


def select(ids):
    import spacy
    nlp = spacy.load('en_core_web_sm')
    out = json.loads(SEL.read_text('utf-8')) if SEL.exists() else {}
    for pid in ids:
        rows = []
        for k, s in enumerate(SENTS[pid], 1):
            doc = nlp(s['en'])
            n = sum(1 for t in doc if t.dep_ in ('relcl', 'advcl', 'ccomp', 'csubj', 'acl', 'xcomp', 'appos')
                    or (t.dep_ == 'conj' and t.pos_ in ('VERB', 'AUX')))
            rows.append((k, words(s['en']), n))
        score = lambda r: -(r[1] + 6 * r[2])            # noqa: E731
        pick = sorted([r for r in rows if r[1] >= LONG and r[2] >= 2], key=score)[:MAXN]
        if len(pick) < MINN:
            more = sorted([r for r in rows if r not in pick and r[1] >= LONG2], key=score)
            pick += more[:MINN - len(pick)]
        out[pid] = [{'k': k, '词数': w, '结构数': n} for k, w, n in sorted(pick)]
        print(pid, [(r['k'], r['词数'], r['结构数']) for r in out[pid]], flush=True)
    DIR.mkdir(exist_ok=True)
    SEL.write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')


def chunks_ok(en, cs):
    """意群按顺序拼回原句（只忽略空格）；返回每块在原句里的 (起, 止)，拼不回就返回 None。"""
    pos, spans = 0, []
    for c in cs:
        t = (c.get('片段') or '').strip()
        if not t:
            return None
        while pos < len(en) and en[pos] == ' ':
            pos += 1
        if not en.startswith(t, pos):
            return None
        spans.append((pos, pos + len(t)))
        pos += len(t)
    return spans if en[pos:].strip() == '' else None


def problems(pid):
    """检查一篇的分析，返回问题列表（空 = 通过）。"""
    f = DIR / f'{pid}.json'
    if not f.exists():
        return [f'{pid}：没有分析文件']
    try:
        a = json.loads(f.read_text('utf-8'))
    except json.JSONDecodeError as e:
        return [f'{pid}：JSON 格式错误 {e}']
    want = [r['k'] for r in json.loads(SEL.read_text('utf-8'))[pid]]
    got = [x.get('k') for x in a.get('sentences', [])]
    bad = [] if got == want else [f'{pid}：分析的句子 {got} ≠ 挑出的句子 {want}']
    for x in a.get('sentences', []):
        k = x.get('k')
        if k not in want:
            continue
        en, tag = SENTS[pid][k - 1]['en'], f'{pid} 第 {k} 句'

        def span(t, where):
            if not isinstance(t, str) or not t.strip():
                bad.append(f'{tag} {where}：空')
                return -1
            i = en.find(t)
            if i < 0:
                bad.append(f'{tag} {where}：「{t[:40]}」不是原句里一字不差的片段')
            return i
        for key in ('公式', '意群', '主干', '拆解', '读懂步骤', '易错点', '翻译', '知识点'):
            if not x.get(key):
                bad.append(f'{tag}：缺 {key}')
        m = x.get('主干') or {}
        for r in (('谓语',) if (m.get('主语') or '').strip() == '（省略）' else ('主语', '谓语')):
            span(m.get(r), f'主干·{r}')
        if m.get('宾语/表语'):
            span(m['宾语/表语'], '主干·宾语/表语')
        cs = x.get('意群') or []
        sp = chunks_ok(en, cs)
        if sp is None:
            bad.append(f'{tag} 意群：各块按顺序拼起来与原句不一致（每块必须是原句里连续、一字不差的片段，不重不漏）')
        elif len(cs) < 3:
            bad.append(f'{tag} 意群：至少切成 3 块')
        else:
            for c in cs:
                if c.get('层级') not in (1, 2, 3, 4) or not (c.get('意思') or '').strip():
                    bad.append(f'{tag} 意群「{c["片段"][:20]}」：层级须是 1—4、意思不能空')
            v = (m.get('谓语') or '').strip()
            vi = en.find(v) if v else -1
            if vi >= 0 and not any(c.get('层级') == 1 and a0 <= vi < b0 for c, (a0, b0) in zip(cs, sp)):
                bad.append(f'{tag} 意群：主干谓语「{v}」不在第 1 层的块里')
        for r in x.get('拆解', []):
            span(r.get('片段'), '拆解')
            c = re.sub(r'（.*?）$', '', r.get('成分', ''))
            if c not in PARTS:
                bad.append(f'{tag} 拆解：成分「{r.get("成分")}」不在词表里')
            if not r.get('作用'):
                bad.append(f'{tag} 拆解「{(r.get("片段") or "")[:20]}」：缺 作用')
        for r in x.get('知识点', []):
            if re.sub(r'（.*?）$', '', r.get('名称', '')) not in POINTS:
                bad.append(f'{tag} 知识点「{r.get("名称")}」不在词表里')
            span(r.get('例'), '知识点·例')
            if not r.get('说明'):
                bad.append(f'{tag} 知识点「{r.get("名称")}」：缺 说明')
        for r in x.get('易错点', []):
            if not (r.get('误读') or '').strip() or not (r.get('正解') or '').strip():
                bad.append(f'{tag} 易错点：误读、正解都要写')
        t = x.get('翻译') or {}
        if not t.get('方法') or any(mm not in METHODS for mm in t.get('方法', [])) or not t.get('说明') or not (t.get('顺译') or '').strip():
            bad.append(f'{tag} 翻译：方法须从词表里选（{"、".join(METHODS)}），并写说明和顺译')
        if not isinstance(x.get('读懂步骤'), list) or len(x.get('读懂步骤', [])) < 3:
            bad.append(f'{tag} 读懂步骤：至少三步')
    return bad


CSS = """@page{size:A4;margin:16mm 15mm 18mm}
body{font-family:'Noto Sans SC','Source Han Sans SC',sans-serif;color:#1d2330;font-size:10.5pt;line-height:1.6}
h1{font-size:20pt;margin:0 0 2mm;color:#123c69}.sub{color:#556;font-size:10pt;margin-bottom:6mm;border-bottom:1.5px solid #123c69;padding-bottom:2mm}
.guide{border:1.5px solid #123c69;border-radius:3mm;padding:3mm 5mm;margin-bottom:6mm;background:#f5f8fd}.guide h2{font-size:12pt;color:#123c69;margin:0 0 1.5mm}
.guide ol{margin:0;padding-left:6mm}.guide li{margin:.6mm 0}
.s{margin:0 0 7mm;padding:4mm 5mm;border:1px solid #d5dbe5;border-radius:3mm;background:#fbfcfe}
.no{display:inline-block;background:#123c69;color:#fff;border-radius:2mm;padding:0 2.5mm;font-size:9.5pt;margin-right:2mm}
.en{font-family:'Inter','Noto Sans',sans-serif;font-size:11.5pt;line-height:1.75;margin:2mm 0 3mm}
.en b{color:#b3261e}.f{background:#fff6d6;border-left:3px solid #e0a800;padding:1.5mm 3mm;margin:2mm 0;font-weight:600}
.cut{font-family:'Inter','Noto Sans',sans-serif;font-size:11pt;line-height:1.9;background:#f4f7fb;border-radius:2mm;padding:2mm 3mm}
.cut .sl{color:#d0021b;font-weight:700;margin:0 1.2mm}.cut sup{color:#123c69;font-weight:700;font-size:8pt}
.cut .l1{color:#b3261e;font-weight:600}
h3{font-size:11pt;color:#123c69;margin:3mm 0 1mm;break-after:avoid}.s+.s{break-before:page}tr,.en,.f,.zh,.dr,li,.kp>div,.er>div{break-inside:avoid}
table{border-collapse:collapse;width:100%;font-size:10pt;table-layout:fixed}
td,th{border:1px solid #d5dbe5;padding:1.2mm 2mm;vertical-align:top;text-align:left}th{background:#eef2f8;font-weight:600}
td.e{font-family:'Inter','Noto Sans',sans-serif}.lv{display:inline-block;font-size:8pt;border-radius:1.5mm;padding:0 1.5mm;margin-right:1.5mm;color:#fff}
.lv1{background:#b3261e}.lv2{background:#1052a8}.lv3{background:#2e7d32}.lv4{background:#8e44ad}
ol{margin:0;padding-left:6mm}.zh{background:#eef6ee;border-left:3px solid #3c8d40;padding:1.5mm 3mm}
.dr{background:#f6f6f6;border-left:3px solid #999;padding:1.5mm 3mm;margin-bottom:1.5mm;color:#333}
.er>div{margin:.8mm 0}.er .x{color:#b3261e;font-weight:600}.er .v{color:#2e7d32;font-weight:600}
.kp b{color:#123c69}.mono{font-family:'Inter',sans-serif}"""

LEVEL = {1: '主干', 2: '一层修饰', 3: '二层修饰', 4: '三层修饰'}
GUIDE = """<div class='guide'><h2>考研长难句通用拆解法（每句都按这五步走）</h2><ol>
<li><b>切意群</b>：先看标点（逗号、破折号、括号、分号）和“信号词”——连词（and / but / because / although / if / when）、关系词（who / which / that / where）、
非谓语（to do / doing / done）、介词短语开头处——在这些地方画“/”，把长句切成几小块，每块单独都能看懂。</li>
<li><b>找主干</b>：在各块里找<b>真正的谓语动词</b>（有时态、跟主语一致的那个动词；to do、doing、done 不是谓语），它前面的核心名词是主语，后面的是宾语或表语。主干所在的块是第 1 层。</li>
<li><b>挂修饰</b>：其余每块都问一句“它修饰谁 / 说明什么”——修饰主干的是第 2 层，修饰第 2 层的是第 3 层……把层次理清，句子就不乱了。</li>
<li><b>顺着读</b>：按意群顺序一块一块往下理解（顺译），不要回头找、不要逐词死抠；遇到“插入语”先跳过，读完主干再回来看。</li>
<li><b>调成中文</b>：把顺译的草稿按中文习惯调整——长定语往前放或拆成短句、被动改主动、名词化改动词——得到通顺的译文。</li></ol></div>"""


def esc(s):
    return html.escape(s or '', quote=False)


def mark(en, m):
    """原句里把主干（主语、谓语、宾语/表语）加粗标红（与六级相同：主语取紧挨在谓语前面的那一处，宾语/表语取谓语后面的第一处）。"""
    def finds(t):
        t = (t or '').strip()
        if not t or t.startswith('（'):
            return []
        pat = re.compile(r'(?<![A-Za-z])' + re.escape(t) + r'(?![A-Za-z])')
        hs = [(h.start(), h.end()) for h in pat.finditer(en)]
        i = en.find(t)
        return hs or ([(i, i + len(t))] if i >= 0 else [])
    S, V, O = (finds(m.get(r)) for r in ('主语', '谓语', '宾语/表语'))
    spans = []
    if S and V:
        pairs = [(v[0] - s[1], s, v) for s in S for v in V if s[1] <= v[0]]
        if pairs:
            _, s, v = min(pairs)
        else:
            v = V[0]
            s = next((s for s in S if s[0] >= v[1]), S[0])
        spans = [s, v]
    else:
        spans = (S or V)[:1]
    if O:
        after = max(x[1] for x in spans) if spans else 0
        spans.append(next((o for o in O if o[0] >= after), O[0]))
    out, cur = [], 0
    for a, b in sorted(spans):
        if a < cur:
            continue
        out += [esc(en[cur:a]), f'<b>{esc(en[a:b])}</b>']
        cur = b
    return ''.join(out) + esc(en[cur:])


def cut_html(cs):
    """断句图：原句按意群切开，块与块之间画红色“/”，每块前标圆圈序号；第 1 层（主干）的块加深标红。"""
    out = []
    for i, c in enumerate(cs):
        cls = ' class="l1"' if c['层级'] == 1 else ''
        out.append(f'<sup>{CIRC[i]}</sup><span{cls}>{esc(c["片段"])}</span>')
    return '<span class="sl">/</span>'.join(out)


def kp(r):
    return f"<div><b>{esc(r['名称'])}</b>：<span class='mono'>{esc(r['例'])}</span> —— {esc(r['说明'])}</div>"


def page_html(pid):
    p = P[pid]
    a = json.loads((DIR / f'{pid}.json').read_text('utf-8'))
    body = [f"<h1>长难句分析</h1><div class='sub'>考研英语 {esc(p['paper'])} {esc(p['passage'])} · {esc(p['title'])} · "
            f"本篇 {len(a['sentences'])} 句（红色加粗 = 句子主干；红色“/” = 意群切分处）</div>{GUIDE}"]
    for x in a['sentences']:
        s = SENTS[pid][x['k'] - 1]
        m = x['主干']
        crow = ''.join(f"<tr><td>{CIRC[i]}</td><td class='e' style='padding-left:{2 + 5 * (c['层级'] - 1)}mm'>"
                       f"<span class='lv lv{c['层级']}'>{LEVEL[c['层级']]}</span>{esc(c['片段'])}</td><td>{esc(c['意思'])}</td></tr>"
                       for i, c in enumerate(x['意群']))
        rows = ''.join(f"<tr><td class='e'>{esc(r['片段'])}</td><td>{esc(r['成分'])}</td><td>{esc(r['作用'])}</td><td>{esc(r.get('说明', ''))}</td></tr>"
                       for r in x['拆解'])
        errs = ''.join(f"<div><span class='x'>✗ 误读：</span>{esc(r['误读'])}<br><span class='v'>✓ 正解：</span>{esc(r['正解'])}</div>" for r in x['易错点'])
        body.append(
            f"<div class='s'><span class='no'>第 {x['k']} 句</span><span style='color:#667;font-size:9.5pt'>{words(s['en'])} 词</span>"
            f"<div class='en'>{mark(s['en'], m)}</div>"
            f"<div class='f'>结构：{esc(x['公式'])}</div>"
            f"<h3>① 切意群：先在哪里画“/”</h3><div class='cut'>{cut_html(x['意群'])}</div>"
            f"<table style='margin-top:1.5mm'><colgroup><col style='width:6%'><col style='width:56%'><col style='width:38%'></colgroup>"
            f"<tr><th>块</th><th>意群（缩进 = 层级）</th><th>这一块的意思（顺着英文语序）</th></tr>{crow}</table>"
            f"<h3>② 找主干</h3><div>主语：<span class='mono'>{esc(m['主语'])}</span>　谓语：<span class='mono'>{esc(m['谓语'])}</span>"
            + (f"　宾语/表语：<span class='mono'>{esc(m['宾语/表语'])}</span>" if m.get('宾语/表语') else '') + "</div>"
            f"<h3>③ 层层拆解：每个修饰成分挂在谁身上</h3><table><colgroup><col style='width:29%'><col style='width:15%'><col style='width:22%'><col style='width:34%'></colgroup>"
            f"<tr><th>片段</th><th>成分</th><th>作用（修饰谁 / 做什么）</th><th>说明</th></tr>{rows}</table>"
            f"<h3>④ 一步步读懂</h3><ol>{''.join(f'<li>{esc(t)}</li>' for t in x['读懂步骤'])}</ol>"
            f"<h3>⑤ 易错点：最容易读错的地方</h3><div class='er'>{errs}</div>"
            f"<h3>⑥ 怎么翻译</h3><div class='dr'>顺译草稿：{esc(x['翻译']['顺译'])}</div>"
            f"<div>调整方法：{esc('、'.join(x['翻译']['方法']))}。{esc(x['翻译']['说明'])}</div>"
            f"<div class='zh' style='margin-top:1.5mm'>参考译文：{esc(s['zh'])}</div>"
            f"<h3>⑦ 知识点</h3><div class='kp'>{''.join(kp(r) for r in x['知识点'])}</div></div>")
    return f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{''.join(body)}</body></html>"


def pdf(ids):
    sys.path.insert(0, str(HERE))
    import make_dictation as MD
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page()
        for pid in ids:
            bad = problems(pid)
            if bad:
                raise SystemExit('检查没通过，不排版：\n  ' + '\n  '.join(bad))
            p = MD.P[pid]
            d, base = MD.folder(p), MD.base_name(p)
            d.mkdir(parents=True, exist_ok=True)
            pg.set_content(page_html(pid))
            pg.evaluate('document.fonts.ready')
            f = d / f'{base} - 4 长难句分析.pdf'
            pg.pdf(path=str(f), format='A4', print_background=True, display_header_footer=True, header_template='<span></span>',
                   footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#999'><span class='pageNumber'></span> / <span class='totalPages'></span></div>",
                   margin={'top': '16mm', 'bottom': '18mm', 'left': '15mm', 'right': '15mm'})
            print(f'{f.name}', flush=True)
        br.close()


SWAP = {'定语从句': '宾语从句', '宾语从句': '定语从句', '非限制性定语从句': '同位语从句', '同位语从句': '定语从句', '现在分词短语': '过去分词短语',
        '过去分词短语': '现在分词短语', '不定式短语': '动名词短语', '原因状语从句': '条件状语从句', '条件状语从句': '原因状语从句',
        '时间状语从句': '让步状语从句', '让步状语从句': '时间状语从句', '介词短语': '同位语', '表语从句': '主语从句', '主语从句': '宾语从句'}


def plant(batches, out):
    """复核埋雷：每批复制到 out/bNN/，在每批一篇里埋 3 个确定的错误（成分名称换错、主干主语换成修饰成分、两块意群的“意思”对调），
    答案写在 <out>_key.json（审阅员看不到）。"""
    import random
    import shutil
    out = Path(out)
    shutil.rmtree(out, ignore_errors=True)
    key = []
    for i, b in enumerate(batches, 1):
        d = out / f'b{i:02d}'
        d.mkdir(parents=True)
        for pid in b:
            shutil.copy(DIR / f'{pid}.json', d / f'{pid}.json')
        rnd = random.Random(f'kaoyan-ld-{i}')
        pid = rnd.choice(b)
        a = json.loads((d / f'{pid}.json').read_text('utf-8'))
        xs = a['sentences']
        mines = []
        x = next((x for x in xs if any(r['成分'] in SWAP for r in x['拆解'])), None)
        if x:
            r = next(r for r in x['拆解'] if r['成分'] in SWAP)
            mines.append({'pid': pid, 'k': x['k'], 'what': f"拆解「{r['片段'][:30]}」成分 {r['成分']} → {SWAP[r['成分']]}"})
            r['成分'] = SWAP[r['成分']]
        x = next((x for x in xs if x['k'] not in [m['k'] for m in mines] and len(x['拆解']) >= 2), xs[-1])
        cand = [r['片段'] for r in x['拆解'] if r['片段'] != x['主干']['主语'] and r['成分'] not in ('主句', '主语', '谓语')]
        if cand:
            mines.append({'pid': pid, 'k': x['k'], 'what': f"主干主语 {x['主干']['主语'][:30]} → {cand[0][:30]}"})
            x['主干']['主语'] = cand[0]
        y = next((y for y in xs if len(y['意群']) >= 4 and y['k'] not in [m['k'] for m in mines]), xs[0])
        c1, c2 = y['意群'][1], y['意群'][-1]
        mines.append({'pid': pid, 'k': y['k'], 'what': f"意群「{c1['片段'][:20]}」与「{c2['片段'][:20]}」的意思对调"})
        c1['意思'], c2['意思'] = c2['意思'], c1['意思']
        (d / f'{pid}.json').write_text(json.dumps(a, ensure_ascii=False, indent=1), 'utf-8')
        key.append({'batch': f'b{i:02d}', 'passages': b, 'mines': mines})
    Path(str(out) + '_key.json').write_text(json.dumps(key, ensure_ascii=False, indent=1), 'utf-8')
    return key


if __name__ == '__main__':
    cmd, ids = sys.argv[1], sys.argv[2:] or list(P)
    if cmd == 'select':
        select(ids)
    elif cmd == 'check':
        bad = [b for pid in ids for b in problems(pid)]
        print('\n'.join(bad) or f'{len(ids)} 篇全部通过')
        sys.exit(1 if bad else 0)
    elif cmd == 'pdf':
        pdf(ids)
    elif cmd == 'plant':
        ps = ids[1:]
        print(json.dumps(plant([ps[i:i + 6] for i in range(0, len(ps), 6)], ids[0]), ensure_ascii=False)[:300])
