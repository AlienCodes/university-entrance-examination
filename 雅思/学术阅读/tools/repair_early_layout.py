"""Reflow only failing teaching screens, retaining all original English, Chinese, and vocabulary."""
import os
from pathlib import Path
import re

from draft_lesson import TEXT, record, request_json
from early_editor import FILES, digest, read, store_candidate
from lesson import LESSON, PID, PROJECT, load, save

CLAUSES=re.compile(r'[,;:—–]\s+|\s+(?=(?:and|or|but|whereas|although|because|while|which|who|whose|when|so that|in order to|rather than|if|even though|as a result|including|with|without)\b)',re.I)
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

def subdivide(row,old,reason):
    en=row['en'];zh=row['zh'];choices=movable(row)
    if not choices:raise ValueError('This sentence has no safe phrase boundary')
    items=list(choices);keys=[str(i+1) for i in range(len(items))]
    prompt={'en':en,'whole_translation':zh,'terms':[w['h'] for w in row['w']],'possible_starts':dict(zip(keys,[en[k:k+52] for k in items])),'old_cuts':old,'layout_report':reason}
    instr=('已在实际手机字号的画面中发现排版问题。按英文从句、句意和朗读停顿，重新选择足够但不过量的屏幕。'
        '每一个切点给出后一个英文意群从哪个编号开始，并从整句中文精确摘出与它对应的开头若干字作为唯一定位符，'
        '保持两种语言的语义同步。已有的中文、词条和英文一字不改；不要拆开一个搭配或专名，各屏词汇和阅读量要均衡。')
    slots=[f'cut{i+1}' for i in range(min(8,len(items),max(2,len(row['w'])//5+1)))]
    schema=record(**{k:record(start={'type':'integer','enum':list(range(len(items)+1))},chinese_start=TEXT) for k in slots})
    for attempt in range(3):
        answer=request_json(instr+' 不用的字段填0和空字符串。',prompt,schema,attempt,token_limit=400)
        selection=[answer[k] for k in slots if answer[k]['start']]
        try:
            if not selection or any(not 1<=v['start']<=len(items) or not v['chinese_start'].strip() or zh.count(v['chinese_start'].strip())!=1 for v in selection):raise ValueError
            pts=[items[v['start']-1] for v in selection];cn=[zh.index(v['chinese_start'].strip()) for v in selection]
            if pts!=sorted(set(pts)) or cn!=sorted(set(cn)) or min(cn)<=0:raise ValueError
            for a,b in zip([0]+pts,pts+[len(en)]):
                if len(en[a:b].split())<4 or not any(a<=x and y<=b for w in row['w'] for x,y in w['sp']):raise ValueError
            parts=[zh[a:b] for a,b in zip([0]+cn,cn+[len(zh)])]
            if any(not re.search(r'[\u3400-\u9fff]',part) for part in parts):raise ValueError
            result={'at':[choices[i] for i in pts],'zh':parts}
            if result==old:raise ValueError
            return result
        except ValueError:
            prompt['retry']='切点不能重复。每段都有英文词条，相邻两段的中文切点要确实对应英文，中文定位符必须按原文写。'
    raise ValueError('No verified bilingual repartition found')

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
    document=load();rows=[s for g in document['paras'] for s in g]
    cuts=read(LESSON/FILES[2]);proof=read(LESSON/FILES[3]);before=digest(LESSON/FILES[2])
    if proof['text_sha256']!=digest(LESSON/FILES[0]):raise ValueError('Teaching text differs from its review')
    for n,reasons in targets.items():
        cuts[PID][str(n)]=subdivide(rows[n-1],cuts[PID].get(str(n)),reasons)
    save(LESSON/FILES[2],cuts);proof['split_sha256']=digest(LESSON/FILES[2]);proof['split_sentences']=len(cuts[PID]);proof['checked']=False
    proof.setdefault('screen_reflow',[]).append({'previous_split_sha256':before,'reading_units':list(targets),'source_and_translation_unchanged':True})
    save(LESSON/FILES[3],proof);store_candidate()

if __name__=='__main__':main()
