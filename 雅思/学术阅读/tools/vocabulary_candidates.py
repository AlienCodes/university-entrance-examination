"""Extract inflected source spans and dictionary senses to ground human and local-model editors."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

POS={'NOUN':'n.','PROPN':'n.','VERB':'v.','ADJ':'adj.','ADV':'adv.'}
# Basic auxiliaries, pronouns and light verbs are assessed as parts of collocations.
LIGHT=set('be have do get make go come take say tell put know mean use see look thing way even much very also well just really always so only then now too most many much often more some one two other first year new time people still good as not up down back out'.split())
LIMITED={'increase','decrease','maintain','restore','accommodate','sufficient','habitat','population','estimate','compare','likely','whereas','despite','relative','previously','subsequently','former','latter','fewer','require','expect','approximately'}
TEACHING_TERMS={
 'Sirenia':'海牛目','sea cows':'海中奶牛','manatees':'海牛','manatee':'海牛','dugongs':'儒艮','dugong':'儒艮',
 'forelimbs':'前肢','flippers':'鳍状肢','photosynthesis':'光合作用','horticultural analogue':'园艺近似种',
}
PHRASES="""as a result|as opposed to|as long as|as well as|by contrast|in contrast|in turn|on the other hand|rather than|regardless of|on behalf of|in terms of|in response to|give rise to|account for|make up|carry out|carry on|turn out|bring about|rely on|depend on|result in|result from|lead to|contribute to|stem from|play a role in|play a part in|in the absence of|in the presence of|in the long term|in the long run|due to|be likely to|less likely to|more likely to|at least|by means of|at risk|in part|at the expense of|be subject to|be associated with|is associated with|associated with|related to|focus on|deal with|draw on|weigh up|take into account|in particular|sea cows|on average|in common|in light of|up to|far from|cope with""".split('|')


def dictionary(filename, wanted):
    found={}
    with filename.open(encoding='utf-8') as f:
        for row in csv.DictReader(f):
            w=row['word'].lower()
            if w not in wanted:continue
            txt=row['translation'].strip()
            meanings = [x.strip() for x in txt.split(r'\n') if x.strip() and not x.startswith(('[' ,'<'))]
            cleaned='；'.join(meanings)[:130]
            if cleaned:found[w]=(cleaned,row['tag'].split(),int(row['frq'] or 0))
    return found


def collocations(en,doc,lex):
    spans=[]
    for phrase in PHRASES:
        for m in re.finditer(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',en,re.I):
            spans.append((m.start(),m.end(),phrase,'phr.',lex.get(phrase,('',[],0))[0],7))
    return spans


def choose(en,doc,lex):
    out=collocations(en,doc,lex)
    for t in doc:
        lemma=t.lemma_.lower();info=lex.get(lemma) or lex.get(t.lower_)
        if t.pos_ not in POS or lemma in LIGHT or not re.fullmatch(r'[a-z]+(?:[-’\'][a-z]+)*',lemma):continue
        if t.pos_=='PROPN' and not (t.text in TEACHING_TERMS or t.lower_ in TEACHING_TERMS):continue
        if t.is_stop and lemma not in LIMITED:continue
        meaning,tags,frequency=info or ('',[],0)
        if not meaning and t.pos_=='PROPN':continue
        base=5 if lemma in LIMITED or t.lower_ in TEACHING_TERMS else 4 if 'ielts' in tags or 'cet6' in tags else 3 if not frequency or frequency>3000 else 2
        out.append((t.idx,t.idx+len(t.text),lemma,POS[t.pos_],meaning,base))
    occupied=set();chosen=[];seen=set()
    for start,end,lemma,pos,hint,rank in sorted(out,key=lambda x:(-x[5],-(x[1]-x[0]),x[0])):
        if lemma in seen or any(x in occupied for x in range(start,end)):continue
        occupied.update(range(start,end));seen.add(lemma)
        chosen.append((start,{'form':en[start:end],'head':lemma,'pos':pos,'dictionary':hint}))
    # Return all candidates. The editor determines which words merit teaching on this screen.
    return [v for _,v in sorted(chosen)]

def short_expression(en):
    # These short rhetorical sentences and author bylines have no content-word POS.
    phrases=[
        (r'^by\b','by','prep.','由……撰写（作者署名）'),
        (r"\bcan['’]t\b","can't",'modal.','无法'),
        (r'\bwent really well\b','go well','phr.','进展顺利'),
        (r'\bfrom time to time\b','from time to time','phr.','不时'),
        (r'\band so on\b','and so on','phr.','等等'),
        (r'\bmake it\b','make it','phr.','做到；成功'),
        (r'\bmean for\b','mean for','phr.','对……意味着'),
        (r'\bno-no\b','no-no','n.','禁忌'),
        (r'\bamongst\b','amongst','prep.','在……之中'),
        (r'\bwhy\b','why','adv.','为什么'),
        (r'\bwhat\b','what','pron.','什么'),
    ]
    for expression,lemma,pos,meaning in phrases:
        match=re.search(expression,en,re.I)
        if match:
            form=match.group()
            return [{'form':form,'head':lemma,'pos':pos,'dictionary':meaning}],{form:meaning}
    return [],{}



def main(inputs,out,lexicon):
    import spacy
    nlp=spacy.load('en_core_web_sm',exclude=['ner'])
    corpus=[json.loads(p.read_text()) for p in inputs]
    sentences=list(dict.fromkeys(s for d in corpus for g in d['paragraphs'] for s in g))
    docs=dict(zip(sentences,nlp.pipe(sentences,batch_size=64)))
    needed=set(PHRASES)|{s for d in docs.values() for t in d for s in (t.lemma_.lower(),t.lower_)}
    lex=dictionary(lexicon,needed)
    out.mkdir(parents=True,exist_ok=True)
    for d in corpus:
        rows=[]
        for g in d['paragraphs']:
            for en in g:
                candidates=choose(en,docs[en],lex)
                hints={a:b for a,b in TEACHING_TERMS.items() if re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',en,re.I)}
                if not candidates:
                    candidates,extra=short_expression(en)
                    hints.update(extra)
                rows.append({'en':en,'candidates':candidates,'term_hints':hints})
        obj={'lesson':d['id'],'rows':rows}
        (out/(d['id']+'.json')).write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('lexicon',type=Path);p.add_argument('out',type=Path);p.add_argument('sources',nargs='+',type=Path)
    a=p.parse_args();main(a.sources,a.out,a.lexicon)
