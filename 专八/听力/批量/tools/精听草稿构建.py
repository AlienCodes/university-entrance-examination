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
        en=sentences(clean(source[a:b]))
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
PENDING={
 (2022,'A'):[
 '原PDF第1页确印“stating once again the anthropology”；语法应为that的可能性须听原声裁决，目前保留the。',
 ],
 (2023,'A'):[
 '原PDF第2页确印“But before, it was fossil metaphor”；before所指及实际措辞须听原声核实，目前未擅改。',
 ],
 (2023,'B1'):[
 '原PDF第3页确印“a year sharp spent volunteering”；sharp为扫描原稿本身疑误，须原声裁决，英文暂保留，不给sharp强加词义。',
 '原PDF第3页确印“To put it simple”；尚待原声核对simple/simply，未擅自改口语措辞。',
 '第5题扫描题干为“what kind of gap year experience do employers care most?”，缺about；待核实际口述，暂按原扫描保留。',
 ],
 (2023,'B2'):[
 '原PDF第5页主持人说“I see.”，OCR为“Oh, I see.”；最终应以原声核准是否有Oh，目前按扫描更正为I see。',
 ],
 (2024,'A'):[
 '原PDF第1页确印“adults and adolescence”；很可能应为adolescents，必须对照原声后裁决；英文保留扫描原稿，中文按所指年龄人群译。',
 '原PDF第2页末段确印“that is a language translation”；冠词和口语断句须原声核实，未按书面语重写。',
 ],
 (2024,'B1'):[
 '原PDF第3页“minor novels”的语境指称须结合原声复核；现按较少受到关注的小说译，未照解析自行补出篇幅和结构特征。',
 ],
 (2024,'B2'):[
 '原PDF第4页确印“examine the Antarctica’s vast ice sheets”，定冠词the疑多；待原声裁决，未擅改。',
 '原PDF第5页确印“I knew that there are climate science deniers”；knew/know须原声核准，英文暂按原稿。',
 '原PDF第5页“Also the effects ... in a global capacity.”为主持人的不完整口语句；译文保留其承接关系，须原声核断句，不拼入前一位男士话轮。',
 '开头three times faster按新闻通常语意译为2007年的三倍；请连同three feet/six inches/six feet口述数字逐个核准。',
 ],
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
        # 对照页图确认：2023 B2主持人的应答没有OCR多出的“Oh,”。
        if (year,code)==(2023,'B2'):
            assert original[33]['en']=='Oh, I see.'
            original[33]['en']='I see.';original[33]['zh']='我明白了。'
            base['en'][33]='I see.'
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
            'title':base['title'],
            'source_refs':[{'path':str(source.relative_to(D)),'original_pdf':pdf,'sha256':sha,
                            'pdf_pages':PAGES[year][code],
                            'verified_against':'原PDF页图逐篇查看；正文及B部末尾题干，未混入参考答案或解题说明'}],
            'sentences':out,'待核':PENDING.get((year,code),[]),
            'review':{'status':'draft','basis':'扫描原文及原PDF页图；人工逐句中译、语境词汇，尚待真实原声逐句对照及复核。',
                      'body_sentences':body_count,'question_stems':0 if code=='A' else 5},
        })
    return {'year':year,'units':units}


def write_drafts(years=(2022,2023,2024)):
    for year in years:
        obj=build(year);out=D/f'译注草稿/{year}.json';out.parent.mkdir(exist_ok=True)
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
