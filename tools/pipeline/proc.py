import json,sys
from collections import Counter
src,tag=sys.argv[1],sys.argv[2]
d=json.load(open(src))['result']
json.dump(d,open(f'{tag}.json','w'),ensure_ascii=False,indent=1)
K,D=d['kept'],d['dropped']
print('kept',len(K),'dropped',len(D),Counter(f['field'] for f in K),Counter(f['severity'] for f in K))
with open(f'{tag}_list.txt','w') as o:
  for t,L in (('k',K),('d',D)):
    for n,f in enumerate(L):
      o.write(f"[{t}{n}] {f['pid']}:{f['sent']} {f['field']} {f['headword']} ({f['lens']},{f['severity']}){' VOTES '+str(f.get('votes')) if t=='d' else ''}\n   CUR: {f['current']}\n   NEW: {f['proposed']}\n   WHY: {f['reason'][:300]}\n")
      if t=='d': o.write(f"   VWHY: {[w[:220] if w else w for w in f['why']]}\n")
