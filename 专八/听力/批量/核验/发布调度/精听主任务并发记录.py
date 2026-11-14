import json,time
from pathlib import Path
base=Path('/workspace/tem8-monitor-intensive-43528080039');path=base/'latest-all-jobs.json';dest=base/'main-leaf-concurrency.json';laststamp=None;lastactive=None;peak=0
while True:
 try:
  stamp=path.stat().st_mtime_ns
  if stamp!=laststamp:
   d=json.loads(path.read_text());leaf=[j for j in d['jobs'] if j['name'].startswith('render (')];active=[j['name'] for j in leaf if j['status']=='in_progress'];peak=max(peak,len(active));summary={'run':'43528080039','utc':time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime()),'total_leaf':len(leaf),'in_progress':len(active),'peak_observed':peak,'exam_in_progress':sum('(exam,' in n for n in active),'intensive_in_progress':sum('(intensive,' in n for n in active),'queued':sum(j['status']=='queued' for j in leaf),'active_names':active,'scope':'same once-per-60s job API snapshot, no extra API, observed peak at polling times only'}
   dest.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');laststamp=stamp
   if lastactive!=len(active):
    with (base/'main-leaf-concurrency-history.jsonl').open('a') as f:f.write(json.dumps(summary,ensure_ascii=False)+'\n')
    print(json.dumps(summary,ensure_ascii=False),flush=True);lastactive=len(active)
  if (base/'failure-alert.json').exists() or (base/'45-current-cache-complete.json').exists():break
 except (FileNotFoundError,json.JSONDecodeError):pass
 time.sleep(2)
