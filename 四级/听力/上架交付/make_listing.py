#!/usr/bin/env python3
"""Build the CET-4 shop kit from the actual delivered PDFs, without re-encoding videos."""
from __future__ import annotations
import argparse
import asyncio
import base64
import csv
import hashlib
import html
import io
import json
import re
import shutil
from pathlib import Path
from urllib.parse import quote
from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED

import fitz
from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
LISTENING = HERE.parent
BRAND = '朋克英语'
PRODUCT = '四级听力真题35套精讲'
TITLE = '四级听力35套精讲｜同义替换·听写本·真题原卷'
TAGLINE = '875道题讲清答案依据，做题、精听、听写一套串起来。'
DESCRIPTION = '''【四级听力35套真题精讲｜全套PDF学习资料】
听完一遍，对了答案，还是不知道自己错在哪里？
这套资料把“答案从哪句来、选项换了什么说法、其他选项为什么错”放到每道题旁边，方便你做完一套就回头精听、复盘。

收录2018年6月—2026年6月，20次考试、35套听力、875道题。

你会收到：
① 真题35套精讲（785页）：原文逐句英汉对照，黄色标出答案出处；每题附选项翻译、答案依据、解题思路、原文与选项对应、错项排除。
② 同义替换手册（44页）：960组原文与正确选项对应，分5类整理，含原词复现，每组标明出处。
③ 高频词手册（21页）：487个词条，按35套原文中的出现套数排序，回到原文记词。
④ 听写本（178页）＋独立答案（73页）：听录音、补关键词，再核对。
⑤ 35天刷题计划（2页）：每天一套，也可按自己的节奏安排；对应精讲页码。
⑥ 另附历年真题原卷。

6份PDF讲义合计1103页（不含另附原卷）。带目录的5份PDF支持目录跳转、书签和“已读”勾选；35天计划用于打卡。适合手机、平板、电脑阅读，也可自行打印。

建议顺序：先做题→找答案依据→对照原文精听→听写→复听错题。可搭配同系列考试版、原文精读视频使用。

适合：想精听真题、需要中文辅助、希望系统复盘错题的四级备考同学。请先查看试读，确认版式与内容适合自己。

本商品为PDF电子资料（虚拟商品），不邮寄纸质书。数字内容交付后一般不支持退换（法律及平台另有规定的除外）；文件损坏、漏发等问题请联系处理。'''

CSS = r'''
*{box-sizing:border-box}html,body{margin:0;padding:0}body{font-family:'Noto Sans CJK SC',sans-serif;color:#123c31;background:#ddd}
.slide{width:1000px;height:1000px;position:relative;overflow:hidden;background:#f7f5ec;padding:46px 48px 54px}
.slide.dark{background:#093d30;color:#fffbed}.brand{font-size:19px;font-weight:800;letter-spacing:2px;display:flex;justify-content:space-between;align-items:center}
.brand span{font-family:Arial,sans-serif;font-size:14px;letter-spacing:3px;font-weight:400}.eyebrow{margin-top:30px;color:#476456;font-size:17px;font-weight:600;letter-spacing:2px}
.dark .eyebrow{color:#b9d4c4}h1{font-size:55px;font-weight:900;line-height:1.35;letter-spacing:-2px;margin:15px 0 10px}h2{font-size:28px;line-height:1.4;margin:0 0 12px}h3{font-size:24px;margin:0 0 12px}
.sub{font-size:22px;line-height:1.6;margin:8px 0 0;color:#527163}.dark .sub{color:#d1dfd3}.yellow{color:#ffe34a}.pink{color:#fc83b6}.hl{background:linear-gradient(transparent 63%,#ffe34a 63%);color:#123c31}
.bottom{position:absolute;left:48px;right:48px;bottom:22px;border-top:1px solid #c2cec3;padding-top:12px;display:flex;justify-content:space-between;font-size:14px;color:#526c5c}.dark .bottom{border-color:#508167;color:#bdcfbf}
.paper{background:white;box-shadow:0 12px 28px #103b3024;overflow:hidden;border:1px solid #dce2d7}.paper img{display:block;width:100%;height:auto}.pill{display:inline-block;padding:9px 18px;border-radius:30px;background:#ffe34a;color:#123c31;font-size:20px;font-weight:800}
.card{background:#fffdfa;border:1px solid #dce2d7;border-radius:14px;padding:20px}.dark .card{background:#15503e;border-color:#39765c}.muted{color:#5b7164}.dark .muted{color:#c5d9c7}.body{font-size:21px;line-height:1.7}.small{font-size:16px;line-height:1.65}.row{display:flex;gap:24px}.stat{font-family:Arial,sans-serif;font-weight:900;font-size:70px;line-height:1.1}.grid{display:grid;gap:16px}.num{font-family:Arial,sans-serif;font-size:50px;font-weight:900}.label{font-size:18px;line-height:1.5}.tag{display:inline-block;background:#edfff2;padding:6px 12px;font-size:16px;border-radius:6px;color:#14533a;font-weight:700}
.bullet{margin:14px 0;padding-left:21px;position:relative}.bullet:before{content:'';position:absolute;width:8px;height:8px;border-radius:50%;background:#deab18;left:0;top:13px}
.detail{position:absolute;left:48px;right:48px;top:269px;bottom:65px}.sheet{width:100%;height:100%;object-fit:contain;object-position:top;background:white}.note{background:#ffe34a;color:#123c31;padding:16px 20px;border-radius:8px;font-size:20px;line-height:1.5}
.flow{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.flow div{background:#e2ebe1;border-radius:8px;padding:16px 8px;text-align:center;font-size:19px;font-weight:700}.flow b{display:block;font-size:28px;color:#65856b}
'''

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def write(path, text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8')

def pack(folder, target):
    with ZipFile(target,'w',ZIP_STORED,allowZip64=True) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(folder.parent).as_posix())
    with ZipFile(target) as z:
        assert z.testzip() is None
        assert all(i.flag_bits & 0x800 for i in z.infolist() if not i.filename.isascii())

def check_inputs(pdf_dir):
    files=[]
    names=['四级听力真题35套精讲','四级听力同义替换手册','四级听力高频词手册','四级听力听写本','四级听力听写本（答案）','四级听力35天刷题计划']
    expected=[785,44,21,178,73,2]
    report=[]
    for name,n in zip(names,expected):
        found=[p for p in pdf_dir.rglob('*.pdf') if re.sub(r'^\d+\s+','',p.stem)==name]
        assert len(found)==1,(name,found)
        p=found[0];d=fitz.open(p)
        assert len(d)==n,(p,len(d),n)
        assert all(len(x.get_text().strip())>30 for x in d)
        links=[l for page in d for l in page.get_links()]
        for l in links:
            if l.get('kind')==fitz.LINK_GOTO:assert 0<=l['page']<len(d)
        toc=d.get_toc(); widgets=sum(len(list(x.widgets())) for x in d)
        if n!=2:assert toc and links and widgets
        files.append(p)
        report.append(dict(file=name+'.pdf',pages=len(d),bookmarks=len(toc),links=len(links),checkboxes=widgets,sha256=sha(p)))
    js=[json.loads(p.read_text()) for p in (LISTENING/'讲义/解析').glob('*.json')]
    assert len(js)==35
    for j in js:
        assert set(j['题'])==set(map(str,range(1,26)))
        for q in j['题'].values():
            assert q['答案'] in 'ABCD' and q['依据'] and q['讲'] and q['替换']
            assert len(q['错项'])==3 and set(q['选项译'])==set('ABCD')
    assert sum(len(q['替换']) for j in js for q in j['题'].values())==960
    assert sum(expected)==1103
    assert len(TITLE)<=30 and len(DESCRIPTION)<=1000
    assert not re.search(r'保过|包过|必买|保证提分|100%',TITLE+DESCRIPTION)
    return files,report,js

def document(title, body):
    return f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{title}</title><style>{CSS}</style>{body}</html>'

def navigation(buyer, pdf, js):
    d=fitz.open(pdf)
    lookup={}
    for _,title,page in d.get_toc():
        m=re.search(r'(20\d{2})年(\d+)月\s*第(\d)套',title)
        if m:
            y,month,n=m.groups();lookup[f'{y}{int(month):02}-{n}']=page
    assert len(lookup)==35
    rows=[];data=io.StringIO();w=csv.writer(data)
    w.writerow(['套次','精讲PDF文件页','精讲印刷页','考试视频文件名','原文视频文件名'])
    for j in sorted(js,key=lambda x:x['套'],reverse=True):
        sid=j['套'];y=int(sid[:4]);m=int(sid[4:6]);n=int(sid[-1]);page=lookup[sid]
        title=f'{y}年{m}月 第{n}套';stem=f'{y}-{m}-{n}'
        exam=stem+'考试.mp4';text=stem+'原文.mp4'
        w.writerow([title,page,page-1,exam,text])
        href=quote('1 四级听力真题35套精讲.pdf')+f'#page={page}'
        rows.append(f'<tr><td>{title}</td><td><a href="{href}">打开精讲 · P{page-1}</a></td><td><a href="../四级听力/{quote(exam)}">考试</a></td><td><a href="../四级听力/{quote(text)}">原文</a></td></tr>')
    write(buyer/'35套资料对应索引.csv','\ufeff'+data.getvalue())
    write(buyer/'35套资料导航.html','''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>35套听力资料导航</title><style>body{font:17px/1.7 system-ui,sans-serif;background:#f7f5ec;color:#123c31;max-width:1000px;margin:35px auto;padding:0 22px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;border-bottom:1px solid #d4dfd3;text-align:left}a{color:#14604a}p{color:#4e6859}h1{line-height:1.3}</style><h1>四级听力 · 35套资料导航</h1><p>点击对应套次打开精讲。精讲链接直接定位文件页，表格里的P页码对应讲义印刷页。请按年份、月份和套次匹配资料。</p><p>若一起使用本Release的视频包，将3个视频ZIP解压到与本讲义文件夹相同的位置，它们会合并到“四级听力”文件夹。此时下方视频链接可直接打开；手机阅读器对本地链接的支持可能不同，也可按CSV里的完整文件名查找。</p><table><thead><tr><th>套次</th><th>精讲</th><th>考试视频</th><th>原文精读</th></tr></thead><tbody>'''+''.join(rows)+'</tbody></table></html>')

def slide(title, subtitle, content, dark=False, eyebrow='CET-4 LISTENING · 全套学习资料'):
    cls='slide dark' if dark else 'slide'
    return f'<main class="{cls}"><div class="brand">朋克英语<span>PUNK ENGLISH</span></div><div class="eyebrow">{eyebrow}</div><h1>{title}</h1><p class="sub">{subtitle}</p><section class="detail">{content}</section><footer class="bottom"><span>2018.06—2026.06 · 大学英语四级听力</span><span>PDF电子资料 · 非纸质书</span></footer></main>'

def image_tag(path,style='',cls=''):
    data=base64.b64encode(path.read_bytes()).decode()
    return f'<img class="{cls}" style="{style}" src="data:image/png;base64,{data}" alt="实际交付PDF内页">'

async def build(args):
    dest=args.dest.resolve();dest.mkdir(parents=True,exist_ok=True)
    temp=dest/'build';temp.mkdir(exist_ok=True)
    kit=dest/'四级听力_小店上架包';kit.mkdir(exist_ok=True)
    pics=kit/'商品图_按文件名顺序上传';pics.mkdir(exist_ok=True)
    sources=kit/'可编辑排版源文件';sources.mkdir(exist_ok=True)
    buyer=dest/'四级听力_全套PDF讲义';buyer.mkdir(exist_ok=True)
    files,report,js=check_inputs(args.pdf_dir)
    for n,p in enumerate(files,1):shutil.copyfile(p,buyer/f'{n} {re.sub(r"^\d+\s+", "", p.name)}')
    navigation(buyer,files[0],js)
    shots={}
    needed={1:[0,1,4,5,7,8],2:[0,2],3:[0,2],4:[0,3],5:[0,3],6:[0]}
    for n,p in enumerate(files,1):
        d=fitz.open(p)
        for i in needed[n]:
            out=temp/f'pdf{n}-p{i+1}.png';d[i].get_pixmap(matrix=fitz.Matrix(1.8,1.8)).save(out);shots[n,i]=out
    def shot(n,i,style='',cls=''):return image_tag(shots[n,i],style,cls)
    pages=[]
    cover=args.hero.resolve()
    pages.append(('01_主图_35套真题精讲',f'<main class="slide" style="padding:0;background:#093d30">{image_tag(cover,"width:1000px;height:1000px;object-fit:cover")}</main>'))
    short=['35套真题精讲','同义替换手册','高频词手册','听写本','听写本答案','35天刷题计划']
    cards=''.join(f'<div class="card" style="height:277px;padding:14px;text-align:center">{shot(i,0,"height:182px;width:100%;object-fit:contain")}<div style="font-size:21px;font-weight:800;margin-top:10px">{name}</div><div class="small muted">{report[i-1]["pages"]}页 · PDF</div></div>' for i,name in enumerate(short,1))
    pages.append(('02_商品总览_六份讲义与原卷',slide('买到手，是这一整套。','6份讲义PDF，共1103页；另附历年真题原卷。',f'<div class="grid" style="grid-template-columns:repeat(3,1fr);gap:16px">{cards}</div><div class="note" style="margin-top:20px;display:flex;justify-content:space-between"><b>＋ 历年真题原卷</b><span>先做原卷，再用讲义复盘</span></div>')))
    q=json.loads((LISTENING/'讲义/解析/202606-2.json').read_text())['题']['4']
    proof=html.escape(q['依据'][0]['句']);opt='He was in good condition.'
    pages.append(('03_逐题解析_答案为什么选B',slide('听到了，为什么还选错？','把原文、选项和解题依据，放在一起看。',f'<div class="card" style="padding:28px"><span class="tag">真实讲义示例 · 2026年6月第2套 · 第4题</span><p class="body" style="margin:22px 0 6px">原文依据</p><h2 style="font-family:Georgia,serif;font-size:31px;color:#164a38">{proof}</h2><div class="note" style="margin:18px 0"><b>in good health ⇄ in good condition</b><br><span class="small">身体健康 ⇄ 状态良好</span></div><div class="body"><b>正确选项 B：</b>{opt}</div><div class="body" style="margin-top:12px">原文说他获救时身体很好，只是瘦了一些。<br>所以选“状态良好”，而不是“失去意识”。</div></div><div class="grid" style="grid-template-columns:repeat(2,1fr);margin-top:22px"><div class="card"><h3>每题都有</h3><div class="body">答案依据 · 解题思路<br>原文与选项对应 · 错项排除</div></div><div class="card"><h3>35套 · 875题</h3><div class="body">四个选项均配中文<br>知道自己错在哪一步</div></div></div>')))
    pages.append(('04_原文对照_黄色标出答案',slide('答案出处，直接标出来。','英文原文＋逐句中文；黄色高亮对应题号。',f'<div class="row" style="height:620px"><div class="paper" style="width:535px">{shot(1,8)}</div><div style="flex:1;padding-top:12px"><span class="pill">真实PDF内页</span><div class="body" style="margin-top:24px"><div class="bullet">新闻、长对话、短文<br>原文逐句对照</div><div class="bullet">不懂就看中文，<br>再回到录音复听</div><div class="bullet">黄色找到答案句，<br>右上角找到题号</div><div class="bullet">配套每套答案速查，<br>做完及时核对</div></div><div class="note" style="margin-top:24px">先盲听做题，<br>再对照原文精听。</div></div></div>')))
    types=[('同义改写',472),('词性句式转换',214),('正反转换',20),('概括归纳',111),('原词复现',143)]
    rows=''.join(f'<div style="display:flex;justify-content:space-between;border-bottom:1px solid #48735b;padding:14px 0;font-size:23px"><span>{k}</span><b class="yellow">{v}组</b></div>' for k,v in types)
    pages.append(('05_同义替换_960组对应关系',slide('选项换了说法，也能认出来。','960组原文与正确选项对应 · 分类整理、标明出处。',f'<div class="row"><div style="width:355px"><div class="stat yellow">960<span style="font-size:26px">组</span></div><p class="body">原文 ⇄ 正确选项</p>{rows}<p class="small muted" style="margin-top:18px">其中含143组“原词复现”；<br>每组保留对应年份、套次和题号。</p></div><div class="paper" style="flex:1;height:612px">{shot(2,2)}</div></div>',True)))
    pages.append(('06_高频词_按出现套数整理',slide('背词，也回到真题里背。','487个词条，按35套原文中的出现套数排序。',f'<div class="row"><div class="paper" style="width:525px;height:605px">{shot(3,2)}</div><div style="flex:1"><div class="card"><div class="num">37<span style="font-size:22px">个</span></div><b>必背词 · 出现于8套及以上</b></div><div class="card" style="margin-top:15px"><div class="num">122<span style="font-size:22px">个</span></div><b>常考词 · 出现于5—7套</b></div><div class="card" style="margin-top:15px"><div class="num">328<span style="font-size:22px">个</span></div><b>高频词 · 出现于3—4套</b></div><p class="small muted">词条附释义与出处，可回到对应原文复听。“必背、常考、高频”为本资料的统计分组。</p></div></div>')))
    pages.append(('07_听写练习_练完独立核对',slide('把“好像听懂”，写下来。','听写本178页＋独立答案73页，先练再核对。',f'<div class="row" style="gap:25px;height:485px"><div style="width:50%"><span class="pill">听写本 · 补关键词</span><div class="paper" style="margin-top:16px;height:420px">{shot(4,3)}</div></div><div style="width:50%"><span class="pill" style="background:#fc83b6">答案 · 按编号核对</span><div class="paper" style="margin-top:16px;height:420px">{shot(5,3)}</div></div></div><div class="card body" style="margin-top:28px;display:flex;justify-content:space-between"><b>听录音，填关键词</b><span>→</span><b>对答案，找漏听处</b><span>→</span><b>回原文，再听一次</b></div><p class="small muted" style="margin-top:15px">配合原声录音使用；听写本和答案分开，练习时不用提前看答案。</p>',True)))
    steps=['完整做一遍','看精讲依据','听写关键词','背本套词汇','复听错题']
    pages.append(('08_学习方法_35天刷题计划',slide('把一套真题，真正学完。','35天刷题计划，五项任务逐一打勾。',f'<div class="row"><div class="paper" style="width:545px;height:500px">{shot(6,0)}</div><div style="flex:1"><div class="stat">35<span style="font-size:28px">天</span></div><div class="body" style="margin-top:22px"><div class="bullet">每天一套，<br>也可按自己的节奏安排</div><div class="bullet">记录每套答对题数，<br>复盘自己的薄弱点</div><div class="bullet">计划内标出精讲页码，<br>找到对应讲解</div></div></div></div><div class="flow" style="margin-top:28px">'+''.join(f'<div><b>{i}</b>{s}</div>' for i,s in enumerate(steps,1))+'</div>')))
    byyear={}
    for j in js:
        key=j['套'];year=int(key[:4]);month=int(key[4:6]);byyear.setdefault(year,{}).setdefault(month,0);byyear[year][month]+=1
    years=''.join(f'<div class="card" style="height:172px"><div style="font-family:Arial;font-size:43px;font-weight:900">{year}<span style="font-family:inherit;font-size:20px;margin-left:10px" class="muted">{sum(months.values())}套</span></div><div style="font-size:19px;line-height:1.5;margin-top:12px">'+ ' '.join(f'<span style="display:inline-block;white-space:nowrap;margin-right:9px">{m}月 {n}套</span>' for m,n in sorted(months.items()))+'</div></div>' for year,months in sorted(byyear.items(),reverse=True))
    pages.append(('09_收录清单_35套范围一眼看清',slide('从2018，练到2026。','20次考试 · 35套听力 · 875题；收录范围逐项列清。',f'<div class="grid" style="grid-template-columns:repeat(3,1fr);gap:18px">{years}</div><div class="note" style="margin-top:24px">收录截至2026年6月，35套均有配套精讲与听写练习。</div>')))
    pages.append(('10_阅读体验与购买须知',slide('先看真实内页，再决定。','内容、版式和学习方式，都适合自己再入手。',f'<div class="row"><div class="card" style="width:49%;height:265px"><span class="tag">适合这样的你</span><div class="body"><div class="bullet">对完答案，还想弄懂依据</div><div class="bullet">需要中文辅助精听真题</div><div class="bullet">想把错题整理成可复习内容</div></div></div><div class="card" style="width:49%;height:265px"><span class="tag">阅读与交付</span><div class="body"><div class="bullet">PDF电子资料，不邮寄纸书</div><div class="bullet">手机、平板、电脑可阅读</div><div class="bullet">可自行打印，按需选页</div></div></div></div><div class="row" style="margin-top:24px"><div class="paper" style="width:380px;height:292px">{shot(1,1)}</div><div style="flex:1;padding:10px 0"><h2>目录一点击，就跳到那一套。</h2><p class="body">带目录的5份PDF有书签、已读勾选，方便继续上次的学习；35天计划用于打卡。</p><p class="small muted">原卷与讲义配合使用。PDF批注和保存效果依阅读器而异，建议用支持表单的阅读器打开。</p></div></div><div class="note" style="margin-top:20px"><b>做题 → 找依据 → 精听 → 听写 → 复听</b></div>')))
    layout=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1000,'height':1000},device_scale_factor=2)
        for stem,body in pages:
            out=sources/(stem+'.html');write(out,document(stem,body))
            await page.set_content(out.read_text(),wait_until='load');await page.evaluate('document.fonts.ready')
            await page.wait_for_function('Array.from(document.images).every(i=>i.complete && i.naturalWidth>0)')
            problems=await page.evaluate('''() => {
              const bad=[];
              for(const e of document.querySelectorAll('h1,h2,h3,.brand,.bottom,.pill,.tag,.note,.flow,.card')) {
                const r=e.getBoundingClientRect();
                if(r.x<0||r.y<0||r.right>1000.5||r.bottom>1000.5)bad.push('超出画布:'+e.innerText.slice(0,40));
                // CJK font descent may extend an auto-height heading's line box;
                // it is visible, and is not clipped content. Fixed cards must fit.
                if(e.scrollWidth>e.clientWidth+2||(e.matches('.card,.note,.flow')&&e.scrollHeight>e.clientHeight+2))bad.push('内容溢出:'+e.innerText.slice(0,40));
              }
              if(/\\b\\d{1,2}\\s*\\/\\s*\\d{1,2}\\b/.test(document.body.innerText))bad.push('画面出现图片编号');
              return bad;
            }''')
            assert not problems,(stem,problems)
            layout.append(dict(image=stem,problems=problems))
            await page.screenshot(path=str(pics/(stem+'.jpg')),type='jpeg',quality=95)
        guide=document('四级听力免费试读', '<main class="slide"><div class="brand">朋克英语<span>PUNK ENGLISH</span></div><div class="eyebrow">CET-4 LISTENING · 免费试读</div><h1 style="font-size:68px;margin-top:55px">四级听力<br>35套真题精讲</h1><p class="sub" style="font-size:30px;margin-top:28px">先看内容，再决定是否适合自己。</p><div class="note" style="margin-top:55px;font-size:26px;line-height:1.8">以下均为正式交付PDF的真实页面：<br>原文逐句对照 · 逐题精讲 · 同义替换<br>高频词 · 听写与答案 · 35天计划</div><p class="body" style="margin-top:38px">全套收录2018年6月—2026年6月，35套、875题。<br>6份讲义PDF共1103页，另附历年真题原卷。</p><p class="small muted" style="margin-top:28px">本文件为节选试读，非完整商品。<br>内页中的页码沿用正式讲义，便于核对。<br>电子资料 · 非纸质书</p></main>')
        write(temp/'试读封面.html',guide)
        await page.set_content(guide,wait_until='load');await page.evaluate('document.fonts.ready')
        await page.pdf(path=str(temp/'试读封面.pdf'),width='1000px',height='1000px',print_background=True,margin={'top':'0','bottom':'0','left':'0','right':'0'})
        await browser.close()
    trial=fitz.open(temp/'试读封面.pdf')
    for n,indices in {1:[4,5,7,8],2:[2],3:[2],4:[3],5:[3],6:[0]}.items():
        source=fitz.open(files[n-1])
        for i in indices:trial.insert_pdf(source,from_page=i,to_page=i,links=False,annots=False,widgets=False)
    trial.save(dest/'CET4-listening-free-sample.pdf',garbage=4,deflate=True)
    assert len(trial)==10
    write(kit/'商品标题_直接复制.txt',TITLE)
    write(kit/'一句话卖点_直接复制.txt',TAGLINE)
    write(kit/'商品简介_直接复制.txt',DESCRIPTION)
    write(kit/'长标题_平台允许时使用.txt','四级听力真题35套精讲 2018—2026 原文逐句英汉对照 答案依据 同义替换 高频词 听写本 35天计划 PDF电子资料 附真题原卷')
    seller='''四级听力｜商家上架说明（不要当成买家资料发送）

商品标题、简介和一句话卖点均为纯正文，可直接复制。主图使用01，其余图片按02—10顺序上传；文件名负责排序，图片里不印编号。图片统一为2000×2000 JPG；源HTML可编辑后按相同尺寸重新截图导出。AI主图源文件单独保留。

交付内容：已生成6份PDF讲义，共1103页。店主已明确：历年真题原卷会另外添加，因此商品图和简介保留“另附历年真题原卷”。请将你准备的原卷放入买家最终交付文件夹“7 历年真题原卷”，或在原有发货流程中一起发送。建议按本包的35套范围核对年份、月份、套次，听力选项顺序应与讲义对应；如果原卷版本不同，请提供对应提示。原卷的页数不计入1103页。

全套讲义包可以直接解压阅读；按你计划的发货方式加入原卷后交付。不要把本说明、小店上架包或开发源文件发给买家。

配套视频已存在：35个考试版＋35个原文精读版，分在3个视频ZIP里。Release提供这3个包与原发布来源；无需重做视频。简介仅写可搭配同系列视频使用，没有增加“未来永久免费更新”“永久答疑”等额外服务承诺。B站视频是否已全部公开、商品类目、售价、发货方式和售后设置，以你实际店铺为准。

建议只设一个完整套装SKU：全套PDF讲义＋历年真题原卷。售价沿用你现有定价。规格说明：PDF电子资料，不邮寄纸质书。上传免费试读PDF供买家先了解版式。

售后答复参考：文件无法打开时，先请买家完整下载并用PDF阅读器尝试；文件损坏或漏发及时补发。数字内容的退换按商品说明、平台规则及适用法律处理。

图文不得改成保过、保证提分、虚构销量或未实际包含的内容。资料收录截至2026年6月，不代表2026全年已收齐。
'''
    write(kit/'商家上传与发货说明.txt',seller)
    faqs='''【这是纸质书吗？】
这是PDF电子资料，不邮寄纸质书；可在手机、平板、电脑阅读，也可自行打印。

【一共有几份资料？】
6份讲义PDF，共1103页；另附历年真题原卷。讲义包括35套精讲、同义替换、高频词、听写本、听写答案和35天计划。原卷页数另计。

【收录到哪次考试？】
2018年6月—2026年6月，共20次考试、35套、875题。详见收录范围图。

【怎么开始学？】
先用原卷或同系列考试视频做一套；对答案，找依据；对照原文复听；完成听写，再复听错题。35天计划可以按自己的节奏调整。

【手机能不能看？】
可以。建议用支持PDF书签和表单的阅读器；目录、已读勾选等效果因阅读器而异，文件修改后请保存。35天计划可打印打卡。

【听写时在哪里对答案？】
听写本与答案是独立的两个PDF。先练习，再打开答案按同套、同篇和编号核对。
'''
    write(kit/'买家常见问题_可复制.txt',faqs)
    write(kit/'发货消息_补入实际下载地址后使用.txt','同学你好，你的四级听力资料已准备好：6份PDF讲义＋历年真题原卷。请通过本订单约定的交付方式查收。建议先打开“1 四级听力真题35套精讲.pdf”的使用说明，再按35天计划开始。文件无法打开或发现漏发，可以通过订单联系处理。祝学习顺利！')
    write(kit/'商品参数.json',json.dumps({'商品名称':TITLE,'资料类型':'PDF电子资料','范围':'2018.06—2026.06','听力套数':35,'题数':875,'PDF讲义份数':6,'PDF讲义总页数':1103,'原卷':'店主另行添加并随商品交付','纸质书':False,'sku':'全套PDF讲义＋历年真题原卷','image_count':10},ensure_ascii=False,indent=2))
    customer='''四级听力全套PDF讲义｜先看这里

6份PDF共1103页，涵盖2018年6月—2026年6月的35套听力、875题。

1 真题35套精讲：先做题，再看每题依据、思路、替换和错项排除。
2 同义替换手册：960组原文与正确选项对应（含原词复现）。
3 高频词手册：487个词条，回到真题语境中记词。
4 听写本：配合原声录音补关键词。
5 听写本答案：练习后再按编号核对。
6 35天刷题计划：每天一套，也可按自己的节奏安排。

推荐：先做题 → 找依据 → 原文精听 → 听写 → 复听错题。
同一文件夹内的“35套资料导航.html”和CSV索引可按套次定位精讲、查找视频。与视频一起使用时，将3个视频包解压到与本讲义文件夹相同的位置，视频会合并到“四级听力”文件夹。
PDF可以自行打印。带目录的5份文件有可点击目录、书签和“已读”勾选；请在支持这些功能的PDF阅读器中打开，勾选后保存。35天计划可打印打卡。

配套视频按年份、月份、套次与本讲义对应：同一套的“考试”和“原文”是一组。请以实际套次匹配；讲义的展示顺序与视频包的同年套次顺序可能不同。
'''
    write(buyer/'0 阅读说明.txt',customer)
    manifest={'product':PRODUCT,'sets':35,'questions':875,'exam_dates':20,'pages_total':1103,'replacement_pairs':960,'vocabulary_entries':487,'pdf_files':report,'original_papers':'店主另行添加；不包含在脚本生成的6份PDF讲义包中','layout':layout}
    write(dest/'CET4-content-check.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    thumbnails=''.join(f'<figure><a href="商品图_按文件名顺序上传/{stem}.jpg"><img src="商品图_按文件名顺序上传/{stem}.jpg" alt="{stem}"></a><figcaption>{stem}</figcaption></figure>' for stem,_ in pages)
    write(kit/'打开查看商品图.html',f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>四级听力｜商品图预览</title><style>body{{font:16px sans-serif;background:#f2f0e6;color:#123c31;margin:32px}}main{{max-width:1400px;margin:auto}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px}}figure{{margin:0}}img{{width:100%;border-radius:12px}}figcaption{{padding:12px 0;font-size:14px}}p{{line-height:1.8}}</style><main><h1>四级听力 · 小店商品图</h1><p>主图在前，其后展示实际交付内容、真实例题、内页与使用方法。点击图片可看原尺寸。</p><div class="grid">{thumbnails}</div></main></html>')
    shutil.copyfile(cover,kit/'主图_AI设计源图.png')
    pack(kit,dest/'CET4-listening-shop-ready.zip')
    pack(buyer,dest/'CET4-listening-PDF-complete.zip')
    print(json.dumps({'pdf_pages':1103,'question_count':875,'images':len(pages),'sample_pages':len(trial),'title_chars':len(TITLE),'description_chars':len(DESCRIPTION),'output':str(dest)},ensure_ascii=False))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdf-dir',type=Path,default=LISTENING/'讲义/成品')
    p.add_argument('--hero',type=Path,default=HERE/'assets/主图_AI原图.png')
    p.add_argument('--dest',type=Path,required=True)
    p.add_argument('--chromium',default='/usr/bin/chromium')
    asyncio.run(build(p.parse_args()))

if __name__=='__main__':main()
