"""从现有已审校资料制作高考听力 PDF 套装；不修改任何源材料或答案。

用法：python 制作.py --sample | --build | --check
"""
from __future__ import annotations

import argparse
import ast
import collections
import contextlib
import functools
import hashlib
import html
import http.server
import importlib.util
import json
import os
import re
import tempfile
import threading
import unicodedata
from pathlib import Path

import fitz
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
D = HERE.parent
G = D.parent
ROOT = G.parent
OUT = D / '成品'
AUDIT = D / '核验'
PREVIEW = D / '商品图' / '真实内页'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


import sys
sys.path.insert(0, str(G / '精读' / 'tools'))
from 数据 import load_text, sha  # noqa: E402
from 审校登记 import check as reviewed  # noqa: E402

J = module('gaokao_handout_base', ROOT / '六级作文' / 'tools' / '讲义.py')


def esc(text):
    # 本地字体子集不含 U+2160—2162；用同义拉丁罗马数字，避免 PDF 出现空字形。
    return J.esc(str(text).translate(str.maketrans({'Ⅰ': 'I', 'Ⅱ': 'II', 'Ⅲ': 'III'})))
BOOKS = {
    'practice': ('01', '高考英语听力真题练习册', '先独立练习，检验真实水平'),
    'reading': ('02', '高考英语听力原文双语精读', '原文逐句对照，词汇短语随文标注'),
    'vocab': ('03', '高考英语听力常见词汇手册', '按出现试卷数排序，配原文例句'),
    'phrases': ('04', '高考英语听力短语与搭配手册', '在真实语境中记住常用表达'),
    'dictation': ('05', '高考英语听力听写训练本', '关键词挖空，发现没听清的细节'),
    'dictanswers': ('06', '高考英语听力听写答案本', '逐空核对，回到完整原句复听'),
    'answers': ('07', '高考英语听力真题参考答案', '按年份卷别查找，对应练习册题号'),
    'plan': ('08', '高考英语听力训练指南与复习计划', '练习、精读、听写、复听，记录进度'),
}
STOP = set('a an the this that these those i me my mine we us our ours you your yours he him his she her hers it its they them their theirs and or but so as if than then to of in on at by for from with without into onto out up down off is am are was were be been being do does did have has had can could may might must shall should will would not no yes okay ok oh uh um well now just also only very really too more most much many some any all both each every either neither such what when where why who whose which how there here one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split())
INSTRUCTION = re.compile(r'^(?:Section\b|Directions\b|In Section\b|At the end of each conversation|The conversations and the questions|After you hear a conversation|Questions?\b|Now listen|Listen again|Now read|You will hear|You have|Read the|That[’\']s the end|This is the end|One\.|Two\.|Three\.|Four\.|Five\.|Six\.|Seven\.|Eight\.|Nine\.|Ten\.)', re.I)

# 与已发布考试视频共用同一个展示修复函数；只加载纯函数，不初始化视频引擎。
_display_source = G / 'tools' / '听力视频.py'
_display_node = next(n for n in ast.parse(_display_source.read_text('utf-8')).body if isinstance(n, ast.FunctionDef) and n.name == 'fix')
_display_globals = {'re': re}
exec(compile(ast.Module(body=[_display_node], type_ignores=[]), str(_display_source), 'exec'), _display_globals)
display_fix = _display_globals['fix']


def is_instruction(text):
    if re.match(r'^Question\s*[:：]', text, re.I):
        return False  # 上海口述题干仍随题组呈现。
    return bool(INSTRUCTION.match(text) or re.fullmatch(r'(?:eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)[.!:]?', text, re.I))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def normal(text):
    return re.sub(r'\W+', '', unicodedata.normalize('NFKC', text).replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')).lower()


def first_read(rows, enabled):
    """只删有逐字证据的整段重复；对不完全一致的重读保留全部，绝不猜改。"""
    if enabled:
        for cut in range(1, len(rows)):
            left, right = rows[:cut], rows[cut:]
            text = ' '.join(s['en'] for s in left)
            if len(text.split()) >= 8 and normal(text) == normal(' '.join(s['en'] for s in right)):
                return left, [s['source_sentence'] for s in right]
    return rows, []


@functools.lru_cache(maxsize=2)
def data(sample=False):
    papers = json.loads((G / '套.json').read_text())
    questions = json.loads((G / '抽取' / '定稿题.json').read_text())
    answers = json.loads((G / '答案.json').read_text())
    ids = ['2023-shq', '2026-xkb1'] if sample else sorted(papers, key=lambda x: (-int(x[:4]), list(papers).index(x)))
    rows = []
    for sid in ids:
        reviewed(sid)
        draft, p, _ = load_text(sid)
        source = [{**s, 'source_sentence': k, 'start': draft['sentences'][k - 1]['start'], 'end': draft['sentences'][k - 1]['end']} for k, s in enumerate(p['paras'][0], 1)]
        q = questions[papers[sid]['题目']]
        tl = json.loads((G / '数据' / sid / '时间轴.json').read_text())
        shanghai = '-sh' in sid
        ranges = [(float(a) + tl['cut'], float(b) + tl['cut'], not shanghai) for a, b in tl['dlg']]
        ranges += [(float(g.get('play', g['start'])) + tl['cut'], float(g['ans'][0]) + tl['cut'], True) for g in tl['grp']]
        assert len(ranges) == len(q['组']), (sid, len(ranges), len(q['组']))
        used, groups, removed = set(), [], []
        for (a, b, repeated), (qn0, qn1) in zip(ranges, q['组']):
            selected = [s for s in source if a - .45 <= s['start'] < b + .15 and not is_instruction(s['en'])]
            assert selected, (sid, qn0, '空录音组')
            assert not (used & {s['source_sentence'] for s in selected}), (sid, qn0, '录音组重叠')
            used |= {s['source_sentence'] for s in selected}
            keep, omitted = first_read(selected, repeated)
            removed += omitted
            groups.append({'title': f'第{qn0}题' if qn0 == qn1 else f'第{qn0}—{qn1}题', 'qs': list(range(qn0, qn1 + 1)), 'sentences': keep})
        extra = [s for s in source if s['source_sentence'] not in used]
        if extra:
            groups.append({'title': '录音说明、例题与补充语句', 'qs': [], 'sentences': extra})
        # 同一题组的复读只有在全文逐字一致时才合并；所有未合并句都必须出现一次。
        kept = [s['source_sentence'] for g in groups for s in g['sentences']]
        assert len(kept) == len(set(kept)) and sorted(kept + removed) == list(range(1, len(source) + 1)), sid
        for i, s in enumerate(sorted((s for g in groups for s in g['sentences']), key=lambda s: s['source_sentence']), 1):
            s['display_sentence'] = i
        stems = [s for s in source if re.match(r'^Question\s*[:：]', s['en'], re.I)]
        qs, display_fixes = [], []
        for n in range(1, 21):
            item = q['题'][str(n)]
            stem = display_fix(item['干'])
            zh = ''
            if shanghai and len(stems) == 20:
                stem = re.sub(r'^Question\s*[:：]\s*', '', stems[n - 1]['en'], flags=re.I)
                zh = re.sub(r'^问题[:：]\s*', '', stems[n - 1]['zh'])
            opts = {letter: display_fix(text) for letter, text in item['选项'].items()}
            for field, raw, fixed in [('题干', item['干'], display_fix(item['干']))] + [(letter, item['选项'][letter], opts[letter]) for letter in opts]:
                if raw != fixed:
                    display_fixes.append({'题号': n, '字段': field, '原始抽取': raw, '视频及PDF显示': fixed})
            assert list(opts) == list('ABCD' if shanghai else 'ABC')
            ans = answers[sid][str(n)]
            assert ans in opts
            qs.append({'n': n, 'stem': stem, 'stem_zh': zh, 'options': opts, 'answer': ans})
        rows.append({'id': sid, 'title': p['paper_title'], 'summary': p['summary'], 'groups': groups, 'questions': qs, 'source_sentences': len(source), 'removed_exact_repeats': removed, 'display_fixes': display_fixes,
                     'hashes': {'原文': sha(G / '精读' / '定稿' / f'{sid}.json'), '译注': sha(G / '精读' / 'ann' / f'{sid}.txt'), '题目全集': sha(G / '抽取' / '定稿题.json'), '答案全集': sha(G / '答案.json')}})
    return rows


def content_sents(case):
    return [s for g in case['groups'] if g['qs'] for s in g['sentences'] if not INSTRUCTION.match(s['en'])]


def entries(cases, phrase=False):
    store = {}
    for case in cases:
        for s in content_sents(case):
            for w in s['w']:
                h = w['h']
                if (w['t'] == 'phr') != phrase or not phrase and (h.lower() in STOP or not re.search('[a-zA-Z]', h) or h[0].isupper()):
                    continue
                key = h.lower().replace('’', "'")
                e = store.setdefault(key, {'head': h, 'meanings': [], 'cases': [], 'examples': [], 'hits': 0})
                if w['m'] not in e['meanings']:
                    e['meanings'].append(w['m'])
                if case['id'] not in e['cases']:
                    e['cases'].append(case['id'])
                if not any(x['en'] == s['en'] for x in e['examples']):
                    e['examples'].append({'case': case['id'], 'title': case['title'], 'sentence': s['display_sentence'], 'en': s['en'], 'zh': s['zh'], 'spans': w['sp']})
                    e['examples'].sort(key=lambda x: (not 5 <= len(x['en'].split()) <= 22, abs(len(x['en'].split()) - 12)))
                    e['examples'] = e['examples'][:3]
                e['hits'] += 1
    # “常见”词至少出现 3 套；短语汇编保留所有实际标注过的短语。
    return sorted((v for v in store.values() if phrase or len(v['cases']) >= (1 if len(cases) < 3 else 3)), key=lambda e: (-len(e['cases']), e['head'].lower()))


def blanks(case):
    result = []
    for s in content_sents(case):
        if len(s['en'].split()) < 4:
            continue
        candidates = [w for w in s['w'] if len(w['sp']) == 1 and len(s['en'][w['sp'][0][0]:w['sp'][0][1]]) >= 3 and w['h'].lower() not in STOP and not w['h'][0].isupper()]
        if not candidates:
            continue
        w = sorted(candidates, key=lambda x: (x['t'] != 'core', -len(x['h'])))[0]
        a, b = w['sp'][0]
        result.append({'n': len(result) + 1, 'source_sentence': s['source_sentence'], 'display_sentence': s['display_sentence'], 'en': s['en'], 'zh': s['zh'], 'span': [a, b], 'answer': s['en'][a:b]})
    return result


CSS = r"""
:root{--blue:#6a4db4;--berry:#be643c;--hy:#fff0a7;--paper:#fcfaf7;--ink:#302b43;--soft:#f5f1fb;--rule:#dfd5f0}
@page{size:A4;margin:15mm 15mm 17mm;@bottom-left{content:'朋克英语 · 高考听力';font-family:'Noto Sans SC';font-size:7.5pt;color:#827a92}@bottom-right{content:counter(page);font-family:'Nunito';font-size:8pt;color:#827a92}}
@page front{margin:0;@bottom-left{content:none}@bottom-right{content:none}}
body{font-size:10pt;line-height:1.65}
.cover{page:front;width:210mm;height:297mm;position:relative;background:#faf7ff;break-after:page;padding:46mm 25mm 24mm;overflow:hidden}
.cover:before{content:'';position:absolute;right:-35mm;bottom:8mm;width:180mm;height:180mm;border-radius:50%;background:#ffead8}
.cover:after{content:'';position:absolute;right:18mm;bottom:30mm;width:55mm;height:55mm;border-radius:50%;background:#e4d9f7}
.cover>*{position:relative;z-index:1}.cover .eyebrow{font-family:'Nunito';font-size:11pt;letter-spacing:.18em;color:#7b63a9}
.cover h1{font-size:31pt;line-height:1.4;margin:13mm 0 7mm;max-width:160mm;color:#3f315e}
.cover .cover-tag{display:inline-block;background:#f67342;color:white;padding:1.8mm 4mm;border-radius:6mm;font-size:11.5pt;font-weight:700}
.cover .sub{font-size:14pt;color:#6c5b85;max-width:148mm;margin-top:10mm;line-height:1.8}
.cover .format{margin-top:28mm;font-size:12pt;color:#57466f;line-height:2}
.cover .brand{position:absolute;bottom:19mm;left:25mm;font-size:13pt;font-weight:700;color:#5c457e}
.band h1{font-size:18pt}.band .meta{min-width:20mm}.toc{font-size:10pt}.toc .tr{break-inside:avoid}
.toc .tr>a{grid-template-columns:1fr 10mm}.toc .tr>a .pg{grid-column:2}.toc .tr>a .a{grid-column:1}
.intro{background:var(--soft);border-radius:2mm;padding:3mm 4mm;margin:3mm 0 5mm;font-size:9.6pt}
.group{margin:5mm 0 2.8mm;border-bottom:1.2px solid var(--rule);padding:0 0 1.5mm;break-after:avoid;font-size:11.5pt;color:var(--blue);font-weight:700}
.sent{margin:0 0 3mm;break-inside:avoid;padding-left:9mm;position:relative}
.sn{position:absolute;left:0;top:1mm;font-family:'Nunito';font-size:8pt;color:#a18eae}
.eng{font-family:'EB Garamond','Noto Sans SC';font-size:12pt;line-height:1.5}.cn{font-size:9.6pt;color:#68616f;line-height:1.65;margin-top:.6mm}
.wordline{font-size:8.8pt;color:#756282;margin-top:.7mm;line-height:1.8}.wordline b{font-family:'EB Garamond';font-size:10.2pt;color:#5b4680;font-weight:600}
mark{background:#fff0a7;color:inherit;border-radius:.4mm}.ph{background:#eee4fb}
.question{border-top:1px solid #e6deef;padding:3mm 0;break-inside:avoid}.question .stem{font-family:'EB Garamond','Noto Sans SC';font-size:12pt;font-weight:600;line-height:1.5}
.options{margin:1.5mm 0 0 7mm;display:grid;grid-template-columns:1fr 1fr;gap:1mm 5mm}.options div{font-family:'EB Garamond','Noto Sans SC';font-size:11.5pt;line-height:1.4}.options.long{grid-template-columns:1fr}
.bubbles{display:flex;gap:2mm;align-items:center;flex-wrap:wrap;margin:2mm 0}.bubble{display:inline-block;width:4mm;height:4mm;border:1px solid #a897be;border-radius:50%;margin-left:1.4mm;vertical-align:middle}
.answerline{font-size:9pt;color:#93849c;margin-bottom:4mm}.keygrid{display:grid;grid-template-columns:repeat(5,1fr);gap:2mm}.keygrid>div{border:1px solid #ddd3eb;border-radius:2mm;padding:2mm;text-align:center;font-size:9.5pt}.keygrid b{display:block;font-family:'Nunito';font-size:16pt;color:#6a4db4}.keygrid small{color:#9b8ba6}
.lex{padding:3mm 0;border-top:1px solid #e4dceb;break-inside:avoid}.lex .head{display:flex;align-items:baseline;justify-content:space-between;gap:4mm}.lex .head b{font-family:'EB Garamond','Noto Sans SC';font-size:14pt;color:#5b427d}.lex .head span{font-size:8.4pt;color:#8a748f;white-space:nowrap}.lex .mean{font-size:10pt;margin:1mm 0 1.5mm}.lex .example{background:#faf8fc;padding:2mm 3mm;border-radius:1.5mm}.lex .where{font-size:8pt;color:#96859e;margin-top:1mm;line-height:1.65}
.dict{margin:0 0 4mm;break-inside:avoid}.dict .eng{line-height:2}.gap{display:inline-block;min-width:17mm;border-bottom:1px solid #75618d;height:5mm;margin:0 1mm;vertical-align:baseline;position:relative}.dict .label{font-family:'Nunito';font-size:8pt;color:#977fa9;margin-right:2mm}.dict .lines{height:9mm;border-bottom:1px dotted #d7cce1}
.dictkey{border-bottom:1px solid #e8dfed;padding:2mm 0;break-inside:avoid}.dictkey .head{color:#5b427d;font-size:10pt;font-weight:700}.dictkey .eng{font-size:11pt;margin-top:1mm}.dictkey .cn{font-size:9pt}
.checkrow{display:grid;grid-template-columns:1fr 66mm;gap:3mm;padding:2.4mm 0;border-bottom:1px solid #e8dfed;break-inside:avoid;font-size:9pt}.steps{display:flex;gap:3mm;justify-content:flex-end}.steps span{white-space:nowrap}.steps span:before{content:'';width:2.8mm;height:2.8mm;border:1px solid #a58bbd;display:inline-block;vertical-align:-.4mm;margin-right:.8mm}
.guide p{margin:2mm 0;font-size:10pt}.guide h2{font-size:13pt;color:#68498a;margin:6mm 0 2mm;break-after:avoid}.writingline{height:10mm;border-bottom:1px solid #d8cbe5}.errorbox{border:1px solid #dfd3ec;border-radius:2mm;padding:4mm;margin:4mm 0;break-inside:avoid;font-size:9.5pt}
"""


def marked(s):
    spans = sorted((a, b, w['t']) for w in s['w'] for a, b in w['sp'])
    out, last = [], 0
    for a, b, t in spans:
        assert a >= last, '词汇高亮重叠'
        out += [esc(s['en'][last:a]), f'<mark class="{"ph" if t == "phr" else ""}">{esc(s["en"][a:b])}</mark>']
        last = b
    return ''.join(out) + esc(s['en'][last:])


def heading(case, mark):
    return f'<section class="chap" id="{mark}"><div class="band"><div><div class="no">GAOKAO LISTENING</div><h1>{esc(case["title"])}</h1></div><div class="meta">朋克英语<br>高考听力</div></div>'


def body_case(key, case, mark):
    out = [heading(case, mark)]
    if key == 'practice':
        out.append('<div class="intro">配套原声：在 B 站搜索“朋克英语”，按年份、卷别选择“考试”。先独立作答，再查阅单独的参考答案本；本册不显示答案。上海卷部分题干由录音口述，按原卷仅列选项。</div>')
        out.append('<div class="answerline">姓名：________________　日期：________________　正确题数：____ / 20</div>')
        for group in case['groups']:
            if not group['qs']:
                continue
            out.append(f'<div class="group">{esc(group["title"])}</div>')
            for n in group['qs']:
                q = case['questions'][n - 1]
                # 上海练习保留原试卷只列选项的形式，听题能力与视频一致。
                stem = '' if '-sh' in case['id'] else q['stem']
                out.append(f'<div class="question"><div class="stem">{n}. {esc(stem)}</div><div class="options {"long" if max(map(len,q["options"].values()))>60 else ""}">')
                out += [f'<div>{l}. {esc(text)}</div>' for l, text in q['options'].items()]
                out.append('</div></div>')
        out.append('<div class="group">答题记录</div><div class="bubbles">' + ''.join(f'<span>{q["n"]}　' + ' '.join(f'{l}<i class="bubble"></i>' for l in q['options']) + '</span>' for q in case['questions']) + '</div>')
    elif key == 'reading':
        out.append(f'<div class="intro">{esc(case["summary"])}<br>黄色为词汇，淡紫色为短语。与精读视频共用已审校原文、译文；完全相同的整组重复朗读只保留首遍，不完全相同的保留原有语句。录音说明、例题及补充语句单列。</div>')
        for group in case['groups']:
            out.append(f'<div class="group">{esc(group["title"])}</div>')
            for s in group['sentences']:
                wl = '　 ·　 '.join(f'<b>{esc(w["h"])}</b> {esc(w["m"])}' for w in s['w'])
                out.append(f'<div class="sent"><span class="sn">{s["display_sentence"]:03d}</span><div class="eng">{marked(s)}</div><div class="cn">{esc(s["zh"])}</div><div class="wordline">{wl}</div></div>')
    elif key in ('dictation', 'dictanswers'):
        out.append('<div class="intro">按练习册的年份、卷别选择同一套“考试”或“原文精读”视频。训练本与答案本每套各自从 1 编号；可暂停、回放，同一句保留的不同朗读可能各自出题。答案按录音原句词形填写，勿只填词典原形。</div>')
        for b in blanks(case):
            if key == 'dictation':
                a, z = b['span']
                gap = f'<span class="gap" style="min-width:{max(17,min(37,len(b["answer"])*2.4))}mm"></span>'
                suffix = b['en'][z:]
                punctuation = re.match(r'^[,.;:!?…’”\'"\)]+', suffix)
                if punctuation:
                    gap = '<x-nb>' + gap + esc(punctuation.group()) + '</x-nb>'
                    suffix = suffix[punctuation.end():]
                out.append(f'<div class="dict"><div class="eng"><span class="label">{b["n"]:03d}</span>{esc(b["en"][:a])}{gap}{esc(suffix)}</div><div class="lines"></div></div>')
            else:
                a, z = b['span']
                en = esc(b['en'][:a]) + '<mark>' + esc(b['en'][a:z]) + '</mark>' + esc(b['en'][z:])
                out.append(f'<div class="dictkey"><div class="head">{b["n"]:03d}　{esc(b["answer"])}<span style="font-weight:400;color:#9a8aa5">　精读第{b["display_sentence"]}句</span></div><div class="eng">{en}</div><div class="cn">{esc(b["zh"])}</div></div>')
    elif key == 'answers':
        out.append('<div class="intro">参考答案沿用已发布考试视频的数据，与本包练习册题目和选项逐题对应。本册供练习后核对，不包含逐题解析。</div>')
        out.append('<div class="keygrid">' + ''.join(f'<div>第{q["n"]}题<b>{q["answer"]}</b><small>{esc(q["options"][q["answer"]])}</small></div>' for q in case['questions']) + '</div>')
    out.append('</section>')
    return ''.join(out)


def lexicon(terms, key):
    chunks = [terms[i:i+30] for i in range(0, len(terms), 30)]
    entries_out, chapters = [], []
    for i, chunk in enumerate(chunks, 1):
        mark = f'CH{i:03d}'
        title = f'第{(i-1)*30+1}—{min(i*30,len(terms))}条'
        entries_out.append((mark, title, chunk[0]['head'] + ' — ' + chunk[-1]['head']))
        out = [heading({'title': BOOKS[key][1]}, mark), f'<div class="intro">{esc(title)}。按出现的试卷数降序排列，同一试卷内多次出现只计一套；不同试卷共用同一录音时仍分别计入。释义来自已审校的原文语境，不作为未来命题频率预测。</div>']
        for k, e in enumerate(chunk, (i-1)*30+1):
            ex = e['examples'][0]
            a, b = ex['spans'][0]
            en = esc(ex['en'][:a]) + '<mark>' + esc(ex['en'][a:b]) + '</mark>' + esc(ex['en'][b:])
            defs = '；'.join(e['meanings'][:3])
            out.append(f'<div class="lex"><div class="head"><b>{k}. {esc(e["head"])}</b><span>出现于{len(e["cases"])}套</span></div><div class="mean">{esc(defs)}</div><div class="example"><div class="eng">{en}</div><div class="cn">{esc(ex["zh"])}</div></div><div class="where">例句出处：{esc(ex["title"])} · 精读第{ex["sentence"]}句</div></div>')
        out.append('</section>')
        chapters.append(''.join(out))
    return entries_out, ''.join(chapters)


def guide(cases):
    e = [('GUIDE', '训练指南', '先练习，再精读'), ('PLAN', '逐套复习计划', '按自己的节奏打勾'), ('ERROR', '错题复盘与复听记录', '可重复打印使用')]
    body = heading({'title': '训练指南'}, 'GUIDE') + '<div class="guide">'
    parts = [
        ('第一步：先独立完成练习', '打开真题练习册，找到对应年份和卷别。在 B 站搜索“朋克英语”，选择同名“考试”视频。按视频节奏作答，先不看原文与参考答案。'),
        ('第二步：核对后，记录错因', '用单独的参考答案本核对。先把题号和自己的选项记下来，再判断卡在哪里：单词不认识、熟词没听出来、数字没记住、人物关系混淆、推断超出了原文，还是注意力中断。'),
        ('第三步：先听，再看双语原文', '先回放没听清的片段。仍不明白时，再打开原文双语精读，读懂句意，留意词汇、短语和上下文。把原来认得却没听出的词单独记下来。'),
        ('第四步：用听写检查细节', '打开听写训练本，按同一套录音逐句练习。听写答案本标出挖空处的原句词形，并给出完整句子和中文，核对后盖住答案复听。'),
        ('第五步：回到原声，检验是否听懂', '暂时合上原文，再听刚才的片段。可以说出主要意思后再跟读；不必追求一次跟上，先保证听到的声音与理解的意思对得上。'),
        ('数字与时间', '听到数字先记清对象，再处理加减、折扣、时差和改约。原定时间、实际时间、出发时间与到达时间可能不同，不要只抓住第一个数字。'),
        ('人物与态度', '留意是谁说的、说给谁听、谈论的是谁。遇到 but、actually、however 等转折，再确认后面的信息有没有修正前面的判断。'),
        ('常见场景', '日常安排、学校学习、出行住宿、购物用餐、工作沟通等场景中，同一意思可能换一种说法。把词汇放回原句复听，比只背中文释义更有帮助。'),
        ('安排复习节奏', '可先隔一天复听错题，再隔几天检查一次。每天的量按自己的基础调整；计划表记录实际完成情况，不必为了打勾匆忙跳过薄弱处。'),
        ('电子阅读与打印', '八份资料均为 PDF。目录可点击跳转，侧边栏提供书签；支持表单的阅读器可在目录“已读”框打勾后保存。建议用电脑或平板阅读精读，用 A4 实际大小打印练习与听写；黑白打印仍可使用。'),
    ]
    for title, text in parts:
        body += f'<h2>{esc(title)}</h2><p>{esc(text)}</p>'
    body += '</div></section>' + heading({'title': '逐套复习计划'}, 'PLAN')
    body += '<div class="intro">不设固定天数，按年份、卷别和实际进度选择。每完成一项打一个勾；“复听”建议在离开原文后进行。</div>'
    for case in cases:
        body += f'<div class="checkrow"><div>{esc(case["title"])}</div><div class="steps"><span>练习</span><span>精读</span><span>听写</span><span>复听</span></div></div>'
    body += '</section>' + heading({'title': '错题复盘与复听记录'}, 'ERROR')
    body += '<div class="intro">此页可重复打印。只写出最关键的错因和下次要注意的线索，不必把整篇原文抄一遍。</div>'
    for _ in range(3):
        body += '<div class="errorbox">年份卷别：________________　题号：______　日期：________<br>我的选项：______　参考答案：______<div class="writingline">错在哪里：</div><div class="writingline">原文中的关键信息：</div><div class="writingline">没听清的词汇或表达：</div><div class="writingline">复听日期与结果：</div></div>'
    return e, body + '</section>'


def compose(key, cases):
    if key in ('vocab', 'phrases'):
        return lexicon(entries(cases, key == 'phrases'), key)
    if key == 'plan':
        return guide(cases)
    es = [(f'CH{i:03d}', case['title'], '') for i, case in enumerate(cases, 1)]
    return es, ''.join(body_case(key, c, m) for c, (m, _, _) in zip(cases, es))


def cover(key):
    _, title, sub = BOOKS[key]
    return f'<section class="cover"><div class="eyebrow">GAOKAO ENGLISH · LISTENING</div><h1>{esc(title)}</h1><div class="cover-tag">2019年至今 · 持续整理</div><div class="sub">{esc(sub)}</div><div class="format">PDF电子资料<br>A4版式 · 可自行打印<br>配套考试与原文精读视频：B站搜索“朋克英语”</div><div class="brand">朋克英语 出品</div></section>'


def toc(es, page_numbers):
    return '<section class="chap" id="CONTENTS"><div class="band"><div><div class="no">CONTENTS</div><h1>目录</h1></div></div><div class="intro">点击标题跳转；侧边栏书签也可定位。目录左侧为“已读”框，支持表单的阅读器可打勾并保存。</div><div class="toc">' + ''.join(f'<div class="tr"><span class="ck"></span><a href="#{m}"><span class="a">{esc(a)}{("　"+esc(b)) if b else ""}</span><span class="pg">{page_numbers.get(m, "")}</span></a></div>' for m, a, b in es) + '</div></section>'


@contextlib.contextmanager
def server():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(ROOT)))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_port}/'
    finally:
        httpd.shutdown()


def render(pg, base, tmp, key, content, es, numbers):
    body = cover(key) + toc(es, numbers) + content
    document = J.page_html(body, BOOKS[key][1]).replace('</style>', CSS + '</style>')
    document = document.replace(ROOT.as_uri() + '/', base)
    source = tmp / f'{key}.html'
    source.write_text(document, 'utf-8')
    pg.goto(base + source.relative_to(ROOT).as_posix(), wait_until='load', timeout=60000)
    pg.evaluate('document.fonts.ready')
    problems = pg.evaluate('''() => {
      const out=[];for(const e of document.querySelectorAll('section *')){
        const r=e.getBoundingClientRect(),b=e.closest('section').getBoundingClientRect();
        if(r.width&&(r.left<b.left-1||r.right>b.right+1||e.scrollWidth>e.clientWidth+2&&getComputedStyle(e).overflow==='hidden'))out.push((e.className||e.tagName)+': '+e.textContent.slice(0,55));
      }return out.slice(0,30);
    }''')
    assert not problems, (key, problems)
    wrap = pg.evaluate(J.WRAP_JS)
    assert not wrap, (key, wrap[:15])
    target = tmp / f'{key}.pdf'
    pg.pdf(path=str(target), print_background=True, prefer_css_page_size=True)
    reader = PdfReader(target)
    destinations = {str(k).lstrip('/'): reader.get_destination_page_number(v) for k, v in reader.named_destinations.items()}
    assert all(m in destinations for m, *_ in es), (key, '缺少目录目标')
    return target, {m: destinations[m] + 1 for m, *_ in es}


def finish_pdf(target, output, es):
    reader = PdfReader(target)
    dest = {str(k).lstrip('/'): reader.get_destination_page_number(v) for k, v in reader.named_destinations.items()}
    writer = PdfWriter(clone_from=target)
    for page in writer.pages:
        for ref in page.get('/Annots') or []:
            obj = ref.get_object()
            d = obj.get('/Dest')
            if obj.get('/Subtype') == '/Link' and d is not None and not isinstance(d, ArrayObject):
                name = str(d).lstrip('/')
                assert name in dest
                obj[NameObject('/Dest')] = ArrayObject([writer.pages[dest[name]].indirect_reference, NameObject('/Fit')])
    for mark, a, b in es:
        writer.add_outline_item(a + ('　' + b if b else ''), dest[mark])
    J.add_checkboxes(writer)
    writer.page_mode = '/UseOutlines'
    writer.add_metadata({'/Title': output.stem, '/Author': '朋克英语', '/Subject': '2019年至今高考英语听力电子资料'})
    writer.write(output)


def check_pdf(path, es, numbers, key, cases):
    reader = PdfReader(path)
    page_index = {p.indirect_reference.idnum: i for i, p in enumerate(reader.pages)}
    links, widgets = [], []
    for i, page in enumerate(reader.pages):
        for ref in page.get('/Annots') or []:
            o = ref.get_object()
            if o.get('/Subtype') == '/Link' and isinstance(o.get('/Dest'), ArrayObject):
                links.append((i, float(o['/Rect'][1]), page_index[o['/Dest'][0].idnum]))
            if o.get('/Subtype') == '/Widget':
                widgets.append(o)
                assert set(o['/AP']['/N']) == {'/On', '/Off'}
    links.sort(key=lambda v: (v[0], -v[1]))
    assert len(links) == len(es) == len(widgets) == len(reader.outline), (path, len(links), len(widgets))
    assert [d + 1 for _, _, d in links] == [numbers[m] for m, *_ in es], path
    assert [reader.get_destination_page_number(o) + 1 for o in reader.outline] == [numbers[m] for m, *_ in es], path
    with fitz.open(path) as doc:
        for (mark, a, _), (_, _, dest) in zip(es, links):
            assert normal(a) in normal(doc[dest].get_text()), (path, a, '目标页标题不符')
        if key in ('reading', 'practice', 'dictation', 'dictanswers', 'answers'):
            for i, case in enumerate(cases):
                a = numbers[es[i][0]] - 1
                z = numbers[es[i + 1][0]] - 1 if i + 1 < len(es) else len(doc)
                text = normal(''.join(doc[p].get_text() for p in range(a, z)))
                if key == 'reading':
                    wanted = [x for g in case['groups'] for s in g['sentences'] for x in (s['en'], s['zh'])]
                elif key == 'practice':
                    wanted = [t for q in case['questions'] for t in q['options'].values()]
                    assert '参考答案沿用' not in text
                elif key == 'dictanswers':
                    wanted = [b['en'] for b in blanks(case)]
                elif key == 'dictation':
                    wanted = [b['en'][:b['span'][0]] + b['en'][b['span'][1]:] for b in blanks(case)]
                else:
                    wanted = [q['options'][q['answer']] for q in case['questions']]
                for t in wanted:
                    assert normal(t) in text, (path.name, case['id'], 'PDF正文缺失', t[:110])
        if key in ('vocab', 'phrases'):
            terms = entries(cases, key == 'phrases')
            for i, (mark, _, _) in enumerate(es):
                a = numbers[mark] - 1
                z = numbers[es[i + 1][0]] - 1 if i + 1 < len(es) else len(doc)
                text = normal(''.join(doc[p].get_text() for p in range(a, z)))
                for e in terms[i*30:(i+1)*30]:
                    for t in [e['head'], e['examples'][0]['en'], e['examples'][0]['zh']]:
                        assert normal(t) in text, (path.name, e['head'], '词汇或例句缺失', t[:100])
        for page in doc:
            assert abs(page.rect.width - 595.276) < 1 and abs(page.rect.height - 841.89) < 1
            text = page.get_text()
            assert '\ufffd' not in text and '\x00' not in text, (path, '缺字')
    J.font_check(path)
    return {'file': path.name, 'pages': len(reader.pages), 'bytes': path.stat().st_size, 'sha256': sha(path), 'toc_links': len(links), 'bookmarks': len(reader.outline), 'read_checkboxes': len(widgets), 'checks': '正文对源、目录目标、页码、书签、复选框、字体、A4尺寸通过'}


def preview(path, key, chapter_start):
    PREVIEW.mkdir(parents=True, exist_ok=True)
    with fitz.open(path) as doc:
        for page_number, label in [(0, '封面'), (chapter_start - 1, '内页')]:
            page = doc[page_number]
            page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False).save(PREVIEW / f'{key}_{label}.png')


def verify_model(cases):
    originals = json.loads((G / '答案.json').read_text())
    n = 0
    for c in cases:
        assert len(c['questions']) == 20
        for q in c['questions']:
            assert originals[c['id']][str(q['n'])] == q['answer']
        for b in blanks(c):
            a, z = b['span']
            assert b['answer'] == b['en'][a:z] and b['answer'].strip()
            n += 1
    return n


def build(sample=False, reuse=()):
    cases = data(sample)
    nblanks = verify_model(cases)
    output = D / '样张' if sample else OUT
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    with server() as base, sync_playwright() as p, tempfile.TemporaryDirectory(dir=D, prefix='_build_') as t:
        browser = p.chromium.launch(executable_path=os.environ.get('GAOKAO_CHROME', '/usr/bin/chromium'), args=['--no-sandbox'])
        page = browser.new_page()
        tmp = Path(t)
        keys = ['practice', 'reading', 'dictation', 'dictanswers', 'answers', 'vocab', 'phrases', 'plan']
        for key in keys:
            es, content = compose(key, cases)
            path = output / f'{BOOKS[key][0]} {BOOKS[key][1]}.pdf'
            if key in reuse:
                old = PdfReader(path)
                assert len(old.outline) == len(es)
                numbers = {m: old.get_destination_page_number(o) + 1 for (m, *_), o in zip(es, old.outline)}
            else:
                target, numbers = render(page, base, tmp, key, content, es, {})
                target, final_numbers = render(page, base, tmp, key, content, es, numbers)
                assert numbers == final_numbers, (key, '第二遍目录排版后页码改变')
                finish_pdf(target, path, es)
            results[key] = check_pdf(path, es, numbers, key, cases)
            results[key]['chapters'] = numbers
            if not sample:
                preview(path, key, numbers[es[0][0]])
            print(json.dumps({'done': key, 'pages': results[key]['pages'], 'bytes': results[key]['bytes']}, ensure_ascii=False), flush=True)
        browser.close()
    manifest = {'series': '高考英语听力电子资料套装', 'brand': '朋克英语', 'year_label': '2019年至今', 'case_count': len(cases), 'questions': len(cases)*20, 'source_sentence_count': sum(c['source_sentences'] for c in cases), 'reading_sentence_count': sum(len(g['sentences']) for c in cases for g in c['groups']), 'exact_repeat_sentences_merged': sum(len(c['removed_exact_repeats']) for c in cases), 'dictation_blanks': nblanks, 'vocab_entries': len(entries(cases)), 'phrase_entries': len(entries(cases, True)), 'files': results, 'cases': [{'id': c['id'], 'title': c['title'], 'questions': 20, 'dictation_blanks': len(blanks(c)), 'hashes': c['hashes']} for c in cases], 'boundaries': '交付八份PDF；不含纸质书、原始DOC、MP3或MP4；参考答案沿用已发布视频，不含新增逐题解析。'}
    dump(output / '文件清单与核验.json', manifest)
    if not sample:
        dump(AUDIT / '内容处理记录.json', [{'id': c['id'], 'exact_repeat_sentences_merged': c['removed_exact_repeats'], 'blanks': blanks(c)} for c in cases])
        dump(AUDIT / '题目展示修复记录.json', {'规则来源': '高考听力/tools/听力视频.py:fix', '规则源文件SHA256': sha(_display_source), '修复': [{'id': c['id'], '修复': c['display_fixes']} for c in cases if c['display_fixes']]})
        dump(AUDIT / '最终核验.json', manifest)
    print(f'全部通过：{len(cases)}套，{len(results)}份PDF，共{sum(x["pages"] for x in results.values())}页，{nblanks}个听写空。', flush=True)


def check_existing():
    manifest = json.loads((OUT / '文件清单与核验.json').read_text())
    cases = data(False)
    verify_model(cases)
    for key, row in manifest['files'].items():
        path = OUT / row['file']
        assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes']
        es, _ = compose(key, cases)
        check_pdf(path, es, row['chapters'], key, cases)
    print('八份成品PDF和当前源材料核验通过')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sample', action='store_true')
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--reuse', nargs='*', choices=list(BOOKS), default=[])
    a = ap.parse_args()
    check_existing() if a.check else build(sample=a.sample, reuse=a.reuse)
