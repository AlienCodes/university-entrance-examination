import collections,hashlib,json,re,subprocess,time
from pathlib import Path
ROOT=Path('/workspace/tem8-project');OUT=Path('/workspace/tem8-monitor-intensive-43528080039');OUT.mkdir(exist_ok=True)
RUN='43528080039';HEAD='f25216794e383505baa132ca581e1380e82192c8';REPO='AlienCodes/university-entrance-examination'
registry=json.loads((ROOT/'专八/听力/批量/审核登记.json').read_text()); expected={k.split(':',1)[1]:v['payload_sha256'] for k,v in registry['entries'].items() if k.startswith('intensive:')};assert len(expected)==45
(OUT/'expected-current-fingerprints.json').write_text(json.dumps(expected,indent=2)+'\n')
ENC='核当前截图与真实审阅登记一致，再编码与独立核验';STORE='成功结果立即持久保存（临时artifact不是唯一副本）';PRE='全部预检与完整截图（考试先音频预演；精听原声/分屏/排版）'
def api(endpoint):return json.loads(subprocess.check_output(['gh','api',f'repos/{REPO}/'+endpoint],cwd=ROOT,timeout=45))
def write(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def cache_rows():
 release=api('releases/tags/tem8-listening-render-cache-2009-2024');assets={a['name']:a for a in release['assets']};rows={}
 for ident,fp in expected.items():
  prefix=f'tem8-intensive-{ident}-{fp[:16]}-';pairs=[]
  for n,a in assets.items():
   if n.startswith(prefix) and n.endswith('.mp4') and n[:-4]+'-evidence.zip' in assets:
    ev=assets[n[:-4]+'-evidence.zip'];h=(a.get('digest') or '').removeprefix('sha256:');eh=(ev.get('digest') or '').removeprefix('sha256:')
    if len(h)==64 and len(eh)==64 and a['size']>0 and ev['size']>0 and n.endswith('-'+h[:12]+'.mp4'):
     pairs.append({'mp4':n,'mp4_sha256':h,'mp4_bytes':a['size'],'evidence':ev['name'],'evidence_sha256':eh,'evidence_bytes':ev['size']})
  rows[ident]={'payload_sha256':fp,'pairs':pairs}
 write('current-cache-server-digests.json',{'run':RUN,'head_sha':HEAD,'release_tag':release['tag_name'],'rows':rows})
 return rows
last={};last_summary=None;poll=0
while True:
 started=time.monotonic();poll+=1
 try:
  d=api(f'actions/runs/{RUN}/jobs?per_page=100');assert d['total_count']==len(d['jobs'])<=100
  write('latest-all-jobs.json',d)
  jobs=[j for j in d['jobs'] if '(intensive,' in j['name']];assert len(jobs)==45
  assert all(j['head_sha']==HEAD for j in jobs)
  rows={};changes=[];failed=[]
  for j in jobs:
   ident=re.fullmatch(r'render \(intensive, ([^,]+), \d{4}\)',j['name']).group(1);assert ident in expected
   steps={s['name']:s for s in j.get('steps',[])}
   phase=j['status']
   if j['status']=='in_progress':phase=next((s['name'] for s in j['steps'] if s['status']=='in_progress'),'starting')
   row={'job_id':j['id'],'status':j['status'],'conclusion':j['conclusion'],'phase':phase,'url':j['html_url'],
        'precheck':steps.get(PRE,{}).get('conclusion'),'fastclock_fullverify':steps.get(ENC,{}).get('conclusion'),'persistent_store':steps.get(STORE,{}).get('conclusion')}
   rows[ident]=row
   compact={k:row[k] for k in ['status','conclusion','phase','precheck','fastclock_fullverify','persistent_store']}
   if last.get(ident)!=compact:changes.append({'id':ident,**compact});last[ident]=compact
   if j['status']=='completed' and j['conclusion']!='success':failed.append({'id':ident,**row,'steps':j.get('steps',[])})
   if j['status']=='completed' and j['conclusion']=='success':assert row['fastclock_fullverify']==row['persistent_store']=='success'
  summary=dict(collections.Counter('success' if r['conclusion']=='success' else 'failed' if r['status']=='completed' else r['status'] for r in rows.values()))
  summary.update(fastclock_fullverify_passed=sum(r['fastclock_fullverify']=='success' for r in rows.values()),persistent_store_passed=sum(r['persistent_store']=='success' for r in rows.values()))
  record={'run':RUN,'head_sha':HEAD,'utc':time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime()),'poll':poll,'summary':summary,'rows':rows}
  write('latest-intensive-status.json',record)
  if changes or summary!=last_summary:
   print(json.dumps({'utc':record['utc'],'summary':summary,'changes':changes},ensure_ascii=False),flush=True)
   with (OUT/'state-changes.jsonl').open('a') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
   last_summary=summary
  if failed:
   write('failure-alert.json',{'run':RUN,'head_sha':HEAD,'utc':record['utc'],'failed':failed});print('INTENSIVE_FAILURE_ALERT '+json.dumps(failed,ensure_ascii=False),flush=True);raise SystemExit(2)
  if summary.get('success')==45:
   cached=cache_rows();ready=[k for k,v in cached.items() if v['pairs']]
   if len(ready)==45:
    write('45-current-cache-complete.json',{'run':RUN,'head_sha':HEAD,'utc':record['utc'],'summary':summary,'cache_pairs':cached,'scope':'All45 jobs success including enforced fast clock/fullverify and stage/store; current-fingerprint persistent MP4/evidence pairs have server SHA256. Does not claim15 whole-year assembly complete.'});print('ALL45_CURRENT_CACHE_COMPLETE',flush=True);break
   print('CACHE_STILL_WAITING '+json.dumps([k for k in expected if k not in ready]),flush=True)
 except SystemExit:raise
 except Exception as exc:
  print('MONITOR_READ_ERROR '+repr(exc),flush=True)
 time.sleep(max(0,60-(time.monotonic()-started)))
