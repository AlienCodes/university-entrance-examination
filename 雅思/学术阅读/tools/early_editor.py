"""Prepare the early-volume lessons from the checked paper and independently verify their teaching text."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

from draft_lesson import CJK, TEXT as STRING, record, request_json
from early_reference import collect as reference_readings
from lesson import LESSON, PID, PROJECT, save
from material import verify_original
from release_assets import fetch, inventory
from translation import translate_sentence

VERSION = 'paper-context-5.1'
PAPER_EDITION = 'paper-context-4'
DRAFT = 'ielts-academic-editorial-10-1'
FILES = ('双语精读.tsv', '篇目信息.json', '分屏.json', 'content-review.json')
PAPER = PROJECT/'原稿'/(PID+'.json')
PREP = PROJECT/'备课'/(PID+'.json')
POS = re.compile(r'^([a-z]+[.])\s+(.*)$', re.I)
NOISE = re.compile(r'术语与语境|\b(?:translation|original sentence|as an ai)\s*[:：]|以下是|译文如下|参考译文[：:]|原文[：:]|翻译[：:]|该句的|作为.{0,6}模型|\*\*|[<>]|[\r\n\t]', re.I)
CLAUSE = re.compile(
    r'[;:—–]\s+|,\s+(?=(?:the|a|an|we|they|he|she|it|this|these|those|one|some|others?|'
    r'and|but|although|despite|if|when|which|who|where|with|as|including|allowing|making|resulting|'
    r'leading|showing|giving|providing|according|using|built|known)\b)|'
    r'\s+(?=(?:but|whereas|although|because|while|which|who|whose|when|so that|in order to|'
    r'rather than|if|even though|as a result|such as|including|during the|in contrast to|'
    r'and (?:it|they|he|she|the)|for [a-z]+ing|to (?:provide|determine|obtain|ensure|enable|allow|help))\b)',re.I)
ZH_CLAUSE = re.compile(r'[，；：。！？]+[”’]?|(?=以便|从而|用于|以供|用来|供人|其中|因为|因此|同时|并且|而且|例如|包括|也就是|这意味着|而在|但却|然而)')
EDITOR = ('你是雅思学术阅读教材责任编辑。source中的每个英文意群依次翻成准确、简洁、自然的简体中文。'
 '英文是唯一依据。译全动作、否定、程度、数字、单位和逻辑，上一句只能帮助确定指代。严禁补写上一句的内容。'
 '机器参照可能错译或发挥，应主动纠正。parts中每一项只译给定的一段，相邻中文拼起来就是自然的一句话。'
 '保留与本文相符的专名、引用和年份。为每个实际词条给语境中的中文义，尽量2至8个汉字，写出最贴切的一义。'
 '只给教材正文和词条。')
CJK_POS = re.compile(r'^(?:名词|动词|形容词|副词|短语|n\.|v\.|adj\.|adv\.|phr\.)[：: ]*')
def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()

def corrections():
    return read(PROJECT/'审校/早期册语境校订.json').get(PID,{})

def teaching_notes(project,pid):
    source=project/'审校/逐篇语境重点-10至1.json'
    return read(source).get(pid,[]) if source.is_file() else []

def key_for(project,pid):
    manual=read(project/'审校/早期册语境校订.json').get(pid,{})
    paper=project/'原稿'/(pid+'.json')
    manual_complete=len(manual)==sum(map(len,read(paper)['paragraphs']))
    inputs=[digest(paper),digest(project/'备课'/(pid+'.json')),PAPER_EDITION if manual_complete else VERSION,manual]
    notes=teaching_notes(project,pid)
    if notes:inputs.append(notes)
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

def positions(sentence,surface):
    # Screen offsets must point into the printed string even after a unit symbol,
    # roman numeral or ellipsis that would expand under Unicode normalization.
    return [m.span() for m in re.finditer(r'(?<!\w)'+re.escape(surface)+r'(?!\w)',sentence,re.I)]

def boundaries(en,terms):
    blocked=[(a,b) for v in terms for a,b in positions(en,v['form'])]
    if len(en.split())<31 and len(en)<200 and len(terms)<=9:
        return []
    result=[]
    for hit in CLAUSE.finditer(en):
        at=hit.end()
        if any(a<at<b for a,b in blocked) or not any(b<=at for a,b in blocked) or not any(a>=at for a,b in blocked):continue
        intro=en[:at].strip()
        if len(intro.split())<=11 and intro.endswith(',') and re.match(r'^(?:during|in|by|at|since|between|from|on)\b',intro,re.I):continue
        if min(len(intro.split()),len(en[at:].split()))<6 or at in result:continue
        result.append(at)
    return result

def aligned_parts(en,zh,vocab):
    terms=[{'form':v[0]} for v in vocab]
    starts=boundaries(en,terms)
    offsets=sorted({m.end() for m in ZH_CLAUSE.finditer(zh) if 4<=m.end()<=len(zh)-4})
    if not starts or not offsets:return [en],[zh]
    ens={str(i):en[pos:pos+60] for i,pos in enumerate(starts,1)}
    zhs={str(i):zh[pos:pos+28] for i,pos in enumerate(offsets,1)}
    count=min(len(starts),len(offsets),max(1,min(6,(len(terms)+4)//7,len(en.split())//10)))
    fields={f'cut{i+1}':record(en={'type':'integer','enum':list(range(len(starts)+1))},
                              zh={'type':'integer','enum':list(range(len(offsets)+1))}) for i in range(count)}
    prompt={'English':en,'checked_Chinese':zh,'starts_in_English':ens,'starts_in_Chinese':zhs,'vocabulary':[v[0] for v in vocab]}
    instruction=('你只负责为已经审定的完整英中句子选择换屏点。每个英文编号与中文编号都表示后一屏的开头，'
                 '须属于同一意群。优先完整显示；需要分屏时，保留完整名词短语、并列修饰词、比较与动宾搭配。'
                 '不能让一个时间状语或词表项独占一屏。不确定两种语言是否恰好对应，就让整句同屏。不选的字段填两个0。')
    for attempt in range(2):
        answer=request_json(instruction,prompt,record(**fields),attempt,token_limit=220)
        pairs=[(v['en'],v['zh']) for v in answer.values() if v['en'] or v['zh']]
        if not pairs:break
        if all(i and j for i,j in pairs):
            es=[starts[i-1] for i,j in pairs];zs=[offsets[j-1] for i,j in pairs]
            if es==sorted(set(es)) and zs==sorted(set(zs)):
                chunks=[en[a:b] for a,b in zip([0]+es,es+[len(en)])]
                parts=[zh[a:b] for a,b in zip([0]+zs,zs+[len(zh)])]
                if (all(len(chunk.split())>=6 and any(positions(chunk,t['form']) for t in terms) for chunk in chunks)
                    and all(len(CJK.findall(part))>=4 for part in parts)):
                    return chunks,parts
        prompt['retry']='各切点要成对、顺序一致，每一屏都能按意思对上。如果找不到这样的切法，请填0。'
    return [en],[zh]

COLLOCATIONS=[
    (r'\b(?:am|is|are|was|were|be|been) based (?:at|in)\b','be based','以……为驻地'),
    (r'\bit is alleged\b','it is alleged','据称'),
    (r'\bcombined forces\b','combined forces','合力'),
    (r'\bput (?:it |this |that |them )(?:all )?down to\b','put … down to','将……归因于'),
    (r'\bthe four corners of the globe\b','the four corners of the globe','世界各地'),
    (r'\bat the whim of\b','at the whim of','随……的意愿'),
    (r'\bkeep(?:s|ing)? pace with\b|\bkept pace with\b','keep pace with','跟上'),
    (r'\b(?:pins?|pinned|pinning) down\b','pin down','确切地确定'),
    (r'\b(?:ruled?|rules|ruling) out\b','rule out','排除'),
    (r'\b(?:paves?|paved|paving) the way for\b','pave the way for','为……铺平道路'),
    (r'\b(?:sets?|setting) out on\b','set out on','动身踏上'),
    (r'\b(?:come|comes|came|coming) up with\b','come up with','想出；提出'),
    (r'\b(?:give|gives|gave|given|giving) rise to\b','give rise to','引起'),
    (r'\bat the expense of\b','at the expense of','以……为代价'),
    (r'\bin its own right\b','in its own right','凭其自身'),
    (r'\b(?:taking|takes?|took|taken) (?:it |this )?for granted\b','take for granted','视为理所当然'),
    (r'\bno longer\b','no longer','不再'),
    (r'\bnot necessarily\b','not necessarily','未必'),
    (r'\bat least as\b','at least as','至少同样'),
    (r'\bgain(?:s|ed|ing)? access to\b','gain access to','获得；得以使用'),
    (r'\bdry season\b','dry season','旱季'),
    (r'\bwatering animals\b','water animals','给牲畜饮水'),
    (r'\b(?:go|goes|went|going) beyond\b','go beyond','超出'),
    (r'\b(?:fall|falls|fallen|fell) into disuse\b','fall into disuse','逐渐废弃'),
    (r'\bwater table\b','water table','地下水位'),
    (r'\bsilt(?:s|ed|ing)? up\b','silt up','淤塞'),
    (r'\bin pristine condition\b','in pristine condition','处于完好状态'),
    (r'\bin terms of\b','in terms of','就……而言'),
    (r'\bas a result of\b','as a result of','由于'),
    (r'\bin response to\b','in response to','对……作出反应'),
    (r'\bin addition to\b','in addition to','除……之外还'),
    (r'\bas opposed to\b','as opposed to','与……相对'),
    (r'\bon the other hand\b','on the other hand','另一方面'),
    (r'\b(?:result|results|resulted|resulting) from\b','result from','由……造成'),
    (r'\b(?:result|results|resulted|resulting) in\b','result in','导致'),
    (r'\b(?:accounts?|accounted|accounting) for\b','account for','按文意区分“解释”“占”'),
    (r'\b(?:relies|relied|rely|relying) on\b','rely on','依靠'),
    (r'\b(?:keep(?:s|ing)?|kept) up with\b','keep up with','跟上'),
]

def vocabulary(row,prior,notes):
    en=row['en'];items=[]
    for pattern,head,meaning in COLLOCATIONS:
        hit=re.search(pattern,en,re.I)
        if hit:items.append(dict(form=hit[0],head=head,pos='phr.',dictionary=meaning))
    for hit in re.finditer(r'(?<![\w-])[A-Za-z]+(?:[-‑][A-Za-z]+)+(?![\w-])',en):
        items.append(dict(form=hit[0],head=hit[0],pos='',dictionary='完整复合词，按句法和语境给出词性和义项'))
    items.extend(dict(t) for t in row['candidates'])
    for entry in notes:
        phrase=entry['english'];spans=positions(en,phrase)
        if spans and 1<=len(phrase.split())<=4 and all(phrase.casefold()!=t['form'].casefold() for t in items):
            # A course note may describe an entire clause. Only use the short cue as a dictionary entry when its own sense is supplied.
            meaning=entry.get('meaning',entry['check'])
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

def fields(prefix,n):
    return [prefix+str(i+1) for i in range(n)]

def finite_response(instruction,payload,schema,limit):
    for trial in range(3):
        try:
            return request_json(instruction,payload,schema,trial,token_limit=limit)
        except (ValueError,TimeoutError):
            if trial==2:raise
            payload={**payload,'output_rule':'各字段只填一条简洁结果，严格按既有字段作答，不重复。'}

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

def gloss_value(value,fallback):
    text=value.strip()
    aliases={'a.':'adj.','ad.':'adv.','vt.':'v.','vi.':'v.','v.t.':'v.','v.i.':'v.','pl.':'n.','phrase.':'phr.'}
    allowed={'n.','v.','adj.','adv.','prep.','conj.','aux.','num.','pron.','phr.','abbr.','interj.'}
    pos=fallback
    for i in range(3):
        match=re.match(r'^([a-z.]{1,10}\.)\s*',text,re.I)
        if not match:break
        found=aliases.get(match[1].lower(),match[1].lower())
        if found not in allowed:break
        pos=found
        text=text[match.end():]
    return pos,CJK_POS.sub('',text.strip())

def revision(value):
    reject={'正确','无误','留空','空字符串','原译正确','无需修改','无须修改','不需修改','无需改动','不变','保持不变','同原文','N/A'}
    return '' if value.strip() in reject else value.strip()

# These explicit operators frequently disappear in a fluent Chinese paraphrase.
# Alternatives are reading cues, not a compulsory word-for-word translation.
SCOPE_CUES=(
    (r'\b(?:often|frequently)\b',r'常|往往|时常|屡|频|惯|多有|多半|大多|多数|每每|反复|多会|多为|不时|动辄|多见|多次|很多时候|许多时候','频率（常常、往往）'),
    (r'\b(?:sometimes|occasionally)\b',r'有时|偶|不时|间或|时而|有的|时有|也会|有些|有可能','偶尔或有时'),
    (r'\b(?:rarely|seldom)\b',r'少|罕|难得|不常|几乎[不没]|鲜|寥|不多|不大|很难|难以','少有、罕见'),
    (r'\bat least\b',r'至少|起码|不低于|不小于|不亚于|不逊|以上|最低|最少|下限|少说|少不了','最低限或至少'),
    (r'\bat most\b',r'至多|最多|不超过|不高于|不多于|以内|不过|顶多|仅|上限|充其量','最高限或至多'),
    (r'\bno longer\b',r'不再|再也不|已不|已经不|不复|再无|已无|已没有|已失去|失去|停止|结束|消失|取消|绝迹|已非|(?:不必|无需|不能|无法|不用|无力)再|已.{0,12}不(?:见|到|了|能|得|行|及)','不再'),
    (r'\bnot until\b',r'才|直到|直至|之前|以前|在此之前','直到……才'),
)

def scope_gaps(en,zh):
    if re.search(r'\b(?:how|less|more|as) (?:often|frequently)\b',en,re.I) and re.search(r'次|频|多久|多长时间|多少回|较[多低高少]',zh):
        en=re.sub(r'\b(?:how|less|more|as) (?:often|frequently)\b','',en,flags=re.I)
    return [label for pattern,equivalent,label in SCOPE_CUES
            if re.search(pattern,en,re.I) and not re.search(equivalent,zh)]

def ground_vocabulary(row,source,witness):
    """Resolve glosses without a visible equivalent against this individual sentence."""
    zh=row['zh'];en=row['en']
    exact={n['english'].casefold():n['meaning'] for n in source.get('language_review',[])
           if n.get('meaning') and n.get('scope_en',en)==en and n['english'].casefold() in en.casefold()}
    polysemy={'account','address','approach','charge','current','diet','drink','figure','fresh','maintain','matter',
              'novel','object','party','plant','population','present','record','scale','spring','state','stock','subject','survey',
              'sustain','track','train','trial','volume','water','yet','accommodate'}
    meanings=[v[3] for v in row['v']]
    uncertain=[]
    for v in row['v']:
        if v[0].casefold() in exact:v[3]=exact[v[0].casefold()]
        elif v[1].casefold() in polysemy or meanings.count(v[3])>1 or not all(x in zh for x in re.split(r'[；;，、]',v[3]) if x):uncertain.append(v)
    for off in range(0,len(uncertain),6):
        batch=uncertain[off:off+6]
        pos={'type':'string','enum':['n.','v.','adj.','adv.','prep.','conj.','phr.','pron.','det.','num.','aux.','abbr.','interj.']}
        schema=record(**{v[0]:record(pos=pos,equivalent=STRING,gloss=STRING) for v in batch})
        payload={'English':en,'reviewed_translation':zh,'second_reading':witness,
                 'words':{v[0]:v[1] for v in batch}}
        instruction=('只核对这一句的词义。逐个读取以实际英文词形命名的字段。先判断这个词在英文中的词性和所指。'
                     '如果审定译句中有适合单独背诵的对应短语，将其逐字摘入equivalent；不是同一意思或不能独立成义就填空。'
                     'gloss中始终只给当句最贴切的一义，一般2至8个汉字，不写“此处指”、释义列表、词性或整段说明。若几个并列词分别对应几个用途，应按顺序核对，不能把相邻一项的意思给当前词。短语的词性可填phr.。'
                     'second_reading可用于辨别指代，但摘录仅来自reviewed_translation。')
        for attempt in range(2):
            response=finite_response(instruction,payload,schema,140+len(batch)*68)
            selected=[];errors=[]
            for v in batch:
                ans=response[v[0]];quote=ans['equivalent'].strip();gloss=ans['gloss'].strip()
                usable=bool(quote and quote in zh and len(quote)<=12 and clean(quote)
                            and not re.search(r'[，,；;。？！：:、“”/|]',quote))
                val=quote if usable else gloss
                if not usable:
                    senses=[s.strip() for s in re.split(r'[，；、]',val)]
                    supported=[s for s in senses if len(s)>=2 and s in zh]
                    if len(senses)>1 and len(supported)==1:val=supported[0]
                if (not clean(val) or not 0<len(val)<=24 or re.search(r'[|；，、]|此处指|在此处|这里特指|本句中',val)):
                    errors.append(v[0])
                selected.append((ans['pos'],val))
            if not errors:break
            payload['repair']='这些词要给短的、能独立使用的语境义：'+'、'.join(errors)
        else:raise ValueError('Unresolved contextual glossary '+str(errors))
        for v,(pos,meaning) in zip(batch,selected,strict=True):v[2:]=[pos,meaning]

def confirmed_names(rows,known):
    registered=set(known)
    for r in rows:
        for zh in [r['zh'],*[v[3] for v in r['v']]]:
            locations=[m.start() for m in re.finditer(r'(?<=[\u4e00-\u9fff])·(?=[\u4e00-\u9fff])',zh)]
            def covered(i):
                return any(a<=i<a+len(n) for n in registered for a in [zh.find(n)] if a>=0) or any(
                    m.start()<=i<m.end() for n in registered for m in re.finditer(re.escape(n),zh))
            unknown=[i for i in locations if not covered(i)]
            if not unknown:continue
            keys=fields('name',len(unknown));samples={k:zh[max(0,i-10):i+13] for k,i in zip(keys,unknown)}
            ans=finite_response('根据英文和译文，为每个间隔号摘出包含它的完整中文音译专名，逐字复制译文，不包含周围的连词或标点。',
                {'English':r['en'],'Chinese':zh,'occurrences':samples},record(**dict.fromkeys(keys,STRING)),70+len(unknown)*48)
            for k in keys:
                word=ans[k].strip()
                if '·' in word and word in zh and len(word)<=32:registered.add(word)
            if not all(covered(i) for i in locations):raise ValueError(f'Unresolved transliterated name at {PID}/{r["n"]}')
    return sorted(registered,key=lambda name:(-len(name),name))

def teach(index,source,prep,prior,previous,workdir):
    n=index+1;en=prep['en']
    patch=corrections().get(str(n))
    if patch:
        anchors=patch.get('cuts',[])
        if patch['en']!=en or any(en.count(a)!=1 for a in anchors):
            raise ValueError(f'Manual translation no longer matches {PID}/{n}')
        marks=[en.index(a) for a in anchors]
        chunks=[en[a:b] for a,b in zip([0]+marks,marks+[len(en)])]
        terms=patch['terms']
        spans=[positions(en,t[0]) for t in terms]
        if (marks!=sorted(set(marks)) or not all(spans) or
                any(a<cut<b for offsets in spans for a,b in offsets for cut in marks) or
                not all(any(positions(chunk,t[0]) for t in terms) for chunk in chunks) or
                not good(en,chunks,terms,patch['parts'],[t[3] for t in terms],previous)):
            raise ValueError(f'Manual translation, vocabulary or screen boundary differs from {PID}/{n}')
        return dict(n=n,en=en,zh=''.join(patch['parts']),parts=patch['parts'],english_parts=chunks,v=terms,
                    independent_translation='',paper_edited=True)
    notes=[a for a in source.get('language_review',[]) if a.get('scope_en',en)==en and a['english'].casefold() in en.casefold()]
    terms=vocabulary(prep,prior.get(en,[]),notes)
    if not terms:raise ValueError(f'{PID} sentence {n} lacks a teachable entry')
    chunks=[en]
    try:
        direct=translate_sentence(en,'',[],[])
    except ValueError:
        direct=''
    if not clean(direct):direct=''
    phrases=fields('p',len(chunks));words=fields('w',len(terms))
    schema=record(translation=record(**dict.fromkeys(phrases,STRING)),vocabulary=record(**dict.fromkeys(words,STRING)))
    data={'passage':source['title'],'English':dict(zip(phrases,chunks)),
          'words':{k:[t['form'],t['head'],t.get('pos',''),t.get('dictionary','')[:115],
                         prep['term_hints'].get(t['form'],t.get('earlier_sense',''))] for k,t in zip(words,terms)},
          'paper_notes':[a['check'] for a in notes]}
    # The paper context is already represented by its title and scoped terms.
    # Keep the previous sentence out of the translation prompt to avoid carrying its quantities over.
    instruction=(EDITOR+' 先作为整句理解全文。translation的p1只写一次整句译文，不重复分句，紧贴主从关系。准确处理原文的单位、地点、比较和从属关系。'
                 '只表达英文所含的程度、语气与目的。vocabulary每个w字段只写这个词此处的中文义。'
                 '格式是英语词性加一个空格再加当句中文义，例如 v. 记录。按句法核对词性。普通助动词可留空，其余重要词与搭配请写全。')
    for attempt in range(3):
        answer=finite_response(instruction,data,schema,min(2700,max(350,155+len(en)//2+len(terms)*31)))
        zh=[answer['translation'][k].strip() for k in phrases]
        senses=[gloss_value(answer['vocabulary'][k],t.get('pos','')) for k,t in zip(words,terms)]
        values=[val for pos,val in senses]
        keep=[i for i,x in enumerate(values) if x]
        for nte in notes:
            for i,t in enumerate(terms):
                if nte.get('meaning') and t['form'].casefold()==nte['english'].casefold():
                    values[i]=nte['meaning']
                    if i not in keep:keep.append(i)
        keep.sort();chosen=[{**terms[i],'pos':senses[i][0]} for i in keep];meanings=[values[i] for i in keep]
        if chosen and good(en,chunks,chosen,zh,meanings,previous) and all(any(positions(ch,t['form']) for t in chosen) for ch in chunks):break
        data['repair']='每一段要有忠实的中文和与本段英文对应的核心词。从全部候选中保留足够多的实词和搭配，只写简短语境义。'
    else:raise ValueError(f'{PID} sentence {n}: unusable initial translation or gloss')
    row=assemble(n,en,zh,chosen,meanings);row['english_parts']=chunks;row['independent_translation']=direct
    return row

def verify(group,source,all_rows,witness=None):
    manual={r['n']:dict(r,review_reason='依据原句逐词核定词形、语境义和完整译文。') for r in group if r.get('paper_edited')}
    auto=[r for r in group if r['n'] not in manual]
    if not auto:return [manual[r['n']] for r in group]
    items={};schema={}
    for r in auto:
        k='s'+str(r['n'])
        items[k]={'English':r['en'],'draft':r['zh'],'independent_translation':r['independent_translation'],
                  'second_reading':(witness or {}).get(r['n'],''),
                  'paper_notes':[x['check'] for x in source.get('language_review',[]) if x.get('scope_en',r['en'])==r['en'] and x['english'].casefold() in r['en'].casefold()]}
        schema[k]=record(translation=STRING,reason=STRING)
    instruction=('你在为精读教材定稿。独立核对每一条英文原句、初译和两个参照。以英文为准，'
                 '核对主从和修饰关系、指代、否定、时间、数值、单位与限定词；既不遗漏，也不补写原句没有的原因、目的或程度。'
                 'translation始终给完整、自然的一句或一组中文，且每一层意思只写一次。已妥当的初译可原样保留，不可照搬参照。'
                 '若修正了明确错误，reason简述依据，否则留空。')
    payload={'passage':source['title'],'sentences':items}
    for attempt in range(3):
        resp=finite_response(instruction,payload,record(**schema),max(380,min(2300,210+sum(len(r['en'])*2 for r in auto))))
        checked=dict(manual);errors=[]
        for r in auto:
            answer=resp['s'+str(r['n'])];row=dict(r);row['v']=[list(x) for x in r['v']]
            zh=revision(answer['translation']) or r['zh']
            gaps=scope_gaps(r['en'],zh)
            if gaps or not good(r['en'],[r['en']],row['v'],[zh],[x[3] for x in row['v']],all_rows[r['n']-2]['en'] if r['n']>1 else ''):
                errors.append((r['n'],gaps));continue
            row['zh']=zh;row['parts']=[zh];row['english_parts']=[r['en']]
            row['review_reason']=revision(answer['reason']) if zh!=r['zh'] else ''
            if zh!=r['zh'] and not row['review_reason']:row['review_reason']='据本句英文修订整句译文。'
            checked[r['n']]=row
        if not errors:break
        payload['repair']='逐句查补上次译文漏掉的程度、频率或范围，再给完整译文。保留原文语气。需复核的字段：'+str(errors)
    else:raise ValueError(f'{PID}: no valid source-based translation at {errors}')
    for r in auto:
        row=checked[r['n']]
        ground_vocabulary(row,source,(witness or {}).get(r['n'],''))
        changed=[(old[0],old[3],new[3]) for old,new in zip(r['v'],row['v']) if old[2:]!=new[2:]]
        if changed:row['review_reason']+=' 词义、词性对照本句复核：'+'、'.join(x[0] for x in changed)+'。'
        row['english_parts'],row['parts']=aligned_parts(row['en'],row['zh'],row['v'])
    return [checked[r['n']] for r in group]

def editorial():
    source=read(PAPER);rows=read(PREP)['rows'];sentences=[s for g in source['paragraphs'] for s in g]
    notes=teaching_notes(PROJECT,PID)
    if any(sentences[n['sentence']-1]!=n['scope_en'] for n in notes):raise ValueError('A teaching note refers to another sentence')
    source['language_review']=source.get('language_review',[])+notes
    if sentences!=[r['en'] for r in rows]:raise ValueError('Prepared vocabulary refers to other text')
    wp=work();assets=inventory(DRAFT);statefile=wp/(key()+'-work.json')
    if not statefile.exists() and statefile.name in assets:fetch(assets[statefile.name],wp)
    state=read(statefile) if statefile.exists() else {'id':PID,'key':key(),'drafted':[],'verified':[]}
    if state['key']!=key():raise ValueError('Checkpoint belongs to a different source')
    prior=old_terms()
    for i in range(len(state['drafted']),len(rows)):
        item=teach(i,source,rows[i],prior,sentences[i-1] if i else '',wp)
        state['drafted'].append(item);save(statefile,state)
        if i+1 in {3,7} or (i+1)%10==0:
            subprocess.run(['gh','release','upload',DRAFT,str(statefile),'--clobber'],check=True)
        print(PID,'draft',i+1,'/',len(rows),flush=True)
    witness=reference_readings(source,wp)
    for i in range(len(state['verified']),len(rows),3):
        state['verified'].extend(verify(state['drafted'][i:i+3],source,rows,witness));save(statefile,state)
        if len(state['verified'])%9==0:
            subprocess.run(['gh','release','upload',DRAFT,str(statefile),'--clobber'],check=True)
        print(PID,'checked',len(state['verified']),'/',len(rows),flush=True)
    output(source,state['verified'],len(witness))

def output(source,rows,reference_count):
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
    en_title=source['title'];zh_title=source['title_zh'];short_en=' '.join(en_title.split()[:5])+('…' if len(en_title.split())>5 else '');short_zh=zh_title.split('（')[0]
    if len(short_zh)>12:short_zh=short_zh[:11]+'…'
    meta={k:source[k] for k in ('id','book','test','passage','title','title_zh','pdf_pages')}
    known_names={name for row in corrections().values() for name in row['names']}
    meta.update(genre='剑桥雅思 · 学术阅读',header={'english':short_en,'chinese':short_zh},lemmas={},row_lemmas=terms,zh_names=confirmed_names(rows,known_names),pronunciation={})
    save(LESSON/'篇目信息.json',meta);save(LESSON/'分屏.json',{PID:cuts})
    proof={'id':PID,'source_sha256':digest(PAPER),'candidate_sha256':digest(PREP),'editor_version':VERSION,'paper_note_revision':os.getenv('IELTS_NOTES_REVISION',''),'key':key(),'reading_units':len(rows),
           'vocabulary_entries':sum(len(r['v']) for r in rows),'split_sentences':len(cuts),'translation_review':{'sentences_checked':len(rows),'paper_edited_sentences':sum(bool(r.get('paper_edited')) for r in rows),'aligned_independent_readings':reference_count,'corrections':marks,
           'model_basis':'Complete English sentences are drafted and reviewed before read-only bilingual segmentation. Alternative readings are consulted alongside the paper. Paper-edited lines retain their confirmed translation and glossary.'},
           'text_sha256':digest(LESSON/FILES[0]),'metadata_sha256':digest(LESSON/FILES[1]),'split_sha256':digest(LESSON/FILES[2]),'checked':False}
    save(LESSON/'content-review.json',proof);store_candidate()

def store_candidate():
    with zipfile.ZipFile(work()/(key()+'-teaching.zip'),'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in FILES:z.write(LESSON/name,name)
    subprocess.run(['gh','release','upload',DRAFT,str(work()/(key()+'-teaching.zip')),'--clobber'],check=True)

def restore():
    fingerprint=key()
    local=(LESSON/FILES[3]).is_file() and all((LESSON/f).is_file() for f in FILES[:3])
    if not local or read(LESSON/FILES[3]).get('key')!=fingerprint:
        name=fingerprint+'-teaching.zip';assets=inventory(DRAFT)
        if name not in assets:return False
        path=fetch(assets[name],work());LESSON.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(path) as z:
            if set(z.namelist())!=set(FILES):raise ValueError('Unexpected teaching material')
            for f in FILES:(LESSON/f).write_bytes(z.read(f))
    p=read(LESSON/FILES[3])
    if p['key']!=fingerprint or p['source_sha256']!=digest(PAPER) or p['candidate_sha256']!=digest(PREP) or any(digest(LESSON/f)!=p[k] for f,k in zip(FILES[:3],('text_sha256','metadata_sha256','split_sha256'))):raise ValueError('Restored teaching material does not match paper')
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
