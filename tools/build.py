import json,re,os,sys,html
S=json.load(open('sents.json'))
IRR={'be':'is are was were been being am','have':'has had having','do':'does did done doing','go':'goes went gone going',
'make':'made','take':'took taken','give':'gave given','find':'found','come':'came','bring':'brought','think':'thought','buy':'bought',
'keep':'kept','hold':'held','lead':'led','leave':'left','fall':'fell fallen','rise':'rose risen','grow':'grew grown','know':'knew known',
'show':'shown','spend':'spent','send':'sent','build':'built','begin':'began begun','break':'broke broken','choose':'chose chosen',
'draw':'drew drawn','drive':'drove driven','eat':'ate eaten','fly':'flew flown','forget':'forgot forgotten','get':'got gotten',
'hide':'hid hidden','lie':'lay lain','lose':'lost','mean':'meant','meet':'met','pay':'paid','run':'ran','say':'said','see':'saw seen',
'sell':'sold','shake':'shook shaken','speak':'spoke spoken','stand':'stood','strike':'struck','teach':'taught','tell':'told',
'throw':'threw thrown','understand':'understood','wake':'woke woken','wear':'wore worn','win':'won','write':'wrote written',
'seek':'sought','catch':'caught','fight':'fought','feel':'felt','hear':'heard','sit':'sat','sleep':'slept','spring':'sprang sprung',
'undertake':'undertook undertaken','withdraw':'withdrew withdrawn','arise':'arose arisen','bear':'bore borne born','bind':'bound',
'dig':'dug','feed':'fed','flee':'fled','freeze':'froze frozen','hang':'hung','lay':'laid','light':'lit','ride':'rode ridden',
'shine':'shone','shoot':'shot','slide':'slid','spin':'spun','steal':'stole stolen','stick':'stuck','sweep':'swept','swing':'swung',
'tear':'tore torn','mislead':'misled','overcome':'overcame','become':'became','forbid':'forbade forbidden','sink':'sank sunk',
'swim':'swam swum','ring':'rang rung','sing':'sang sung','drink':'drank drunk','overtake':'overtook overtaken','undergo':'underwent undergone',
'phenomenon':'phenomena','criterion':'criteria','analysis':'analyses','hypothesis':'hypotheses','child':'children','mouse':'mice',
'leaf':'leaves','life':'lives','half':'halves','woman':'women','man':'men','tooth':'teeth','foot':'feet','shelf':'shelves','thief':'thieves',
'datum':'data','medium':'media','good':'better best','bad':'worse worst','well':'better best','far':'further farther furthest'}
V='aeiou'
def variants(w):
    w=w.lower(); s={w}
    s|=set(IRR.get(w,'').split())
    s|={w+'s',w+'es',w+'ed',w+'d',w+'ing',w+'er',w+'est',w+'r',w+'st',w+"'s",w+'’s'}
    if w.endswith('e'): s|={w[:-1]+'ing'}
    if w.endswith('ie'): s|={w[:-2]+'ying'}
    if w.endswith('y') and len(w)>1 and w[-2] not in V: s|={w[:-1]+'ies',w[:-1]+'ied',w[:-1]+'ier',w[:-1]+'iest'}
    if w.endswith('f'): s|={w[:-1]+'ves'}
    if w.endswith('fe'): s|={w[:-2]+'ves'}
    if len(w)>=3 and w[-1] not in V+'wxy' and w[-2] in V and w[-3] not in V: s|={w+w[-1]+'ed',w+w[-1]+'ing',w+w[-1]+'er',w+w[-1]+'est'}
    if w.endswith('c'): s|={w+'ked',w+'king'}
    if w.endswith('meter'): s|={w[:-5]+'metre',w[:-5]+'metres'}
    return s
def tokre(t):
    if t in ('sb.','sth.','sb','sth'): return r"[\w’'-]+(?:\s+[\w’'-]+){0,3}"
    vs=sorted(variants(t),key=len,reverse=True)
    return '(?:'+'|'.join(re.escape(v).replace("\\'","['’]").replace('’',"['’]") for v in vs)+')'
def seqre(phrase):
    toks=phrase.split()
    return r'(?<![\w-])'+r'[\s-]+'.join(tokre(t) for t in toks)+r'(?![\w-])'
def find(entry,sent,taken):
    I=re.I
    if entry.get('surf'):
        # 原文写法可用“…”表示中间隔开的词，如 pay attention to{pay…attention to}
        parts=[r'(?<![\w-])'+re.escape(x.strip()).replace('’',"['’]")+r'(?![\w-])' for x in entry['surf'].split('…')]
    else:
        parts=[seqre(p.strip()) for p in entry['h'].split('…')]
    spans=[];pos=0
    for p in parts:
        m=None
        for mm in re.finditer(p,sent,I):
            if mm.start()<pos: continue
            if any(not(mm.end()<=a or mm.start()>=b) for a,b in taken): continue
            m=mm;break
        if not m: return None
        spans.append((m.start(),m.end()));pos=m.end()
    if len(spans)>1 and spans[-1][0]-spans[0][1]>80: return None
    return spans
ENT=re.compile(r'^([*~]?)(.+?)(?:\{(.+?)\})?=(.+)$')
def parse(path):
    meta={};sents={}
    cur=None
    for line in open(path):
        line=line.rstrip('\n')
        if not line.strip(): continue
        if line[:2] in ('T:','G:','S:'): meta[line[0]]=line[2:].strip(); continue
        m=re.match(r'^(\d+) (.+)$',line)
        if m: cur=int(m.group(1)); sents[cur]={'zh':m.group(2).strip(),'w':[]}; continue
        if line.startswith('='):
            for e in line[1:].split(' | '):
                e=e.strip()
                if not e: continue
                mm=ENT.match(e)
                if not mm: print('BAD ENTRY',path,e); continue
                tier={'':'core','*':'ext','~':'phr'}[mm.group(1)]
                sents[cur]['w'].append({'t':tier,'h':mm.group(2).strip(),'surf':mm.group(3),'m':mm.group(4).strip()})
    return meta,sents
out=[];errs=0
# 踩坑记录：原文排版问题（直引号、引号内侧空格、标点后缺空格、括号前缺空格、在人名缩写处断句）
TYPO=[(r'"','直引号'),(r"'",'直撇号'),(r'“\s|\s”','引号内侧空格'),(r'(?<=[A-Za-z])[,;:](?=[A-Za-z“])','标点后缺空格'),
      (r'(?<=[A-Za-z])\((?=[A-Za-z])','括号前缺空格'),(r'(?:^|\s)[A-HJ-Z]\.$','在人名缩写处断句'),(r'\b(\w+) \1\b','重复单词')]
for o in S:
    for k,s_ in enumerate([x for p in o['sents'] for x in p],1):
        for pat,name in TYPO:
            m=re.search(pat,s_)
            if m and not (name=='重复单词' and m.group(1).lower() in ('that','had','is')):
                print(f'排版检查未通过：{o["id"]} 第{k}句 {name}：{s_[:80]}'); errs+=1
for o in S:
    pid=o['id'];p=f'ann/{pid}.txt'
    rec={k:o[k] for k in ('id','year','paper','part','words','file')}
    rec['name']=f"{o['year']} {o['paper']} 阅读{o['part']}"
    flat=[s for para in o['sents'] for s in para]
    if not os.path.exists(p):
        rec['done']=False
        rec['paras']=[[{'en':en,'zh':'','w':[]} for en in para] for para in o['sents']]
        rec['nv']=0
        out.append(rec); continue
    meta,ann=parse(p)
    rec.update(done=True,title=meta.get('T',''),genre=meta.get('G',''),summary=meta.get('S',''))
    if len(ann)!=len(flat): print(pid,'sentence count mismatch',len(ann),len(flat)); errs+=1
    paras=[];k=0
    for para in o['sents']:
        P=[]
        for en in para:
            k+=1; a=ann.get(k,{'zh':'','w':[]})
            taken=[];words=[]
            for e in sorted(a['w'],key=lambda e:-len(e['h'])):
                sp=find(e,en,taken)
                if sp is None: print(f'NOT FOUND {pid} s{k}: {e["h"]} {e.get("surf") or ""} || {en[:90]}'); errs+=1; continue
                taken+=sp; e['sp']=sp
            for e in a['w']:
                if 'sp' in e: words.append({'t':e['t'],'h':e['h'],'m':e['m'],'sp':e['sp']})
            P.append({'en':en,'zh':a['zh'],'w':words})
        paras.append(P)
    rec['paras']=paras
    # 铁律：每一句至少标出一个单词
    empty=[i+1 for i,x in enumerate(s for P in paras for s in P) if not x['w']]
    if empty: print(f'铁律检查未通过：{pid} 第 {empty} 句没有标注任何单词'); errs+=1
    rec['nv']=sum(len(s['w']) for P in paras for s in P)
    out.append(rec)
# word bank
bank={}
for r in out:
    if not r.get('done'): continue
    for pi,P in enumerate(r['paras']):
        for si,s in enumerate(P):
            for w in s['w']:
                key=w['h'].lower()
                b=bank.setdefault(key,{'h':w['h'],'t':w['t'],'m':[],'src':[]})
                if w['m'] not in b['m']: b['m'].append(w['m'])
                if r['id'] not in b['src']: b['src'].append(r['id'])
# frequency across all 70 passages' raw text
allsent={o['id']:[s for para in o['sents'] for s in para] for o in S}
for key,b in bank.items():
    pat=r'.{0,60}?'.join(seqre(x.strip()) for x in b['h'].split('…'))
    rx=re.compile(pat,re.I)
    b['freq']=[pid for pid,ss in allsent.items() if any(rx.search(x) for x in ss)]
# 音频（tools/tts 生成）：audio/timings.json -> 每篇的文件路径和逐句起止时间
tp='../audio/timings.json'
if os.path.exists(tp):
    T=json.load(open(tp))
    for r in out:
        for v,ps in T.items():
            if r['id'] in ps:
                a=ps[r['id']]
                r.setdefault('audio',{})[v]={'file':'audio/'+a['file'],'dur':a['duration'],'s':[[x['k'],x['start'],x['end']] for x in a['sentences']]}
data={'passages':out,'bank':sorted(bank.values(),key=lambda b:(-len(b['freq']),b['h'].lower()))}
json.dump(data,open('../data/vocab.json','w'),ensure_ascii=False)
tpl=open('template.html').read().replace('/*__SCRIPT__*/',open('page.js').read())
open('../index.html','w').write(tpl.replace('/*__DATA__*/null',json.dumps(data,ensure_ascii=False).replace('</','<\\/')))
done=[r for r in out if r.get('done')]
if errs: raise SystemExit(f'有 {errs} 处错误，未生成网页')
print('passages done',len(done),'vocab',sum(r['nv'] for r in done),'bank',len(bank),'errors',errs)
for r in done: print(r['name'],r['words'],'词 标注',r['nv'])
