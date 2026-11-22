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

SYSTEM = """你是面向中文考生的剑桥雅思学术阅读教材编辑。全文和前后文仅作语境，逐项编辑指定英文。
1. 每句译成准确、自然的简体中文。先分析主干、施事、动作对象、修饰范围、指代、比较和时间。完整保留数量、否定、义务、推测强度与因果方向。原文没有的目的、情绪、结果或背景不能补进译句。保留英语学习者能一一对照的层次，同时避免翻译腔。不要机械逐词照搬语序。
2. 标出值得雅思学生记忆的词、固定搭配和有意义的范围表达，注意上下文中的实际词性、义项和指代。例如 habitat to accommodate the expected increase 表示栖息地为预期增长留出空间，不是适应；a large population of males 表示雄鸟数量多，不能说它们聚在一起。下方译句和右栏可以用不同措辞，但必须是同一个语境义。右栏只给当句用得到的简洁释义，不罗列无关义项。短句如确实只有1、2个重点即可；普通句一般4至7个，重要词多时应选全。
3. form 必须从输入这一句按原样连续摘录，包括连字符及词尾，head 是可供背诵的词典词形或固定短语，pos 是简短英文词性如 v.、n.、adj.、adv. 或 phr.。避免重叠选词、纯人名、冠词和无教学意义的凑数。一般不把句中整个意群当作单词。
4. 按编号逐项给结果，输出单个 JSON 对象，例如 {"a":[{"n":1,"zh":"译文","v":[["exact form","lemma","n.","语境义"]]}]}。不要添加说明、英文复述或Markdown。"""
AUDIT = """你是独立校对译文和双语词条的雅思教材编辑。逐个比较源句与稿件。检查遗漏/无端添加、范围或指代变化、数字、主从句、时态、可能性、否定、比较方向，以及每个词头及其语境义是否正确，右栏用词与整句译词可以不同。发现确切问题才改；不可为了文风任意改写。给出 JSON 对象 {"issues":[{"n":句号,"reason":"具体原词、错误与正确含义","zh":"整句修正，如无需则空字符串","v":[["只列需修正或新增的精确原形","词头","英语词性","当句释义"]]}]}。全组正确时给 {"issues":[]}。"""
CUTS = """你为雅思学术阅读视频决定哪些长句确实需要分屏。每句优先保持完整。确需分开时只在语法和意义自然的分界处分为2屏，极长且含三个独立目标的可3屏。每屏中文恰好翻译该屏英文；保留否定、比较和插入语回指。原文和译文都不得改意。不要斩开固定搭配、专名、名词短语或比较两端。只报有合适分点的句子。JSON格式 {"a":[{"n":1,"at":["第二屏开头三至六个连续原词"],"zh":["第一屏译文，","第二屏译文。"]}]}，不需分则 {"a":[]}。"""
POS = {'n.','v.','adj.','adv.','prep.','conj.','phr.','pron.','det.','num.','aux.','modal','abbr.','interj.'}
CJK = re.compile(r'[\u3400-\u9fff]')


def ask(instruction,data,attempt=0):
    req={'messages':[{'role':'system','content':instruction},{'role':'user','content':json.dumps(data,ensure_ascii=False)}],
         'temperature':.12 if not attempt else .25,'seed':751+attempt,'max_tokens':3800,
         'response_format':{'type':'json_object'},'cache_prompt':True}
    url=urllib.request.Request('http://127.0.0.1:8123/v1/chat/completions',data=json.dumps(req,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(url,timeout=1150) as r:
        d=json.load(r)
    s=d['choices'][0]['message']['content']
    return json.loads(s)


def simple(s):
    return unicodedata.normalize('NFKC',s).casefold().replace('’',"'").replace('‘',"'").replace('‐','-').replace('‑','-')


def positions(sentence,surface):
    pat=r'(?<!\w)'+re.escape(simple(surface))+r'(?!\w)'
    return [m.span() for m in re.finditer(pat,simple(sentence),re.I)]


def term(sentence,value):
    if not isinstance(value,list) or len(value)!=4 or not all(isinstance(x,str) for x in value):return None
    form,head,pos,meaning=[x.strip() for x in value];pos=pos.rstrip('.')+'.'
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


def translate(rows,topic,context):
    source=[{'n':n,'en':s} for n,s in rows];bad={}
    for attempt in range(3):
        out=ask(SYSTEM,{'title':topic,'surrounding_context':context,'sentences':source,'fix_if_repeated':bad},attempt)
        raw={int(x['n']):x for x in out.get('a',[]) if isinstance(x,dict) and str(x.get('n','')).isdigit()}
        result=[];bad={}
        for n,s in rows:
            v=raw.get(n,{});zh=str(v.get('zh','')).strip();terms=arranged(s,v.get('v',[]));nt=len(s.split())
            if not CJK.search(zh) or '\n' in zh or len(terms)<(3 if nt>=15 else 2 if nt>=7 else 1):
                bad[n]='请给完整译文并选取足够的、本句确实出现且不重叠的词语';continue
            result.append({'n':n,'en':s,'zh':zh,'v':terms})
        if not bad:return result
    if len(rows)>1:
        return [r for row in rows for r in translate([row],topic,context)]
    raise ValueError(f'No valid annotated sentence {rows[0][0]}: {bad}')


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


def run(source,out):
    data=json.loads(source.read_text());title=data['title']
    out.mkdir(parents=True,exist_ok=True)
    sents=[x for group in data['paragraphs'] for x in group]
    rows=list(enumerate(sents,1));content=[]
    cache=out/'draft-progress.json'
    if cache.exists():content=json.loads(cache.read_text())
    for start in range(len(content),len(rows),3):
        group=rows[start:start+3]
        block=translate(group,title,' '.join(sents[max(0,start-2):start+5]))
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
    save('篇目信息.json',dict(id=data['id'],book=data['book'],test=data['test'],passage=data['passage'],title=title,title_zh=meta['title_zh'],
         genre=meta['genre'],header=header,lemmas=lemma,row_lemmas=individual,pronunciation={},zh_names=[],pdf_pages=data['pdf_pages']))
    save('分屏.json',{data['id']:cuts})
    save('draft-review.json',dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),text_sha256=hashlib.sha256(text.encode()).hexdigest(),
         model='Qwen3-4B-Instruct-2507 Q4_K_M local CPU',sentences=len(rows),annotations=sum(len(z['v']) for z in content),
         offline_second_pass=changes,cut_sentences=len(cuts),awaiting_editorial_review=True))
    cache.unlink()


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('source',type=Path);ap.add_argument('output',type=Path)
    args=ap.parse_args();run(args.source,args.output)
