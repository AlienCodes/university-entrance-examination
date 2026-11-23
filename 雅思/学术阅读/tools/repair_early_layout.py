"""Reflow only failing teaching screens, retaining all original English, Chinese, and vocabulary."""
import os
from functools import lru_cache
from pathlib import Path
import re
import tempfile

from draft_lesson import TEXT, record, request_json
from early_editor import FILES, ZH_CLAUSE, aligned_boundary, digest, finite_response, read, store_candidate, translation_anchors
from lesson import LESSON, PID, PROJECT, save

CLAUSES=re.compile(r'[,;:—–]\s+|\s+(?=(?:and|or|but|whereas|although|because|while|which|who|whose|when|so that|in order to|rather than|if|even though|as a result|including)\b)',re.I)
VISUAL=re.compile(r'溢出|超出|越界|放不下|字号|孤[字词行]|孤悬|单落|单独|压住|字体|边界|截断|超宽|挤|遮挡|跨行|拆到两行|断行|连字符|续接号|行首缩进')
def movable(row):
    en=row['en']
    span=[(a,b) for w in row['w'] for a,b in w['sp']]
    result={}
    for hit in CLAUSES.finditer(en):
        i=hit.end()
        if min(len(en[:i].split()),len(en[i:].split()))<4 or any(a<i<b for a,b in span):continue
        token=next((en[i:m.end()] for m in re.finditer(r'\S+',en) if m.end()>i and len(en[i:m.end()].split())>=2 and en.count(en[i:m.end()])==1),'')
        if token:result[i]=token
    return result

def numbered_reflow(row,choices,old,can_display=None,rejected=()):
    en=row['en'];zh=row['zh'];ep=sorted(choices)
    zp=sorted({m.end() for m in ZH_CLAUSE.finditer(zh) if 3<=m.end()<=len(zh)-3})
    if not zp:return None
    # Selecting existing offsets avoids asking the editor to reproduce a Chinese string from memory.
    anchors=translation_anchors(zh,[(w['sp'],w['m']) for w in row['w']])
    pairs=[(e,z) for e in ep for z in zp if aligned_boundary(anchors,e,z)]
    if not pairs:return None
    def plan_for(sequence):
        es=[0,*[e for e,z in sequence],len(en)];zs=[0,*[z for e,z in sequence],len(zh)]
        sizes=[]
        for a,b,c,d in zip(es,es[1:],zs,zs[1:]):
            terms=sum(any(a<=x and y<=b for x,y in w['sp']) for w in row['w'])
            if terms<1 or len(en[a:b].split())<4 or len(re.findall(r'[\u3400-\u9fff]',zh[c:d]))<3:return None
            sizes.append(max(terms/8,(b-a)/170,(d-c)/68))
        plan={'at':[choices[i] for i in es[1:-1]],'zh':[zh[c:d] for c,d in zip(zs,zs[1:])]}
        return (max(sizes)+.22*len(sequence),plan)
    paths=[()];ranked=[]
    for count in range(1,min(4,len(ep),len(zp))+1):
        trials={}
        for path in paths:
            for pair in pairs:
                if path and (pair[0]<=path[-1][0] or pair[1]<=path[-1][1]):continue
                sequence=path+(pair,);best=plan_for(sequence)
                if best is not None:trials[sequence]=best
        if not trials:break
        paths=sorted(trials,key=lambda seq:trials[seq][0])[:24]
        ranked.extend((trials[seq][0],seq,trials[seq][1]) for seq in paths if trials[seq][1]!=old and trials[seq][1] not in rejected)
        if not can_display and ranked and min(trials[seq][0] for seq in paths)-.22*count<=1.12:break
    if not ranked:return None
    ranked.sort(key=lambda item:item[0])
    options=[];best=None
    for score,seq,plan in ranked[:28]:
        if best is not None and score>best+.18:break
        if can_display and not can_display(plan):continue
        if best is None:best=score
        options.append((seq,plan))
        if len(options)==6:break
    if not options:return None
    if len(options)==1:return options[0][1]
    options_for_reader={}
    for i,(seq,plan) in enumerate(options,1):
        es=[0,*[e for e,z in seq],len(en)]
        options_for_reader[i]=[[en[a:b],part] for a,b,part in zip(es,es[1:],plan['zh'])]
    data={'candidate_screens':options_for_reader}
    selection=finite_response('逐屏比较每组原样摘自原文的英中意群，选择语法完整、两种语言最准确对应的一组。若每组都有错位，填0。',data,
                              record(choice={'type':'integer','enum':list(range(len(options)+1))}),85)
    if selection['choice']:return options[selection['choice']-1][1]
    return None

def subdivide(row,old,reason,can_display=None,rejected=()):
    en=row['en'];zh=row['zh'];choices=movable(row)
    if not choices:raise ValueError('This sentence has no safe phrase boundary')
    result=numbered_reflow(row,choices,old,can_display,rejected)
    if result:return result
    anchors=translation_anchors(zh,[(w['sp'],w['m']) for w in row['w']])
    items=list(choices);keys=[str(i+1) for i in range(len(items))]
    prompt={'en':en,'whole_translation':zh,'terms':[w['h'] for w in row['w']],'possible_starts':dict(zip(keys,[en[k:k+52] for k in items])),'old_cuts':old,'layout_report':reason}
    instr=('已在实际手机字号的画面中发现排版问题。按英文从句、句意和朗读停顿，重新选择足够但不过量的屏幕。'
        '每一个切点给出后一个英文意群从哪个编号开始，并从整句中文精确摘出与它对应的开头若干字作为唯一定位符，'
        '保持两种语言的语义同步。已有的中文、词条和英文一字不改；不要拆开一个搭配或专名，各屏词汇和阅读量要均衡。')
    slots=[f'cut{i+1}' for i in range(min(8,len(items),max(2,len(row['w'])//5+1)))]
    schema=record(**{k:record(start={'type':'integer','enum':list(range(len(items)+1))},chinese_start=TEXT) for k in slots})
    for attempt in range(3):
        try:answer=request_json(instr+' 不用的字段填0和空字符串。',prompt,schema,attempt,token_limit=400)
        except (ValueError,TimeoutError):continue
        selection=[answer[k] for k in slots if answer[k]['start']]
        try:
            if not selection or any(not 1<=v['start']<=len(items) or not v['chinese_start'].strip() or zh.count(v['chinese_start'].strip())!=1 for v in selection):raise ValueError
            pts=[items[v['start']-1] for v in selection];cn=[zh.index(v['chinese_start'].strip()) for v in selection]
            if pts!=sorted(set(pts)) or cn!=sorted(set(cn)) or min(cn)<=0:raise ValueError
            if not all(aligned_boundary(anchors,e,z) for e,z in zip(pts,cn)):raise ValueError
            for a,b in zip([0]+pts,pts+[len(en)]):
                if len(en[a:b].split())<4 or not any(a<=x and y<=b for w in row['w'] for x,y in w['sp']):raise ValueError
            parts=[zh[a:b] for a,b in zip([0]+cn,cn+[len(zh)])]
            if any(not re.search(r'[\u3400-\u9fff]',part) for part in parts):raise ValueError
            result={'at':[choices[i] for i in pts],'zh':parts}
            if result==old or result in rejected or (can_display and not can_display(result)):raise ValueError
            return result
        except ValueError:
            prompt['retry']='切点不能重复。每段都有英文词条，相邻两段的中文切点要确实对应英文，中文定位符必须按原文写。'
    raise ValueError('No verified bilingual repartition found for '+row['en'][:90])

def native_probe(page,document,preview):
    from pilot_video import engine
    total=sum(len(group) for group in document['paras'])
    def fit(html,start):
        preview.write_text(html,'utf-8');page.goto(preview.as_uri())
        page.evaluate('document.fonts.ready');page.wait_for_timeout(150)
        return page.evaluate(engine.FIT,start)
    @lru_cache(maxsize=64)
    def natural(html):
        return fit(html,None)
    def check(n,row,plan):
        if plan is None:plan={'at':[],'zh':[row['zh']]}
        en=row['en'];points=[0,*[en.index(a) for a in plan['at']],len(en)];count=len(points)-1
        if any(not re.search(r'[ —]$',en[:i]) for i in points[1:-1]):return False
        slides=[]
        for i,(a,b,zh) in enumerate(zip(points,points[1:],plan['zh']),1):
            part=(a,b,zh,f' · PART {i}/{count}' if count>1 else '')
            slides.append(engine.sentence_slide(document,row,n,total,part))
        sizes=[]
        for html in slides:
            fs,vs,fits=natural(html)
            if not fits or fs<engine.MIN_FS or vs<engine.MIN_VS:return False
            sizes.append((fs,vs))
        shared=[min(s[0] for s in sizes),min(s[1] for s in sizes)]
        for i,html in enumerate(slides,1):
            actual=fit(html,shared)
            if actual[:2]!=shared or engine.screen_checks(page,f'第 {n} 句 第 {i} 屏',True,actual):return False
        return True
    return check

def main():
    review=PROJECT/'样片/review.json';log=Path(os.environ['IELTS_WORK'])/'native-layout.log'
    messages=read(review)['problems'] if review.is_file() else []
    if not messages and log.is_file():messages=[s for s in log.read_text(errors='replace').splitlines() if '第 ' in s and VISUAL.search(s)]
    targets={}
    for problem in messages:
        m=re.search(r'第\s*(\d+)\s*句',str(problem))
        if not m or not VISUAL.search(str(problem)):raise ValueError('This visual issue needs its specific diagnosis: '+str(problem)[:260])
        targets.setdefault(int(m[1]),[]).append(str(problem))
    if not targets:raise ValueError('No recoverable native layout issue was reported')
    from playwright.sync_api import sync_playwright
    from pilot_video import engine, prepare
    document=prepare();rows=[s for g in document['paras'] for s in g]
    cuts=read(LESSON/FILES[2]);proof=read(LESSON/FILES[3]);before=digest(LESSON/FILES[2])
    if proof['text_sha256']!=digest(LESSON/FILES[0]):raise ValueError('Teaching text differs from its review')
    changed=[];unresolved=[];previous=proof.setdefault('rejected_screen_plans',{})
    with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        page=browser.new_page(viewport=dict(width=engine.W,height=engine.H),device_scale_factor=2)
        probe=native_probe(page,document,Path(td)/'screen.html')
        for n,reasons in targets.items():
            old=cuts[PID].get(str(n));history=previous.setdefault(str(n),[])
            if old and old not in history:history.append(old)
            try:
                cuts[PID][str(n)]=subdivide(rows[n-1],old,reasons,lambda plan:probe(n,rows[n-1],plan),history)
                changed.append(n)
            except (ValueError,TimeoutError) as exc:
                unresolved.append(n);print(f'{PID} 第 {n} 句换屏仍待复核：{exc}',flush=True)
        browser.close()
    if not changed:raise ValueError(f'{PID}: no screen change passed both the reading and the native layout for {unresolved}')
    save(LESSON/FILES[2],cuts);proof['split_sha256']=digest(LESSON/FILES[2]);proof['split_sentences']=len(cuts[PID]);proof['checked']=False
    proof.setdefault('screen_reflow',[]).append({'previous_split_sha256':before,'reading_units':changed,'still_to_review':unresolved,'source_and_translation_unchanged':True})
    save(LESSON/FILES[3],proof);store_candidate()

if __name__=='__main__':main()
