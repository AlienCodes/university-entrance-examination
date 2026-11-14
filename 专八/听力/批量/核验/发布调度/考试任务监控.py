"""每55秒只读监控明确登记的生产/修复run；已证实shutdown待补，未知失败阻断。"""
import argparse,collections,datetime,json,re,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',type=Path,required=True);p.add_argument('--run',required=True);p.add_argument('--producer-register',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[5];out=a.state;out.mkdir(parents=True,exist_ok=True);previous=None
history=json.loads((out/'exam-history.json').read_text()) if (out/'exam-history.json').exists() else []
years=[str(y) for y in list(range(2009,2020))+list(range(2021,2025))]
def ident(j):
 m=re.match(r'render \(exam, (\d{4}),',j['name']);return m.group(1) if m else None
def store(j):return next((s['conclusion'] for s in j.get('steps',[]) if s['name'].startswith('成功结果立即持久保存')),None)
while True:
 now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  register=json.loads(a.producer_register.read_text());assert str(register['production_run_id'])==a.run
  known={}
  for file in (root/'专八/听力/批量/核验/考试正式发布').glob('*-runner关闭证据.json'):
   proof=json.loads(file.read_text())
   if any('runner has received a shutdown signal' in s for s in proof['observed_lines']):known[proof['job_id']]=str(file.relative_to(root))
  all_leaves=[];main_jobs=[]
  for r in register['runs']:
   data=json.loads(subprocess.check_output(['gh','api',f"repos/AlienCodes/university-entrance-examination/actions/runs/{r['run_id']}/jobs?per_page=100"],timeout=45))
   (out/('run-'+r['run_id']+'-jobs.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2))
   if str(r['run_id'])==a.run:
    main_jobs=data['jobs'];(out/'jobs-current.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
   for j in data['jobs']:
    year=ident(j)
    if year:
     assert year in r['target_ids'],'repair出现未授权年份'
     assert j.get('head_sha',r['source_commit'])==r['source_commit'],'producer实际commit与登记不同'
     j['_producer']=r;all_leaves.append(j)
  unknown=[j for j in all_leaves if j['status']=='completed' and j['conclusion']!='success' and j['id'] not in known and not (j['conclusion']=='cancelled' and j['_producer'].get('ignore_root_cancelled'))]
  chosen=[];rows=[]
  for year in years:
   candidates=[j for j in all_leaves if ident(j)==year]
   successful=[j for j in candidates if j['conclusion']=='success' and store(j)=='success']
   active=[j for j in candidates if j['status']=='in_progress'];queued=[j for j in candidates if j['status']=='queued']
   selected=max(successful or active or queued or candidates,key=lambda j:j['id']) if candidates else None
   if selected:chosen.append(selected)
   status='success' if successful else ('in_progress' if active else ('queued' if queued else 'waiting_repair'))
   rows.append({'id':selected['id'] if selected else None,'year':year,'status':status,'run_id':selected['run_id'] if selected else None,'step':next((s['name'] for s in selected.get('steps',[]) if s['status']=='in_progress'),None) if selected else None,'store':store(selected) if selected else None})
  key=json.dumps(rows,ensure_ascii=False,sort_keys=True)
  if key!=previous:
   change=[r for r in rows if not previous or r not in json.loads(previous)]
   record={'at':now,'run_id':a.run,'exam_status':dict(collections.Counter(r['status'] for r in rows)),'all_job_status':dict(collections.Counter(j['status'] for j in main_jobs)),'unknown_failure_jobs':[j['id'] for j in unknown],'known_infra_jobs':sorted(known),'changed':change}
   print(json.dumps(record,ensure_ascii=False),flush=True);history.append(record);(out/'exam-history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2));previous=key
  if unknown:(out/'exam-failed.json').write_text(json.dumps(unknown,ensure_ascii=False,indent=2))
  else:(out/'exam-failed.json').unlink(missing_ok=True)
  if all(r['status']=='success' for r in rows) and not unknown:
   (out/'exam-all-success.json').write_text(json.dumps({'run_id':a.run,'at':now,'producer_register':register,'jobs':chosen},ensure_ascii=False,indent=2));print('ALL_15_EXAMS_SUCCESS',flush=True);break
 except Exception as exc:print(json.dumps({'at':now,'monitor_error':type(exc).__name__,'message':str(exc)}),flush=True)
 time.sleep(55)
