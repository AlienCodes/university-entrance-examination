"""原44叶与明确登记的独立2024-A producer合并；仅监控，不再POST或重做任何视频。"""
from collections import Counter
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('tem8_independent_merge_activation',HERE/'精听缓存核齐与组装调度.py')
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
P,ROOT,STATE,PIN=A.pub,A.ROOT,A.STATE,A.pin
ENC='核当前截图与真实审阅登记一致，再编码与独立核验'
STORE='成功结果立即持久保存（临时artifact不是唯一副本）'
PRE='全部预检与完整截图（考试先音频预演；精听原声/分屏/排版）'
UNIT='2024-A'


def api(path):
    while True:
        try:
            return json.loads(subprocess.check_output(['gh','api','repos/'+PIN['repository']+'/'+path],cwd=ROOT,text=True,stderr=subprocess.STDOUT,timeout=45))
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:
            message=getattr(exc,'output',None) or repr(exc)
            if isinstance(message,bytes):message=message.decode(errors='replace')
            print('READ_API_WAIT '+json.dumps({'at':A.now(),'error':str(message)[-1200:]},ensure_ascii=False),flush=True)
            time.sleep(60)


def jobs(run):
    result=[];page=1
    while True:
        data=api(f'actions/runs/{run}/jobs?filter=all&per_page=100&page={page}');result+=data['jobs']
        if len(result)>=data['total_count']:return result
        assert data['jobs'];page+=1


def selected(rows,expected_commit):
    result={}
    for job in rows:
        hit=re.fullmatch(r'render \(intensive, ([^,]+), \d{4}\)',job['name'])
        if not hit:continue
        ident=hit[1];assert job['head_sha']==expected_commit
        if ident not in result or job['id']>result[ident]['id']:result[ident]=job
    return result


def make_rows(original,recovery,manifest):
    assert set(original)==set(manifest) and set(recovery)<=set([UNIT])
    combined={k:v for k,v in original.items() if k!=UNIT}
    if UNIT in recovery:combined[UNIT]=recovery[UNIT]
    result={}
    for ident,job in combined.items():
        source=manifest[ident];assert str(job['run_id'])==source['run_id'] and job['head_sha']==source['commit']
        steps={s['name']:s for s in job.get('steps',[])}
        result[ident]={'job_id':job['id'],'producer_run':source['run_id'],'producer_commit':source['commit'],
                       'status':job['status'],'conclusion':job['conclusion'],'url':job['html_url'],
                       'phase':next((s['name'] for s in job.get('steps',[]) if s['status']=='in_progress'),job['status']),
                       'precheck':steps.get(PRE,{}).get('conclusion'),'fastclock_fullverify':steps.get(ENC,{}).get('conclusion'),
                       'persistent_store':steps.get(STORE,{}).get('conclusion')}
        if job['conclusion']=='success':assert result[ident]['fastclock_fullverify']==result[ident]['persistent_store']=='success'
    return result


def resolved_failure(proof,newjob):
    source=STATE/'failure-alert.json';dest=STATE/'failure-alert-resolved-by-independent-2024-A.json'
    if source.exists():
        old=P.read(source);assert len(old['failed'])==1 and old['failed'][0]['job_id']==132238965743
        assert not dest.exists();source.rename(dest)
        (HERE/'精听2024-A原失败已解决归档.json').write_bytes(dest.read_bytes())
    assert dest.exists()
    record={'status':'resolved-by-registered-independent-current-cache','original_run':PIN['production_run'],
            'original_commit':PIN['production_commit'],'old_job_id':132238965743,'new_job_id':newjob['id'],
            'new_run_id':str(newjob['run_id']),'new_producer_commit':newjob['head_sha'],'resolved_at':A.now(),
            'old_failure_archive':dest.name,'old_failure_sha256':P.sha(dest),'strict_cache':proof,
            'scope':'原失败原字节保留；独立producer来源如实记录，未伪称原f252重试，未变生成核心或45审批。'}
    P.dump(HERE/'精听2024-A单次恢复核验.json',record)
    stopped=STATE/'assembly-activation-failure.json'
    if stopped.exists():stopped.rename(STATE/'assembly-activation-stopped-before-independent-recovery.json')
    return record


def main():
    A.frozen();manifest=A.producer_manifest();registration=P.read(HERE/'精听2024-A独立恢复运行登记.json')
    new=manifest[UNIT];old_run=PIN['production_run'];last=None;recovered=None
    assert not (HERE/'精听2024-A单次重试请求.json').exists()
    while True:
        started=time.monotonic()
        original=selected(jobs(old_run),PIN['production_commit'])
        new_jobs=jobs(new['run_id']);recovery=selected(new_jobs,new['commit'])
        assert not any(j['name'].startswith('render (exam,') for j in new_jobs),'独立恢复不得执行任何考试'
        rows=make_rows(original,recovery,manifest)
        failure=[{'id':ident,**row} for ident,row in rows.items() if row['status']=='completed' and row['conclusion']!='success']
        # 已向root交原始annotations的2022-A失联只保留阻断，不擅自重试；继续观察已授权2024-A。
        known=[f for f in failure if f['id']=='2022-A' and f['job_id']==132238965399 and
               (HERE/'精听2022-A-runner失联核验.json').exists() and
               P.read(HERE/'精听2022-A-runner失联核验.json')['status']=='hosted-runner-lost-communication']
        unexpected=[f for f in failure if f not in known]
        summary=dict(Counter('success' if r['conclusion']=='success' else r['status'] for r in rows.values()))
        if UNIT not in rows:summary['new2024A_waiting_job']=1
        summary.update(fastclock_fullverify_passed=sum(r['fastclock_fullverify']=='success' for r in rows.values()),
                       persistent_store_passed=sum(r['persistent_store']=='success' for r in rows.values()))
        if known:summary['known_2022A_runner_failure_blocking_full15']=len(known)
        current={'original_run':old_run,'original_commit':PIN['production_commit'],'utc':A.now(),'summary':summary,
                 'producer_manifest':manifest,'rows':rows,'selection':'original44 + registered independent2024A latest job; historical failed original2024A excluded from latest acceptance, preserved in archive'}
        P.dump(STATE/'latest-intensive-status.json',current)
        key=json.dumps(rows,sort_keys=True)
        if key!=last:
            print(json.dumps({'at':current['utc'],'summary':summary,'2024A':rows.get(UNIT)},ensure_ascii=False),flush=True)
            with (STATE/'state-changes.jsonl').open('a') as f:f.write(json.dumps(current,ensure_ascii=False)+'\n')
            last=key
        if unexpected:
            P.dump(HERE/'精听独立恢复期间新失败.json',{'at':A.now(),'failures':failure,'producer_manifest':manifest})
            raise RuntimeError('独立恢复或其他叶失败，不自动再次重试')
        if UNIT in recovery and recovery[UNIT]['conclusion']=='success' and recovered is None:
            A.frozen();proof=A.cache_producer(UNIT,new,P.release(P.CACHE_TAG))
            recovered=resolved_failure(proof,recovery[UNIT]);print('INDEPENDENT_2024A_CACHE_STRICT_RESOLVED',flush=True)
        if summary.get('success')==45:
            assert len(rows)==45 and recovered is not None
            P.dump(STATE/'45-current-cache-complete.json',{'original_run':old_run,'original_commit':PIN['production_commit'],
                    'utc':A.now(),'summary':summary,'producer_manifest':manifest,'recovery':recovered})
            print('ALL45_COMPOSITE_CURRENT_SUCCESS',flush=True)
            subprocess.run([sys.executable,str(HERE/'精听缓存核齐与组装调度.py')],cwd=ROOT,check=True)
            return
        time.sleep(max(0,60-(time.monotonic()-started)))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        P.dump(STATE/'independent-recovery-monitor-failure.json',{'status':'stopped','at':A.now(),'reason':repr(exc)})
        raise
