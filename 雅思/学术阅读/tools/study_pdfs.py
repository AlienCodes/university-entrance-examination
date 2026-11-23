"""Print the two student handouts from a checked lesson and its approved teaching notes."""
import argparse
import hashlib
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT = Path(__file__).resolve().parents[1]
KINDS = {
    'Summary Completion':'摘要填空','True / False / Not Given':'判断事实','Note Completion':'笔记填空',
    'Matching Information':'段落信息匹配','One Choice':'单项选择','Yes / No / Not Given':'判断作者观点',
    'Matching Features':'人物或特征匹配','Matching Headings':'段落标题匹配','Sentence Completion':'句子填空',
    'Table Completion':'表格填空','Two Choices':'双项选择','Matching Sentence Endings':'句子结尾匹配',
    'Diagram Labeling':'图示标注','Flow Chart Completion':'流程图填空','Short Answers':'简答'
}
CSS = """
@page { size: A4; margin: 16mm 17mm 17mm; }
* { box-sizing: border-box; }
html { color: #172c34; font: 10.7pt/1.60 'Noto Sans CJK SC','Noto Sans',sans-serif; }
body { margin: 0; }
h1,h2,h3,p { margin: 0; }
.cover { border-bottom: 2px solid #183d43; padding-bottom: 11px; margin-bottom: 18px; }
.scope { color:#426469; font-size: 9.4pt; font-weight:650; letter-spacing:.045em; }
h1 { font-weight:750; font-size:24pt; line-height:1.28; margin:5px 0 7px; }
.sub { font-size:11.4pt; color:#3b555a; }
.summary { color:#263d40; font-size:9.8pt; margin-top:7px; }
.card { break-inside: avoid; margin: 0 0 17px; padding-top: 11px; border-top: 1px solid #a4b3b5; }
.card.first { border-top: 0; padding-top: 0; }
.qh { display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; }
.num { font-size:14pt; font-weight:750; color:#103c43; }
.kind { font-size:9.8pt; color:#475b60; }
.answer { margin-left:auto; color:#075d59; font-weight:730; font-size:12pt; }
.prompt { margin:5px 0 4px; color:#20353d; font: 11.3pt/1.38 'Liberation Serif','Noto Serif',serif; }
.options { margin:4px 0 7px; padding:0; list-style:none; font:10.4pt/1.38 'Liberation Serif',serif; }
.options li { padding-left:22px; position:relative; }
.options b { position:absolute; left:0; color:#31555c; }
.evidence { margin:7px 0; padding:6px 10px; border-left:2.2px solid #568781; background:#f1f6f5; }
.place { font-size:9pt; font-weight:660; color:#225751; }
.en { font:11.4pt/1.40 'Liberation Serif','Noto Serif',serif; color:#182c34; }
.zh { margin:2px 0 4px; color:#435458; font-size:9.7pt; }
.logic { color:#192e33; }
.label { color:#245852; font-weight:700; }
.meta { color:#4b6262; margin-top:4px; font-size:9pt; }
.subject { font-weight:720; color:#234a4a; }
.grammar { break-before: page; }
.grammar.first { break-before:auto; }
.grammar h2 { font-size:18pt; color:#183d43; margin:8px 0 10px; line-height:1.35; }
.reading { background:#f1f6f5; border-left:3px solid #53867f; padding:10px 13px; margin: 7px 0 13px; }
.reading .en { font-size:13pt; line-height:1.52; }
.reading .zh { font-size:10.6pt; margin-top:5px; }
h3 { font-size:11pt; color:#235651; margin:12px 0 3px; }
.pattern { font:12pt/1.5 'Liberation Serif','Noto Serif',serif; color:#123e46; }
footer { color:#5a6b6d; }
"""
def e(s):
    return html.escape(str(s),quote=True)
def rng(q):
    a=q['numbers']
    return str(a[0]) if len(a)==1 else f'{a[0]}–{a[-1]}'
def source_ref(s,index):
    return f"{s['tag']} 段 · 精读第 {index} 句" if s['tag'] else f'精读第 {index} 句'
def doc(title,body):
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{e(title)}</title><style>{CSS}</style></head><body>{body}</body></html>'
def heading(lesson,title,desc):
    coordinate,name=lesson['display_title'].split(' ',1)
    book,test,part=coordinate.split('-')
    return f'<header class="cover"><p class="scope">剑桥雅思 {book}　·　Academic Reading　·　Test {test}　·　Passage {part}</p><h1>{e(title)}</h1><p class="sub">{e(name)}</p><p class="summary">{e(desc)}</p></header>'
def reading_doc(d,y):
    blocks=[heading(d,'逐题解析','题号沿用原书。原文定位使用的句子编号与同篇精读视频、逐屏讲义左下角一致。')]
    used=set()
    for idx,q in enumerate(d['questions']):
        qn=q['numbers'][0]
        assert not used.intersection(q['numbers'])
        used.update(q['numbers'])
        detail=y['questions'][str(qn)]
        evidence=detail['evidence']
        if not evidence:raise ValueError((d['lesson'],qn,'no evidence'))
        refs=[]
        for i in evidence:
            s=d['sentences'][i-1]
            refs.append(f'<div class="place">{e(source_ref(s,i))}</div><p class="en">{e(s["en"])}</p><p class="zh">{e(s["zh"])}</p>')
        meta=[]
        if q.get('word_limit'):meta.append(e(q['word_limit']))
        if q.get('marking'):meta.append(e(q['marking']))
        if q.get('accepted_variants'):meta.append('另可写 '+e(q['accepted_variants']))
        if len(q['numbers'])==2:meta.append('两个答案顺序不限，每个答案占一格')
        target=q.get('chosen_text','')
        if target:
            meta.append('对应选项　'+e(target))
        parts=[f'<section class="card{" first" if idx==0 else ""}"><div class="qh"><span class="num">第 {rng(q)} 题</span><span class="kind">{e(KINDS[q["kind"]])}</span><span class="answer">答案　{e(q["answer"])}</span></div>',
               f'<p class="prompt" lang="en">{e(q["question"])}</p>']
        if q.get('options'):
            choices=''.join(f'<li><b>{e(k)}.</b>{e(v)}</li>' for k,v in q['options'].items())
            parts.append(f'<ul class="options" lang="en">{choices}</ul>')
        if meta:parts.append('<p class="meta">'+'　·　'.join(meta)+'</p>')
        parts.extend(['<div class="evidence">',''.join(refs),'</div>',f'<p class="logic"><span class="label">推理　</span>{e(detail["logic"])}</p></section>'])
        blocks.extend(parts)
    return doc(d['display_title']+' · 逐题解析',''.join(blocks))
def grammar_doc(d,y):
    blocks=[]
    for idx,r in enumerate(y['grammar']):
        no=r['sentence'];s=d['sentences'][no-1]
        blocks.append(f'<section class="grammar{" first" if idx==0 else ""}">')
        if idx==0:blocks.append(heading(d,'长难句与写作句式','先从原句里找主干，再读修饰成分。每页附写作场景、英文例句与中译。例句中的人物、数据和情境用于示范。'))
        else:blocks.append(f'<p class="scope">{e(d["display_title"])}　·　长难句与写作句式</p>')
        blocks.append(f'<h2>{e(r["heading"])}</h2><p class="place">{e(source_ref(s,no))}</p><div class="reading"><p class="en">{e(s["en"])}</p><p class="zh">{e(s["zh"])}</p></div>')
        if r.get('subject') and r.get('verb'):
            blocks.append(f'<p class="meta">主语核心　{e(r["subject"])}　　 谓语核心　{e(r["verb"])}</p>')
        for name,k in [('句子怎样读','analysis'),('可复用的结构','pattern'),('写作场景','task')]:
            blocks.append(f'<h3>{name}</h3><p class="{"pattern" if k=="pattern" else "logic"}">{e(r[k])}</p>')
        blocks.append(f'<div class="reading"><p class="en">{e(r["example"])}</p><p class="zh">{e(r["example_zh"])}</p></div><h3>运用提示</h3><p>{e(r["usage"])}</p></section>')
    return doc(d['display_title']+' · 长难句与写作句式',''.join(blocks))
def render(browser,pid,editor,out):
    src=PROJECT/'配套讲义/题目与证据'/(pid+'.json')
    d=json.loads(src.read_text()); y=json.loads((editor/(pid+'.json')).read_text())
    assert y['lesson']==pid and y['input_sha256']==hashlib.sha256(src.read_bytes()).hexdigest()
    assert {int(k) for k in y['questions']}=={q['numbers'][0] for q in d['questions']} and len(y['grammar'])==3
    folder=out/d['display_title']; folder.mkdir(parents=True,exist_ok=True)
    page=browser.new_page()
    try:
        for name,body in [('逐题解析',reading_doc(d,y)),('长难句与写作句式',grammar_doc(d,y))]:
            page.set_content(body,wait_until='load')
            page.evaluate('document.fonts.ready')
            footer=f'<div style="font:8px sans-serif;width:100%;padding:0 64px;color:#58696b;display:flex;justify-content:space-between"><span>{e(d["display_title"])} · {name}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
            target=folder/(name+'.pdf')
            page.pdf(path=str(target),format='A4',prefer_css_page_size=True,print_background=True,display_header_footer=True,header_template='<span></span>',footer_template=footer)
    finally:page.close()
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('editor',type=Path);a.add_argument('out',type=Path);a.add_argument('ids',nargs='+')
    args=a.parse_args()
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        for pid in args.ids:render(b,pid,args.editor,args.out)
        b.close()
