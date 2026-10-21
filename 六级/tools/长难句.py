"""六级、高考（加 --gaokao）长难句分析（用户 2026-10-21：每篇把又长又复杂的句子挑出来，讲清楚怎么读懂、怎么翻译、包含哪些知识点）。

    /opt/ttsenv/bin/python 六级/tools/长难句.py select [s01 …]   # ① 程序挑句 → 六级/长难句/挑句.json（不花 token）
    /opt/ttsenv/bin/python 六级/tools/长难句.py check  [s01 …]   # ② 程序检查模型写的分析 六级/长难句/<篇目>.json
    /opt/ttsenv/bin/python 六级/tools/长难句.py pdf    [s01 …]   # ③ 程序排版 → 六级/听写卡/<文件夹>/… - 4 长难句分析.pdf

分工（虹吸）：挑句、检查、排版、参考译文都由程序做；模型只写程序做不了的“结构分析、读懂步骤、翻译方法、知识点”。
挑句：每句按 词数 + 6 × 从句与非谓语结构数（spaCy 依存：relcl、advcl、ccomp、csubj、acl、xcomp、appos、并列谓语）打分，
      词数 ≥ 25 且结构数 ≥ 2 的句子按分数取前 4 句（不够就放宽到词数 ≥ 22，至少 2 句、最多 5 句），按原文顺序排列。
检查：所有引用的英文片段必须与原句一字不差、按出现顺序；“成分”“知识点”只能用下面词表里的名称；必填项不能空；
      参考译文不让模型写，排版时直接用已复核定稿的译文（六级/data/vocab.json）。
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C6 = HERE.parent
GK = '--gaokao' in sys.argv          # 高考 70 篇（用户 2026-10-21：高考也要长难句分析）：数据 data/vocab.json，分析 长难句/，PDF 放进 听写卡/<篇目文件夹>/
if GK:
    sys.argv.remove('--gaokao')
BASE = C6.parent if GK else C6
DIR = BASE / '长难句'
P = {p['id']: p for p in json.loads((BASE / 'data' / 'vocab.json').read_text('utf-8'))['passages'] if p.get('done')}
LONG, LONG2, MAXN = (20, 17, 4) if GK else (25, 22, 5)   # 高考句子短：词数门槛 20（放宽 17），每篇最多 4 句
SENTS = {pid: [s for pa in p['paras'] for s in pa] for pid, p in P.items()}
PARTS = ['主句', '主语', '谓语', '宾语', '表语', '宾语补足语', '主语从句', '宾语从句', '表语从句', '同位语从句', '定语从句', '非限制性定语从句',
         '时间状语从句', '原因状语从句', '条件状语从句', '让步状语从句', '目的状语从句', '结果状语从句', '比较状语从句', '方式状语从句', '地点状语从句',
         '现在分词短语', '过去分词短语', '不定式短语', '动名词短语', '介词短语', '形容词短语', '副词短语', '同位语', '插入语', '并列结构', '并列谓语',
         '独立主格结构', '比较结构', '倒装结构', '强调句', '省略结构', 'there be 句型', '形式主语', '形式宾语', '引语']
POINTS = PARTS + ['固定搭配', '虚拟语气', '被动语态', '时态', '情态动词', '代词指代', '平行结构', '否定结构', '双重否定', '部分否定', '比较级', '最高级',
                  '名词化', '介词 + which/whom', '关系副词', 'what 从句', 'whether 从句', '分隔结构', '后置定语', '多重定语', '长主语']
METHODS = ['顺译', '逆序译', '拆分译', '合并译', '定语前置', '定语后置拆译', '词性转换', '增译', '省译', '被动转主动', '名词动词化', '正反译', '插入语处理']
SEL = DIR / '挑句.json'


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
        pick = [r for r in rows if r[1] >= LONG and r[2] >= 2]
        if len(pick) < 2:
            pick = sorted(rows, key=lambda r: -(r[1] + 6 * r[2]))[:2] if len([r for r in rows if r[1] >= LONG2]) < 2 else \
                   [r for r in rows if r[1] >= LONG2]
        pick = sorted(pick, key=lambda r: -(r[1] + 6 * r[2]))[:4 if len(pick) <= 6 else MAXN]
        out[pid] = [{'k': k, '词数': w, '结构数': n} for k, w, n in sorted(pick)]
        print(pid, [(r['k'], r['词数'], r['结构数']) for r in out[pid]], flush=True)
    DIR.mkdir(exist_ok=True)
    SEL.write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')


def problems(pid):
    """检查一篇的分析，返回问题列表（空 = 通过）。"""
    f = DIR / f'{pid}.json'
    if not f.exists():
        return [f'{pid}：没有分析文件']
    a = json.loads(f.read_text('utf-8'))
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
                bad.append(f'{tag} {where}：空'); return -1
            i = en.find(t)
            if i < 0:
                bad.append(f'{tag} {where}：「{t[:40]}」不是原句里一字不差的片段')
            return i
        for key in ('公式', '读懂步骤', '翻译', '知识点', '主干', '拆解'):
            if not x.get(key):
                bad.append(f'{tag}：缺 {key}')
        m = x.get('主干') or {}
        pos = [span(m.get(r), f'主干·{r}') for r in (('谓语',) if (m.get('主语') or '').strip() == '（省略）' else ('主语', '谓语'))] + ([span(m['宾语/表语'], '主干·宾语/表语')] if m.get('宾语/表语') else [])
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
        t = x.get('翻译') or {}
        if not t.get('方法') or any(mm not in METHODS for mm in t.get('方法', [])) or not t.get('说明'):
            bad.append(f'{tag} 翻译：方法须从词表里选（{"、".join(METHODS)}），并写说明')
        if not isinstance(x.get('读懂步骤'), list) or len(x.get('读懂步骤', [])) < 2:
            bad.append(f'{tag} 读懂步骤：至少两步')
    return bad


CSS = """@page{size:A4;margin:16mm 15mm 18mm}
body{font-family:'Noto Sans SC','Source Han Sans SC',sans-serif;color:#1d2330;font-size:10.5pt;line-height:1.6}
h1{font-size:20pt;margin:0 0 2mm;color:#123c69}.sub{color:#556;font-size:10pt;margin-bottom:6mm;border-bottom:1.5px solid #123c69;padding-bottom:2mm}
.s{margin:0 0 7mm;padding:4mm 5mm;border:1px solid #d5dbe5;border-radius:3mm;background:#fbfcfe}
.no{display:inline-block;background:#123c69;color:#fff;border-radius:2mm;padding:0 2.5mm;font-size:9.5pt;margin-right:2mm}
.en{font-family:'Inter','Noto Sans',sans-serif;font-size:11.5pt;line-height:1.75;margin:2mm 0 3mm}
.en b{color:#b3261e}.f{background:#fff6d6;border-left:3px solid #e0a800;padding:1.5mm 3mm;margin:2mm 0;font-weight:600}
h3{font-size:11pt;color:#123c69;margin:3mm 0 1mm;break-after:avoid}.s+.s{break-before:page}tr,.en,.f,.zh,li,.kp>div{break-inside:avoid}table{border-collapse:collapse;width:100%;font-size:10pt;table-layout:fixed}
td,th{border:1px solid #d5dbe5;padding:1.2mm 2mm;vertical-align:top;text-align:left}th{background:#eef2f8;font-weight:600}
td.e{font-family:'Inter','Noto Sans',sans-serif}ol{margin:0;padding-left:6mm}.zh{background:#eef6ee;border-left:3px solid #3c8d40;padding:1.5mm 3mm}
.kp b{color:#123c69}.mono{font-family:'Inter',sans-serif}"""


def esc(s):
    return html.escape(s or '', quote=False)


def mark(en, m):
    """原句里把主干（主语、谓语、宾语/表语）加粗标红：整词匹配（“is”不落在“This”里），并按句中顺序找（谓语在主语之后、宾语/表语在谓语之后）；
    祈使句主语写“（省略）”，不标。"""
    spans, pos = [], 0
    for t in (m.get('主语'), m.get('谓语'), m.get('宾语/表语')):
        t = (t or '').strip()
        if not t or t.startswith('（'):
            continue
        pat = re.compile(r'(?<![A-Za-z])' + re.escape(t) + r'(?![A-Za-z])')
        hit = pat.search(en, pos) or pat.search(en)
        a = hit.start() if hit else en.find(t)
        if a >= 0:
            spans.append((a, a + len(t)))
            pos = a + len(t)
    out, cur = [], 0
    for a, b in sorted(spans):
        if a < cur:
            continue
        out += [esc(en[cur:a]), f'<b>{esc(en[a:b])}</b>']
        cur = b
    return ''.join(out) + esc(en[cur:])


def kp(r):
    return f"<div><b>{esc(r['名称'])}</b>：<span class='mono'>{esc(r['例'])}</span> —— {esc(r['说明'])}</div>"


def page_html(pid):
    p = P[pid]
    a = json.loads((DIR / f'{pid}.json').read_text('utf-8'))
    src = f"高考英语 {esc(p['name'])}" if GK else f"大学英语六级 {esc(p['paper'])} {esc(p['passage'])}"
    body = [f"<h1>长难句分析</h1><div class='sub'>{src} · {esc(p['title'])} · "
            f"本篇 {len(a['sentences'])} 句（红色加粗 = 句子主干）</div>"]
    for x in a['sentences']:
        s = SENTS[pid][x['k'] - 1]
        m = x['主干']
        rows = ''.join(f"<tr><td class='e'>{esc(r['片段'])}</td><td>{esc(r['成分'])}</td><td>{esc(r['作用'])}</td><td>{esc(r.get('说明', ''))}</td></tr>"
                       for r in x['拆解'])
        body.append(
            f"<div class='s'><span class='no'>第 {x['k']} 句</span><div class='en'>{mark(s['en'], m)}</div>"
            f"<div class='f'>结构：{esc(x['公式'])}</div>"
            f"<h3>① 找主干</h3><div>主语：<span class='mono'>{esc(m['主语'])}</span>　谓语：<span class='mono'>{esc(m['谓语'])}</span>"
            + (f"　宾语/表语：<span class='mono'>{esc(m['宾语/表语'])}</span>" if m.get('宾语/表语') else '') + "</div>"
            f"<h3>② 层层拆解</h3><table><colgroup><col style='width:29%'><col style='width:15%'><col style='width:22%'><col style='width:34%'></colgroup><tr><th>片段</th><th>成分</th><th>作用（修饰谁 / 做什么）</th><th>说明</th></tr>{rows}</table>"
            f"<h3>③ 怎么读懂</h3><ol>{''.join(f'<li>{esc(t)}</li>' for t in x['读懂步骤'])}</ol>"
            f"<h3>④ 怎么翻译</h3><div>方法：{esc('、'.join(x['翻译']['方法']))}。{esc(x['翻译']['说明'])}</div>"
            f"<div class='zh'>参考译文：{esc(s['zh'])}</div>"
            f"<h3>⑤ 知识点</h3><div class='kp'>{''.join(kp(r) for r in x['知识点'])}</div></div>")
    return f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{''.join(body)}</body></html>"


def pdf(ids):
    if not GK:
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
            if GK:                                 # 高考听写卡文件夹：“序号 年份 试卷 阅读X 题目”，每篇恰好一个
                fs = [d for d in (BASE / '听写卡').iterdir() if d.name[3:] == f"{P[pid]['name']} {P[pid]['title']}"]
                assert len(fs) == 1, (pid, fs)
                d, base = fs[0], fs[0].name[3:]
            else:
                p = MD.P[pid] if hasattr(MD, 'P') else next(x for x in MD.ORDER if x['id'] == pid)
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
    """复核埋雷：把每批的分析复制到 out/bNN/，在每批一篇里埋 3 个确定的错误（成分名称换错、主干主语换成修饰成分、两行“作用”对调），
    答案写在 out 旁边的 <out>_key.json（审阅员看不到）。"""
    import random, shutil
    out = Path(out)
    shutil.rmtree(out, ignore_errors=True)
    key = []
    for i, b in enumerate(batches, 1):
        d = out / f'b{i:02d}'
        d.mkdir(parents=True)
        for pid in b:
            shutil.copy(DIR / f'{pid}.json', d / f'{pid}.json')
        rnd = random.Random(f'cet6-ld-{i}')
        pid = rnd.choice(b)
        a = json.loads((d / f'{pid}.json').read_text('utf-8'))
        xs = a['sentences']
        mines = []
        x = next((x for x in xs if any(r['成分'] in SWAP for r in x['拆解'])), None)
        if x:
            r = next(r for r in x['拆解'] if r['成分'] in SWAP)
            mines.append({'pid': pid, 'k': x['k'], 'what': f"拆解「{r['片段'][:30]}」成分 {r['成分']} → {SWAP[r['成分']]}"})
            r['成分'] = SWAP[r['成分']]
        x = next((x for x in xs if x is not (mines and None) and len(x['拆解']) >= 2 and x['k'] not in [m['k'] for m in mines]), xs[-1])
        cand = [r['片段'] for r in x['拆解'] if r['片段'] != x['主干']['主语'] and r['成分'] not in ('主句', '主语', '谓语')]
        if cand:
            mines.append({'pid': pid, 'k': x['k'], 'what': f"主干主语 {x['主干']['主语'][:30]} → {cand[0][:30]}"})
            x['主干']['主语'] = cand[0]
        y = next((y for y in xs if len(y['拆解']) >= 3 and y['k'] not in [m['k'] for m in mines]), None) or next(y for y in xs if len(y['拆解']) >= 2)
        r1, r2 = y['拆解'][0], y['拆解'][-1]
        mines.append({'pid': pid, 'k': y['k'], 'what': f"拆解「{r1['片段'][:20]}」与「{r2['片段'][:20]}」的作用对调"})
        r1['作用'], r2['作用'] = r2['作用'], r1['作用']
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
    elif cmd == 'plant':           # plant <out_dir> s01 s02 … ：每 6 篇一批
        ps = ids[1:]
        print(json.dumps(plant([ps[i:i + 6] for i in range(0, len(ps), 6)], ids[0]), ensure_ascii=False)[:300])
