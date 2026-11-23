"""Align an independent public bilingual witness to the uploaded English paper for editorial comparison."""
from collections import Counter,defaultdict
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
import re
import unicodedata
from urllib.error import URLError
from urllib.request import Request,urlopen

class ParallelSentences(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items=[]
        self.phase=0
        self.english=0
        self.fragments=[]
        self.chinese=''
    def handle_starttag(self,tag,attrs):
        if tag!='span':return
        values=dict(attrs);cls=values.get('class','').split()
        if self.phase:
            self.phase+=1
            if self.english:self.english+=1
            elif 'text' in cls:self.english=1
        elif 'phase' in cls and values.get('data-translation'):
            self.phase=1;self.chinese=values['data-translation'].strip();self.fragments=[]
    def handle_endtag(self,tag):
        if tag!='span' or not self.phase:return
        if self.english:self.english-=1
        self.phase-=1
        if not self.phase and self.fragments and self.chinese:
            self.items.append((' '.join(''.join(self.fragments).split()),self.chinese))
    def handle_data(self,text):
        if self.english:self.fragments.append(text)

def tokens(text):
    return re.findall(r'[a-z]+|[0-9]+',''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c)))

def aligned(material,raw):
    doc=ParallelSentences();doc.feed(raw.decode('utf-8','replace'))
    rows=[(tokens(e),c) for e,c in doc.items]
    left=[];ln=[];right=[];rn=[]
    for i,s in enumerate(material):
        t=tokens(s);left.extend(t);ln.extend([i]*len(t))
    for i,(t,c) in enumerate(rows):right.extend(t);rn.extend([i]*len(t))
    matched=defaultdict(Counter)
    for block in SequenceMatcher(None,left,right,autojunk=False).get_matching_blocks():
        for j in range(block.size):matched[ln[block.a+j]][rn[block.b+j]]+=1
    result={}
    for i,s in enumerate(material):
        hit=matched[i];ids=sorted(k for k,n in hit.items() if n>=.86*len(rows[k][0]))
        if ids and sum(hit[k] for k in ids)>=.94*len(tokens(s)):
            text=' '.join(rows[k][1] for k in ids)
            result[i+1]=re.sub(r'^\s*[A-O]\s+(?=[\u3400-\u9fff])','',text)
    return result

def collect(source,workdir):
    address=source.get('witness','')
    if not isinstance(address,str) or not re.fullmatch(r'https://top\.zhan\.com/ielts/read/[\w-]+\.html',address):return {}
    cache=Path(workdir)/'independent-page.html'
    if not cache.exists():
        try:
            with urlopen(Request(address,headers={'User-Agent':'Mozilla/5.0 Academic reading editorial comparison'}),timeout=25) as r:
                raw=r.read(3500001)
            if len(raw)>3500000:return {}
            cache.write_bytes(raw)
        except (URLError,OSError,TimeoutError):return {}
    return aligned([s for g in source['paragraphs'] for s in g],cache.read_bytes())
