"""原run的2024-A runner shutdown仅恢复一次；其余44叶照常完成，不重做成功子片。

每60秒filter=all&per_page=100分页取完整job，以ident的最新job ID为准。
仅原run completed后POST一次旧2024-A job/rerun；新叶全部关卡和持久证据严格通过才解除旧失败阻断。
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import zipfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('tem8_recovery_activation',HERE/'精听缓存核齐与组装调度.py')
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
P,ROOT,STATE,PIN=A.pub,A.ROOT,A.STATE,A.pin
RUN,HEAD,OLDJOB,UNIT=PIN['production_run'],PIN['production_commit'],132238965743,'2024-A'
REQUEST=HERE/'精听2024-A单次重试请求.json'
ENC='核当前截图与真实审阅登记一致，再编码与独立核验'
STORE='成功结果立即持久保存（临时artifact不是唯一副本）'
PRE='全部预检与完整截图（考试先音频预演；精听原声/分屏/排版）'


def api(path,post=False):
    cmd=['gh','api']+(['-X','POST'] if post else [])+['repos/'+PIN['repository']+'/'+path]
    while True:
        try:
            text=subprocess.check_output(cmd,cwd=ROOT,text=True,stderr=subprocess.STDOUT,timeout=45)
            return json.loads(text) if text.strip() else None
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:
            if post:raise  # 唯一有副作用的重试POST不自动重发。
            message=getattr(exc,'output',None) or repr(exc)
            if isinstance(message,bytes):message=message.decode(errors='replace')
            record={'at':A.now(),'method':'GET','endpoint':path,'error':str(message)[-2000:],
                    'action':'只读API等待认证/网络恢复，60秒后重读；未重试任何job或写Git'}
            print('READ_API_BLOCKED '+json.dumps(record,ensure_ascii=False),flush=True)
            with (HERE/'精听只读API失败记录.jsonl').open('a') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
            time.sleep(60)


def latest_jobs(jobs):
    found={}
    for j in jobs:
        hit=re.fullmatch(r'render \(intensive, ([^,]+), \d{4}\)',j['name'])
        if not hit:continue
        ident=hit[1]
        assert ident in PIN['expected_payload_sha256'] and j['head_sha']==HEAD
        if ident not in found or j['id']>found[ident]['id']:found[ident]=j
    assert set(found)==set(PIN['expected_payload_sha256'])
    return found


def list_all_jobs():
    jobs=[];page=1
    while True:
        data=api(f'actions/runs/{RUN}/jobs?filter=all&per_page=100&page={page}')
        jobs.extend(data['jobs'])
        if len(jobs)>=data['total_count']:break
        assert data['jobs'],'分页未完整返回job';page+=1
    return {'total_count':len(jobs),'jobs':jobs}


def eligible(run,latest,already_requested):
    other=[j for ident,j in latest.items() if ident!=UNIT]
    return not already_requested and run['status']=='completed' and run['head_sha']==HEAD and \
           len(other)==44 and all(j['status']=='completed' and j['conclusion']=='success' for j in other) and \
           latest[UNIT]['id']==OLDJOB and latest[UNIT]['conclusion']=='failure'


def request_once(run,latest):
    assert eligible(run,latest,REQUEST.exists())
    A.frozen()
    record={'status':'requesting-once','run_id':RUN,'head_sha':HEAD,'old_job_id':OLDJOB,
            'old_attempt':latest[UNIT].get('run_attempt',1),'request_time':A.now(),'request_epoch':time.time(),
            'original_run_status':run['status'],'original_run_conclusion':run['conclusion'],
            'endpoint':f'actions/jobs/{OLDJOB}/rerun','max_requests':1,
            'authorization':'root明确授权仅此job及其dependent重试一次，原run/原f252 checkout，不改45审批。'}
    # 先持久记请求意图，进程/网络中断也不能自动重复POST。
    P.dump(REQUEST,record)
    try:
        record['response']=api(record['endpoint'],True);record['status']='requested-once'
    except Exception as exc:
        record['status']='request-failed-no-auto-retry';record['error']=repr(exc);P.dump(REQUEST,record);raise
    P.dump(REQUEST,record)
    print('SINGLE_2024A_RERUN_REQUESTED '+json.dumps(record,ensure_ascii=False),flush=True)


def recovered_cache(job):
    assert REQUEST.exists() and job['id']>OLDJOB and job['head_sha']==HEAD and job['conclusion']=='success'
    assert job.get('run_attempt',2)>1
    fp=P.gate('intensive',UNIT)['payload_sha256'];rel=P.release(P.CACHE_TAG)
    assert P.cached_ready(rel,'intensive',UNIT,fp),'新2024-A持久证据未过既有完整门'
    have={x['name']:x for x in rel['assets']}
    # 此唯一恢复叶额外读一次meta/clock，明确核原run/f252来源及真实fastclock证据。
    for video,ev in P.cache_pairs(rel,'intensive',UNIT,fp):
        with tempfile.TemporaryDirectory(prefix='tem8-recovered2024A-') as td:
            P.gh('release','download',P.CACHE_TAG,'-R',P.REPO,'-p',ev,'-D',td)
            path=Path(td)/ev
            if have[ev]['digest']!='sha256:'+P.sha(path):continue
            with zipfile.ZipFile(path) as z:
                assert z.testzip() is None
                meta=json.loads(z.read('meta.json'))
                if meta['approval_payload_sha256']!=fp:continue
                assert meta['source_commit']==HEAD and str(meta['run_id'])==RUN
                assert have[video]['digest']=='sha256:'+meta['mp4_sha256'] and have[video]['size']==meta['mp4_bytes']
                for n,h in meta['evidence'].items():assert hashlib.sha256(z.read(n)).hexdigest()==h
                report=json.loads(z.read('evidence/工作记录/verification.json'))
                raw=z.read('evidence/工作记录/clock-precheck.json');clock=json.loads(raw)
                states=json.loads(z.read('evidence/工作记录/states.json'))
                assert report['ok'] is True and report['draft'] is False and report['sha256']==meta['mp4_sha256']
                assert clock['status']=='pass' and clock['failures']==[] and clock['threshold_unchanged']==3
                assert clock['checker_sha256']==PIN['frozen_files']['专八/听力/批量/tools/图片时钟核验.py']
                assert clock['source_fingerprints']['fingerprint']==report['fingerprint']
                assert clock['frames_sha256']==hashlib.sha256(json.dumps(states,separators=(',',':')).encode()).hexdigest()
                assert clock['states']==len(states) and len(clock['all_probes'])==clock['probes']
                assert all(x['ok'] is True and x['mean_difference']<=3 for x in clock['all_probes'])
                detail=next(c['detail'] for c in report['checks'] if c['item']=='图片时钟全状态首尾及邻帧')
                assert detail['report_sha256']==hashlib.sha256(raw).hexdigest() and detail['video_sha256']==clock['video_sha256']
                pngs={n.removeprefix('evidence/已审截图/shots/'):h for n,h in meta['evidence'].items() if n.startswith('evidence/已审截图/shots/')}
                assert pngs==clock['PNG_sha256']
                assert Counter(pngs.values())==Counter(P.gate('intensive',UNIT)['shots'].values())
                record={'status':'resolved-current-cache-strict-pass','run_id':RUN,'head_sha':HEAD,'old_job_id':OLDJOB,
                        'new_job_id':job['id'],'new_attempt':job.get('run_attempt'),'checked_at':A.now(),
                        'payload_sha256':fp,'mp4':video,'mp4_sha256':meta['mp4_sha256'],'mp4_bytes':meta['mp4_bytes'],
                        'evidence':ev,'evidence_sha256':P.sha(path),'source_commit':meta['source_commit'],'source_run_id':meta['run_id'],
                        'clock_states':clock['states'],'clock_probes':clock['probes'],'clock_report_sha256':hashlib.sha256(raw).hexdigest(),
                        'existing_cached_ready':True,'all_evidence_crc_sha':True,'whole_assembly_not_yet_claimed':True}
                P.dump(HERE/'精听2024-A单次恢复核验.json',record)
                return record
    raise AssertionError('恢复叶没有同原run/f252且完整SHA/clock通过的持久成品')


def resolve_old_failure(record):
    old=STATE/'failure-alert.json';resolved=STATE/'failure-alert-resolved-2024-A-job132238965743.json'
    assert old.exists() and not resolved.exists()
    original=P.read(old);assert len(original['failed'])==1 and original['failed'][0]['job_id']==OLDJOB
    old.rename(resolved)  # 原字节留存，绝不抹除历史失败。
    record['resolved_failure_archive']={'file':resolved.name,'sha256':P.sha(resolved)}
    P.dump(HERE/'精听2024-A单次恢复核验.json',record)
    shutil_target=HERE/'精听2024-A原失败已解决归档.json';shutil_target.write_bytes(resolved.read_bytes())
    stopped=STATE/'assembly-activation-failure.json'
    if stopped.exists():stopped.rename(STATE/'assembly-activation-stopped-before-recovery.json')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--self-test',action='store_true');args=ap.parse_args()
    if args.self_test:
        test_latest_and_eligibility();return
    assert not (HERE/'精听原runPOST策略已停用.json').exists(), '原run POST策略已永久停用；仅使用独立2024-A恢复编排，禁止延迟双发'
    A.frozen();last=None
    while True:
        started=time.monotonic();data=list_all_jobs();latest=latest_jobs(data['jobs'])
        P.dump(STATE/'latest-all-jobs.json',data)
        rows={};unexpected=[]
        for ident,j in latest.items():
            steps={s['name']:s for s in j.get('steps',[])}
            rows[ident]={'job_id':j['id'],'attempt':j.get('run_attempt'),'status':j['status'],'conclusion':j['conclusion'],
                         'phase':next((s['name'] for s in j.get('steps',[]) if s['status']=='in_progress'),j['status']),
                         'url':j['html_url'],'precheck':steps.get(PRE,{}).get('conclusion'),
                         'fastclock_fullverify':steps.get(ENC,{}).get('conclusion'),'persistent_store':steps.get(STORE,{}).get('conclusion')}
            if j['status']=='completed' and j['conclusion']!='success' and not (ident==UNIT and j['id']==OLDJOB):unexpected.append(j)
            if j['conclusion']=='success':assert rows[ident]['fastclock_fullverify']==rows[ident]['persistent_store']=='success'
        summary=dict(Counter('success' if r['conclusion']=='success' else 'pending_recovery' if k==UNIT and r['job_id']==OLDJOB else r['status'] for k,r in rows.items()))
        summary.update(fastclock_fullverify_passed=sum(r['fastclock_fullverify']=='success' for r in rows.values()),persistent_store_passed=sum(r['persistent_store']=='success' for r in rows.values()))
        status={'run':RUN,'head_sha':HEAD,'utc':A.now(),'summary':summary,'rows':rows,'selection':'filter=all, latest job ID per ident; old failures preserved separately'}
        P.dump(STATE/'latest-intensive-status.json',status)
        key=json.dumps(rows,sort_keys=True)
        if key!=last:
            print(json.dumps({'utc':status['utc'],'summary':summary,'2024A':rows[UNIT]},ensure_ascii=False),flush=True)
            with (STATE/'state-changes.jsonl').open('a') as f:f.write(json.dumps(status,ensure_ascii=False)+'\n')
            last=key
        if unexpected:
            P.dump(HERE/'精听恢复期间新失败.json',{'run':RUN,'head_sha':HEAD,'jobs':unexpected})
            raise RuntimeError('出现新失败或2024-A第二次失败，不自动再试')
        if latest[UNIT]['id']==OLDJOB:
            if REQUEST.exists():
                assert time.time()-P.read(REQUEST)['request_epoch']<900,'已请求一次但15分钟未出现新job，交root处理'
            elif summary.get('success')==44:
                run=api(f'actions/runs/{RUN}')
                assert run['head_sha']==HEAD
                if eligible(run,latest,False):request_once(run,latest)
                else:print('WAIT_ORIGINAL_RUN_COMPLETED '+json.dumps({'status':run['status'],'conclusion':run['conclusion']}),flush=True)
        elif latest[UNIT]['conclusion']=='success':
            assert summary.get('success')==45
            record=recovered_cache(latest[UNIT]);resolve_old_failure(record)
            P.dump(STATE/'45-current-cache-complete.json',{'run':RUN,'head_sha':HEAD,'utc':A.now(),'summary':summary,
                    'recovery':record,'scope':'44 original success + latest2024A attempt success; recovered cache strict checked; full45 cached_ready repeats before activation'})
            print('ALL45_RECOVERED_CURRENT_SUCCESS',flush=True)
            subprocess.run([sys.executable,str(HERE/'精听缓存核齐与组装调度.py')],cwd=ROOT,check=True)
            return
        time.sleep(max(0,60-(time.monotonic()-started)))


def test_latest_and_eligibility():
    jobs=[]
    for n,ident in enumerate(PIN['expected_payload_sha256']):
        jobs.append({'id':OLDJOB if ident==UNIT else n+1,'name':f'render (intensive, {ident}, {ident[:4]})','head_sha':HEAD,
                     'status':'completed','conclusion':'failure' if ident==UNIT else 'success'})
    current=latest_jobs(jobs);run={'status':'completed','head_sha':HEAD,'conclusion':'failure'}
    assert eligible(run,current,False)
    assert not eligible({**run,'status':'in_progress'},current,False)
    assert not eligible(run,current,True)
    new={**current[UNIT],'id':OLDJOB+10,'conclusion':'success'}
    assert latest_jobs(jobs+[new])[UNIT]['id']==new['id'] and latest_jobs(jobs+[new])[UNIT]['conclusion']=='success'
    assert latest_jobs([new]+jobs)[UNIT]['conclusion']=='success'
    assert not eligible(run,latest_jobs(jobs+[new]),False)
    P.dump(HERE/'精听单次恢复选择正反例.json',{'status':'pass','cases':6,
           'scope':'纯内存状态选择/一次资格判断；未请求GitHub重试、未改源/审批、未创建control'})
    print('RECOVERY_SELECTION_6_TESTS_PASS',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        P.dump(STATE/'recovery-monitor-failure.json',{'status':'stopped','at':A.now(),'error':repr(exc)})
        raise
