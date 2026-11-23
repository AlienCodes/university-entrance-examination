"""Prepare the early-volume lessons from the checked paper and independently verify their teaching text."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

from draft_lesson import CJK, TEXT as STRING, array, confirmed_names, positions, record, request_json
from lesson import LESSON, PID, PROJECT, save
from material import verify_original
from release_assets import fetch, inventory
from translation import translate_sentence

VERSION = 'paper-context-2'
DRAFT = 'ielts-academic-editorial-10-1'
FILES = ('双语精读.tsv', '篇目信息.json', '分屏.json', 'content-review.json')
PAPER = PROJECT/'原稿'/(PID+'.json')
PREP = PROJECT/'备课'/(PID+'.json')
POS = re.compile(r'^([a-z]+[.])\s+(.*)$', re.I)
NOISE = re.compile(r'术语与语境|\b(?:translation|original sentence|as an ai)\s*[:：]|以下是|译文如下|参考译文[：:]|原文[：:]|翻译[：:]|该句的|作为.{0,6}模型|\*\*|[<>]|[\r\n\t]', re.I)
CLAUSE = re.compile(r'[;:—–]\s+|,\s+|\s+(?=(?:and|but|whereas|although|because|while|which|who|whose|when|so that|in order to|rather than|if|even though|as a result)\b)',re.I)
EDITOR = ('你是雅思学术阅读教材责任编辑。source中的每个英文意群依次翻成准确、简洁、自然的简体中文。'
 '英文是唯一依据。译全动作、否定、程度、数字、单位和逻辑，上一句只能帮助确定指代。严禁补写上一句的内容。'
 '机器参照可能错译或发挥，应主动纠正。parts中每一项只译给定的一段，相邻中文拼起来就是自然的一句话。'
 '保留与本文相符的专名、引用和年份。为每个实际词条给语境中的中文义，尽量2至8个汉字，写出最贴切的一义。'
 '只给教材正文和词条。')
VERIFY = ('你是独立校勘此页的第二位英汉教材编辑。逐项对照英文、对应的中文意群及每个词条。'
 '只在能够指出具体错误时修订，例如漏译、增译、主客体颠倒、专名年份、情态或数量范围、当句词义错误、中文病句。'
 '不得加入原文没有的背景。逐句依原意判断，切口前后语义必须对应。correct 为 true 表示每段中文及词条均可使用；'
 '若存在问题，correct 为 false，将改正后的完整分段译文写入 parts，在 corrections 中用词条的原编号写确实需要改正的词义，同时说明依据。'
 '若正确则 parts、corrections 均为空。不要仅为换同义词改稿。')
CJK_POS = re.compile(r'^(?:名词|动词|形容词|副词|短语|n\.|v\.|adj\.|adv\.|phr\.)[：: ]*')
def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()

def corrections():
    return read(PROJECT/'审校/早期册语境校订.json').get(PID,{})

def key_for(project,pid):
    manual=read(project/'审校/早期册语境校订.json').get(pid,{})
    inputs=[digest(project/'原稿'/(pid+'.json')),digest(project/'备课'/(pid+'.json')),VERSION,manual]
    fingerprint=hashlib.sha256(json.dumps(inputs,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:16]
    return f'{pid}-{fingerprint}'

def key():
    return key_for(PROJECT,PID)

def work():
    path=Path(os.environ['IELTS_WORK'])/PID
    path.mkdir(parents=True,exist_ok=True)
    return path

def read(file):
    return json.loads(file.read_text())

def old_terms():
    assets=inventory(DRAFT)
    wp=work()
    if PID+'-draft.zip' in assets:
        zpath=fetch(assets[PID+'-draft.zip'],wp)
        with zipfile.ZipFile(zpath) as z:
            text=z.read(PID+'/双语精读.tsv').decode()
            met=json.loads(z.read(PID+'/篇目信息.json'))
            return {line.split('\t')[0]:[[form,met.get('row_lemmas',{}).get(f'{n}.{i}',form),*(POS.match(v).groups() if POS.match(v) else ('phr.',v))] for i,a in enumerate(line.split('\t')[2:]) for form,v in [a.split('|',1)]] for n,line in enumerate((a for a in text.splitlines() if a),1)}
    for n in (digest(PAPER),read(PAPER).get('source_review',{}).get('draft_compatibility',{}).get('source_sha256','')):
        name=f'{PID}-{n[:16]}-draft-progress.json'
        if name in assets:
            return {r['en']:r['v'] for r in read(fetch(assets[name],wp))}
    return {}

def clean(text):
    return isinstance(text,str) and CJK.search(text) and not NOISE.search(text)

def boundaries(en,terms):
    blocked=[(a,b) for v in terms for a,b in positions(en,v['form'])]
    if len(en.split())<31 and len(en)<200 and len(terms)<=9:
        return []
    result=[]
    for hit in CLAUSE.finditer(en):
        at=hit.end()
        if any(a<at<b for a,b in blocked) or not any(b<=at for a,b in blocked) or not any(a>=at for a,b in blocked):continue
        if min(len(en[:at].split()),len(en[at:].split()))<6 or at in result:continue
        result.append(at)
    return result

def decide(en,terms):
    choices=boundaries(en,terms)
    if not choices:return [en]
    labels={str(i):en[pos:pos+52] for i,pos in enumerate(choices,1)}
    schema=record(cuts={'type':'array','items':{'type':'integer','minimum':1,'maximum':len(choices)},'maxItems':min(9,len(choices))})
    instruction=('依据从句、并列和句意，判断是否应给手机屏幕分屏。优先保留完整句；文字确实较长，或一屏有太多词条，才按完整意群拆。'
                 '按需要选给定编号，让各屏阅读量接近，多项并列长句可超过两处分屏。不要让一侧堆满十几条、另一侧只有一两条。不要拆主谓宾、词组、比较结构或专名，中等长度的句子允许不分。')
    proposed=request_json(instruction,{'sentence':en,'words':[t['form'] for t in terms],'possible_starts':labels},schema)['cuts']
    selected=sorted(set(choices[i-1] for i in proposed if 1<=i<=len(choices)))
    spans=list(zip([0]+selected,selected+[len(en)]))
    if any(len(en[a:b].split())<6 or not any(a<=s and e<=b for t in terms for s,e in positions(en,t['form'])) for a,b in spans):return [en]
    return [en[a:b] for a,b in spans]

def vocabulary(row,prior,notes):
    en=row['en'];items=[dict(t) for t in row['candidates']]
    for entry in notes:
        phrase=entry['english'];spans=positions(en,phrase)
        if spans and 1<=len(phrase.split())<=4 and all(phrase.casefold()!=t['form'].casefold() for t in items):
            # A course note may describe an entire clause. Only use the short cue as a dictionary entry when its own sense is supplied.
            meaning=entry['check']
            if len(meaning)<=14 and not any(c in meaning for c in '，；。'):
                a,b=spans[0];items.append(dict(form=en[a:b],head=phrase.lower(),pos='phr.' if ' ' in phrase else '',dictionary=meaning))
    byform={t['form'].casefold():t for t in items}
    for form,head,pos,meaning in prior:
        spans=positions(en,form)
        if not spans or not clean(meaning) or len(form.split())>5:continue
        if form.casefold() in byform:
            byform[form.casefold()]['earlier_sense']=meaning
        elif not any(a<d and c<b for a,b in spans for old in items for c,d in positions(en,old['form'])):
            t=dict(form=en[spans[0][0]:spans[0][1]],head=head,pos=pos,dictionary=meaning);byform[form.casefold()]=t;items.append(t)
    used=set();result=[]
    for t in items:
        spans=positions(en,t['form']);pixels={i for a,b in spans for i in range(a,b)}
        if not pixels or used & pixels:continue
        used.update(pixels);result.append(t)
    return sorted(result,key=lambda t:positions(en,t['form'])[0][0])

def choose_terms(en,items,notes):
    positions_allowed=['n.','v.','adj.','adv.','prep.','conj.','pron.','num.','phr.']
    form=record(form=STRING,head=STRING,pos={'type':'string','enum':positions_allowed})
    instructions=('为雅思精读筛选当句值得掌握的词汇、义项、搭配和短语。尽量收全学术词、主题词、熟词生义、'
        '短语动词、重要数量和逻辑表达。不要为凑数列孤立的普通助动词、时间地点常用词、代词。'
        '如 were treated to、inch its way、be fundamental to 等，依实际句法选择完整而紧凑的搭配。'
        '保留每个有学习价值的实词，不过分扩大词组而遮掉彼此独立的重点词。一个多词表达和其中的单词不要重复列出。'
        '选择候选词时写其编号及此句正确词性；另外列出未列入的值得学的表达。添加表达的 form 必须逐字摘自本句，'
        'head 为自然的词典词头，pos 为其在句中的词性。数量由难度决定，短句通常2至6条，困难的句子可以有十余条。')
    schema=record(kept=array(record(number={'type':'integer'},pos={'type':'string','enum':positions_allowed})),additional=array(form))
    prompt={'sentence':en,'dictionary_candidates':{str(i+1):t['form'] for i,t in enumerate(items)},'paper_notes':notes}
    response=request_json(instructions,prompt,schema)
    selected=[]
    for t in response['additional']:
        spans=positions(en,t['form'])
        if not spans or not t['head'].strip() or len(t['head'])>70 or len(t['form'].split())>7:continue
        a,b=spans[0]
        if en[a:b].casefold()!=t['form'].casefold():continue
        selected.append(dict(form=en[a:b],head=t['head'].strip(),pos=t['pos'],dictionary=''))
    for t in response['kept']:
        n=t['number']-1
        if 0<=n<len(items):selected.append({**items[n],'pos':t['pos']})
    # Paper-glossed technical terms retain priority over a generic selection.
    anchors={x['english'].casefold() for x in notes}
    for t in items:
        if t['form'].casefold() in anchors and not any(i['form'].casefold()==t['form'].casefold() for i in selected):selected.insert(0,t)
    filtered=[];used=set()
    for t in selected or items:
        points={i for a,b in positions(en,t['form']) for i in range(a,b)}
        if points and not used.intersection(points):
            filtered.append(t);used.update(points)
    return sorted(filtered,key=lambda t:positions(en,t['form'])[0][0])

def assemble(n,en,parts,terms,meanings):
    return {'n':n,'en':en,'parts':parts,'zh':''.join(parts),'v':[[t['form'],t['head'],t.get('pos',''),m] for t,m in zip(terms,meanings,strict=True)]}

def good(en,parts,terms,zh,meanings,previous):
    if len(zh)!=len(parts) or not all(clean(x) for x in zh) or len(meanings)!=len(terms):return False
    if not all(clean(x) and 0<len(x)<=36 and '|' not in x for x in meanings):return False
    result=''.join(zh)
    if len(result)>max(44,len(en)*1.35) or (len(en)>70 and len(result)<len(en)*.075):return False
    # Do not silently transplant a year from an adjacent sentence.
    years=lambda s:set(re.findall(r'(?<!\d)(?:1[4-9]\d{2}|20\d{2})(?!\d)',s))
    if (years(previous)-years(en)) & (years(result)-years(en)):return False
    return True

def teach(index,source,prep,prior,previous,workdir):
    n=index+1;en=prep['en'];terms=vocabulary(prep,prior.get(en,[]),source.get('language_review',[]))
    if not terms:raise ValueError(f'{PID} sentence {n} lacks a teachable entry')
    notes=[a for a in source.get('language_review',[]) if a['english'].casefold() in en.casefold()]
    terms=choose_terms(en,terms,notes)
    patch=corrections().get(str(n))
    if patch and patch['en']!=en:raise ValueError(f'Manual revision for a different sentence {PID}/{n}')
    chunks=[en] if patch and len(patch['parts'])==1 else decide(en,terms)
    context=[{'en':t['form'],'lemma':t['head'],'pos':t['pos'],'dictionary':t.get('dictionary','')[:180],'sense_hint':prep['term_hints'].get(t['form'],t.get('earlier_sense',''))} for t in terms]
    try:
        direct=translate_sentence(en,'',[],[])
    except ValueError:
        direct=''
    if not clean(direct):direct=''
    identifiers=[f'w{i+1}' for i in range(len(terms))]
    schema=record(parts={'type':'array','items':STRING,'minItems':len(chunks),'maxItems':len(chunks)},glosses=record(**{k:STRING for k in identifiers}))
    args={'title':source['title'],'previous_for_pronouns_only':previous,'source':chunks,'translation_hypothesis':direct,'words':dict(zip(identifiers,context)),'paper_notes':notes}
    for attempt in range(3):
        answer=request_json(EDITOR,args,schema,attempt)
        zh=[x.strip() for x in answer['parts']]
        meanings=[CJK_POS.sub('',answer['glosses'].get(k,'').strip()) for k in identifiers]
        if good(en,chunks,terms,zh,meanings,previous):break
        args['revise']='请提供每段的正文翻译以及每个词条的中文。清除说明文字、换行、无依据的年份、过长的词条释义。'
    else:raise ValueError(f'{PID} sentence {n}: unusable initial translation or gloss')
    if patch:
        zh=patch['parts'];meanings=[patch['meanings'].get(t['form'],m) for t,m in zip(terms,meanings,strict=True)]
        if not good(en,chunks,terms,zh,meanings,previous):raise ValueError(f'Incorrect manual edit at {PID}/{n}')
    row=assemble(n,en,zh,terms,meanings);row['english_parts']=chunks;row['independent_translation']=direct
    return row

def verify(group,source,all_rows):
    keys={f's{x["n"]}':record(correct={'type':'boolean'},reason=STRING,parts=array(STRING),
              corrections=array(record(number={'type':'integer'},meaning=STRING))) for x in group}
    payload={'title':source['title'],'rows':[{'n':r['n'],'en':r['english_parts'],'zh':r['parts'],'comparison':r['independent_translation'],'vocabulary':[(i+1,v[0],v[3]) for i,v in enumerate(r['v'])]} for r in group]}
    for attempt in range(3):
        resp=request_json(VERIFY,payload,record(**keys),attempt);final=[];errors=[]
        for r in group:
            v=resp['s'+str(r['n'])];row=dict(r);row['v']=[list(x) for x in r['v']]
            if not v['correct']:
                if v['parts']:row['parts']=[x.strip() for x in v['parts']]
                for c in v['corrections']:
                    if 1<=c['number']<=len(row['v']):row['v'][c['number']-1][3]=c['meaning'].strip()
                changed=row['parts']!=r['parts'] or row['v']!=r['v']
                if not v['reason'].strip() or not changed:errors.append(r['n'])
            patch=corrections().get(str(r['n']))
            if patch:
                row['parts']=patch['parts']
                for term in row['v']:term[3]=patch['meanings'].get(term[0],term[3])
            row['zh']=''.join(row['parts'])
            if not good(r['en'],r['english_parts'],row['v'],row['parts'],[x[3] for x in row['v']],all_rows[r['n']-2]['en'] if r['n']>1 else ''):errors.append(r['n'])
            row['review_reason']=v['reason'].strip() if not v['correct'] else '';final.append(row)
        if not errors:return final
        payload['repair']='下列句号的核对回复缺少完整意群或词义，请按给定英文更正：'+str(sorted(set(errors)))
    raise ValueError(f'{PID}: unresolved second review for {errors}')

def editorial():
    source=read(PAPER);rows=read(PREP)['rows'];sentences=[s for g in source['paragraphs'] for s in g]
    if sentences!=[r['en'] for r in rows]:raise ValueError('Prepared vocabulary refers to other text')
    wp=work();assets=inventory(DRAFT);statefile=wp/(key()+'-work.json')
    if not statefile.exists() and statefile.name in assets:fetch(assets[statefile.name],wp)
    state=read(statefile) if statefile.exists() else {'id':PID,'key':key(),'drafted':[],'verified':[]}
    if state['key']!=key():raise ValueError('Checkpoint belongs to a different source')
    prior=old_terms()
    for i in range(len(state['drafted']),len(rows)):
        item=teach(i,source,rows[i],prior,sentences[i-1] if i else '',wp)
        state['drafted'].append(item);save(statefile,state)
        if (i+1)%10==0:
            subprocess.run(['gh','release','upload',DRAFT,str(statefile),'--clobber'],check=True)
        print(PID,'draft',i+1,'/',len(rows),flush=True)
    for i in range(len(state['verified']),len(rows),3):
        state['verified'].extend(verify(state['drafted'][i:i+3],source,rows));save(statefile,state)
        print(PID,'checked',len(state['verified']),'/',len(rows),flush=True)
    output(source,state['verified'])

def output(source,rows):
    LESSON.mkdir(parents=True,exist_ok=True)
    terms={};lines=[];cuts={};marks=[];i=0
    for group in source['paragraphs']:
        for en in group:
            r=rows[i];i+=1
            if r['en']!=en or ''.join(r['english_parts'])!=en:raise ValueError('Source sentence changed')
            gloss=[]
            for k,(form,head,pos,meaning) in enumerate(r['v']):
                gloss.append(form+'|'+(pos+' ' if pos and pos!='phr.' else '')+meaning);terms[f'{i}.{k}']=head
            lines.append('\t'.join([en,r['zh'],*gloss]))
            if len(r['english_parts'])>1:
                anchors=[]
                for s in r['english_parts'][1:]:
                    words=s.lstrip().split();anchor=next((' '.join(words[:n]) for n in range(2,len(words)+1) if en.count(' '.join(words[:n]))==1),None)
                    if not anchor:raise ValueError(f'Ambiguous boundary {PID}/{i}')
                    anchors.append(anchor)
                cuts[str(i)]={'at':anchors,'zh':r['parts']}
            if r['review_reason']:marks.append({'n':i,'reason':r['review_reason']})
        lines.append('')
    (LESSON/'双语精读.tsv').write_text('\n'.join(lines),encoding='utf-8');verify_original(PROJECT,PID)
    # The full titles are anchored to the paper; the short forms only occupy the chalkboard header.
    en_title=source['title'];zh_title=source['title_zh'];short_en=' '.join(en_title.split()[:5]);short_zh=zh_title.split('（')[0]
    if len(short_zh)>12:short_zh=short_zh[:11]+'…'
    meta={k:source[k] for k in ('id','book','test','passage','title','title_zh','pdf_pages')}
    known_names={name for row in corrections().values() for name in row['names']}
    meta.update(genre='剑桥雅思 · 学术阅读',header={'english':short_en,'chinese':short_zh},lemmas={},row_lemmas=terms,zh_names=sorted(known_names.union(confirmed_names(rows)),key=lambda name:(-len(name),name)),pronunciation={})
    save(LESSON/'篇目信息.json',meta);save(LESSON/'分屏.json',{PID:cuts})
    proof={'id':PID,'source_sha256':digest(PAPER),'candidate_sha256':digest(PREP),'editor_version':VERSION,'key':key(),'reading_units':len(rows),
           'vocabulary_entries':sum(len(r['v']) for r in rows),'split_sentences':len(cuts),'translation_review':{'sentences_checked':len(rows),'corrections':marks,
           'model_basis':'Independent sentence-only HY-MT reference, Qwen contextual editor and separate source-based correction; kept Chinese parts, surface forms and local meanings.'},
           'text_sha256':digest(LESSON/FILES[0]),'metadata_sha256':digest(LESSON/FILES[1]),'split_sha256':digest(LESSON/FILES[2]),'checked':False}
    save(LESSON/'content-review.json',proof);store_candidate()

def store_candidate():
    with zipfile.ZipFile(work()/(key()+'-teaching.zip'),'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in FILES:z.write(LESSON/name,name)
    subprocess.run(['gh','release','upload',DRAFT,str(work()/(key()+'-teaching.zip')),'--clobber'],check=True)

def restore():
    name=key()+'-teaching.zip';assets=inventory(DRAFT)
    if name not in assets:return False
    path=fetch(assets[name],work());LESSON.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path) as z:
        if set(z.namelist())!=set(FILES):raise ValueError('Unexpected teaching material')
        for f in FILES:(LESSON/f).write_bytes(z.read(f))
    p=read(LESSON/FILES[3])
    if p['key']!=key() or any(digest(LESSON/f)!=p[k] for f,k in zip(FILES[:3],('text_sha256','metadata_sha256','split_sha256'))):raise ValueError('Restored teaching material does not match paper')
    verify_original(PROJECT,PID);return True

def seal():
    report=read(PROJECT/'样片/review.json');p=read(LESSON/FILES[3]);screens=report['screens'][1:]
    if report['lesson']!=PID or report['problems'] or not screens:raise ValueError('Unresolved visual review')
    if len(screens)!=p['reading_units']+sum(len(s['at']) for s in read(LESSON/'分屏.json')[PID].values()):raise ValueError('Unexpected number of reading screens')
    p['checked']=True;p['mobile_layout']={'total_screens':len(screens)+1,'issues':0,'english_css_px':sorted({r['sizes'][0] for r in screens}),'vocabulary_css_px':sorted({r['sizes'][1] for r in screens})};save(LESSON/FILES[3],p)
    with zipfile.ZipFile(work()/(key()+'-reviewed.zip'),'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in FILES:z.write(LESSON/name,name)
    subprocess.run(['gh','release','upload',DRAFT,str(work()/(key()+'-reviewed.zip')),'--clobber'],check=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['restore','edit','seal','checkpoint','key']);args=parser.parse_args()
    if args.command=='restore': print('true' if restore() else 'false')
    if args.command=='edit':editorial()
    if args.command=='seal':seal()
    if args.command=='key':print(key())
    if args.command=='checkpoint':
        f=work()/(key()+'-work.json')
        if f.is_file():subprocess.run(['gh','release','upload',DRAFT,str(f),'--clobber'],check=True)
