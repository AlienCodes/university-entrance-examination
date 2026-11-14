import json,subprocess,time,collections
from pathlib import Path
RUN='43549769019';HEAD='1d6e5f3e6dc9c53ef4cc546add74a0dc715ae3df';REPO='AlienCodes/university-entrance-examination';ROOT=Path('/workspace/tem8-project');OUT=Path('/workspace/tem8-full15-43549769019');OUT.mkdir(exist_ok=True)
previous=None
while True:
 started=time.monotonic()
 try:
  d=json.loads(subprocess.check_output(['gh','api',f'repos/{REPO}/actions/runs/{RUN}/jobs?per_page=100'],cwd=ROOT,timeout=45));assert len(d['jobs'])==d['total_count']<=100;assert all(j['head_sha']==HEAD for j in d['jobs'])
 except Exception as exc:
  print('READ_API_WAIT '+repr(exc),flush=True);time.sleep(60);continue
 (OUT/'jobs-current.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 rows=[{'id':j['id'],'name':j['name'],'status':j['status'],'conclusion':j['conclusion'],'url':j['html_url'],'phase':next((s['name'] for s in j.get('steps',[]) if s['status']=='in_progress'),j['status'])} for j in d['jobs']]
 key=json.dumps(rows,ensure_ascii=False,sort_keys=True)
 record={'run':RUN,'head_sha':HEAD,'utc':time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime()),'summary':dict(collections.Counter(r['conclusion'] or r['status'] for r in rows)),'rows':rows}
 (OUT/'status-current.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 if key!=previous:
  print(json.dumps(record,ensure_ascii=False),flush=True)
  with (OUT/'history.jsonl').open('a') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
  previous=key
 failed=[r for r in rows if r['status']=='completed' and r['conclusion'] not in ['success','skipped']]
 if failed:
  (OUT/'failure-alert.json').write_text(json.dumps({'run':RUN,'head_sha':HEAD,'failed':failed},ensure_ascii=False,indent=2)+'\n');print('FULL15_FAILURE_ALERT',flush=True);break
 publish=next((r for r in rows if r['name']=='publish'),None)
 if publish and publish['conclusion']=='success' and sum(r['name'].startswith('assemble (') and r['conclusion']=='success' for r in rows)==15:
  (OUT/'all15-and-publication-success.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print('FULL15_AND_PUBLICATION_SUCCESS',flush=True);break
 time.sleep(max(0,60-(time.monotonic()-started)))
