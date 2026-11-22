"""Draft bilingual teaching annotations using an open-weight model on the runner itself."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
import unicodedata
import urllib.request

from translation import translate_sentence

SYSTEM = """你是剑桥雅思学术阅读词汇编辑。每句 en 是试卷原文，translation 是英汉专用模型的独立初译，须据语法和上下文判断各词在这个句子里的意思。
每个候选有编号、原文词形和词典提示。按原顺序给每一个编号填写简洁的简体中文语境义，通常2至8个汉字，不重复词性和英文。词典给多个义项时只选本句所用的意思，右栏跟整句可用不同措辞，语义必须一致。没有教学价值的简单词可用空字符串。重要的学术词、领域词、固定搭配、数量与范围表达应尽量保留。若有漏选的地道搭配或词，可写入 extras，包括精确连续英文原形、英文词头、词性和语境义。以原文为准。例如栖息地 accommodate 增长的种群表示为其留出空间；population 在生态学中是种群。只返回指定的 JSON 数据。"""
AUDIT = """你是独立校对译文和双语词条的雅思教材编辑。逐个比较源句与稿件。检查遗漏/无端添加、范围或指代变化、数字、主从句、时态、可能性、否定、比较方向，以及每个词头及其语境义是否正确，右栏用词与整句译词可以不同。发现确切问题才改；不可为了文风任意改写。给出 JSON 对象 {"issues":[{"n":句号,"reason":"具体原词、错误与正确含义","zh":"整句修正，如无需则空字符串","v":[["只列需修正或新增的精确原形","词头","英语词性","当句释义"]]}]}。全组正确时给 {"issues":[]}。"""
CUTS = """你为雅思学术阅读视频决定哪些长句确实需要分屏。每句优先保持完整。确需分开时只在语法和意义自然的分界处分为2屏，极长且含三个独立目标的可3屏。每屏中文恰好翻译该屏英文；保留否定、比较和插入语回指。原文和译文都不得改意。不要斩开固定搭配、专名、名词短语或比较两端。将已经审校的中文原样切开，只允许调整切口的标点，禁止改写句子。只报有合适分点的句子。JSON格式 {"a":[{"n":1,"at":["第二屏开头三至六个连续原词"],"zh":["第一屏译文，","第二屏译文。"]}]}，不需分则 {"a":[]}。"""
NAMES = "从输入的中文教材译句和词条中，逐字摘录包含间隔号·的完整人名、作品或机构名。人名前的职业、国籍、在、说等不能算进人名，返回 JSON 对象 names，每项为一个原文中的完整名称；同一名字仅列一次。"

POS = {'n.','v.','adj.','adv.','prep.','conj.','phr.','pron.','det.','num.','aux.','modal.','abbr.','interj.'}
CJK = re.compile(r'[\u3400-\u9fff]')


def record(**properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


def array(items):
    return {'type':'array','items':items}


TEXT = {'type':'string'}
VOCAB = array({'type':'array','items':TEXT,'minItems':4,'maxItems':4})
META = record(title_zh=TEXT,short_zh=TEXT,short_en=TEXT,genre=TEXT)


def reply_schema(instruction, data):
    if instruction == SYSTEM:
        vocab=record(form=TEXT,head=TEXT,pos={'type':'string','enum':sorted(POS)},meaning=TEXT)
        result={}
        for row in data['sentences']:
            keys={'w'+str(i):TEXT for i in range(1,len(row['candidates'])+1)}
            result['s'+str(row['n'])]=record(terms=record(**keys),extras={'type':'array','items':vocab,'maxItems':5})
        return record(**result)
    if instruction in (AUDIT,CUTS):
        ids=[s['n'] for s in data['rows']]
        number={'type':'integer','enum':ids}
        if instruction == AUDIT:
            return record(issues=array(record(n=number,reason=TEXT,zh=TEXT,v=VOCAB)))
        return record(a=array(record(n=number,at=array(TEXT),zh=array(TEXT))))
    if instruction==NAMES:
        return record(names=array(TEXT))
    return META


def ask(instruction,data,attempt=0):
    schema=reply_schema(instruction,data)
    req={'messages':[{'role':'system','content':instruction},{'role':'user','content':json.dumps(data,ensure_ascii=False)}],
         'temperature':.12 if not attempt else .25,'seed':751+attempt,'max_tokens':3800,
         'response_format':{'type':'json_schema','json_schema':{'name':'reading','strict':True,'schema':schema}},'cache_prompt':True}
    url=urllib.request.Request('http://127.0.0.1:8123/v1/chat/completions',data=json.dumps(req,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(url,timeout=1150) as response:
        choice=json.load(response)['choices'][0]
    if choice.get('finish_reason')=='length':
        raise ValueError('Incomplete editorial response at token limit')
    return json.loads(choice['message']['content'])


def simple(s):
    return unicodedata.normalize('NFKC',s).casefold().replace('’',"'").replace('‘',"'").replace('‐','-').replace('‑','-')


def positions(sentence,surface):
    pat=r'(?<!\w)'+re.escape(simple(surface))+r'(?!\w)'
    return [m.span() for m in re.finditer(pat,simple(sentence),re.I)]


def term(sentence,value):
    if isinstance(value,dict):
        value=[value.get(k) for k in ('form','head','pos','meaning')]
    if not isinstance(value,list) or len(value)!=4 or not all(isinstance(x,str) for x in value):return None
    form,head,pos,meaning=[x.strip() for x in value]
    pos=pos.rstrip('.').lower()+'.'
    if not CJK.search(meaning) or not head or not re.search('[A-Za-z]',head) or '|' in head+meaning or any(c in head+meaning+form for c in '\t\n'):return None
    where=positions(sentence,form)
    if not where:return None
    form=sentence[where[0][0]:where[0][1]]
    if pos not in POS:pos='phr.' if ' ' in form else ''
    return [form,head,pos,meaning]


def arranged(sentence,values):
    byform={}
    for entry in values:
        v=term(sentence,entry)
        if v:byform[simple(v[0])]=v
    occupied=set();out=[]
    for v in sorted(byform.values(),key=lambda x:-len(x[0])):
        spans=positions(sentence,v[0]);chars={k for a,b in spans for k in range(a,b)}
        if chars & occupied:continue
        occupied.update(chars);out.append((spans[0][0],v))
    return [v for _,v in sorted(out)]


def translate(rows,topic,context,grounding=None):
    grounding=grounding or {}
    remaining=dict(rows)
    good={}
    errors={}
    for attempt in range(3):
        source=[]
        for n,en in remaining.items():
            guide=grounding[n]
            candidates={f'w{idx}':t for idx,t in enumerate(guide['candidates'],1)}
            source.append(dict(n=n,en=en,translation=guide['translation'],candidates=candidates,term_hints=guide['term_hints']))
        out=ask(SYSTEM,{'title':topic,'surrounding_context':context,'sentences':source,'fix_if_repeated':errors},attempt)
        raw={n:out.get('s'+str(n),{}) for n in remaining}
        errors={}
        for n,en in list(remaining.items()):
            v=raw.get(n,{})
            guide=grounding[n]
            zh=guide['translation'].strip()
            choices=v.get('terms',{})
            values=[]
            for idx,t in enumerate(guide['candidates'],1):
                meaning=choices.get('w'+str(idx),'').strip()
                if not meaning and t['form'] in guide['term_hints']:
                    meaning=guide['term_hints'][t['form']]
                if meaning:
                    values.append([t['form'],t['head'],t['pos'],meaning])
            values.extend(v.get('extras',[]))
            terms=arranged(en,values)
            words=len(en.split())
            minimum=min(7,max(1,(len(guide['candidates'])+1)//2),max(1,(words+2)//3))
            if not CJK.search(zh) or any(ch in zh for ch in '\t\n') or len(terms)<minimum:
                errors[n]=f'请保留编号{n}，给完整中文并摘录至少{minimum}个本句中真实出现的不同词或搭配。已有{len(terms)}个可匹配。'
                print('Review retry',n,'received',str(v)[:640],flush=True)
            else:
                good[n]={'n':n,'en':en,'zh':zh,'v':terms}
                del remaining[n]
        if not remaining:
            break
    if remaining:
        if len(rows)==1:
            raise ValueError(f'No valid annotated sentence {rows[0][0]}: {errors}')
        for row in remaining.items():
            good[row[0]]=translate([row],topic,context,grounding)[0]
    return [good[n] for n,en in rows]


def audit(rows,title):
    changes=[];positions_by_id={x['n']:x for x in rows}
    for i in range(0,len(rows),4):
        group=rows[i:i+4]
        findings=ask(AUDIT,{'title':title,'rows':group}).get('issues',[])
        for note in findings:
            if not isinstance(note,dict) or note.get('n') not in [x['n'] for x in group]:continue
            entry=positions_by_id[note['n']];before=[entry['zh'],entry['v']]
            zh=note.get('zh','')
            if isinstance(zh,str) and CJK.search(zh) and '\n' not in zh:entry['zh']=zh.strip()
            corrections=note.get('v',[])
            if isinstance(corrections,list):entry['v']=arranged(entry['en'],entry['v']+corrections)
            if before!=[entry['zh'],entry['v']]:changes.append({'n':entry['n'],'reason':note.get('reason','')})
    return changes


def split_decisions(rows,title):
    candidates=[r for r in rows if len(r['en'])>=205 or len(r['en'].split())>=36]
    approved={}
    for start in range(0,len(candidates),3):
        group=candidates[start:start+3]
        proposals=ask(CUTS,{'title':title,'rows':group}).get('a',[])
        for p in proposals:
            if not isinstance(p,dict):continue
            row=next((r for r in group if r['n']==p.get('n')),None)
            if row is None:continue
            anchors=p.get('at',[]);zh=p.get('zh',[])
            if not isinstance(anchors,list) or len(anchors) not in (1,2) or not isinstance(zh,list) or len(zh)!=len(anchors)+1 or not all(isinstance(s,str) and CJK.search(s) for s in zh):continue
            clause_text=lambda value:re.sub(r'[，。！？；、,.;:：？!\s]','',value)
            if clause_text(''.join(zh))!=clause_text(row['zh']):continue
            en=row['en'];cuts=[]
            for a in anchors:
                if not isinstance(a,str) or en.count(a)!=1:break
                cut=en.index(a)
                if cut<=0 or en[cut-1] not in ' —':break
                cuts.append(cut)
            if len(cuts)!=len(anchors) or cuts!=sorted(cuts):continue
            breaks=[0]+cuts+[len(en)]
            if any(len(en[left:right].split())<5 for left,right in zip(breaks,breaks[1:])):continue
            spans=[t for val in row['v'] for t in positions(en,val[0])]
            if any(a<c<b for a,b in spans for c in cuts):continue
            if not all(any(left<=a and b<=right for a,b in spans) for left,right in zip(breaks,breaks[1:])):continue
            row['zh']=''.join(zh);approved[str(row['n'])]={'at':anchors,'zh':zh}
    return approved


def confirmed_names(content):
    contexts=[text for r in content for text in [r['zh'],*[v[3] for v in r['v']]] if '·' in text]
    if not contexts:
        return []
    names=[]
    for start in range(0,len(contexts),9):
        group=contexts[start:start+9]
        names.extend(x for x in ask(NAMES,{'Chinese':group})['names'] if isinstance(x,str) and '·' in x and len(x)<=32 and any(x in v for v in group))
    return sorted(set(names),key=lambda x:(-len(x),x))


def grounding_notes(data,out):
    source=Path(__file__).resolve().parents[1]/'备课'/f"{data['id']}.json"
    rows=json.loads(source.read_text())['rows']
    sentences=[s for g in data['paragraphs'] for s in g]
    if [r['en'] for r in rows]!=sentences:
        raise ValueError('Dictionary candidates do not match the approved print text')
    cache=out/'translation-progress.json'
    previous=json.loads(cache.read_text()) if cache.exists() else {}
    for n,(r,en) in enumerate(zip(rows,sentences),1):
        hints=r['term_hints']
        notes=[t for t in data.get('language_review',[]) if isinstance(t,dict) and str(t.get('english','')).lower() in en.lower()]
        if str(n) not in previous:
            previous[str(n)]=translate_sentence(en,sentences[n-2] if n>1 else '',hints.items(),notes)
            cache.write_text(json.dumps(previous,ensure_ascii=False))
        r['translation']=previous[str(n)]
    return {i:{k:r[k] for k in ('candidates','term_hints','translation')} for i,r in enumerate(rows,1)}


def run(source,out):
    data=json.loads(source.read_text());title=data['title']
    out.mkdir(parents=True,exist_ok=True)
    sents=[x for group in data['paragraphs'] for x in group]
    rows=list(enumerate(sents,1));content=[]
    grounding=grounding_notes(data,out)
    cache=out/'draft-progress.json'
    if cache.exists():content=json.loads(cache.read_text())
    tips=data.get('language_review',[])+[{'english':f['term'],'check':f.get('definition_zh',f['definition'])} for f in data.get('footnotes',[]) if isinstance(f,dict) and 'term' in f and 'definition' in f]
    for start in range(len(content),len(rows),3):
        group=rows[start:start+3]
        passage=' '.join(sents[max(0,start-2):start+5])
        hints=[t for t in tips if isinstance(t,dict) and str(t.get('english','')).lower() in passage.lower()]
        block=translate(group,title,{'text':passage,'verified_notes':hints},grounding)
        content.extend(block)
        cache.write_text(json.dumps(content,ensure_ascii=False))
        print(f"{data['id']} {len(content)}/{len(rows)}",flush=True)
    changes=audit(content,title)
    cuts=split_decisions(content,title)
    meta=ask('把剑桥雅思学术阅读的英文标题翻成准确、自然的中文。全文标题、用于页眉的简洁中英文短题名和主题。只输出 {"title_zh":"完整中文标题","short_zh":"至多11个汉字","short_en":"从标题选简短核心词，不多于5词","genre":"说明文 · 主题"}。',{'title':title,'first':sents[:2]})
    for k in ['title_zh','short_zh','genre']:
        if not isinstance(meta.get(k),str) or not CJK.search(meta[k]):raise ValueError('Missing title: '+k)
    posmap={'phr.':''}
    lines=[];lemma={};individual={};names=set();ni=0
    for para in data['paragraphs']:
        for s in para:
            row=content[ni];ni+=1
            if row['en']!=s:raise ValueError('Source order changed')
            z=row['zh'].replace('\t',' ').strip()
            gloss=[]
            for j,(form,head,pos,meaning) in enumerate(row['v']):
                individual[f'{ni}.{j}']=head
                gloss.append(form+'|'+((posmap.get(pos,pos)+' ') if posmap.get(pos,pos) else '')+meaning)
            lines.append('\t'.join([s,z,*gloss]))
        lines.append('')
    text='\n'.join(lines)
    (out/'双语精读.tsv').write_text(text)
    def save(name,obj):(out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=1)+'\n')
    header={'english':meta.get('short_en',title),'chinese':meta['short_zh']}
    save('篇目信息.json',dict(id=data['id'],book=data['book'],test=data['test'],passage=data['passage'],title=title,title_zh=data.get('title_zh') or meta['title_zh'],
         genre=meta['genre'],header=header,lemmas=lemma,row_lemmas=individual,pronunciation={},zh_names=confirmed_names(content),pdf_pages=data['pdf_pages']))
    save('分屏.json',{data['id']:cuts})
    save('draft-review.json',dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),text_sha256=hashlib.sha256(text.encode()).hexdigest(),
         model='Tencent HY-MT1.5-1.8B Q8_0 translation and separate Qwen3-4B-Instruct-2507 Q4_K_M contextual editing, both local CPU',sentences=len(rows),annotations=sum(len(z['v']) for z in content),
         offline_second_pass=changes,cut_sentences=len(cuts),awaiting_editorial_review=True))
    if cache.exists():cache.unlink()
    (out/'translation-progress.json').unlink(missing_ok=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('source',type=Path);ap.add_argument('output',type=Path)
    args=ap.parse_args();run(args.source,args.output)
