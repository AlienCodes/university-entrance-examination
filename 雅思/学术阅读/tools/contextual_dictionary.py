from difflib import SequenceMatcher
from collections import Counter
from pathlib import Path
import json,re,unicodedata,sys
from lxml import html
def word(s):
 s=''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))
 return re.findall(r'[a-z]+|[0-9]+',s)
def capture(pid,source):
 data=html.fromstring((source/(pid+'.html')).read_bytes().decode('utf8','replace'))
 roots=data.xpath('//*[contains(@class,"drag_area_left_noimg")]') or data.xpath('//*[contains(@class,"drag_area_left")]')
 items=[]
 if roots:
  for span in roots[0].xpath('.//span[contains(concat(" ",@class," ")," phase ")]'):
   en=' '.join(t.text_content() for t in span.xpath('./span[contains(@class,"text")]'))
   zh=span.get('data-translation','').strip()
   if en and zh:items.append((word(en),zh))
 return items
def apply(p,source):
 d=json.loads(p.read_text());items=capture(d['lesson'],source)
 left=[];counter=[];right=[];translation=[]
 for i,r in enumerate(d['rows']):
  v=word(r['en']);left+=v;counter.extend([i]*len(v))
 for i,(v,c) in enumerate(items):right+=v;translation.extend([i]*len(v))
 limits={}
 for block in SequenceMatcher(None,left,right,autojunk=False).get_matching_blocks():
  for n in range(block.size):
   ri=counter[block.a+n];limits.setdefault(ri,Counter())[translation[block.b+n]]+=1
 n=0
 for i,r in enumerate(d['rows']):
  hits=limits.get(i,{})
  if sum(hits.values())<.78*len(word(r['en'])):continue
  ref=' '.join(items[k][1] for k,v in hits.items() if v>=min(4,len(items[k][0])) or v/sum(hits.values())>.36)
  for t in r['candidates']:
   if t['form'] in r['term_hints']:continue
   ds=re.sub(r'\([^)]*\)|（[^）]*）|\[[^]]*\]|[a-z.]+',' ',t['dictionary'])
   meanings=[x.strip() for x in re.split(r'[，；、,;\s]+',ds) if re.fullmatch(r'[\u4e00-\u9fff]{2,8}',x.strip()) and x.strip() in ref]
   if not meanings:continue
   m=sorted(set(meanings),key=lambda q:(-len(q),q))[0]
   r['term_hints'][t['form']]=m;n+=1
 d['term_hint_basis']='已核学术词典及独立双语资料只用于辨别当前单词义项。'
 p.write_text(json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n')
 return n
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description='Match dictionary senses against the independent bilingual witness. Only isolated dictionary terms are saved.')
 parser.add_argument('witness_html',type=Path)
 parser.add_argument('candidate_files',nargs='+',type=Path)
 args=parser.parse_args()
 print(sum(apply(p,args.witness_html) for p in args.candidate_files))
