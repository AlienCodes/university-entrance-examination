"""按试卷制作50份文件夹；新增汉译英听写卡、词汇讲解及逐题详解。
python 分套资料.py --sample | --build [--cases ...] [--without-details]
"""
import argparse
import collections
import hashlib
import html
import json
import re
import shutil
import tempfile
from pathlib import Path

import fitz
from pypdf import PdfReader, PdfWriter
from playwright.sync_api import sync_playwright
import 详解数据 as X

M = X.M
D = M.D
OUT = D / '分套资料'
AUDIT = D / '核验/分套'
SOURCE = json.loads((D / '成品/文件清单与核验.json').read_text('utf-8'))
NAMES = {
    'practice': '听力练习册', 'reading': '原文双语精读', 'vocab': '词汇与短语讲解',
    'cards': '汉译英听写卡', 'cardanswers': '汉译英听写卡（答案）',
    'dictation': '听写训练本', 'dictanswers': '听写训练本（答案）',
    'details': '听力逐题详解', 'plan': '本套复习记录表',
}
CN_POS = {'n':'名词','v':'动词','adj':'形容词','adv':'副词','prep':'介词','conj':'连词','pron':'代词','num':'数词','det':'限定词','int':'感叹词','phr':'短语','aux':'助动词','abbr':'缩略语'}


def normalized_meaning(value):
    m = re.match(r'^([a-z]+)\.\s*(.+)$', value)
    return CN_POS.get(m[1],m[1])+'：'+m[2] if m else value


def words(case):
    terms = {}
    for sentence in M.content_sents(case):
        for w in sentence['w']:
            h = w['h']
            if h.lower() in M.STOP or not re.search('[a-zA-Z]',h) or h[0].isupper():
                continue
            key = (w['t']=='phr',h.lower())
            term = terms.setdefault(key,{'head':h,'phrase':w['t']=='phr','meanings':[],'examples':[]})
            if w['m'] not in term['meanings']:
                term['meanings'].append(w['m'])
                term['examples'].append({'sid':sentence['display_sentence'],'en':sentence['en'],'zh':sentence['zh'],'word':w})
    return list(terms.values())


def cards(case):
    """相同中文、同类词条合并为一行；答案并列，避免汉译英同义答案被误判。"""
    result = {}
    for term in words(case):
        meaning = normalized_meaning(term['meanings'][0])
        key = (term['phrase'],meaning)
        item = result.setdefault(key,{'phrase':term['phrase'],'zh':meaning,'answers':[]})
        if term['head'] not in item['answers']:
            item['answers'].append(term['head'])
    return list(result.values())


CSS = r'''
.case-tag{font-size:11pt;font-weight:700;color:#775293;margin-bottom:4mm;letter-spacing:.04em}
.subheading{font-size:13pt;color:#68458e;border-bottom:1px solid #dcd0e9;padding-bottom:1.4mm;margin:5mm 0 3mm;break-after:avoid}
.cv{padding:3mm 0;border-bottom:1px solid #e7deed;break-inside:avoid}
.cv-head{font-family:'EB Garamond','Noto Sans SC';font-size:14pt;color:#67458c;font-weight:600}
.cv-meaning{font-size:10.2pt;line-height:1.7;margin:1.1mm 0;color:#554364}
.cv-form{font-size:8.6pt;color:#8e7a9e;margin:.7mm 0 1.4mm}
.cv-example{background:#faf8fc;border-radius:1.5mm;padding:2mm 3mm;margin:1.5mm 0}
.cv-source{font-size:8pt;color:#9584a4;margin-top:.8mm}
.cardtable{width:100%;border-collapse:collapse;table-layout:fixed;font-size:10.5pt}
.cardtable thead{display:table-header-group}.cardtable th{background:#f0e9f7;color:#654785;text-align:left;padding:2.8mm 3mm;font-weight:500;font-size:10pt}
.cardtable th:first-child{width:8mm}.cardtable th:nth-child(2){width:86mm}
.cardtable tr{break-inside:avoid}.cardtable td{padding:2.3mm 3mm;border-bottom:1px solid #e8dfed;vertical-align:middle;line-height:1.6}
.cardtable td:first-child{padding-left:1mm;padding-right:0;font-family:'Nunito';font-size:7.5pt;color:#aa94b7}
.cardtable .blank{display:block;height:6mm;border-bottom:.6px solid #ac98ba;margin:.6mm 0 1mm}
.cardtable .answer{font-family:'EB Garamond','Noto Sans SC';font-size:12pt;color:#5c427e;line-height:1.6}
.card-section{break-before:page}.card-section.first{break-before:auto}
.detail{break-before:page;padding-bottom:3mm}.detail.first{break-before:auto}
.detail-title{display:flex;justify-content:space-between;gap:4mm;align-items:baseline;border-bottom:1px solid #d8cae5;padding:1.5mm 0 2mm;margin-bottom:3mm;break-after:avoid}
.detail-title h2{font-size:16pt;color:#69458d}.answer-pill{border:1px solid #c2d7c2;background:#eef6ef;padding:.7mm 3mm;border-radius:2mm;color:#416b45;font-size:10.5pt;white-space:nowrap}
.detail-stem{font-family:'EB Garamond','Noto Sans SC';font-size:12.2pt;line-height:1.5}.detail-stem-zh{font-size:10.1pt;color:#71617f;margin:.9mm 0 2mm}
.detail-opts{display:grid;grid-template-columns:1fr;gap:.8mm;margin:1mm 0 3mm;break-inside:avoid}
.detail-opt{display:grid;grid-template-columns:6mm 1fr;gap:0 1.5mm;padding:1mm 2mm;border-radius:1.2mm}
.detail-opt>b{font-family:'Nunito';font-size:10pt;color:#8e759f}.detail-opt .en{font-size:11.4pt}.detail-opt .zh{font-size:9.5pt;color:#796b84;line-height:1.55}.detail-opt.correct{background:#f1f7f0}
.d-label{font-size:10.2pt;color:#704d8e;font-weight:700;margin:2.6mm 0 1.4mm;break-after:avoid}
.evidence{padding:2mm 3mm;background:#faf8fd;border-left:1mm solid #cab7df;margin:1.4mm 0;break-inside:avoid}
.evidence .eng{font-size:11.5pt}.evidence .cn{font-size:9.6pt}.evidence .sid{font-size:8pt;color:#9883aa;margin-bottom:.7mm}
.reason{font-size:10.2pt;line-height:1.85;margin:0 0 2mm;break-inside:avoid}
.wrong{font-size:9.6pt;line-height:1.75;margin:1mm 0;break-inside:avoid}.wrong b{font-family:'Nunito';color:#876294;margin-right:1.5mm}
.source-note{font-size:9pt;line-height:1.75;padding:2mm 3mm;background:#fff8eb;border:1px solid #ead8b4;border-radius:1.5mm;break-inside:avoid;margin:2mm 0}
.study-grid{display:grid;grid-template-columns:1fr 1fr;gap:3mm;margin:4mm 0}.study-cell{border:1px solid #dbcee7;border-radius:2mm;padding:3mm;font-size:10pt;line-height:2.2}
.paperline{height:9mm;border-bottom:1px solid #ded3e9}.tick{display:inline-block;width:3.5mm;height:3.5mm;border:1px solid #9f84b7;margin-right:2mm;vertical-align:-.5mm}
'''


def header(case,kind,mark='CHAPTER'):
    return M.heading(case,mark)+f'<div class="case-tag">{M.esc(NAMES[kind])}</div>'


def vocab_body(case):
    out=[header(case,'vocab'),'<div class="intro">按本套实际出现的词汇和短语整理。每条给出语境释义、原文例句、中文及句号；原文词形与词条不同处一并列出。与本套汉译英卡配合使用。</div>']
    terms=words(case)
    for phrase in [False,True]:
        out.append(f'<h2 class="subheading">{"短语与搭配" if phrase else "本套词汇"}</h2>')
        for term in [t for t in terms if t['phrase']==phrase]:
            out.append(f'<div class="cv"><div class="cv-head">{M.esc(term["head"])}</div><div class="cv-meaning">'+'；'.join(M.esc(normalized_meaning(m)) for m in term['meanings'])+'</div>')
            for ex in term['examples']:
                original=' … '.join(ex['en'][a:b] for a,b in ex['word']['sp'])
                if M.normal(original)!=M.normal(term['head']):
                    out.append(f'<div class="cv-form">原文形式：{M.esc(original)}</div>')
                marked=M.marked({'en':ex['en'],'w':[ex['word']]})
                out.append(f'<div class="cv-example"><div class="eng">{marked}</div><div class="cn">{M.esc(ex["zh"])}</div><div class="cv-source">本套原文精读第{ex["sid"]}句</div></div>')
            out.append('</div>')
    return ''.join(out)+'</section>'


def card_body(case,answers=False):
    kind='cardanswers' if answers else 'cards'
    out=[header(case,kind),'<div class="intro">左侧看中文，右侧默写英文，单列竖排，便于逐项遮挡与书写。先复习本套词汇讲解，再合上资料自测；同一中文有多个本套表达时，答案页并列给出，可逐步补全。</div>']
    all_cards=cards(case);index=0
    for phrase in [False,True]:
        items=[c for c in all_cards if c['phrase']==phrase]
        if not items:continue
        out.append(f'<div class="card-section {"first" if not phrase else ""}"><h2 class="subheading">{"短语默写" if phrase else "单词默写"}</h2><table class="cardtable"><thead><tr><th></th><th>中文释义</th><th>{"英文答案" if answers else "英文默写"}</th></tr></thead><tbody>')
        for item in items:
            index+=1
            right='<span class="answer">'+' / '.join(M.esc(a) for a in item['answers'])+'</span>' if answers else '<span class="blank"></span>'*(2 if phrase else 1)
            out.append(f'<tr><td>{index}</td><td>{M.esc(item["zh"])}</td><td>{right}</td></tr>')
        out.append('</tbody></table></div>')
    return ''.join(out)+'</section>'


def details_body(case):
    detail=X.check_case(case)
    by_sid={s['display_sentence']:s for g in case['groups'] for s in g['sentences']}
    out=[header(case,'details'),'<div class="intro">每题先定位原文，再理解句意、联系题干并排除其余选项。答案与本套当前题目、选项对应；原始资料有措辞或版本问题时，题内另加说明。建议先独立完成练习，再打开本册。</div>']
    for i,q in enumerate(case['questions']):
        r=detail['题'][str(q['n'])]
        ambiguous=r.get('题源多解',False)
        label='题源多解 · 不计分' if ambiguous else '参考答案　'+r['答案']
        out.append(f'<article class="detail {"first" if i==0 else ""}"><div class="detail-title"><h2>第{q["n"]}题</h2><span class="answer-pill">{label}</span></div>')
        out.append(f'<div class="detail-stem">{M.esc(q["stem"] or "（本题题干由录音口述）")}</div><div class="detail-stem-zh">{M.esc(r["题干译"])}</div><div class="detail-opts">')
        for letter,text in q['options'].items():
            out.append(f'<div class="detail-opt {"correct" if letter==r["答案"] and not ambiguous else ""}"><b>{letter}</b><div><div class="en">{M.esc(text)}</div><div class="zh">{M.esc(r["选项译"][letter])}</div></div></div>')
        out.append('</div><div class="d-label">原文依据与中文</div>')
        for sid in r['依据']:
            s=by_sid[sid]
            out.append(f'<div class="evidence"><div class="sid">本套精读第{sid}句</div><div class="eng">{M.esc(s["en"])}</div><div class="cn">{M.esc(s["zh"])}</div></div>')
        out.append(f'<div class="d-label">这道题怎么做</div><p class="reason">{M.esc(r["讲解"])}</p><div class="d-label">其余选项核对</div>')
        for letter,why in r['错项'].items():out.append(f'<p class="wrong"><b>{letter}</b>{M.esc(why)}</p>')
        if r.get('题源提示'):out.append(f'<div class="source-note">题源提示：{M.esc(r["题源提示"])}</div>')
        out.append('</article>')
    return ''.join(out)+'</section>'


def practice_body(case):
    body=M.body_case('practice',case,'CHAPTER')
    body=body.replace(M.heading(case,'CHAPTER'),header(case,'practice'))
    body=body.replace('再查阅单独的参考答案本','再查阅本套“听力逐题详解”')
    path=X.OUT/(case['id']+'.json')
    if path.exists():
        details=json.loads(path.read_text('utf-8'))
        excluded=[n for n,r in details['题'].items() if r.get('题源多解')]
        if excluded:
            numbers='、'.join(excluded)
            note=f'<div class="source-note">本套第{numbers}题的现存题源无法形成唯一单选答案，只作原文理解练习，不计单选分。具体依据见逐题详解。</div>'
            body=body.replace('<div class="answerline">',note+'<div class="answerline">')
            body=body.replace('正确题数：____ / 20',f'有效题正确数：____ / {20-len(excluded)}')
    return body


def plan_body(case):
    out=[header(case,'plan'),'<div class="intro">本表只记录这一套。按自己的节奏完成，不设固定天数；可重复打印。汉译英卡检查词汇回忆，原文听写本检查句子听辨，两项分别练习。</div>']
    out.append('<div class="study-grid">')
    for label in ['独立完成听力练习','核对并阅读逐题详解','学习词汇与短语讲解','完成汉译英听写卡','完成原文听写训练','合上原文，复听错题']:
        out.append(f'<div class="study-cell"><span class="tick"></span>{M.esc(label)}<br>完成日期：________________</div>')
    out.append('</div><h2 class="subheading">本套错题与复听记录</h2>')
    for _ in range(3):
        out.append('<div class="errorbox">题号：________　我的选项：________　核对后的答案：________<div class="paperline">错因与漏听线索：</div><div class="paperline">这次学会的词汇或表达：</div><div class="paperline">复听日期与结果：</div></div>')
    return ''.join(out)+'</section>'


def extract(case,key,target):
    row=SOURCE['files'][key];src=D/'成品'/row['file']
    assert M.sha(src)==row['sha256']
    i=next(i for i,c in enumerate(SOURCE['cases']) if c['id']==case['id'])
    starts=list(row['chapters'].values());a=starts[i]-1;b=starts[i+1]-2 if i+1<len(starts) else row['pages']-1
    out=fitz.open()
    with fitz.open(src) as d:out.insert_pdf(d,from_page=a,to_page=b,links=False)
    for j,page in enumerate(out,1):
        page.add_redact_annot(fitz.Rect(525,803,585,835),fill=(1,1,1))
        page.apply_redactions(images=0,graphics=0)
        page.insert_textbox(fitz.Rect(525,810,555,830),str(j),fontsize=8,fontname='helv',align=2,color=(.51,.45,.58))
    out.set_metadata({'title':case['title']+' · '+NAMES[key],'author':'朋克英语'})
    out.set_toc([[1,case['title'],1]])
    out.save(target,garbage=4,deflate=True)
    return {'file':target.name,'pages':len(out),'bytes':target.stat().st_size,'sha256':M.sha(target),'source_pdf':src.name,'source_pages':[a+1,b+1]}


def render(pg,base,tmp,case,key,body,target):
    title=case['title']+' · '+NAMES[key]
    doc=M.J.page_html(body,title).replace('</style>',M.CSS+CSS+'</style>').replace(M.ROOT.as_uri()+'/',base)
    source=tmp/f'{case["id"]}-{key}.html';source.write_text(doc,'utf-8')
    pg.goto(base+source.relative_to(M.ROOT).as_posix(),wait_until='load');pg.evaluate('document.fonts.ready')
    # 页边框计数器的700字重在正文未使用时也必须预载，避免打印页脚回退系统字体。
    pg.evaluate('async () => {await document.fonts.load(\'700 8pt "Nunito"\', "0123456789");await document.fonts.ready;}')
    bad=pg.evaluate('''() => {
      const out=[];const b=document.body.getBoundingClientRect();for(const e of document.querySelectorAll('section *')){
        const r=e.getBoundingClientRect();if(r.width&&(r.left<b.left-1||r.right>b.right+1||e.scrollWidth>e.clientWidth+2&&getComputedStyle(e).overflow==='hidden'))out.push(e.className+': '+e.textContent.slice(0,60));
      }return out.slice(0,20);
    }''')
    assert not bad,(case['id'],key,bad)
    wrap=pg.evaluate(M.J.WRAP_JS);assert not wrap,(case['id'],key,wrap[:12])
    pg.pdf(path=str(target),print_background=True,prefer_css_page_size=True)
    writer=PdfWriter(clone_from=target)
    # 分套文档的标题就在首页；Chromium未导出命名目标时也必须保留可用书签。
    writer.add_outline_item(title,0)
    writer.add_metadata({'/Title':title,'/Author':'朋克英语'});writer.write(target)
    M.J.font_check(target)
    with fitz.open(target) as d:
        text=M.normal(''.join(p.get_text() for p in d))
        for page in d:
            assert '\x00' not in page.get_text() and '\ufffd' not in page.get_text()
        assert M.normal(case['title']) in text
        if key=='vocab':
            for t in words(case):
                assert M.normal(t['head']) in text
                for ex in t['examples']:
                    assert M.normal(ex['en']) in text and M.normal(ex['zh']) in text,(case['id'],t['head'],'词汇例句缺失')
        elif key in ['cards','cardanswers']:
            for card in cards(case):
                assert M.normal(card['zh']) in text
                if key=='cardanswers':
                    assert all(M.normal(a) in text for a in card['answers'])
            if key=='cards':
                # 正文只应有中文释义、编号和空白；绝不将英文词条装入隐藏列。
                actual=M.normal(''.join(p.get_text() for p in d)).replace(M.normal('GAOKAO LISTENING'),'')
                for term in words(case):
                    if len(term['head'])>=5 and re.fullmatch('[a-zA-Z ]+',term['head']):
                        assert M.normal(term['head']) not in actual,(case['id'],term['head'],'汉译英卡泄露英文答案')
        elif key=='details':
            detail=X.check_case(case)
            for q in case['questions']:
                r=detail['题'][str(q['n'])]
                assert M.normal(r['讲解']) in text and M.normal(r['题干译']) in text
                for why in r['错项'].values():assert M.normal(why) in text
        elif key=='practice':
            for q in case['questions']:
                for option in q['options'].values():assert M.normal(option) in text
            assert '单独的参考答案本' not in ''.join(p.get_text() for p in d)
        count=len(d)
    return {'file':target.name,'pages':count,'bytes':target.stat().st_size,'sha256':M.sha(target)}


def attach_originals(case,folder):
    papers=json.loads((M.G/'套.json').read_text('utf-8'))
    raw=json.loads((M.G/'原始材料/清单.json').read_text('utf-8'))
    records=json.loads((D/'原卷解析来源核验.json').read_text('utf-8'))['files']
    by_source={r['source_file']:r for r in records}
    selected=[]
    for stale in list(folder.glob('*.doc'))+list(folder.glob('*.docx')):
        stale.unlink()
    if case['id']=='2020-xgk1':
        # 普通山东整卷以阅读开篇，不含本套听力。独立原始DOC合收两次，明确标识使用第一次。
        r=next(r for r in records if '（山东）（听力试题及答案）' in r['file'])
        src=D/'真题原卷与解析'/r['file']
        dst=folder/('原始听力试题与答案（合订，本套用第一次）'+src.suffix)
        assert M.sha(src)==r['sha256'];shutil.copyfile(src,dst)
        return [{'file':dst.name,'sha256':r['sha256'],'source':r['source_file'],'note':'原始合订文件含两次听力，本套仅对应2020年1月山东第一次；第二次不是本套题。'}]
    for kind in ['空白卷','解析','原文']:
        for source in raw.get(papers[case['id']]['题目'],{}).get(kind,[]):
            r=by_source[source['文件']];src=D/'真题原卷与解析'/r['file']
            label={'空白卷':'原始真题整卷','解析':'原始整卷答案与解析','原文':'配套听力原文'}[kind]
            dst=folder/(label+src.suffix)
            assert M.sha(src)==r['sha256'];shutil.copyfile(src,dst)
            selected.append({'file':dst.name,'sha256':r['sha256'],'source':r['source_file']})
    return selected


def build(sample=False,only=(),without_details=False,refresh_details=False):
    cases=X.cases();wanted=set(only)
    selected=[c for c in cases if not wanted or c['id'] in wanted]
    if sample and not wanted:selected=[c for c in cases if c['id'] in ['2026-xkb1','2023-shq']]
    out=D/'分套样张' if sample else OUT;out.mkdir(parents=True,exist_ok=True);AUDIT.mkdir(parents=True,exist_ok=True)
    with M.server() as base,sync_playwright() as pw,tempfile.TemporaryDirectory(dir=D,prefix='_build_') as t:
        tmp=Path(t);browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);pg=browser.new_page()
        for case in selected:
            folder=out/case['title'];folder.mkdir(exist_ok=True);files={}
            if refresh_details:
                assert not sample and not without_details
                files=json.loads((AUDIT/(case['id']+'.json')).read_text('utf-8'))['files']
                for row in files.values():assert M.sha(folder/row['file'])==row['sha256']
                bodies={'practice':practice_body(case)}
            else:
                for key in ['reading','dictation','dictanswers']:
                    path=folder/(NAMES[key]+'.pdf');files[key]=extract(case,key,path)
                bodies={'practice':practice_body(case),'vocab':vocab_body(case),'cards':card_body(case),'cardanswers':card_body(case,True),'plan':plan_body(case)}
            if not without_details:bodies['details']=details_body(case)
            for key,body in bodies.items():
                path=folder/(NAMES[key]+'.pdf');files[key]=render(pg,base,tmp,case,key,body,path)
            for stale in folder.glob('*.pdf'):
                if stale.name not in {r['file'] for r in files.values()}:stale.unlink()
            originals=attach_originals(case,folder)
            special={
                '2020-xgk1':'特别说明：原始听力Word合订第一次与第二次；本文件夹的练习、精读及其他PDF只对应2020年1月山东第一次。普通英语整卷不含本套听力，未混入本文件夹；完整原始资料仍保留在根目录的原始资料ZIP中。\n',
                '2023-shq':'特别说明：原始Word未收齐第18—20题选项；本套听力练习册采用此前按录音补全并核定的版本，原始Word保持原样。\n',
                '2020-shq':'特别说明：第15题现存题源有多解，只作理解练习，不计入单选成绩；逐题详解已说明依据。\n',
            }.get(case['id'],'')
            readme=f'''{case['title']} · 高考英语听力配套学习资料

本文件夹只对应这一份试卷，请按同一年份、卷别与场次使用。

建议顺序：听力练习册 → 听力逐题详解 → 原文双语精读 → 词汇与短语讲解 → 汉译英听写卡 → 听写训练本 → 合上原文复听。

汉译英听写卡：左侧中文，右侧空白，竖排单列；词汇回忆练习。答案单独一份，写完再核对。
听写训练本：原文关键词挖空，配合录音听写句子；答案单独一份。
听力逐题详解：答案、题干和选项中文、原文依据与中文、推理过程、其余选项核对。原始题源存在表述问题时，会在具体题目内说明。
词汇与短语讲解：本套词条、语境释义、原文形式、例句、中文与精读句号。
本套复习记录表：完成任务与错题复听记录，可重复打印。

{special}
Word附件保留原始文档字节。名称含“整卷”的文档还可能包含阅读、写作等其他部分；本套听力怎么做，请看“听力逐题详解.pdf”。原始资料的答案或措辞如有问题，以逐题详解内的具体说明为准。
PDF用PDF阅读器查看，Word文档用Word/WPS等兼容软件查看；均可自行打印，无纸质邮寄。
B站搜索“朋克英语”，按本文件夹的年份、卷别选择同名“考试”或“原文精读”视频免费观看。
'''
            (folder/'本套使用说明.txt').write_text(readme,'utf-8')
            record={'id':case['id'],'folder':case['title'],'words':len(words(case)),'cards':len(cards(case)),'dictation_blanks':len(M.blanks(case)),'questions':20,'files':files,'originals':originals,'detail_sha256':M.sha(X.OUT/(case['id']+'.json')) if not without_details else None}
            M.dump((out/(case['id']+'-核验.json')) if sample else AUDIT/(case['id']+'.json'),record)
            print(json.dumps({'done':case['id'],'pdfs':len(files),'pages':sum(v['pages'] for v in files.values()),'cards':len(cards(case))},ensure_ascii=False),flush=True)
        browser.close()
    print('分套制作完成',len(selected),'套',flush=True)


def verify_all():
    cases=X.cases();expected={c['title'] for c in cases}
    assert {p.name for p in OUT.iterdir() if p.is_dir()}==expected
    rows=[]
    for case in cases:
        folder=OUT/case['title'];r=json.loads((AUDIT/(case['id']+'.json')).read_text('utf-8'))
        assert r['id']==case['id'] and r['folder']==case['title']
        assert set(r['files'])==set(NAMES)
        assert r['detail_sha256']==M.sha(X.OUT/(case['id']+'.json')),'详解JSON已变，须重新制作：'+case['id']
        assert {p.name for p in folder.glob('*.pdf')}=={x['file'] for x in r['files'].values()}
        for f in r['files'].values():
            p=folder/f['file'];assert p.stat().st_size==f['bytes'] and M.sha(p)==f['sha256'],p
            with fitz.open(p) as d:assert len(d)==f['pages']
        for f in r['originals']:assert M.sha(folder/f['file'])==f['sha256']
        assert (folder/'本套使用说明.txt').stat().st_size
        rows.append(r)
    result={'version':'分套资料2026-11-13','case_count':len(rows),'pdf_count':sum(len(r['files']) for r in rows),'pages':sum(f['pages'] for r in rows for f in r['files'].values()),'questions':sum(r['questions'] for r in rows),'card_rows':sum(r['cards'] for r in rows),'pdf_types':NAMES,'cases':rows}
    assert result['case_count']==50 and result['pdf_count']==450 and result['questions']==1000
    M.dump(D/'分套资料清单与核验.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['cases','pdf_types']},ensure_ascii=False))
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--sample',action='store_true');ap.add_argument('--build',action='store_true');ap.add_argument('--verify',action='store_true');ap.add_argument('--refresh-details',action='store_true');ap.add_argument('--cases',nargs='*',default=[]);ap.add_argument('--without-details',action='store_true')
    a=ap.parse_args()
    if a.verify:verify_all()
    else:build(sample=a.sample,only=a.cases,without_details=a.without_details,refresh_details=a.refresh_details)
