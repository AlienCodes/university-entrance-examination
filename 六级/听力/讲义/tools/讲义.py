"""六级听力真题 30 套 · 付费讲义套装（2026-11-04）。
版式、断行检查（WRAP_JS）、可点目录 + 书签 + “已读”复选框（toc_check）全部沿用 六级作文/tools/讲义.py（同一系列）。
数据：原文与译文 = 精读已复核的 vocab.json；答案 = 答案裁定.json；解析 = 讲义/解析/<套>.json（解析检查.py 先过）。

python3 讲义.py build [main|syn|vocab|dict|plan|all] [套 …]   不写套 = 30 套
所有数字（套数、题数、词数、页数）都由程序现算。"""
import collections
import html
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / '成品'
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import 材料 as M  # noqa: E402
import 解析检查 as JC  # noqa: E402

_spec = importlib.util.spec_from_file_location('zw_jiangyi', ROOT / '六级作文' / 'tools' / '讲义.py')
J = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(J)
esc = J.esc

NAMES = {'main': '六级听力真题30套精讲', 'syn': '六级听力同义替换手册', 'vocab': '六级听力高频词手册',
         'dict': '六级听力听写本', 'dans': '六级听力听写本（答案）', 'plan': '六级听力30天刷题计划'}

J.CSS += r"""
/* 六级听力讲义 */
.ov{display:grid;grid-template-columns:1fr 62mm;gap:4mm;margin-bottom:3mm;break-inside:avoid}
.ov .sm{font-family:Apos,'LXGW WenKai','Noto Sans SC';font-size:9.8pt;color:var(--ink2);line-height:1.7;background:var(--soft);border-radius:3mm;padding:3mm 4mm}
.ak{display:grid;grid-template-columns:repeat(5,1fr);gap:1.2mm;align-content:start}
.ak div{border:1px solid var(--rule);border-radius:1.5mm;text-align:center;font-size:8.6pt;line-height:1.35;padding:.6mm 0;background:#fff}
.ak div b{display:block;font-family:'Nunito','Noto Sans SC';font-size:11pt;color:var(--berry)}
.ak .t{grid-column:1/-1;border:0;background:none;text-align:left;font-weight:700;color:var(--blue);font-size:9pt}
.gh{display:flex;align-items:baseline;gap:3mm;margin:7mm 0 2.5mm;border-bottom:1.6px solid var(--blue);padding-bottom:1.2mm;break-after:avoid}
.gh b{font-family:'EB Garamond','Noto Sans SC';font-size:15pt;color:var(--blue)}.gh span{font-size:9.6pt;color:var(--mute)}.gh i{margin-left:auto;font-style:normal;font-size:9pt;color:var(--mute)}
.lab2{display:table;font-weight:700;color:#fff;background:var(--ink2);border-radius:1.5mm;padding:.2mm 2.5mm;font-size:9pt;margin:2mm 0 1.6mm;break-after:avoid}
.st{display:grid;grid-template-columns:7mm 1fr;gap:0 1.5mm;margin:0 0 1.5mm;break-inside:avoid}
.st .k{font-family:'Nunito','Noto Sans SC';font-size:7pt;color:var(--mute);text-align:right;padding-top:1.3mm}
.st .e{font-family:'EB Garamond','Noto Sans SC',serif;font-size:11.4pt;line-height:1.5}
.st .z{grid-column:2;font-family:Apos,'LXGW WenKai','Noto Sans SC';font-size:9.2pt;color:var(--mute);line-height:1.55}
.qg{border-top:1px solid #d5d8de;padding:3mm 0 2.4mm;break-inside:avoid}
.qg:first-of-type{border-top:0}
.qh{display:grid;grid-template-columns:9mm 1fr;gap:0 2mm;margin-bottom:1.6mm}
.qn{font-family:'Nunito','Noto Sans SC';font-weight:800;color:#fff;background:var(--blue);border-radius:1.8mm;height:7mm;display:flex;align-items:center;justify-content:center;font-size:10.5pt}
.qe{font-family:'EB Garamond','Noto Sans SC',serif;font-size:11.6pt;font-weight:600;line-height:1.4}.qz{font-size:9.2pt;color:var(--mute)}
.op{display:grid;grid-template-columns:1fr 1fr;gap:1mm 3mm;margin:0 0 1.8mm 11mm}
.op>div{display:grid;grid-template-columns:5mm 1fr;gap:0 1mm;border-radius:1.6mm;padding:.6mm 1.6mm}
.op>div b{font-family:'Nunito','Noto Sans SC';color:var(--mute);font-size:9.5pt}
.op .oe{font-family:'EB Garamond','Noto Sans SC',serif;font-size:10.8pt;line-height:1.4}.op .oz{grid-column:2;font-size:8.8pt;color:var(--mute);line-height:1.45}
.op .ok{background:#e9f6ee;box-shadow:inset 0 0 0 1.2px #8cc9a3}.op .ok b{color:var(--green)}.op .ok .oe{font-weight:600}
.rw{margin:0 0 1.4mm 11mm;font-size:9.8pt;line-height:1.65}
.rw>b{display:inline-block;min-width:17mm;font-size:8.8pt;color:#fff;border-radius:1.2mm;padding:0 1.6mm;margin-right:2mm;text-align:center}
.yj>b{background:var(--blue)}.jg>b{background:var(--green)}.tb>b{background:#b7791f}.cw>b{background:var(--berry)}
.yj .en{font-family:'EB Garamond','Noto Sans SC',serif;font-size:11pt;background:linear-gradient(var(--hy),var(--hy)) 0 89.7%/100% 42% no-repeat}
.yj i{font-style:normal;font-size:8.4pt;color:var(--mute);margin-left:1mm}
.jg span{font-family:Apos,'LXGW WenKai','Noto Sans SC';color:var(--ink)}
.tb .p{display:block;margin:.3mm 0 .3mm 19mm;font-family:'EB Garamond','Noto Sans SC',serif;font-size:10.8pt}.tb .p u{text-decoration:none;color:var(--green);font-weight:600}.tb .p s{text-decoration:none;color:var(--blue)}
.tag{display:inline-block;font-style:normal;font-size:8pt;border-radius:1.2mm;padding:0 1.4mm;margin:0 1mm;line-height:1.5;vertical-align:.08em}
.tag.t{background:#fff1d6;color:#8a5a00}.tag.w{background:#fde7ee;color:var(--berry)}
.cw .x{display:block;margin:.2mm 0}.cw .x>em{font-style:normal;font-family:'Nunito','Noto Sans SC';font-weight:800;color:var(--berry);margin-right:.5mm}
.hv{display:grid;grid-template-columns:repeat(3,1fr);gap:0 4mm}
.hv>div{border-bottom:1px solid #e6e2d8;padding:1mm .5mm;break-inside:avoid;font-size:9pt;line-height:1.4}
.hv b{font-family:'EB Garamond','Noto Sans SC';font-size:11pt}.hv i{float:right;font-style:normal;font-family:'Nunito','Noto Sans SC';font-size:7.8pt;color:var(--berry)}.hv span{display:block;color:var(--mute);font-size:8.6pt}
.guide{font-size:10.2pt}.guide .box p{margin:.8mm 0}
/* 同义替换手册 */
.sy{display:grid;grid-template-columns:1fr 1fr 27mm;font-size:9.4pt;break-inside:avoid}
.sy>div{border-bottom:1px solid #e6e2d8;padding:1.2mm 2mm}.sy.th>div{background:var(--ink);color:#fff;font-weight:500;border:0}
.sy .a{font-family:'EB Garamond','Noto Sans SC';font-size:10.8pt;color:var(--green);font-weight:600}.sy .b{font-family:'EB Garamond','Noto Sans SC';font-size:10.8pt;color:var(--blue)}
.sy .c{font-size:8.4pt;color:var(--mute)}
/* 高频词手册 */
.vw{display:grid;grid-template-columns:30mm 1fr 10mm 72mm;font-size:9.2pt;break-inside:avoid}
.vw>div{border-bottom:1px solid #e6e2d8;padding:1.1mm 1.6mm}.vw.th>div{background:var(--ink);color:#fff;font-weight:500;border:0}
.vw .w{font-family:'EB Garamond','Noto Sans SC';font-size:11pt;font-weight:600}.vw .n{font-family:'Nunito','Noto Sans SC';font-weight:700;color:var(--berry);text-align:center}
.vw .s{font-size:7.8pt;color:var(--mute);line-height:1.45}
/* 听写本 */
.dt{font-family:'EB Garamond','Noto Sans SC',serif;font-size:12pt;line-height:2.3;margin-bottom:2mm;text-align:justify}
.dt .gap sup{top:-.9em}
.da{display:grid;grid-template-columns:repeat(4,1fr);gap:0 3mm}
.da>div{border-bottom:1px dotted #d9d4c7;padding:.6mm 0;font-size:9pt;break-inside:avoid}
.da em{font-style:normal;font-family:'Nunito','Noto Sans SC';font-weight:800;color:var(--berry);font-size:8pt;margin-right:1.2mm}.da b{font-family:'EB Garamond','Noto Sans SC';font-size:11pt}
/* 30 天计划 */
.pl{display:grid;grid-template-columns:13mm 31mm 1fr 19mm 14mm;font-size:9.2pt;break-inside:avoid;align-items:center}
.pl>div{border-bottom:1px solid #e6e2d8;padding:1.6mm 1.5mm}.pl.th>div{background:var(--ink);color:#fff;font-weight:500;border:0}
.pl .d{font-family:'Nunito','Noto Sans SC';font-weight:800;color:var(--blue);font-size:11pt}
.pl .t span{display:inline-block;margin-right:2.6mm;white-space:nowrap}.pl .t span::before{content:'';display:inline-block;width:3mm;height:3mm;border:1.3px solid var(--blue);border-radius:.8mm;margin-right:1mm;vertical-align:-.4mm}
.pl .sc{color:var(--mute);font-size:8.6pt}.pl .pg{font-family:'Nunito','Noto Sans SC';font-weight:700;color:var(--blue);text-align:right}
"""

TYPES_NOTE = {
    '同义改写': '换一个意思相同的词或短语，最常见的一种。',
    '词性句式转换': '意思不变，词性或句子结构变了，比如动词变名词、主动变被动。',
    '正反转换': '一边是肯定说法，一边是否定说法，意思一样。',
    '概括归纳': '选项用一个概括的说法，总结原文里具体的几句话或几个例子。',
    '原词复现': '选项直接用了原文的词，听到哪个词就选哪个，最省力但也最少见。',
}
WRONG_NOTE = {
    '没提到': '选项里的内容原文根本没说。',
    '张冠李戴': '原文确实说了，但说的是别人、别的事，被安到了这道题上。',
    '偷换': '大部分照搬原文，却悄悄换掉了关键词或对象。',
    '说反了': '与原文的意思正好相反。',
    '过度推断': '原文有这个意思，但选项说得太过、太绝对。',
}


def code(sid):
    d = M.V[sid]
    return f"{d['year']}年{d['month']}月 第{d['set']}套"


def short(sid):
    d = M.V[sid]
    return f"{str(d['year'])[2:]}.{d['month']}-{d['set']}"


def gname(g):
    w = g['name'].rstrip('.:').split()
    num = {'1': 'One', '2': 'Two', '3': 'Three'}
    return f"{w[0].capitalize()} {num.get(w[1], w[1].capitalize())}"


def jx(sid):
    return json.loads((JC.J / f'{sid}.json').read_text('utf-8'))['题']


def merge_spans(spans):
    """[(起, 止, 题号)] → 重叠的并在一起，编号写“3·4”。"""
    out = []
    for a, b, n in sorted(spans):
        if out and a < out[-1][1]:
            pa, pb, pn = out[-1]
            out[-1] = (pa, max(pb, b), pn if str(n) in str(pn).split('·') else f'{pn}·{n}')
        else:
            out.append((a, b, n))
    return out


def qstem_zh(g, n, x):
    s = g['qsent'].get(n)
    if s is None:
        return x.get('题译', '')
    return re.sub(r'^(问题|第)\s*[一二三四五六七八九十0-9]+\s*(题)?[：:]\s*', '', s['zh'])


# ------------------------------------------------------------------ 生词 / 高频词
def _zipf():
    import wordfreq
    return lambda h: wordfreq.zipf_frequency(h, 'en')


KIND = {'conversation': '对话', 'passage': '短文', 'recording': '讲座'}
BASIC = {'passage', 'conversation', 'recording', 'lecture', 'in fact', 'according to', 'for example', 'at the end of', 'such as', 'a lot of', 'as well as', 'more than', 'at least', 'so that', 'because of', 'in order to', 'a few', 'kind of', 'lots of', 'as well', 'of course', 'each other', 'even though', 'even if', 'rather than', 'instead of', 'as long as', 'thanks to'}


def vocab_stats():
    """30 套原文（只算正文，不算说明和念题）里每个词条：出现在哪几套、哪几篇、释义。"""
    zipf = _zipf()
    st = {}
    for sid in M.SETS:
        d = M.load(sid)
        for g in d['groups']:
            for s in g['sents']:
                for w in s['w']:
                    h = w['h']
                    if zipf(h) >= 4.6 or h in BASIC:
                        continue
                    e = st.setdefault(h, {'h': h, 'm': w['m'], 'sets': [], 'where': [], 'n': 0})
                    e['n'] += 1
                    if sid not in e['sets']:
                        e['sets'].append(sid)
                    wh = f'{short(sid)} {KIND[g["kind"]]}{gname(g).split()[1][0].replace("O", "1").replace("T", "2" if gname(g).split()[1] == "Two" else "3")}'
                    if wh not in e['where']:
                        e['where'].append(wh)
    return st


# ------------------------------------------------------------------ 主讲义
def set_chapter(i, sid, VS):
    d, T = M.load(sid), jx(sid)
    words = sum(len(s['en'].split()) for g in d['groups'] for s in g['sents'])
    out = [f"<section class='chap' data-mark='CH{i:02d}'><div class='band'><div><div class='no'>LISTENING SET {i:02d}</div>"
           f"<h1><span>{esc(code(sid))}</span></h1></div><div class='meta'><b>大学英语六级 听力真题</b>{len(d['questions'])} 题 · 原文 {words} 词</div></div>"]
    ak = ''.join(f"<div>{n}<b>{q['ans']}</b></div>" for n, q in d['questions'].items())
    out.append(f"<div class='ov'><div class='sm'><b>本套内容：</b>{esc(d['summary'])}</div><div class='ak'><div class='t'>答案速查</div>{ak}</div></div>")
    for g in d['groups']:
        spans = collections.defaultdict(list)
        for n in g['qs']:
            for e in T[str(n)]['依据']:
                en = next(s['en'] for s in g['sents'] if s['sid'] == e['sid'])
                a = en.index(e['句'])
                spans[e['sid']].append((a, a + len(e['句']), n))
        gw = sum(len(s['en'].split()) for s in g['sents'])
        out.append(f"<div class='gh'><b>{esc(gname(g))}</b><span>第 {g['qs'][0]}—{g['qs'][-1]} 题</span><i>原文 {gw} 词 · 黄色 = 答案出处，右上角是题号</i></div>")
        out.append("<div class='lab2'>原文逐句对照</div>")
        for k, s in enumerate(g['sents'], 1):
            out.append(f"<div class='st'><span class='k'>{k}</span><div class='e'>{J.marked(s['en'], merge_spans(spans[s['sid']]))}</div><div class='z'>{esc(s['zh'])}</div></div>")
        out.append("<div class='lab2'>逐题精讲</div>")
        num = {s['sid']: k for k, s in enumerate(g['sents'], 1)}
        for n in g['qs']:
            q, x = d['questions'][n], T[str(n)]
            ops = ''.join(f"<div class='{'ok' if L == q['ans'] else ''}'><b>{L}</b><span class='oe'>{esc(o)}</span><span class='oz'>{esc(x['选项译'][L])}</span></div>"
                          for L, o in zip('ABCD', q['opts']))
            yj = '<br>'.join(f"<span class='en'>{esc(e['句'])}</span><i>（原文第 {num[e['sid']]} 句）</i>" for e in x['依据'])
            tb = ''.join(f"<span class='p'><u>{esc(r['选项'])}</u> ⇄ <s>{esc(r['原文'])}</s><i class='tag t'>{r['类型']}</i></span>" for r in x['替换'])
            cw = ''.join(f"<span class='x'><em>{L}</em><i class='tag w'>{x['错项'][L]['类']}</i>{esc(x['错项'][L]['说'])}</span>" for L in 'ABCD' if L in x['错项'])
            out.append(f"<div class='qg'><div class='qh'><span class='qn'>{n}</span><div><div class='qe'>{esc(q['q'])}</div><div class='qz'>{esc(qstem_zh(g, n, x))}</div></div></div>"
                       f"<div class='op'>{ops}</div>"
                       f"<div class='rw yj'><b>答案依据</b>{yj}</div>"
                       f"<div class='rw jg'><b>思路</b><span>{esc(x['讲'])}</span></div>"
                       f"<div class='rw tb'><b>同义替换</b>{tb}</div>"
                       f"<div class='rw cw'><b>错项排除</b>{cw}</div></div>")
    hv = sorted({w['h'] for g in d['groups'] for s in g['sents'] for w in s['w'] if w['h'] in VS and len(VS[w['h']]['sets']) >= 3},
                key=lambda h: (-len(VS[h]['sets']), h))[:30]
    out.append(f"<div class='gh'><b>本套高频词</b><span>{len(hv)} 个</span><i>右边数字 = 30 套里有几套考到</i></div><div class='hv'>"
               + ''.join(f"<div><b>{esc(h)}</b><i>{len(VS[h]['sets'])} 套</i><span>{esc(VS[h]['m'])}</span></div>" for h in hv) + '</div></section>')
    return ''.join(out)


def guide_chapter(n):
    def box(t, ps):
        return f"<div class='box'><h3>{esc(t)}</h3>" + ''.join(f'<p>{esc(p)}</p>' for p in ps) + '</div>'
    syn = ''.join(f"<p><i class='tag t'>{k}</i>{esc(v)}</p>" for k, v in TYPES_NOTE.items())
    wr = ''.join(f"<p><i class='tag w'>{k}</i>{esc(v)}</p>" for k, v in WRONG_NOTE.items())
    return ("<section class='chap guide' data-mark='GEN'><div class='band'><div><div class='no'>HOW TO USE</div><h1><span>怎么用这本讲义</span></h1></div>"
            f"<div class='meta'><b>{n} 套真题</b>{M.V[M.SETS[-1]]['year']}—{M.V[M.SETS[0]]['year']}</div></div>"
            + box('每一套怎么学', ['① 先不看讲义，用配套的“视频版真题考试”完整做一遍，像考场上一样只听一遍；',
                                '② 对照“答案速查”打分，错的题在“逐题精讲”里找到：先看“答案依据”是原文哪一句，再看“思路”怎么从这句话推到答案；',
                                '③ 看“同义替换”：选项和原文换了哪些说法——六级听力的正确答案很少照搬原文，听懂这些替换就是提分的关键；',
                                '④ 看“错项排除”：每个错误选项属于哪一种陷阱，下次听到类似的说法就能直接排除；',
                                '⑤ 回到“原文逐句对照”，边听录音边看黄色的答案出处，最后用《听写本》把关键词默写一遍。'])
            + f"<div class='box'><h3>同义替换的五种类型</h3>{syn}</div><div class='box'><h3>错误选项的五种陷阱</h3>{wr}</div>"
            + box('配套免费视频', ['每一套都有“视频版真题考试”（按考场节奏播放、题与题之间留出作答时间）和“逐句精读”视频，可免费观看，与本讲义的原文、译文完全一致。'])
            + '</section>')


def main_toc(ids):
    entries = [('GEN', '使用说明', '每一套怎么学 · 替换类型 · 错项陷阱')] + \
              [(f'CH{i:02d}', code(sid), f'{len(M.load(sid)["questions"])} 题 · 原文 · 精讲 · 高频词') for i, sid in enumerate(ids, 1)]
    keys = {'GEN': 'HOW TO USE'}
    keys.update({f'CH{i:02d}': f'LISTENING SET {i:02d}' for i in range(1, len(ids) + 1)})
    return entries, keys


# ------------------------------------------------------------------ 同义替换手册
def syn_rows(ids):
    rows = collections.defaultdict(list)
    for sid in ids:
        for n, x in jx(sid).items():
            for r in x['替换']:
                rows[r['类型']].append((r['选项'], r['原文'], f'{short(sid)} 第{n}题'))
    return rows


def syn_body(ids, pages={}):
    rows = syn_rows(ids)
    types = [t for t in JC.TYPES if rows.get(t)]
    entries = [(f'S{k}', t, f'{len(rows[t])} 组') for k, t in enumerate(types, 1)]
    keys = {f'S{k}': f'SYNONYM {k:02d}' for k in range(1, len(types) + 1)}
    body = J.toc_html(entries, pages)
    for k, t in enumerate(types, 1):
        body += (f"<section class='chap' data-mark='S{k}'><div class='band'><div><div class='no'>SYNONYM {k:02d}</div><h1><span>{esc(t)}</span></h1></div>"
                 f"<div class='meta'><b>{len(rows[t])} 组</b>{esc(TYPES_NOTE[t])}</div></div>"
                 "<div class='sy th'><div>正确选项的说法</div><div>原文的说法</div><div>出处</div></div>"
                 + ''.join(f"<div class='sy'><div class='a'>{esc(a)}</div><div class='b'>{esc(b)}</div><div class='c'>{esc(c)}</div></div>" for a, b, c in rows[t]) + '</section>')
    return body, entries, keys


# ------------------------------------------------------------------ 高频词手册
TIERS = [('必背', 8, 99), ('常考', 5, 7), ('高频', 3, 4)]


def vocab_body(VS, pages={}):
    entries, keys, body = [], {}, ''
    for k, (t, lo, hi) in enumerate(TIERS, 1):
        ws = sorted((e for e in VS.values() if lo <= len(e['sets']) <= hi), key=lambda e: (-len(e['sets']), -e['n'], e['h']))
        entries.append((f'V{k}', f'{t}词（{lo}{"套以上" if hi == 99 else "—" + str(hi) + " 套"}）', f'{len(ws)} 个'))
        keys[f'V{k}'] = f'WORDS · TIER {k}'
        body += (f"<section class='chap' data-mark='V{k}'><div class='band'><div><div class='no'>WORDS · TIER {k}</div><h1><span>{esc(t)}词</span></h1></div>"
                 f"<div class='meta'><b>{len(ws)} 个</b>30 套里有 {lo}{'套以上' if hi == 99 else '—' + str(hi) + ' 套'}考到</div></div>"
                 "<div class='vw th'><div>词条</div><div>释义</div><div>套数</div><div>出处（年.月-套 篇目）</div></div>"
                 + ''.join(f"<div class='vw'><div class='w'>{esc(e['h'])}</div><div>{esc(e['m'])}</div><div class='n'>{len(e['sets'])}</div>"
                           f"<div class='s'>{esc(' · '.join(e['where'][:3]) + (f' 等 {len(e["where"])} 处' if len(e['where']) > 3 else ''))}</div></div>" for e in ws)
                 + '</section>')
    return J.toc_html(entries, pages) + body, entries, keys


# ------------------------------------------------------------------ 听写本
def blanks(sents, zipf):
    """每句（≥ 8 词）挖一个空：本句生词里最难（词频最低）的单词，至少 4 个字母。"""
    out = []
    for s in sents:
        best = None
        if len(s['en'].split()) >= 8:
            for w in s['w']:
                if ' ' in w['h'] or w['t'] != 'core':
                    continue
                for a, b in w['sp']:
                    t = s['en'][a:b]
                    if len(t) >= 4 and t.isalpha() and 2.0 <= zipf(w['h']) < 4.8 and (best is None or zipf(w['h']) < best[0]):
                        best = (zipf(w['h']), a, b, w['m'])
        out.append(best)
    return out


def dict_body(ids, answers, pages={}):
    zipf = _zipf()
    entries = [(f'D{sid.replace("-", "_")}', code(sid), '') for sid in ids]
    keys = {f'D{sid.replace("-", "_")}': f'DICTATION · {code(sid)}' for sid in ids}
    body, k0 = J.toc_html(entries, pages), 0
    how = ''
    if not answers:
        how = ("<div class='how'><b>怎么用这本听写本</b><br>① 先听一段录音（或看配套视频），边听边把横线处的单词写出来，编号对应答案本；"
                 "② 写不出来的先空着，第二遍再听；③ 对照《听写本（答案）》改正，错的词抄进生词本，第二天再默一遍。</div>")
    for sid in ids:
        d = M.load(sid)
        body += f"<section class='chap' data-mark='D{sid.replace("-", "_")}'><div class='band'><div><div class='no'>DICTATION · {esc(code(sid))}</div><h1><span>{esc(code(sid))}</span></h1></div><div class='meta'><b>听写本{'（答案）' if answers else ''}</b></div></div>" + how
        how = ''
        for g in d['groups']:
            bl, n = blanks(g['sents'], zipf), 0
            body += f"<div class='gh'><b>{esc(gname(g))}</b><span>第 {g['qs'][0]}—{g['qs'][-1]} 题</span></div>"
            if answers:
                items = []
                for s, b in zip(g['sents'], bl):
                    if b:
                        n += 1
                        items.append(f"<div><em>{n}</em><b>{esc(s['en'][b[1]:b[2]])}</b> <span class='qz'>{esc(b[3])}</span></div>")
                body += "<div class='da'>" + ''.join(items) + '</div>'
            else:
                txt = []
                for s, b in zip(g['sents'], bl):
                    if b:
                        n += 1
                        w = max(3.2, (b[2] - b[1]) * 0.55 + 1.2)
                        txt.append(esc(s['en'][:b[1]]) + f"<span class='gap' style='width:{w:.1f}em'><sup>{n}</sup></span>" + esc(s['en'][b[2]:]))
                    else:
                        txt.append(esc(s['en']))
                body += "<div class='dt'>" + ' '.join(txt) + '</div>'
        body += '</section>'
    return body, entries, keys


# ------------------------------------------------------------------ 30 天计划
def plan_body(ids, mainpages):
    order = list(reversed(ids))           # 从最早的一套做起，最后几天留给最新真题
    rows = ''.join(f"<div class='pl'><div class='d'>{k:02d}</div><div>{esc(code(sid))}</div>"
                   "<div class='t'><span>完整做一遍</span><span>看精讲</span><span>听写</span><span>背高频词</span><span>复听错题</span></div>"
                   f"<div class='sc'>对 ___ /{len(M.load(sid)['questions'])}</div><div class='pg'>P{mainpages.get(sid, '')}</div></div>"
                   for k, sid in enumerate(order, 1))
    return ("<section data-mark='PLAN'><div class='band'><div><div class='no'>30-DAY PLAN</div><h1><span>30 天刷题计划</span></h1></div>"
            f"<div class='meta'><b>每天一套</b>从 {M.V[order[0]]['year']} 年做到 {M.V[order[-1]]['year']} 年</div></div>"
            "<div class='how'><b>怎么用</b><br>每天做一套真题，五项任务做完一项勾一项；“对 ___ 题”写下这一套做对几道，看得见自己在进步。"
            "从最早的一套做起，越往后越新，最后几天用最新真题模拟考试。右边页码是《30 套精讲》里这一套的起始页。</div>"
            "<div class='pl th'><div>天</div><div>真题</div><div>任务（做完打勾）</div><div>成绩</div><div>精讲页</div></div>" + rows + '</section>')


# ------------------------------------------------------------------ 生成
def cover(title, sub, note):
    return J.cover(title, sub, note).replace('CET-6 ENGLISH WRITING', 'CET-6 LISTENING').replace('六级<br>作文', '六级<br>听力')


def two_pass(pg, tmp, make, title, out_name):
    """目录页码两遍排版：第一遍量出各章起始页，带页码再排一遍，再量必须相同。"""
    body, entries, keys = make({})
    J.render(pg, body, title, tmp / 'b.pdf', tmp)
    p1, _ = J.page_of(tmp / 'b.pdf', keys)
    body, entries, keys = make(p1)
    J.render(pg, body, title, tmp / 'b.pdf', tmp)
    p2, n = J.page_of(tmp / 'b.pdf', keys)
    if p1 != p2 or len(p2) != len(keys):
        sys.exit(f'{title}：目录带页码后起始页变了或找不到：{p1} → {p2}')
    out = OUT / f'{out_name}.pdf'
    J.merge([tmp / 'c.pdf', tmp / 'b.pdf'], out)
    J.linkify(out, tmp / 'b.pdf', entries)
    J.font_check(out)
    J.toc_gate(out, entries, keys)
    print(f'{title}：{n + 1} 页 → {out}')
    return p2


def build(what, ids):
    from playwright.sync_api import sync_playwright
    errs = [e for s in ids for e in JC.check(s)]
    if errs:
        sys.exit('解析检查不通过，不生成：\n  ' + '\n  '.join(errs[:40]))
    OUT.mkdir(exist_ok=True)
    VS = vocab_stats()
    y = f"{M.V[ids[0]]['year']}—{M.V[ids[-1]]['year']}" if len(ids) > 1 else code(ids[0])
    nq = sum(len(M.load(s)['questions']) for s in ids)
    mainpages = {}
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        tmp = Path(tmp)
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page()

        def cov(title, sub, note):
            J.render(pg, cover(title, sub, note), '封面', tmp / 'c.pdf', tmp, footer=False)

        if what in ('main', 'all', 'plan'):
            cov('六级听力真题 30 套精讲' if len(ids) == 30 else '六级听力真题精讲', f'{y} · 大学英语六级 · 共 {len(ids)} 套 {nq} 题',
                '原文逐句英汉对照 → 答案依据 → 思路<br>同义替换 → 错项排除 → 本套高频词<br>每道题都讲清“答案从哪句来、为什么选它、别的为什么错”')

            def mk(p):
                e, k = main_toc(ids)
                return J.toc_html(e, p) + guide_chapter(len(ids)) + ''.join(set_chapter(i, s, VS) for i, s in enumerate(ids, 1)), e, k
            p = two_pass(pg, tmp, mk, NAMES['main'], NAMES['main'])
            mainpages = {s: p[f'CH{i:02d}'] + 1 for i, s in enumerate(ids, 1)}     # + 封面 1 页
        if what in ('syn', 'all'):
            n = sum(len(v) for v in syn_rows(ids).values())
            cov('六级听力 同义替换手册', f'{y} · 共 {len(ids)} 套真题 · {n} 组替换', '正确选项的说法 ⇄ 原文的说法，按五种替换类型分组<br>听懂“换说法”，就听懂了六级听力的出题规律')
            two_pass(pg, tmp, lambda p: syn_body(ids, p), NAMES['syn'], NAMES['syn'])
        if what in ('vocab', 'all'):
            nv = sum(1 for e in VS.values() if len(e['sets']) >= 3)
            cov('六级听力 高频词手册', f'{M.V[M.SETS[-1]]["year"]}—{M.V[M.SETS[0]]["year"]} · {len(M.SETS)} 套真题原文统计 · {nv} 个词条', '按 30 套里考到的套数排序：必背 → 常考 → 高频<br>每个词都标出处，回到原文就能听到它')
            two_pass(pg, tmp, lambda p: vocab_body(VS, p), NAMES['vocab'], NAMES['vocab'])
        if what in ('dict', 'all'):
            for ans, key in ((False, 'dict'), (True, 'dans')):
                cov(NAMES[key].replace('六级听力', '六级听力 '), f'{y} · 共 {len(ids)} 套真题原文', '每句挖出一个关键词，边听边写' if not ans else '编号对应听写本里的横线')
                two_pass(pg, tmp, lambda p, a=ans: dict_body(ids, a, p), NAMES[key], NAMES[key])
        if what in ('plan', 'all'):
            J.render(pg, plan_body(ids, mainpages), NAMES['plan'], tmp / 'b.pdf', tmp)
            out = OUT / f"{NAMES['plan']}.pdf"
            out.write_bytes((tmp / 'b.pdf').read_bytes())
            J.font_check(out)
            print(f"{NAMES['plan']} → {out}")
        br.close()


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'build':
        what = a[1] if len(a) > 1 and a[1] in ('main', 'syn', 'vocab', 'dict', 'plan', 'all') else 'all'
        ids = [x for x in a[2 if len(a) > 1 and a[1] == what else 1:] if x in M.V] or M.SETS
        build(what, ids)
