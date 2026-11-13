"""按版式候选整句EN精确匹配补真实内容词；不更动splits或任何时间。"""
import json,re,hashlib
from pathlib import Path
B=Path(__file__).resolve().parents[1]
TABLE=[
(2022,'2022-A','Most cultural anthropologists will limit themselves to a few geographic areas, for example, Margaret Mead in Samoa and New Guinea, and Clyde Kluckhohn with the Navajo Indians in the Southwestern United States.','Southwestern','southwestern','adj.（美国）西南部的','word'),
(2022,'2022-A','But for the past several decades, large numbers of “anthro” graduates have been employed in other fields, such as urban planning and administration, health care and international development.','decades','decade','n.十年；这里指几十年的时间','word'),
(2022,'2022-B1','Neither my mother nor father completed their education, but they were adamant that their children take advantage of all of the opportunities that a public education offers both in and out of school time.','completed their education',"complete one's education",'phr.完成学业','phr'),
]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for year in sorted({x[0] for x in TABLE}):
 p=B/f'译注草稿/{year}.json';old=p.read_text();d=json.loads(old)
 for y,uid,en,surface,h,m,t in TABLE:
  if y!=year:continue
  u=next(x for x in d['units'] if x['id']==uid);ss=[s for s in u['sentences'] if s['en']==en];assert len(ss)==1,(uid,en,'母稿EN已变，不能按旧句序硬套')
  s=ss[0];matches=list(re.finditer(re.escape(surface),en));assert len(matches)==1;v=matches[0];a,z=v.span()
  already=any(w['h']==h and [a,z] in w['sp'] for w in s['w'])
  if not already:
   assert all(z<=c or a>=e for w in s['w'] for c,e in w['sp']),(uid,h,'不能与原词注重叠')
   s['w'].append({'t':t,'h':h,'m':m,'sp':[[a,z]]})
  rows.append({'year':year,'unit':uid,'en':en,'added':{'surface':surface,'h':h,'m':m,'sp':[a,z]},'reason':'指定分屏缺词覆盖；真实内容词/搭配，整句EN精确匹配。'})
 for u in d['units']:
  for s in u['sentences']:
   used=[]
   for w in s['w']:
    for a,z in w['sp']:assert 0<=a<z<=len(s['en']);assert all(z<=c or a>=e for c,e in used);used.append((a,z))
 assert p.read_text()==old,(year,'并发写入，重读后再补')
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
p=B/'核验/正文异文复核/分屏补词修订.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'changes':rows,'no_time_or_split_changes':True},ensure_ascii=False,indent=2)+'\n');print('真实分屏词注',len(rows),'项；全文span均通过')
