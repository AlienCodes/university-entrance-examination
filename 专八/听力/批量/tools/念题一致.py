"""核查精听母稿念题与已核考试题干；--sync按当前题干精确同步并重绑真实span。
写前重读并核SHA，避免持旧整稿覆盖并发正文修订。仅处理role=question。
"""
import argparse,difflib,hashlib,json,os,re
from pathlib import Path
D=Path(__file__).resolve().parents[1]
YEARS=list(range(2009,2020))+list(range(2021,2025))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def strip(s):return re.sub(r'^Question\s*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*[.:]?\s*','',s,flags=re.I)
def remap(old,new,span):
 a,b=span;surface=old[a:b]
 found=list(re.finditer(r'(?<!\w)'+re.escape(surface)+r'(?!\w)',new,re.I))
 if len(found)==1:return [found[0].start(),found[0].end()]
 ops=difflib.SequenceMatcher(None,old,new,autojunk=False).get_opcodes()
 def at(i,side):
  for op,x,y,u,v in ops:
   if op=='insert' and x==i:
    return v if side=='start' or new[u:v].isalpha() else u
  for op,x,y,u,v in ops:
   if x<=i<=y:
    if op=='equal':return u+i-x
    if op in ('replace','delete'):return u if side=='start' else v
  raise ValueError((i,side,old,new))
 a,b=at(a,'start'),at(b,'end')
 while a<b and new[a].isspace():a+=1
 while b>a and new[b-1].isspace():b-=1
 assert 0<=a<b<=len(new),(surface,new,a,b)
 assert not(a and new[a-1].isalnum() and new[a].isalnum()),(surface,new[a:b])
 assert not(b<len(new) and new[b-1].isalnum() and new[b].isalnum()),(surface,new[a:b])
 return [a,b]
def run(sync=False):
 report=[];bad=[]
 for year in YEARS:
  p=D/'译注草稿'/f'{year}.json';paper=json.loads((D/'数据'/str(year)/'试卷.json').read_text());masters={q['n']:q['stem'] for q in paper['questions']}
  for attempt in range(4):
   before=sha(p);d=json.loads(p.read_text());changed=[];seen=[]
   for u in d['units']:
    for s in u['sentences']:
     if s.get('role')!='question':continue
     n=s['n'];seen.append(n);old=s['en'];new=f'Question {n}. '+masters[n]
     if old!=new:
      changed.append({'n':n,'before':old,'after':new})
      if sync:
       for w in s['w']:w['sp']=[remap(old,new,sp) for sp in w['sp']]
       s['en']=new;s['question_sync_basis']='对应已核考试试卷stem；含实际口述Question题号。'
     if strip(new if sync else old)!=masters[n]:bad.append({'year':year,'n':n,'draft':old,'master':masters[n]})
     spans=[]
     for w in s['w']:
      for a,b in w['sp']:
       text=s['en'];assert 0<=a<b<=len(text),(year,n,w)
       assert not any(a<z and x<b for x,z in spans),(year,n,'overlap')
       spans.append((a,b))
   assert sorted(seen)==list(range(1,11)),(year,seen)
   if sha(p)!=before:continue
   if sync and changed:
    tmp=p.with_suffix('.question-sync.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    if sha(p)!=before:tmp.unlink();continue
    os.replace(tmp,p)
   report.append({'year':year,'before_sha256':before,'after_sha256':sha(p),'questions':len(seen),'changed':changed if sync else [],'body_untouched':True})
   break
  else:raise RuntimeError(f'{year}母稿连续并发变更，未覆盖')
 result={'status':'pass' if not bad else 'fail','synced':sync,'questions_checked':sum(r['questions'] for r in report),'years':report,'problems':bad,'scope':'仅题干/Question题号及其词汇span；正文与zh/w词义未由本工具重写。'}
 out=D/'核验'/('念题母稿同步.json' if sync else '念题母稿一致.json');out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 if bad:raise SystemExit(json.dumps(bad,ensure_ascii=False))
 print('150道念题母稿与已核试卷一致；真实span有效；sync='+str(sync))
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--sync',action='store_true');run(ap.parse_args().sync)
