"""本批译注草稿的可复现提取/自动span辅助；只提取指定原文区，不把OCR当定稿。"""
import json
from pathlib import Path
import re

D=Path(__file__).resolve().parents[1]
SPECS={
2022:[('A','Fields and Branches of Anthropology','Good morning, everyone.','\n1. economist'),
      ('B1','Interview 1','Today we are having Harriet','\n1. Why does'),
      ('B2','Interview 2','Welcome to this edition','\n6. What does')],
2023:[('A','Metaphors in Speaking','Good morning, everyone.','\n1. thought'),
      ('B1','Part One of the Interview','Good evening, everybody.','\n1. What is'),
      ('B2','Part Two of the Interview','Now, Jim, you said','\n6. What does')],
2024:[('A','Why is it harder to learn a second language?','Good morning, everyone.','\n1. natural'),
      ('B1','Interview One','Hello, Barry, nice','\n1. How does'),
      ('B2','Interview Two','Antarctica, a continent','\nHow much does Antarctica')]
}


def clean(raw):
    lines=[]
    for line in raw.splitlines():
        s=line.strip()
        if not s or '原PDF第' in s or re.search('华|专 八',s):continue
        if re.fullmatch(r'[=<>xMWwm:s：\s\d.!‘’“”"©]+',s):continue
        if re.search(r'202[234]\s*-\s*1[1-6]',s):continue
        if re.match(r'^[#£€&)]?[)\\/\s]+202[234]',s):continue
        s=re.sub(r'^[‘’“”\'" ]*[MW]\s*:\s*','',s)
        s=re.sub(r'^:\s*','',s)
        s=re.sub(r'\[(?:\d+|[lI])\s*\]','',s)
        s=re.sub(r'\[\d+[J)]','',s)
        s=re.sub(r'\s+©$','',s)
        lines.append(s)
    s=' '.join(lines)
    s=s.replace('[2]Jand','and').replace('Jand that','and that').replace('Because_we','Because we').replace('but_you','but you')
    s=s.replace('year- long','year-long')
    # 以下仅订正已逐页查看扫描图确认的OCR错误；扫描原稿疑误另列待核。
    for old,new in {
      'hwman':'human','about. the definition':'about the definition',
      '? / The answer':'? The answer','this, ve enlisted':"this, I've enlisted",
      'abilities, ‘and':'abilities, and',"you ve done":"you’ve done",
      'gapyear. com':'gapyear.com','[We also':'We also',
      'processing: And':'processing. And','learning than , grownups':'learning than grownups',
      'acquisition. ， The third':'acquisition. The third', 'that /a number':'that a number',
      "first language ‘acquisition":"first language acquisition", "That’ is":"That is",
      'T like them':'I like them','whether it. is':'whether it is',"I’'d say":"I’d say",
      'toward , fantasy':'toward fantasy','turn away . in':'turn away in',
      'this _ particular':'this particular','risé':'rise','places. , Also':'places. Also',
    }.items():s=s.replace(old,new)
    s=s.replace('_to,','to,').replace('from. Antarctica','from Antarctica').replace('a. few','a few')
    return re.sub(r'\s+',' ',s).strip()


def sentences(text):
    # 本批没有需跨句断开的姓名缩写；句内引用后的句界也保留。
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z“])|(?<=[.!?][”"])\s+(?=[A-Z“])',text) if s.strip()]


def extract(year):
    source=(D/f'来源/{year}/解析.txt').read_text('utf-8');units=[]
    for code,title,start,end in SPECS[year]:
        a=source.index(start);b=source.index(end,a)
        text=clean(source[a:b])
        # root授权：双路ASR/原扫描对照后修正，不按常识改造真实口语。
        fixes={2022:{'stating once again the anthropology':'stating once again that anthropology'},
               2023:{},
               2024:{'adults and adolescence':'adults and adolescents','I knew that there are':'I know that there are','that is a language translation.':'that is, uh, language translation.'}}
        for old,new in fixes[year].items():text=text.replace(old,new)
        en=sentences(text)
        units.append({'code':code,'title':title,'en':en})
    return units


def vocabulary(en,lexicon):
    occupied=[];out=[]
    for head,meaning,surfaces in sorted(lexicon,key=lambda x:-max(map(len,x[2]))):
        found=[]
        for surf in surfaces:
            for m in re.finditer(r'(?<![A-Za-z])'+re.escape(surf)+r'(?![A-Za-z])',en,re.I):
                a,b=m.span()
                if all(b<=x or a>=y for x,y in occupied):found.append([a,b]);occupied.append((a,b))
        if found:out.append({'t':'phr' if ' ' in head else 'word','h':head,'m':meaning,'sp':sorted(found)})
    return sorted(out,key=lambda w:w['sp'][0])


# 仅合并同一话轮中的极短口语过渡；不丢字、不跨换人边界。
MERGES={
 (2022,'A'):[(24,25)],
 (2022,'B1'):[(15,16),(17,18),(34,36)],
 (2022,'B2'):[(30,31)],
 (2023,'A'):[(43,44),(63,64)],
 (2023,'B1'):[(3,4),(5,6),(7,8),(23,24),(37,38)],
 (2023,'B2'):[(3,6),(10,11),(17,18),(21,22),(34,35)],
 (2024,'B1'):[(17,18),(24,25),(27,28),(32,33)],
 (2024,'B2'):[(12,13),(27,28),(32,33),(37,38)],
}
PAGES={2022:{'A':[1,2],'B1':[3,4],'B2':[4,5]},
       2023:{'A':[1,2],'B1':[3,4],'B2':[4,5]},
       2024:{'A':[1,2],'B1':[3,4],'B2':[4,5,6]}}
PENDING={}
AUDIO_NOTES={
 (2022,'A'):['the anthropology→that anthropology：主ASR与独立Whisper在138—156s均清楚为that；原PDF误印。'],
 (2023,'A'):['fossil metaphor：扫描与两路ASR一致，保留真实表达，不按常识重写before。'],
 (2023,'B1'):['a year sharp spent：扫描与两路ASR均为sharp，按root裁决保留真实口语，不擅改为gap或about；译文按间隔年时长及后文工作/志愿经历表达。','To put it simple、employers care most：扫描及两路ASR均一致；保留实际口语，不擅自补simply/about。'],
 (2023,'B2'):['Oh, I see：原PDF省Oh，真实主ASR1421—1427s有Oh，按root授权恢复。'],
 (2024,'A'):['adolescence→adolescents：主ASR及独立Whisper251—262s一致为adolescents；原稿名词误印。','仅末段that is a language translation改为that is, uh, language translation：448—465s主ASR为uh，独立Whisper无冠词，按root核定作犹豫音；前段147s原本无a的句子没有修改。'],
 (2024,'B1'):['minor novels：原扫描及独立Whisper961—973s确认原词；按较少受关注的小说理解，未照解析添出篇幅/结构特征。'],
 (2024,'B2'):['I knew→I know：两路ASR1289—1301s一致为know；原稿时态误印。','the Antarctica’s、Also the effects等扫描表达经两路ASR确认；保留真实冠词/口语断句，不重写成另一句话。','three times faster/six inches/three feet/six feet均已与实际主ASR对应；三倍表述按该气候新闻通常用义译。'],
}



def annotated(en,zh,terms):
    lex=[]
    for item in terms.split('|'):
        if item=='-':continue
        surface,meaning=item.split('=',1)
        surface,sep,head=surface.partition('~')
        lex.append((head or surface,meaning,[surface]))
    w=vocabulary(en,lex)
    assert len(w)==len(lex),(en,lex,w)
    return {'en':en,'zh':zh,'w':w}


def build(year):
    from 精听草稿文本 import DATA,QUESTIONS
    source=D/f'来源/{year}/解析.txt'
    header=source.read_text('utf-8').splitlines()
    pdf=header[0].removeprefix('来源：');sha=header[1].removeprefix('SHA256：')
    units=[]
    for base in extract(year):
        code=base['code'];rows=[r.split('\t') for r in DATA[year][code].strip().splitlines()]
        assert len(rows)==len(base['en']),(year,code,len(rows),len(base['en']))
        original=[annotated(en,*row) for en,row in zip(base['en'],rows)]
        groups=dict(MERGES.get((year,code),[]));out=[];i=1
        while i<=len(original):
            end=groups.get(i,i);parts=original[i-1:end]
            en=' '.join(p['en'] for p in parts);zh=''.join(p['zh'] for p in parts)
            w=[];offset=0
            for p in parts:
                for old in p['w']:
                    v=dict(old);v['sp']=[[a+offset,b+offset] for a,b in old['sp']];w.append(v)
                offset+=len(p['en'])+1
            out.append({'en':en,'zh':zh,'w':w,'source_sentence_range':[i,end]});i=end+1
        assert ' '.join(s['en'] for s in out)==' '.join(base['en']),'正文覆盖出现损失'
        body_count=len(out)
        if code!='A':
            for n,(en,zh,terms) in enumerate(QUESTIONS[year][code],1 if code=='B1' else 6):
                q=annotated(en,zh,terms);q.update(role='question',n=n);out.append(q)
        for s in out:
            assert s['w'] and s['zh'],(year,code,s)
            assert not re.search(r'\[\d|=s|原PDF|详解|202[234]\s*-\s*1[1-6]',s['en'])
            occupied=[]
            for w in s['w']:
                for a,b in w['sp']:
                    assert 0<=a<b<=len(s['en'])
                    assert not any(a<y and b>x for x,y in occupied)
                    occupied.append((a,b))
        units.append({
            'id':f'{year}-{code}','section':'Section A' if code=='A' else 'Section B Part '+('One' if code=='B1' else 'Two'),
            'title':base['title'],'names':[x for x in {2022:['保罗·博汉南','芭芭拉·米勒','玛格丽特·米德','克莱德·克拉克洪','哈丽雅特·桑福德','苏珊·康罗伊'],2023:['埃尔维斯·普雷斯利','拉尔夫·沃尔多·爱默生','弗朗西斯·培根','吉姆·约翰逊'],2024:['本杰明·约翰逊']}[year] if any(x in s['zh'] or any(x in w['m'] for w in s['w']) for s in out)],
            'source_refs':[{'path':str(source.relative_to(D)),'original_pdf':pdf,'sha256':sha,
                            'pdf_pages':PAGES[year][code],
                            'verified_against':'原PDF页图逐篇查看；正文及B部末尾题干，未混入参考答案或解题说明'}],
            'sentences':out,'待核':PENDING.get((year,code),[]),'原音核实记录':AUDIO_NOTES.get((year,code),[]),
            'review':{'status':'draft','basis':'扫描原文及原PDF页图；疑文已对照真实主ASR/独立Whisper；人工逐句中译、语境词汇，尚待整篇原声对齐与译注复核。',
                      'body_sentences':body_count,'question_stems':0 if code=='A' else 5},
        })
    return {'year':year,'units':units}


def write_drafts(years=(2022,2023,2024)):
    for year in years:
        obj=build(year);out=D/f'译注草稿/{year}.json';out.parent.mkdir(exist_ok=True)
        if out.exists():
            current=json.loads(out.read_text())
            assert not any(u.get('instruction_review') for u in current.get('units',[])),'已含正式说明的母稿不可被初稿提取工具覆盖；请按英文整句锚修改。'
        out.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n','utf-8')
        print(out,[(u['id'],len(u['sentences']),sum(len(s['w']) for s in u['sentences'])) for u in obj['units']])


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('years',nargs='*',type=int,choices=[2022,2023,2024])
    ap.add_argument('--write',action='store_true',help='生成译注草稿JSON；默认只显示来源正文编号')
    args=ap.parse_args();years=args.years or [2022,2023,2024]
    if args.write:write_drafts(years)
    else:
        for year in years:
            for unit in extract(year):
                print('\n###',year,unit['code'],len(unit['en']))
                for i,en in enumerate(unit['en'],1):print(f'{i}\t{en}')
