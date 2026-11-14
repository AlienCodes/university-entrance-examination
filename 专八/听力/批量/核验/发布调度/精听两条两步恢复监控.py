"""仅合并原43成功与root明确登记的2022-A/2024-A两步producer；不生成、不重试、不审批。"""
from collections import Counter
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('tem8_root_two_stage_activation',HERE/'精听缓存核齐与组装调度.py')
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
P,ROOT,STATE,PIN=A.pub,A.ROOT,A.STATE,A.pin
TARGETS={'2022-A','2024-A'}
ENC='核当前截图与真实审阅登记一致，再编码与独立核验'
STORE='成功结果立即持久保存（临时artifact不是唯一副本）'
PRE='全部预检与完整截图（考试先音频预演；精听原声/分屏/排版）'
TWO_PRE='两步入口预检、原声与完整截图'


def api(path):
    while True:
        try:return json.loads(subprocess.check_output(['gh','api','repos/'+PIN['repository']+'/'+path],cwd=ROOT,text=True,stderr=subprocess.STDOUT,timeout=45))
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:
            msg=getattr(exc,'output',None) or repr(exc)
            if isinstance(msg,bytes):msg=msg.decode(errors='replace')
            print('READ_API_WAIT '+json.dumps({'at':A.now(),'error':str(msg)[-1200:]},ensure_ascii=False),flush=True);time.sleep(60)


def jobs(run):
    result=[];page=1
    while True:
        data=api(f'actions/runs/{run}/jobs?filter=all&per_page=100&page={page}');result+=data['jobs']
        if len(result)>=data['total_count']:return result
        assert data['jobs'];page+=1


def select(rows,commit):
    found={}
    for j in rows:
        hit=re.fullmatch(r'render \(intensive, ([^,]+), \d{4}\)',j['name'])
        if not hit:continue
        ident=hit[1];assert j['head_sha']==commit
        if ident not in found or j['id']>found[ident]['id']:found[ident]=j
    return found


def retire_failure(ident,proof,job):
    if ident=='2024-A':
        src=STATE/'failure-alert.json';dst=STATE/'failure-alert-resolved-by-root-two-stage.json'
        if src.exists():
            value=P.read(src);assert len(value['failed'])==1 and value['failed'][0]['job_id']==132238965743
            assert not dst.exists();src.rename(dst)
        assert dst.exists()
        (HERE/'精听2024-A原失败已解决归档.json').write_bytes(dst.read_bytes())
        history=['精听2024-A-runner中断核验.json','精听2024-A第二次runner中断核验.json','精听2024-A独立恢复失败运行登记.json']
    else:
        src=HERE/'精听2022-A-原始job.json';value=P.read(src)
        assert value['id']==132238965399 and value['conclusion']=='failure'
        (HERE/'精听2022-A原失败已解决归档.json').write_bytes(src.read_bytes())
        history=['精听2022-A-runner失联核验.json','精听2022-A-原始annotations.json']
    return {'status':'resolved-by-root-approved-two-stage-cache','id':ident,'new_job_id':job['id'],
            'new_run_id':str(job['run_id']),'new_producer_commit':job['head_sha'],'resolved_at':A.now(),
            'strict_cache':proof,'preserved_failure_evidence':{n:P.sha(HERE/n) for n in history},
            'scope':'历史失败仍按失败原字节留存，只解除该目标阻断；不把旧失败/旧原命令producer记为新成功。'}


def main():
    A.frozen();manifest=A.producer_manifest();registration=P.read(HERE/'精听两条两步恢复运行登记.json')
    newrun=registration['run_id'];newcommit=registration['producer_commit'];resolved={};last=None
    assert manifest['2022-A']==manifest['2024-A']=={'run_id':str(newrun),'commit':newcommit}
    while True:
        started=time.monotonic();original=select(jobs(PIN['production_run']),PIN['production_commit'])
        candidate=select(jobs(newrun),newcommit)
        assert set(original)==set(manifest) and set(candidate)<=TARGETS
        selected={k:v for k,v in original.items() if k not in TARGETS};selected.update(candidate)
        rows={};failed=[]
        for ident,j in selected.items():
            producer=manifest[ident];assert str(j['run_id'])==producer['run_id'] and j['head_sha']==producer['commit']
            if ident in TARGETS:assert j.get('run_attempt',1)==1,'不能自动接受未经再批准的同run重试'
            steps={s['name']:s for s in j.get('steps',[])}
            rows[ident]={'job_id':j['id'],'producer_run':producer['run_id'],'producer_commit':producer['commit'],
                         'status':j['status'],'conclusion':j['conclusion'],'url':j['html_url'],
                         'phase':next((s['name'] for s in j.get('steps',[]) if s['status']=='in_progress'),j['status']),
                         'precheck':steps.get(TWO_PRE if ident in TARGETS else PRE,{}).get('conclusion'),'fastclock_fullverify':steps.get(ENC,{}).get('conclusion'),
                         'persistent_store':steps.get(STORE,{}).get('conclusion')}
            if j['conclusion']=='success':assert rows[ident]['precheck']==rows[ident]['fastclock_fullverify']==rows[ident]['persistent_store']=='success'
            elif j['status']=='completed':failed.append({'id':ident,**rows[ident]})
        summary=dict(Counter('success' if r['conclusion']=='success' else r['status'] for r in rows.values()))
        if len(rows)<45:summary['waiting_registered_leaf_jobs']=45-len(rows)
        summary.update(fastclock_fullverify_passed=sum(r['fastclock_fullverify']=='success' for r in rows.values()),
                       persistent_store_passed=sum(r['persistent_store']=='success' for r in rows.values()))
        status={'original_run':PIN['production_run'],'original_commit':PIN['production_commit'],'utc':A.now(),
                'summary':summary,'producer_manifest':manifest,'rows':rows,
                'selection':'original43 + root-approved two-stage run43548049905 two leaves; all three historical failed jobs excluded from acceptance but preserved'}
        P.dump(STATE/'latest-intensive-status.json',status)
        key=json.dumps(rows,sort_keys=True)
        if key!=last:
            print(json.dumps({'at':status['utc'],'summary':summary,'targets':{k:rows.get(k) for k in sorted(TARGETS)}},ensure_ascii=False),flush=True)
            with (STATE/'state-changes.jsonl').open('a') as f:f.write(json.dumps(status,ensure_ascii=False)+'\n')
            last=key
        if failed:
            P.dump(HERE/'精听两步恢复再次失败.json',{'at':A.now(),'failed':failed,'producer_manifest':manifest})
            raise RuntimeError('root新两步策略有新失败，不自动再试')
        for ident in sorted(TARGETS):
            if ident in candidate and candidate[ident]['conclusion']=='success' and ident not in resolved:
                A.frozen();proof=A.cache_producer(ident,manifest[ident],P.release(P.CACHE_TAG))
                assert proof['two_stage_proof_verified']
                resolved[ident]=retire_failure(ident,proof,candidate[ident])
                P.dump(HERE/'精听两条两步恢复完成核验.json',{'status':'pass' if len(resolved)==2 else 'partially-complete-not45',
                       'producer_registration':registration,'resolved':resolved,'at':A.now()})
                print('ROOT_TWO_STAGE_CACHE_STRICT_PASS '+ident,flush=True)
        if summary.get('success')==45:
            assert len(rows)==45 and set(resolved)==TARGETS
            if (STATE/'assembly-activation-failure.json').exists():(STATE/'assembly-activation-failure.json').rename(STATE/'assembly-activation-stopped-before-root-two-stage.json')
            P.dump(STATE/'45-current-cache-complete.json',{'original_run':PIN['production_run'],'original_commit':PIN['production_commit'],
                    'utc':A.now(),'summary':summary,'producer_manifest':manifest,'resolved_two_stage':resolved})
            print('ALL45_ORIGINAL43_PLUS_ROOT_TWO_CURRENT_SUCCESS',flush=True)
            subprocess.run([sys.executable,str(HERE/'精听缓存核齐与组装调度.py')],cwd=ROOT,check=True)
            return
        time.sleep(max(0,60-(time.monotonic()-started)))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        P.dump(STATE/'root-two-stage-monitor-stopped.json',{'status':'stopped','at':A.now(),'reason':repr(exc)})
        raise
