"""考研作文讲义与默写卡（用户 2026-10-23：讲清楚每篇范文是怎么一步一步写出来的、提取好句式并配例句；另做作文默写卡，默写句子和句式，旁边提醒默写的意义）。

    /opt/ttsenv/bin/python 考研作文/tools/讲义.py check [w01 …]     # 程序检查（不写篇目 = data/ 里全部）
    /opt/ttsenv/bin/python 考研作文/tools/讲义.py build [w01 …]     # 检查通过后生成三份 PDF（不写篇目 = 全部 24 篇）

数据：考研作文/讲义/data/<篇目>.json（模型写：审题、思路、步骤、句式、词汇、默写），总论.json（写作总攻略）；
范文句子 考研作文/作文/sents.json、参考译文 考研作文/ann/（复核定稿）、原题 考研作文/原题/（600 dpi 原卷裁图）都直接取用，不另写。
输出 考研作文/讲义/：考研英语写作满分范文精讲.pdf、考研作文默写卡.pdf、考研作文默写卡（答案）.pdf。
检查（有一处就不生成）：字段齐全、数量合规；句式原句、默写挖空都必须是范文里的原样文字（挖空在该句恰好出现一次、互不重叠）；
步骤覆盖范文每一句正文；例句英文以句末标点结束、不用直引号、无多余空格；中文不用半角标点；生成后 PDF 里不许出现系统字体（字体回退）、
页面内容不许横向溢出。
"""
import html
import os
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parent
ROOT = C.parent
D = C / '讲义'
DATA = D / 'data'
sys.path.insert(0, str(HERE))
import ann_lib as A  # noqa: E402

P = {p['id']: p for p in json.loads((C / '作文' / 'sents.json').read_text('utf-8'))}
V = {p['id']: p for p in json.loads((C / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
CIRC = '①②③④⑤⑥⑦⑧⑨⑩'
OUT_HANDOUT = D / '考研英语写作满分范文精讲.pdf'
OUT_CARDS = D / '考研作文默写卡.pdf'
OUT_ANS = D / '考研作文默写卡（答案）.pdf'


def flat(p):
    return [s for pa in p['sents'] for s in pa]


def zh(pid):
    meta, ann = A.parse(str(C / 'ann' / f'{pid}.txt'))
    return meta, {k: v['zh'] for k, v in ann.items()}


def body_ks(p):
    """正文句号（书信、通知的格式行除外）。"""
    n = len(flat(p))
    h, t = p.get('edge', [0, 0])
    return list(range(1 + h, n + 1 - t))


ZH_HALF = re.compile(r'[一-鿿][,;:?!]|[,;:?!][一-鿿]')


def en_ok(s):
    out = []
    if not re.search(r'[.!?]$', s):
        out.append('没有以句末标点结束')
    if re.search(r'["\']', s):
        out.append('直引号或直撇号（用 ’ “ ”）')
    if '  ' in s or s != s.strip():
        out.append('多余空格')
    if not re.match(r'[A-Z“0-9]', s):
        out.append('不是大写开头')
    if len(s.split()) < 6:
        out.append('太短')
    return out


def check(pid):
    f = DATA / f'{pid}.json'
    if not f.exists():
        return [f'{pid}：没有 {f.name}']
    try:
        d = json.loads(f.read_text('utf-8'))
    except Exception as e:      # noqa: BLE001
        return [f'{pid}：JSON 读不出来：{e}']
    p, errs = P[pid], []
    S = flat(p)
    e = lambda m: errs.append(f'{pid} {m}')
    if d.get('id') != pid:
        e('id 不对')
    s = d.get('审题', {})
    for k in ('题型', '语气', '字数'):
        if not isinstance(s.get(k), str) or not s.get(k):
            e(f'审题.{k} 缺')
    for k, lo in (('任务', 2), ('易错', 2)):
        if not isinstance(s.get(k), list) or len(s.get(k, [])) < lo:
            e(f'审题.{k} 至少 {lo} 条')
    if not 2 <= len(d.get('思路', [])) <= 6 or any(not all(x.get(k) for k in ('段', '作用', '内容')) for x in d.get('思路', [])):
        e('思路：2—6 段，每段要有 段、作用、内容')
    steps = d.get('步骤', [])
    if not 3 <= len(steps) <= 8:
        e('步骤：3—8 步')
    covered = set()
    for i, x in enumerate(steps, 1):
        if not x.get('标题') or not x.get('做法') or not isinstance(x.get('对应'), list) or not x['对应']:
            e(f'步骤 {i}：要有 标题、做法、对应（句号列表）')
            continue
        for k in x['对应']:
            if not isinstance(k, int) or not 1 <= k <= len(S):
                e(f'步骤 {i}：句号 {k} 不存在（1—{len(S)}）')
            covered.add(k)
    miss = [k for k in body_ks(p) if k not in covered]
    if miss:
        e(f'步骤没有覆盖正文第 {miss} 句')
    pats = d.get('句式', [])
    if not 4 <= len(pats) <= 7:
        e('句式：4—7 个')
    taken = {}
    for i, x in enumerate(pats, 1):
        for k in ('名称', '表达', '公式', '原句', '原句译', '讲解'):      # 表达：这个句式用来表达什么意思（用户 2026-10-23：每个英文句子下面先有中文，句式要说明白表达什么）
            if not x.get(k):
                e(f'句式 {i}：缺 {k}')
        src = x.get('原句', '')
        hits = [(k, s_.index(src)) for k, s_ in enumerate(S, 1) if src and src in s_]
        if len(hits) != 1 or any(s_.count(src) > 1 for s_ in S if src in s_):
            e(f'句式 {i}：原句在范文里找到 {len(hits)} 处（必须恰好一处，原样文字）：{src[:40]}')
        else:
            k, a = hits[0]
            for (b, c) in taken.get(k, []):
                if a < c and b < a + len(src):
                    e(f'句式 {i}：原句与另一个句式的原句重叠')
            taken.setdefault(k, []).append((a, a + len(src)))
        ex = x.get('例句', [])
        if len(ex) != 2:
            e(f'句式 {i}：例句必须 2 个')
        for j, y in enumerate(ex, 1):
            for m in en_ok(y.get('en', '')):
                e(f'句式 {i} 例句 {j}：{m}')
            z = y.get('zh', '')
            if not z or ZH_HALF.search(z) or not re.search(r'[。！？]$', z):
                e(f'句式 {i} 例句 {j}：中文缺失、用了半角标点或没有句末标点')
        if not 1 <= len(x.get('替换', [])) <= 4 or any(not isinstance(r, dict) or not r.get('en') or not r.get('zh') for r in x.get('替换', [])):
            e(f'句式 {i}：替换说法 1—4 个，每个是 {{"en": …, "zh": …}}（英文下面要有中文）')
    if not 5 <= len(d.get('词汇', [])) <= 10 or any(not all(y.get(k) for k in ('词', '义', '替代')) for y in d.get('词汇', [])):
        e('词汇：5—10 个，每个要有 词、义、替代')
    for y in d.get('词汇', []):
        w = y.get('词', '').lower().split()[0] if y.get('词') else ''
        if w and not any(w[:max(3, len(w) - 2)] in s_.lower() for s_ in S):
            e(f'词汇 {y.get("词")}：范文里找不到')
    dict_ = d.get('默写', [])
    if not 4 <= len(dict_) <= 7:
        e('默写：4—7 句')
    for i, x in enumerate(dict_, 1):
        k = x.get('句')
        if not isinstance(k, int) or not 1 <= k <= len(S):
            e(f'默写 {i}：句号 {k} 不存在')
            continue
        sent, spans = S[k - 1], []
        for g in x.get('挖空', []):
            if sent.count(g) != 1:
                e(f'默写 {i}（第 {k} 句）：挖空“{g}”在句中出现 {sent.count(g)} 次（必须恰好一次）')
                continue
            a = sent.index(g)
            if any(a < c and b < a + len(g) for b, c in spans):
                e(f'默写 {i}：挖空“{g}”与另一个挖空重叠')
            spans.append((a, a + len(g)))
        if not x.get('挖空') or not x.get('句式') or not x.get('意义'):
            e(f'默写 {i}：要有 挖空、句式、意义')
    # 中文字段不用半角标点
    def walk(o, path=''):
        if isinstance(o, dict):
            for k, v in o.items():
                if k not in ('en', '原句', '公式', '替换', '挖空', '词'):
                    walk(v, f'{path}.{k}')
        elif isinstance(o, list):
            for j, v in enumerate(o):
                walk(v, f'{path}[{j}]')
        elif isinstance(o, str) and ZH_HALF.search(o):
            e(f'{path} 用了半角标点：{o[:30]}')
    walk(d)
    return errs


# ------------------------------------------------------------------ 排版
FONTS = [ROOT / 'tools' / 'video' / 'themes' / 'fonts' / 'fonts.css', ROOT / '四级' / 'tools' / 'fonts' / 'fonts.css']
CSS = r"""
@font-face{font-family:Apos;font-weight:400;src:url(NU400);unicode-range:U+2019}@font-face{font-family:Apos;font-weight:700;src:url(NU700);unicode-range:U+2019}
x-nb{white-space:nowrap}
:root{--ink:#1f2537;--ink2:#3d4458;--mute:#6b7287;--blue:#2456a6;--berry:#c0185a;--hy:#ffe46b;--hp:#ffc4d8;--paper:#faf8f3;--rule:#c6d5ec;--card:#ffffff;--soft:#f3f6fb;--green:#2e7d4f}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;font-family:Apos,'Noto Sans SC',sans-serif;font-size:10.2pt;line-height:1.72;color:var(--ink)}
.en,.essay,.ex .e,.f code,.q{font-family:'EB Garamond','Noto Sans SC',serif}
h1,h2,h3{margin:0;font-weight:700}
.chap{break-before:page}
.band{display:flex;align-items:flex-end;justify-content:space-between;border-bottom:2.2px solid var(--ink);padding-bottom:2.6mm;margin-bottom:4.5mm}
.band .no{font-family:'Nunito','Noto Sans SC';font-weight:800;font-size:9pt;letter-spacing:.18em;color:var(--blue)}
.band h1{font-size:19pt;line-height:1.25;margin-top:1mm}
.band h1 span{background:linear-gradient(var(--hy),var(--hy)) 0 87.9%/100% 34% no-repeat;padding:0 1.2mm}
.band .meta{text-align:right;font-size:9pt;color:var(--mute);line-height:1.5}
.band .meta b{display:block;color:var(--ink2);font-size:10pt}
.sec{display:flex;align-items:center;gap:2.5mm;margin:6mm 0 2.6mm;break-after:avoid}
.sec .n{font-family:'Nunito','Noto Sans SC';font-weight:800;color:#fff;background:var(--blue);border-radius:50%;width:6.4mm;height:6.4mm;display:flex;align-items:center;justify-content:center;font-size:9.5pt}
.sec h2{font-size:13pt;letter-spacing:.04em}
.sec .tip{margin-left:auto;font-family:Apos,'LXGW WenKai','Noto Sans SC';color:var(--mute);font-size:9.5pt}
.prompt{border:1px solid #e3e0d6;border-radius:3mm;padding:3mm;background:#fff;text-align:center;break-inside:avoid}
.prompt img{max-width:100%;max-height:108mm}
.chips{display:flex;flex-wrap:wrap;gap:2mm;margin-bottom:2.5mm}
.chip{border-radius:5mm;padding:.4mm 3mm;font-size:9pt;background:var(--soft);color:var(--blue);font-weight:500}
.chip.w{background:#fff4c2;color:#7a5a00}
.task{list-style:none;margin:0;padding:0}
.task li{position:relative;padding-left:7mm;margin:1mm 0;break-inside:avoid}
.task li::before{content:'';position:absolute;left:0;top:1.6mm;width:3.6mm;height:3.6mm;border:1.6px solid var(--blue);border-radius:1mm}
.warn{background:#fff5f8;border-left:3px solid var(--berry);border-radius:0 2mm 2mm 0;padding:2mm 3.5mm;margin-top:2.5mm;break-inside:avoid}
.warn b{color:var(--berry)}.warn ul{margin:.5mm 0 0;padding-left:5mm}
.tone{font-family:Apos,'LXGW WenKai','Noto Sans SC';color:var(--ink2);margin-top:2mm}
.flow{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:2.5mm}
.flow>div{background:var(--soft);border-radius:2.5mm;padding:2.5mm 3mm;border-top:3px solid var(--blue);break-inside:avoid}
.flow b{display:block;font-size:10.5pt}.flow i{font-style:normal;color:var(--berry);font-weight:700;font-size:9pt}
.flow p{margin:1mm 0 0;font-size:9.3pt;line-height:1.6;color:var(--ink2)}
.essay{background:var(--paper);border:1px solid #ebe6da;border-radius:3mm;padding:5mm 6mm;font-size:12.6pt;line-height:1.85;
}
.essay p{margin:0 0 .3em;text-indent:2em}.essay p.ln{text-indent:0}.essay p.ttl{text-align:center;font-weight:700;text-indent:0}.essay p.sig{text-indent:0}
.essay .k{font-family:'Nunito','Noto Sans SC';font-size:6.5pt;color:var(--mute);vertical-align:.7em;margin-right:.6mm}
mark{background:linear-gradient(var(--hy),var(--hy)) 0 89.7%/100% 42% no-repeat;color:inherit;padding:0 .3mm}
mark sup{font-family:Apos,'Noto Sans SC';font-size:7.5pt;color:var(--berry);font-weight:700;margin-left:.3mm}
.trans{font-family:Apos,'LXGW WenKai','Noto Sans SC';font-size:10pt;color:var(--ink2);margin-top:3mm;line-height:1.75}
.trans p{margin:0 0 1.2mm;text-indent:2em}
.step{display:grid;grid-template-columns:9mm 1fr;gap:2mm;margin:2.8mm 0;break-inside:avoid}
.step .s{font-family:'Nunito','Noto Sans SC';font-weight:800;color:var(--blue);font-size:15pt;line-height:1}
.step b{font-size:10.6pt}.step p{margin:.6mm 0}
.step .q{font-size:11pt;color:var(--ink2);border-left:2.5px solid var(--rule);padding-left:3mm;margin-top:1mm;line-height:1.6}
.pat{border:1px solid #e6e2d8;border-radius:3mm;margin:3.5mm 0;overflow:hidden;background:#fff;-webkit-box-decoration-break:clone;box-decoration-break:clone}
.pat .top{break-inside:avoid}.pat .ex,.pat .alt{break-inside:avoid}
.pat .h{display:flex;align-items:center;gap:2mm;background:var(--soft);padding:1.8mm 3.5mm}
.pat .h .c{color:var(--berry);font-weight:700;font-size:12pt}.pat .h b{font-size:11pt}
.pat .b{padding:2.4mm 3.5mm}
.f{background:#fffbe6;border:1px dashed #e7c84a;border-radius:2mm;padding:1.6mm 3mm;font-size:10.4pt;margin-bottom:2mm}
.f::before{content:'公式  ';font-family:Apos,'Noto Sans SC';font-weight:700;color:#8a6d00;font-size:8.6pt}
.o{font-size:11.2pt;margin:1mm 0 1.6mm}.o::before{content:'范文原句  ';font-family:Apos,'Noto Sans SC';font-weight:700;color:var(--blue);font-size:8.6pt}
.why{font-family:Apos,'LXGW WenKai','Noto Sans SC';font-size:10pt;color:var(--ink2);margin:1mm 0 2mm}
.ex{display:grid;grid-template-columns:7mm 1fr;gap:1mm 1.5mm;margin:1.2mm 0}
.ex .t{font-family:'Nunito','Noto Sans SC';font-weight:800;font-size:8pt;color:#fff;background:var(--green);border-radius:1mm;height:4.4mm;text-align:center;margin-top:1mm}
.ex .e{font-size:11.2pt;line-height:1.5}.ex .z{grid-column:2;color:var(--mute);font-size:9.2pt;margin-top:-.6mm}
.alt{margin-top:1.8mm;font-size:9.2pt;color:var(--mute);border-top:1px dashed #e3dfd3;padding-top:1.4mm}.alt b{display:block;font-size:8.6pt;color:var(--blue);margin-bottom:.4mm}
.alt>div{margin:.5mm 0}.alt span{font-family:'EB Garamond','Noto Sans SC';font-size:10.8pt;color:var(--ink)}.alt i{font-style:normal;display:block;font-size:9pt;color:var(--mute)}
.mean{background:#eef6ff;border-left:3px solid var(--blue);border-radius:0 2mm 2mm 0;padding:1.4mm 3mm;margin-bottom:2mm;font-size:10.2pt}.mean b{color:var(--blue);margin-right:2mm;font-size:9pt}
.oz{font-size:9.4pt;color:var(--mute);margin:-.8mm 0 1.6mm}
.step .q>div{margin:.6mm 0}.qz{font-family:Apos,'Noto Sans SC';font-size:9pt;color:var(--mute);line-height:1.5}
.tl{margin:1.2mm 0}.te{font-family:'EB Garamond','Noto Sans SC';font-size:11.2pt}.tz{font-size:9pt;color:var(--mute)}
table.voc{width:100%;border-collapse:collapse;font-size:9.6pt}
table.voc th{background:var(--ink);color:#fff;font-weight:500;padding:1.4mm 2.5mm;text-align:left}
table.voc td{border-bottom:1px solid #e6e2d8;padding:1.4mm 2.5mm;vertical-align:top}
table.voc td.w{font-family:'EB Garamond','Noto Sans SC';font-size:11.4pt;font-weight:600}table.voc td.r{font-family:'EB Garamond','Noto Sans SC';font-size:11pt;color:var(--mute)}
table.voc tr{break-inside:avoid}
.vg{break-inside:avoid}.vr{display:grid;grid-template-columns:34% 36% 30%;font-size:9.6pt}
.vr>div{border-bottom:1px solid #e6e2d8;padding:1.4mm 2.5mm}.vr.th>div{background:var(--ink);color:#fff;font-weight:500;border:0}
.vr .w{font-family:'EB Garamond','Noto Sans SC';font-size:11.4pt;font-weight:600}.vr .r{font-family:'EB Garamond','Noto Sans SC';font-size:11pt;color:var(--mute)}
/* 总论 */
.lead{font-family:Apos,'LXGW WenKai','Noto Sans SC';font-size:11pt;color:var(--ink2)}
.box{background:var(--soft);border-radius:3mm;padding:3mm 4mm;margin:2.5mm 0;break-inside:avoid}
.box h3{font-size:11pt;color:var(--blue);margin-bottom:1mm}
.box ul{margin:0;padding-left:5mm}.box li{margin:.6mm 0}
.tpl{font-family:'EB Garamond','Noto Sans SC';font-size:11pt;background:#fff;border:1px dashed var(--rule);border-radius:2mm;padding:2mm 3mm;margin:1.5mm 0;white-space:pre-wrap;line-height:1.55}
.bad{display:grid;grid-template-columns:1fr 1fr 1.4fr;gap:0;font-size:9.6pt;border:1px solid #eadbe0;border-radius:2mm;overflow:hidden;margin-top:2mm}
.bad>div{padding:1.3mm 2.5mm;border-bottom:1px solid #f1e6ea}.bad .x{font-family:'EB Garamond','Noto Sans SC';font-size:11pt;color:var(--berry);text-decoration:line-through}
.bad .v{font-family:'EB Garamond','Noto Sans SC';font-size:11pt;color:var(--green);font-weight:600}.bad .hd{background:#fbeef2;font-weight:700;color:var(--berry);font-size:9pt}
.toc{font-size:10.6pt}.toc div{display:grid;grid-template-columns:62mm 1fr 14mm;gap:3mm;break-inside:avoid;padding:1.1mm 0;border-bottom:1px dotted #d9d4c7}
.toc .a{color:var(--mute);font-size:9.6pt}.toc .pg{font-family:'Nunito','Noto Sans SC';font-weight:700;color:var(--blue);text-align:right}
.idx td{font-size:9.2pt}.idx td.e{font-family:'EB Garamond','Noto Sans SC';font-size:10.4pt}
/* 默写卡 */
.card{border:1.2px solid #e1dccf;border-radius:3mm;margin:3.2mm 0;display:grid;grid-template-columns:1fr 46mm;break-inside:avoid;overflow:hidden}
.card .l{padding:2.6mm 3.5mm}.card .r{background:#fff9db;border-left:1.2px dashed #e7c84a;padding:2.6mm 3mm;font-family:Apos,'LXGW WenKai','Noto Sans SC';font-size:9.3pt;line-height:1.55;color:#5b4a10}
.card .r b{display:block;font-family:Apos,'Noto Sans SC';color:#8a6d00;font-size:8.6pt;margin-top:1mm}
.card .zh{font-size:9.8pt;color:var(--ink2);margin-bottom:1.6mm}
.card .zh::before{content:attr(data-n);font-family:'Nunito','Noto Sans SC';font-weight:800;color:#fff;background:var(--blue);border-radius:1mm;padding:0 1.5mm;margin-right:2mm;font-size:8.6pt}
.card .en{font-size:12.6pt;line-height:2.25}
.gap{display:inline-block;border-bottom:1.3px solid var(--ink);height:1.1em;vertical-align:-.2em;position:relative}
.gap sup{position:absolute;left:0;top:-1.1em;font-family:'Nunito','Noto Sans SC';font-size:6.5pt;color:var(--berry);font-weight:800}
.ans mark{background:linear-gradient(var(--hp),var(--hp)) 0 89.3%/100% 44% no-repeat}
.lines{margin-top:1.4mm}.lines div{height:9.5mm;border-bottom:1px solid #cfd6e3}
.how{background:var(--soft);border-radius:3mm;padding:3mm 4mm;font-size:9.8pt;margin-bottom:4mm}
.chap.ans{break-before:auto;margin-top:9mm}.chap.ans:first-child{margin-top:0}.keep{break-inside:avoid}
.fit .card{margin:2.2mm 0}.fit .card .l{padding:2mm 3.5mm}.fit .card .r{padding:2mm 3mm}.fit .card .zh{margin-bottom:1.2mm}
.fit .card .en{line-height:2.05}.fit .lines{margin-top:1mm}.fit .lines div{height:8.6mm}.fit .how{margin-bottom:3mm}
.fit2 .card{margin:1.7mm 0}.fit2 .card .en{line-height:1.95}.fit2 .lines div{height:8mm}.fit2 .card .r{font-size:8.9pt;line-height:1.5}.fit2 .how{padding:2.4mm 4mm}
"""


def page_html(body, title, footer=True):
    links = ''.join(f"<link rel='stylesheet' href='{f.as_uri()}'>" for f in FONTS)
    # 页脚用 CSS 页边框（@page @bottom-*，Chromium 131 起支持）：用的是文档自己的网页字体；Chromium 的 footer_template 在另一个上下文里，只能用系统字体（字体回退被 font_check 拦下）
    pg = ("@page{size:A4;margin:16mm 15mm 17mm;@bottom-left{content:'" + title + "';font-family:Apos,'Noto Sans SC';font-size:7.5pt;color:#8a90a0}"
          "@bottom-right{content:counter(page);font-family:'Nunito','Noto Sans SC';font-weight:700;font-size:8pt;color:#8a90a0}}") if footer else '@page{size:A4;margin:0}'
    # 屏幕排版宽度与打印版心相同（A4 210mm − 左右页边 30mm），程序检查（溢出、断行）量到的就是打印出来的换行
    scr = '@media screen{body{width:' + ('180mm' if footer else '210mm') + '}}'
    nu = ROOT / 'tools' / 'video' / 'themes' / 'fonts' / 'nunito' / 'files'
    css = CSS.replace('NU400', (nu / 'nunito-latin-400-normal.woff2').as_uri()).replace('NU700', (nu / 'nunito-latin-700-normal.woff2').as_uri())
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>{links}<style>{pg}{css}{scr}</style></head><body>{body}</body></html>"


CJK = '\u3400-\u9fff'
CORE = re.compile(f'[{CJK}0-9]')


def esc(s, formula=False):
    """转义 + 断行规则（排版审阅 2026-10-23）：末两字不分开（不留孤字）、数字与单位不分开、省略号不放行首、
    Li Ming 不拆开；公式里的中文占位词（动词原形、截止日期……）整体不断开。用自定义元素 x-nb，不用 span（踩坑 34）。"""
    s = s.replace('Li Ming', 'Li\u00a0Ming')
    s = re.sub(r' (?=[…⋯])', '\u00a0', s)
    spans = [m.span() for m in re.finditer(f'\\d[\\d.,]*%? ?[{CJK}]', s)]
    if formula:
        spans += [m.span() for m in re.finditer(f'[{CJK}]{{2,8}}\\d*', s)]
    i = len(s)
    while i > 0 and not CORE.match(s[i - 1]) and not s[i - 1].isspace() and not (s[i - 1].isascii() and s[i - 1].isalpha()):
        i -= 1
    j, n = i, 0
    while j > 0 and n < 2:
        c = s[j - 1]
        if c.isspace() or (c.isascii() and c.isalpha()):
            break
        n += bool(CORE.match(c))
        j -= 1
    if n == 2 and re.search(f'[{CJK}]', s[j:i]):
        k = j
        while k > 0 and s[k - 1] in '…⋯':
            k -= 1
        if k < j and k > 0 and CORE.match(s[k - 1]):
            k -= 1
        spans.append((min(k, j), len(s)))
    out, pos = [], 0
    for a, b in sorted(spans):
        if a < pos:            # 与前一段重叠：并进前一段
            if b > pos:
                out[-1] = out[-1][:-len('</x-nb>')] + html.escape(s[pos:b], quote=False) + '</x-nb>'
                pos = b
            continue
        out.append(html.escape(s[pos:a], quote=False))
        out.append('<x-nb>' + html.escape(s[a:b], quote=False) + '</x-nb>')
        pos = b
    out.append(html.escape(s[pos:], quote=False))
    return ''.join(out)


def marked(sent, spans):
    """句子里的若干片段加荧光笔和编号：spans = [(起, 止, 编号)]。"""
    out, i = [], 0
    for a, b, n in sorted(spans):
        out.append(esc(sent[i:a]))
        out.append(f'<mark>{esc(sent[a:b])}<sup>{n}</sup></mark>')
        i = b
    out.append(esc(sent[i:]))
    return ''.join(out)


def head_info(pid):
    p, v = P[pid], V[pid]
    return p, v, f"{p['pdf']} · 写作 {p['passage']}"


def prompt_img(pid, tmp):
    """原题图缩到 2000 像素宽（A4 打印约 300 dpi），PDF 不至于太大。"""
    from PIL import Image
    src = C / '原题' / P[pid]['prompt_img']
    im = Image.open(src)
    if im.width > 2000:
        im = im.resize((2000, round(im.height * 2000 / im.width)), Image.LANCZOS)
    f = Path(tmp) / f'{pid}.png'
    im.save(f, optimize=True)
    return f.as_uri()


def essay_html(p, spans_by_k, numbered=True):
    S, out, k = flat(p), [], 0
    letter = p.get('letter') or {}
    h, t = p.get('edge', [0, 0])
    for pi, pa in enumerate(p['sents']):
        parts = []
        for s in pa:
            k += 1
            mk = f"<span class='k'>{k}</span>" if numbered else ''
            parts.append(mk + marked(s, spans_by_k.get(k, [])))
        cls = ''
        if h and pi == 0:
            cls = 'ttl' if letter.get('title') else 'ln'
        if t and pi == len(p['sents']) - 1:
            cls = 'sig'
            if letter.get('closing'):     # 结束语与署名分两行
                last = parts[0]
                cut = last.find(letter['signature'])
                parts = [last[:cut].rstrip() + '<br>' + last[cut:]] if cut > 0 else parts
        out.append(f"<p class='{cls}'>{' '.join(parts)}</p>")
    return '<div class="essay">' + ''.join(out) + '</div>'


def essay_chapter(no, pid, tmp):
    p, v, sub = head_info(pid)
    d = json.loads((DATA / f'{pid}.json').read_text('utf-8'))
    meta, Z = zh(pid)
    S = flat(p)
    spans, num = {}, {}
    for i, x in enumerate(d['句式'], 1):
        k = next(k for k, s in enumerate(S, 1) if x['原句'] in s)
        a = S[k - 1].index(x['原句'])
        spans.setdefault(k, []).append((a, a + len(x['原句']), CIRC[i - 1]))
        num[i] = k
    s = d['审题']
    sec = lambda n, t, tip='': f"<div class='sec'><div class='n'>{n}</div><h2>{t}</h2>{f'<div class=tip>{tip}</div>' if tip else ''}</div>"
    tp = [f"<p>{''.join(esc(Z.get(k, '')) for k in range(sum(len(x) for x in p['sents'][:i]) + 1, sum(len(x) for x in p['sents'][:i + 1]) + 1))}</p>"
          for i in range(len(p['sents']))]
    # “参考译文”小标题与第一段不分开（否则会单独留在页底）
    trans = "<div class='keep'><b style='font-family:Apos,Noto Sans SC;font-size:9pt;color:var(--mute)'>参考译文</b>" + tp[0] + '</div>' + ''.join(tp[1:])
    flow = ''.join(f"<div><i>{esc(x['段'])}</i><b>{esc(x['作用'])}</b><p>{esc(x['内容'])}</p></div>" for x in d['思路'])
    steps = ''.join(f"<div class='step'><div class='s'>{i:02d}</div><div><b>{esc(x['标题'])}</b><p>{esc(x['做法'])}</p>"
                    f"<div class='q'>{''.join(f'<div><span class=k>{k}</span> {esc(S[k - 1])}<div class=qz>{esc(Z.get(k, chr(32)))}</div></div>' for k in x['对应'])}</div></div></div>"
                    for i, x in enumerate(d['步骤'], 1))
    pats = ''.join(
        f"<div class='pat'><div class='top'><div class='h'><span class='c'>{CIRC[i - 1]}</span><b>{esc(x['名称'])}</b></div><div class='b'>"
        f"<div class='mean'><b>这个句式表达</b>{esc(x['表达'])}</div><div class='f'>{esc(x['公式'], True)}</div>"
        f"<div class='o en'>{esc(x['原句'])}</div><div class='oz'>{esc(x['原句译'])}</div><div class='why'>{esc(x['讲解'])}</div></div></div><div class='b' style='padding-top:0'>"
        + ''.join(f"<div class='ex'><div class='t'>例{j}</div><div class='e'>{esc(y['en'])}</div><div class='z'>{esc(y['zh'])}</div></div>" for j, y in enumerate(x['例句'], 1))
        + "<div class='alt'><b>也可以这样说</b>" + ''.join(f"<div><span>{esc(r['en'])}</span><i>{esc(r['zh'])}</i></div>" for r in x['替换']) + "</div></div></div>"
        for i, x in enumerate(d['句式'], 1))
    vr = [f"<div class='vr'><div class='w'>{esc(y['词'])}</div><div>{esc(y['义'])}</div><div class='r'>{esc(y['替代'])}</div></div>" for y in d['词汇']]
    # 长表：表头与前 3 行不分开，最后 2 行不分开，中间各行可以换页
    k = len(vr) if len(vr) <= 10 else 3; tail = max(k, len(vr) - 2)   # 10 行以内整张表不分开（拆开会在章末留下两行没有表头的孤行）
    voc = (f"<div class='vg'>" + sec(7, '亮点词汇', '把普通说法换成高分说法')
           + "<div class='vr th'><div>高分表达</div><div>意思</div><div>替代的普通说法</div></div>" + ''.join(vr[:k]) + '</div>'
           + ''.join(f"<div class='vg'>{r}</div>" for r in vr[k:tail]) + (f"<div class='vg'>{''.join(vr[tail:])}</div>" if vr[tail:] else ''))
    return (f"<section class='chap' data-mark='CH{no:02d}'><div class='band'><div><div class='no'>MODEL ESSAY {no:02d} · {esc(p['part'] == 'A' and 'PART A 小作文' or 'PART B 大作文')}</div>"
            f"<h1><span>{esc(meta.get('T', ''))}</span></h1></div><div class='meta'><b>{esc(sub)}</b>{esc(meta.get('G', ''))} · 范文 {p['words']} 词</div></div>"
            + sec(1, '原题') + f"<div class='prompt'><img src='{prompt_img(pid, tmp)}'></div>"
            + sec(2, '审题', '先弄清楚要写什么，再动笔')
            + f"<div class='chips'><span class='chip'>{esc(s['题型'])}</span><span class='chip w'>{esc(s['字数'])}</span></div>"
            + "<ul class='task'>" + ''.join(f'<li>{esc(x)}</li>' for x in s['任务']) + '</ul>'
            + f"<div class='tone'>语气与身份：{esc(s['语气'])}</div>"
            + "<div class='warn'><b>容易失分的地方</b><ul>" + ''.join(f'<li>{esc(x)}</li>' for x in s['易错']) + '</ul></div>'
            + sec(3, '写作思路', '先列提纲，每段一个任务') + f"<div class='flow' style='--n:{len(d['思路'])}'>{flow}</div>"
            + sec(4, '满分范文', '荧光笔 + 圆圈编号 = 下面讲的高分句式') + essay_html(p, spans)
            + f"<div class='trans'>{trans}</div>"
            + sec(5, '一步一步写出这篇范文') + steps
            + sec(6, '高分句式', '公式 → 原句 → 讲解 → 仿写') + pats
            + voc + "</section>")


def general_chapter():
    f = DATA / '总论.json'
    if not f.exists():
        return ''
    g = json.loads(f.read_text('utf-8'))
    out = [f"<section class='chap' data-mark='GEN'><div class='band'><div><div class='no'>WRITING GUIDE</div><h1><span>{esc(g['标题'])}</span></h1></div>"
           f"<div class='meta'><b>先读这一章</b>评分标准 · 结构 · 模板 · 避坑</div></div><p class='lead'>{esc(g['导语'])}</p>"]
    for i, sct in enumerate(g['小节'], 1):
        out.append(f"<div class='sec'><div class='n'>{i}</div><h2>{esc(sct['标题'])}</h2></div>")
        for b in sct['内容']:
            if b['类'] == '段':
                out.append(f"<p>{esc(b['文'])}</p>")
            elif b['类'] == '要点':
                out.append("<div class='box'>" + (f"<h3>{esc(b['标题'])}</h3>" if b.get('标题') else '') + "<ul>"
                           + ''.join(f'<li>{esc(x)}</li>' for x in b['条']) + '</ul></div>')
            elif b['类'] == '模板' and b.get('行'):
                out.append(f"<div class='box'><h3>{esc(b['标题'])}</h3>" + ''.join(f"<div class='tl'><div class='te'>{esc(e_)}</div><div class='tz'>{esc(z_)}</div></div>" for e_, z_ in b['行']) + '</div>')
            elif b['类'] == '模板':
                out.append(f"<div class='box'><h3>{esc(b['标题'])}</h3><div class='tpl'>{esc(b['文'])}</div>" + (f"<p class='why'>{esc(b['说明'])}</p>" if b.get('说明') else '') + "</div>")
            elif b['类'] == '对照':
                out.append("<div class='bad'><div class='hd'>不要这样写</div><div class='hd'>改成</div><div class='hd'>为什么</div>"
                           + ''.join(f"<div class='x'>{esc(r[0])}</div><div class='v'>{esc(r[1])}</div><div>{esc(r[2])}</div>" for r in b['行']) + '</div>')
    out.append('</section>')
    return ''.join(out)


def index_chapter(ids):
    rows = []
    for pid in ids:
        d = json.loads((DATA / f'{pid}.json').read_text('utf-8'))
        meta, _ = zh(pid)
        for x in d['句式']:
            rows.append(f"<tr><td>{esc(x['名称'])}</td><td class='e'>{esc(x['公式'], True)}</td><td>{esc(P[pid]['pdf'][:4])} {esc(P[pid]['pdf'][6:])} {esc(P[pid]['passage'])}</td></tr>")
    return ("<section class='chap' data-mark='IDX'><div class='band'><div><div class='no'>INDEX · ALL PATTERNS</div><h1><span>高分句式总表</span></h1></div>"
            "<div class='meta'><b>考前一页过一遍</b>全部范文里讲过的句式</div></div>"
            f"<table class='voc idx'><tr><th style='width:30%'>句式</th><th>公式</th><th style='width:24%'>出自</th></tr>{''.join(rows)}</table></section>")


def cover(title, sub, note):
    return (f"<div style='height:297mm;width:210mm;background:var(--paper);position:relative;overflow:hidden;"
            f"background-image:radial-gradient(circle at 1.5px 1.5px,rgba(70,92,128,.2) 1.3px,transparent 1.7px);background-size:7mm 7mm'>"
            f"<div style='position:absolute;left:0;top:0;bottom:0;width:14mm;background:repeating-linear-gradient(transparent 0 6mm,#7d8596 6mm 7.2mm,transparent 7.2mm 11mm)'></div>"
            f"<div style='position:absolute;left:34mm;right:24mm;top:62mm'>"
            f"<div style='font-family:Nunito,Noto Sans SC;font-weight:800;letter-spacing:.3em;color:var(--blue);font-size:11pt'>KAOYAN ENGLISH WRITING</div>"
            f"<div style='font-size:34pt;font-weight:700;line-height:1.3;margin:6mm 0'><span style='background:linear-gradient(var(--hy),var(--hy)) 0 87.5%/100% 36% no-repeat;padding:0 2mm'>{esc(title)}</span></div>"
            f"<div style='font-size:15pt;color:var(--ink2);line-height:1.6'>{sub}</div>"
            f"<div style='margin-top:16mm;font-family:Apos,LXGW WenKai,Noto Sans SC;font-size:12pt;color:var(--ink2);line-height:1.9'>{note}</div></div>"
            f"<div style='position:absolute;right:22mm;top:30mm;width:34mm;height:34mm;border-radius:50%;background:var(--hy);display:flex;align-items:center;justify-content:center;"
            f"transform:rotate(10deg);font-weight:700;font-size:15pt;text-align:center;line-height:1.25;box-shadow:0 2mm 4mm rgba(0,0,0,.08)'>考研<br>作文</div></div>")


def toc_html(entries, pages):
    return ("<section data-mark='TOC'><div class='band'><div><div class='no'>CONTENTS</div><h1><span>目录</span></h1></div><div class='meta'></div></div><div class='toc'>"
            + ''.join(f"<div><span class='a'>{esc(a)}</span><span>{esc(b)}</span><span class='pg'>{pages.get(m, '')}</span></div>" for m, a, b in entries) + '</div></section>')


def card_section(pid, answers, how='', fit=0):
    p, v, sub = head_info(pid)
    d = json.loads((DATA / f'{pid}.json').read_text('utf-8'))
    meta, Z = zh(pid)
    S = flat(p)
    items = []
    for i, x in enumerate(d['默写'], 1):
        sent = S[x['句'] - 1]
        spans = sorted((sent.index(g), sent.index(g) + len(g)) for g in x['挖空'])
        out, j = [], 0
        for n, (a, b) in enumerate(spans, 1):
            out.append(esc(sent[j:a]))
            if answers:
                out.append(f'<mark>{esc(sent[a:b])}</mark>')
            else:
                out.append(f"<span class='gap' style='width:{max(12, (b - a) * 2.15):.1f}mm'><sup>{n}</sup></span>")
            j = b
        out.append(esc(sent[j:]))
        en = GAP_PUNCT.sub(r'<x-nb>\1\2</x-nb>', ''.join(out))
        items.append(f"<div class='card'><div class='l'><div class='zh' data-n='{i}'>{esc(Z.get(x['句'], ''))}</div><div class='en'>{en}</div></div>"
                     f"<div class='r'><b>掌握句式</b>{esc(x['句式'])}<b>为什么默写这句</b>{esc(x['意义'])}</div></div>")
    full = ''
    if not answers:
        full = ("<div class='sec'><div class='n'>B</div><h2>整句默写：看中文，写出英文原句</h2><div class='tip'>写完再对照答案</div></div>"
                + ''.join(f"<div class='card' style='grid-template-columns:1fr'><div class='l'><div class='zh' data-n='{i}'>{esc(Z.get(x['句'], ''))}</div>"
                          f"<div class='lines'>{'<div></div>' * (2 if len(S[x['句'] - 1]) < 110 else 3)}</div></div></div>" for i, x in enumerate(d['默写'], 1)))
    return (f"<section class='chap{' ans' if answers else ''}{' fit' if fit else ''}{' fit2' if fit > 1 else ''}' data-mark='C{pid}'><div class='keep'><div class='band'><div><div class='no'>DICTATION · {esc(sub)}</div>"
            f"<h1><span>{esc(meta.get('T', ''))}</span></h1></div><div class='meta'><b>{'答案' if answers else '作文默写卡'}</b>{esc(meta.get('G', ''))}</div></div>"
            + how + ("<div class='sec'><div class='n'>A</div><h2>句式填空：补全横线处的关键表达</h2><div class='tip'>右边提醒：练的是什么句式、为什么值得背</div></div>" if not answers else
               "<div class='sec'><div class='n'>✓</div><h2>答案：粉色是填空的部分，整句也是 B 部分的答案</h2></div>")
            + items[0] + '</div>' + ''.join(items[1:]) + full + '</section>')


GAP_PUNCT = re.compile(r"(<span class='gap'[^>]*><sup>\d+</sup></span>|<mark>[^<]*</mark>)([.,;:?!”’)]+)")


# 断行检查（排版审阅 2026-10-23 查出 25 处后补成程序检查）：逐字量出所在的行
WRAP_JS = r"""() => {
  const CJK = /[㐀-鿿]/, DIG = /[0-9]/, PUN = /[\s，。、；：？！“”‘’（）《》「」…⋯—·,.;:?!()\[\]\/+|%-]/;
  const blockOf = el => { while (el && getComputedStyle(el).display.startsWith('inline')) el = el.parentElement; return el; };
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT), r = document.createRange(), B = new Map();
  for (let n; (n = tw.nextNode());) {
    if (n.nodeType === 1) {          // 填空横线算一个“字”（编号 sup 是绝对定位的，不能拿它当位置）
      if (n.classList.contains('gap')) { const b = blockOf(n.parentElement), k = n.getBoundingClientRect();
        let a = B.get(b); if (!a) B.set(b, a = []); a.push({ c: '＿', y: k.top + k.height / 2 }); }
      continue;
    }
    const t = n.textContent; if (!t.trim()) continue;
    if (getComputedStyle(n.parentElement).position === 'absolute') continue;
    const b = blockOf(n.parentElement); if (!b) continue;
    let a = B.get(b); if (!a) B.set(b, a = []);
    for (let i = 0; i < t.length; i++) {
      if (/\s/.test(t[i])) { a.push({ c: ' ' }); continue; }
      r.setStart(n, i); r.setEnd(n, i + 1);
      const q = r.getClientRects(); if (!q.length) continue;
      const k = q[q.length - 1]; a.push({ c: t[i], y: k.top + k.height / 2 });
    }
  }
  const out = [];
  for (const [b, a] of B) {
    const lh = parseFloat(getComputedStyle(b).fontSize) * 0.6, L = [];
    let cur = null;
    for (const x of a) {
      if (x.y === undefined) { if (cur) cur.push(x); continue; }
      if (!cur || x.y - cur.y0 > lh) L.push(cur = Object.assign([], { y0: x.y }));
      cur.push(x);
    }
    if (L.length < 2) continue;
    const txt = l => l.map(x => x.c).join('').trim();
    const name = (b.className || b.tagName) + '｜' + txt(L[L.length - 2]).slice(-12) + '／' + txt(L[L.length - 1]).slice(0, 12);
    const last = txt(L[L.length - 1]), core = [...last].filter(c => !PUN.test(c));
    if (core.length === 1 && (CJK.test(core[0]) || DIG.test(core[0]))) out.push('孤字：' + name);
    if (core.length === 0) out.push('标点独占一行：' + name);
    const formula = b.matches('.f, .idx td.e');
    for (let i = 1; i < L.length; i++) {
      const p = txt(L[i - 1]), n = txt(L[i]);
      if (!p || !n) continue;
      const e = p[p.length - 1], s0 = n[0];
      const tag = (b.className || b.tagName) + '｜' + p.slice(-10) + '／' + n.slice(0, 10);
      if (DIG.test(e) && CJK.test(s0)) out.push('数字与单位分开：' + tag);
      if (formula && CJK.test(e) && CJK.test(s0)) out.push('公式里的中文词断开：' + tag);
      if (/^[…⋯]/.test(n) || /^[…⋯]+$/.test(n)) out.push('省略号在行首：' + tag);
      if (/Li$/.test(p) && /^Ming/.test(n)) out.push('Li Ming 拆开：' + tag);
    }
  }
  return out;
}"""


def render(pg, body, title, out, tmp, footer=True):
    f = Path(tmp) / 'x.html'
    f.write_text(page_html(body, title, footer), 'utf-8')
    pg.goto(f.as_uri())
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(300)
    bad = pg.evaluate("""() => { const out = []; const W = document.body.getBoundingClientRect().right;
      for (const el of document.querySelectorAll('section *')) { const r = el.getBoundingClientRect();
        if (r.width && (r.right > W + 1 || el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow === 'hidden')) out.push((el.className || el.tagName) + '：' + (el.textContent || '').slice(0, 30)); }
      return out.slice(0, 20); }""")
    if bad:
        raise SystemExit(f'{out.name}：内容横向溢出：\n  ' + '\n  '.join(bad))
    wrap = pg.evaluate(WRAP_JS)
    if wrap:
        msg = f'{out.name}（{title}）断行问题 {len(wrap)} 处：\n  ' + '\n  '.join(wrap)
        if os.environ.get('JY_REPORT'):
            print(msg)
        else:
            raise SystemExit(msg)
    pg.pdf(path=str(out), print_background=True, prefer_css_page_size=True)


def page_of(pdf, marks):
    """每个标记（章首的大标题文字）第一次出现在第几页。"""
    n = int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True).stdout).group(1))
    got = {}
    for i in range(1, n + 1):
        t = subprocess.run(['pdftotext', '-f', str(i), '-l', str(i), str(pdf), '-'], capture_output=True, text=True).stdout
        t = re.sub(r'\s+', '', t)
        for m, key in marks.items():
            if m not in got and re.sub(r'\s+', '', key) in t:
                got[m] = i
    return got, n


def fill(pdf, page):
    """这一页正文（去掉页脚）从顶到最后一行墨迹占了多少。"""
    import numpy as np
    from PIL import Image
    with tempfile.TemporaryDirectory() as t:
        subprocess.run(['pdftoppm', '-r', '20', '-gray', '-png', '-singlefile', '-f', str(page), '-l', str(page), str(pdf), f'{t}/p'], check=True)
        a = np.asarray(Image.open(f'{t}/p.png')).astype(float)
    body = a[: int(a.shape[0] * 0.93)]
    ink = np.where((body < 200).sum(1) > 1)[0]
    return ink.max() / body.shape[0] if len(ink) else 0


def tail_fill(pdf, keys):
    """每一节（按标记找起始页）最后一页的占用比例：{标记: (起始页, 最后一页, 占用)}。"""
    first, n = page_of(pdf, keys)
    order = sorted(first.items(), key=lambda kv: kv[1])
    out = {}
    for i, (m, p) in enumerate(order):
        last = order[i + 1][1] - 1 if i + 1 < len(order) else n
        out[m] = (p, last, fill(pdf, last))
    return out


def merge(parts, out):
    subprocess.run(['pdfunite', *map(str, parts), str(out)], check=True)


def font_check(pdf):
    t = subprocess.run(['pdffonts', str(pdf)], capture_output=True, text=True).stdout
    bad = [l for l in t.splitlines()[2:] if re.search(r'WenQuanYi|DejaVu|Liberation|Droid|Fallback', l)]
    if bad:
        raise SystemExit(f'{pdf.name} 用了系统字体（字体回退）：\n' + '\n'.join(bad))


def build(ids):
    from playwright.sync_api import sync_playwright
    errs = [x for pid in ids for x in check(pid)]
    if errs:
        sys.exit('检查不通过，不生成：\n  ' + '\n  '.join(errs))
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page()
        tmp = Path(tmp)
        # 讲义：封面（不编页码）+ 目录 + 总论 + 各篇 + 句式总表；目录页码两遍排版（第一遍量出各章在第几页）
        render(pg, cover('考研英语写作<br>满分范文精讲'.replace('<br>', ' '), '2021—2026 · 英语一 / 英语二<br>小作文 Part A + 大作文 Part B · 共 ' + str(len(ids)) + ' 篇',
                         '审题 → 思路 → 范文 → 一步一步写 → 高分句式 → 亮点词汇<br>每个句式都有公式、讲解和两个仿写例句'), '封面', tmp / 'cover.pdf', tmp, footer=False)
        entries = ([('GEN', '写作总攻略', '评分标准 · 结构 · 模板 · 避坑')] if (DATA / '总论.json').exists() else []) + \
                  [(f'CH{i:02d}', f'{P[pid]["pdf"]} {P[pid]["passage"]}', zh(pid)[0].get('T', '')) for i, pid in enumerate(ids, 1)] + [('IDX', '高分句式总表', '')]
        keys = {'GEN': 'WRITING GUIDE', 'IDX': 'INDEX · ALL PATTERNS'} if (DATA / '总论.json').exists() else {'IDX': 'INDEX · ALL PATTERNS'}
        keys.update({f'CH{i:02d}': f'MODEL ESSAY {i:02d}' for i in range(1, len(ids) + 1)})
        pages = {}
        for _ in range(2):
            body = toc_html(entries, pages) + general_chapter() + ''.join(essay_chapter(i, pid, tmp) for i, pid in enumerate(ids, 1)) + index_chapter(ids)
            render(pg, body, '考研英语写作满分范文精讲', tmp / 'body.pdf', tmp)
            pages, n = page_of(tmp / 'body.pdf', keys)
        miss = [k for k in keys if k not in pages]
        if miss:
            sys.exit(f'目录：这些章节在 PDF 里找不到：{miss}')
        D.mkdir(exist_ok=True)
        merge([tmp / 'cover.pdf', tmp / 'body.pdf'], OUT_HANDOUT)
        font_check(OUT_HANDOUT)
        print(f'讲义 {n + 1} 页 → {OUT_HANDOUT}')
        # 默写卡与答案
        how = ("<div class='how'><b>怎么用这份默写卡</b><br>① 先读右边的黄色提醒：这一句练的是什么句式、为什么值得背；② A 部分只填横线处的关键表达（编号对应答案里的粉色部分）；"
               "③ B 部分看中文、默写整句英文；④ 写完对照《答案》，错的地方回到讲义里对应的“高分句式”再看一遍。</div>")
        for answers, out, title in ((False, OUT_CARDS, '考研作文默写卡'), (True, OUT_ANS, '考研作文默写卡（答案）')):
            render(pg, cover(title, '2021—2026 · 英语一 / 英语二 · 共 ' + str(len(ids)) + ' 篇范文',
                             '默的不只是单词，是能直接用进作文的句子和句式' if not answers else '粉色 = 填空答案；整句 = 整句默写答案'), '封面', tmp / 'c.pdf', tmp, footer=False)
            body = lambda fit: ''.join(card_section(pid, answers, how if not answers and i == 0 else '', fit.get(pid, 0)) for i, pid in enumerate(ids))
            render(pg, body({}), title, tmp / 'b.pdf', tmp)
            if not answers:
                # 每篇从新的一页开始；最后一页只剩一两张卡（占用不到 35%）的篇目，第二遍收紧间距，挤回前一页
                keys = {pid: 'DICTATION·' + head_info(pid)[2] for pid in ids}
                t1 = tail_fill(tmp / 'b.pdf', keys)
                if len(t1) != len(ids):
                    sys.exit(f'{title}：有篇目在 PDF 里找不到起始页')
                short = lambda t: {pid for pid, (a, b, u) in t.items() if b > a and u < 0.35}
                fit, t = {}, t1
                for lv in (1, 2):   # 收紧两级：还挤不回去的再收一级
                    todo = short(t)
                    if not todo:
                        break
                    fit.update({pid: lv for pid in todo})
                    render(pg, body(fit), title, tmp / 'b.pdf', tmp)
                    t = tail_fill(tmp / 'b.pdf', keys)
                won = sorted(pid for pid in fit if t[pid][1] - t[pid][0] < t1[pid][1] - t1[pid][0])
                print(f'  收紧 {len(fit)} 篇（二级 {sum(v > 1 for v in fit.values())} 篇），少一页的 {len(won)} 篇；最后一页仍只剩一两张卡：{sorted(short(t)) or "无"}')
            merge([tmp / 'c.pdf', tmp / 'b.pdf'], out)
            font_check(out)
            print(f'{title} → {out}')
        br.close()


def main():
    cmd, ids = sys.argv[1], sys.argv[2:]
    if cmd == 'check':
        ids = ids or sorted(f.stem for f in DATA.glob('w*.json'))
        errs = [x for pid in ids for x in check(pid)]
        print('\n'.join(errs) if errs else f'{len(ids)} 篇检查全部通过')
        sys.exit(1 if errs else 0)
    if cmd == 'build':
        build(ids or sorted(P))


if __name__ == '__main__':
    main()
