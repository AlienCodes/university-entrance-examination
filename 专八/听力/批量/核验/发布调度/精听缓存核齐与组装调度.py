"""已授权的窄调度：45叶全部成功→现有cached_ready严格核齐→锁内仅提交整套控制及本审计。

不生成或重试子片，不改core/输入/审核，不下载MP4，只一次核持久证据ZIP和服务器MP4摘要。
--preflight只核冻结/预备控制，不等待、不创建控制、不写Git。
"""
import argparse
import datetime
import fcntl
import importlib.util
import json
import hashlib
from collections import Counter
from pathlib import Path
import shutil
import subprocess
import time
import tempfile
import zipfile

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
STATE=Path('/workspace/tem8-monitor-intensive-43528080039')
READY=Path('/workspace/tem8-intensive-full-control-ready.json')
CONTROL=ROOT/'.github/tem8-listening-intensive-full.json'
FREEZE=HERE/'精听自动组装激活冻结.json'


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


pub=module('intensive_activation_pub',ROOT/'专八/听力/批量/tools/发布汇集.py')
full=module('intensive_activation_full',ROOT/'专八/听力/批量/tools/整套精听发布.py')
pin=pub.read(FREEZE)


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def frozen():
    assert git('branch','--show-current')==pin['branch']
    assert git('remote','get-url','origin')=='https://github.com/'+pin['repository']+'.git'
    subprocess.run(['git','merge-base','--is-ancestor',pin['production_commit'],'HEAD'],cwd=ROOT,check=True)
    assert pub.REPO==pin['repository']
    snapshot=pub.read(HERE/'精听45完整审核登记冻结.json')
    expected=snapshot['entries']
    entries=pub.read(pub.REGISTRY)['entries']
    assert set(entries)==set(expected)|{'exam:'+str(y) for y in pub.YEARS},'登记键范围改变，不能扩入陌生kind/year'
    actual={k:v for k,v in entries.items() if k.startswith('intensive:')}
    assert len(expected)==len(actual)==45 and actual==expected and \
           pub.hash_json(actual)==pub.hash_json(expected)==snapshot['intensive_entries_sha256']==pin['intensive_registry_entries_sha256'], \
           '45条完整精听审核登记改变，不激活（仅exam登记可独立更新）'
    assert pub.sha(READY)==pin['ready_control_sha256'],'预备控制字节改变，不激活'
    assert all(pub.sha(ROOT/path)==digest for path,digest in pin['frozen_files'].items()),'冻结core/workflow改变，不激活'
    full.branch_guard();c=full.load_control(READY)
    assert c['assemble'] is True
    assert len(pin['expected_payload_sha256'])==45
    for ident,fp in pin['expected_payload_sha256'].items():
        assert pub.gate('intensive',ident)['payload_sha256']==fp,'当前子段指纹失效：'+ident


def all_success():
    done=pub.read(STATE/'45-current-cache-complete.json')
    assert str(done['original_run'])==pin['production_run'] and done['original_commit']==pin['production_commit']
    assert done['summary']['success']==done['summary']['persistent_store_passed']==done['summary']['fastclock_fullverify_passed']==45
    current=pub.read(STATE/'latest-intensive-status.json')
    producers=producer_manifest()
    assert current['producer_manifest']==done['producer_manifest']==producers
    assert set(current['rows'])==set(pin['expected_payload_sha256'])
    assert all(r['status']=='completed' and r['conclusion']=='success' and
               r['precheck']==r['fastclock_fullverify']==r['persistent_store']=='success' for r in current['rows'].values())
    assert all(str(current['rows'][ident]['producer_run'])==producer['run_id'] and
               current['rows'][ident]['producer_commit']==producer['commit'] for ident,producer in producers.items())
    assert not (STATE/'failure-alert.json').exists(),'监控已有失败，禁止激活'
    assert all((HERE/(ident+'原失败已解决归档.json')).exists() for ident in ['精听2022-A','精听2024-A']), '未保留两条已解决原始失败'
    return current


def producer_manifest():
    registration=pub.read(HERE/'精听两条两步恢复运行登记.json')
    targets=['2022-A','2024-A']
    assert registration['kind']=='intensive' and registration['targets']==targets
    assert str(registration['old_original_run'])==pin['production_run'] and registration['old_original_commit']==pin['production_commit']
    commit=registration['producer_commit'];rid=str(registration['run_id'])
    assert commit!=pin['production_commit'] and rid.isdigit() and rid!=pin['production_run']
    assert commit=='3b3154e6615fcd609a13bff0ce7251723afa937b' and rid=='43548049905', '只接受root明列的两步producer'
    assert registration['payload_sha256']=={ident:pin['expected_payload_sha256'][ident] for ident in targets}
    assert registration['intensive45_projection_sha256']==pin['intensive_registry_entries_sha256']
    assert registration['root_only_two_approval_sha256']==pin['root_approved_two_stage_change']['approval_sha256']
    assert pub.sha(ROOT/registration['root_only_two_approval'])==registration['root_only_two_approval_sha256']
    assert (HERE/'精听原runPOST策略已停用.json').exists()
    assert not (HERE/'精听2024-A单次重试请求.json').exists(),'原POST与独立恢复不能同时发生'
    subprocess.run(['git','merge-base','--is-ancestor',pin['production_commit'],commit],cwd=ROOT,check=True)
    for path,digest in pin['frozen_files'].items():
        raw=subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
        producer_digest=registration['producer_frozen_files'][path]
        assert hashlib.sha256(raw).hexdigest()==producer_digest,'新producer的冻结文件不同：'+path
        if producer_digest!=digest:
            approved=pin['root_approved_publication_only_change']
            assert path==approved['path'] and producer_digest==approved['before_sha256'] and digest==approved['after_sha256']
            assert approved['all15_actual_assembly_payloads_unchanged'] and pub.sha(ROOT/approved['approval_report'])==approved['approval_sha256']
    raw=subprocess.check_output(['git','show',commit+':'+str(pub.REGISTRY.relative_to(ROOT))],cwd=ROOT)
    entries={k:v for k,v in json.loads(raw)['entries'].items() if k.startswith('intensive:')}
    assert pub.hash_json(entries)==pin['intensive_registry_entries_sha256']
    result={ident:{'run_id':pin['production_run'],'commit':pin['production_commit']} for ident in pin['expected_payload_sha256']}
    for ident in targets:result[ident]={'run_id':rid,'commit':commit}
    return result


def cache_producer(ident,producer,rel):
    fp=pub.gate('intensive',ident)['payload_sha256'];have={a['name']:a for a in rel['assets']}
    assert pub.cached_ready(rel,'intensive',ident,fp),ident+'当前持久cache未严格通过'
    for video,evidence in pub.cache_pairs(rel,'intensive',ident,fp):
        with tempfile.TemporaryDirectory(prefix='tem8-producer-evidence-') as td:
            pub.gh('release','download',pub.CACHE_TAG,'-R',pub.REPO,'-p',evidence,'-D',td)
            archive=Path(td)/evidence
            assert have[evidence]['digest']=='sha256:'+pub.sha(archive)
            with zipfile.ZipFile(archive) as z:
                assert z.testzip() is None
                meta=json.loads(z.read('meta.json'))
                if meta['approval_payload_sha256']!=fp or meta['source_commit']!=producer['commit'] or str(meta['run_id'])!=producer['run_id']:continue
                assert meta['id']==ident and meta['kind']=='intensive'
                assert have[video]['digest']=='sha256:'+meta['mp4_sha256'] and have[video]['size']==meta['mp4_bytes']
                for n,h in meta['evidence'].items():assert hashlib.sha256(z.read(n)).hexdigest()==h
                review=json.loads(z.read('evidence/审核登记.json'))
                assert review==pub.gate('intensive',ident),'cache的完整审核登记不是当前原值'
                for path in pub.input_paths('intensive',ident):
                    assert hashlib.sha256(z.read('evidence/实际输入/'+path.name)).hexdigest()==pub.sha(path)
                actual_png={n.removeprefix('evidence/已审截图/shots/'):h for n,h in meta['evidence'].items() if n.startswith('evidence/已审截图/shots/')}
                assert Counter(actual_png.values())==Counter(review['shots'].values())
                clock_raw=z.read('evidence/工作记录/clock-precheck.json');clock=json.loads(clock_raw)
                states=json.loads(z.read('evidence/工作记录/states.json'))
                verification=json.loads(z.read('evidence/工作记录/verification.json'))
                assert clock['status']=='pass' and clock['failures']==[] and clock['threshold_unchanged']==3
                assert clock['checker_sha256']==pin['frozen_files']['专八/听力/批量/tools/图片时钟核验.py']
                assert clock['PNG_sha256']==actual_png
                assert clock['frames_sha256']==hashlib.sha256(json.dumps(states,separators=(',',':')).encode()).hexdigest()
                assert clock['states']==len(states) and len(clock['all_probes'])==clock['probes']
                assert all(x['ok'] is True and x['mean_difference']<=3 for x in clock['all_probes'])
                assert verification['ok'] is True and verification['draft'] is False and verification['sha256']==meta['mp4_sha256']
                assert clock['source_fingerprints']['fingerprint']==verification['fingerprint']
                detail=next(c['detail'] for c in verification['checks'] if c['item']=='图片时钟全状态首尾及邻帧')
                assert detail['report_sha256']==hashlib.sha256(clock_raw).hexdigest() and detail['video_sha256']==clock['video_sha256']
                two_stage=pub.validate_two_stage_proof(ident,lambda n:json.loads(z.read('evidence/工作记录/'+n)))
                if two_stage:assert two_stage['mp4_sha256']==meta['mp4_sha256'] and two_stage['source_sha256']==meta['source_sha256']
                return {'id':ident,'payload_sha256':fp,'cached_ready':True,'producer_run':str(meta['run_id']),
                        'producer_commit':meta['source_commit'],'mp4':video,'mp4_sha256':meta['mp4_sha256'],'mp4_bytes':meta['mp4_bytes'],
                        'evidence':evidence,'evidence_sha256':pub.sha(archive),'clock_states':clock['states'],'clock_probes':clock['probes'],
                        'clock_report_sha256':hashlib.sha256(clock_raw).hexdigest(),'full_current_review_inputs_png_sources_equal':True,
                        'two_stage_proof_verified':bool(two_stage),
                        'two_stage_proof_sha256':hashlib.sha256(z.read('evidence/工作记录/two-stage-encoding.json')).hexdigest() if two_stage else None}
    raise AssertionError(ident+'没有来自明确登记producer的当前严格缓存')


def strict_cache():
    rel=pub.release(pub.CACHE_TAG);rows=[];producers=producer_manifest()
    for ident,fp in sorted(pin['expected_payload_sha256'].items()):
        rows.append(cache_producer(ident,producers[ident],rel))
        print(json.dumps({'utc':now(),'strict_cache_passed':ident,'count':len(rows)},ensure_ascii=False),flush=True)
    record={'schema':1,'status':'pass','original_run':pin['production_run'],'original_commit':pin['production_commit'],
            'producer_manifest':producers,
            'checked_at':now(),'current_cache_tag':pub.CACHE_TAG,'strict_cache_count':len(rows),'rows':rows,
            'scope':'全部45当前fp证据ZIP由现有cached_ready完整CRC/SHA/原音门核过，服务器MP4摘要吻合；未冒称15年整套已完成。'}
    assert len(rows)==45
    pub.dump(HERE/'精听45当前持久缓存严格核验.json',record)
    return record


def activate():
    frozen();current=all_success();cache=strict_cache();frozen()
    pub.dump(HERE/'精听45正式叶全部成功.json',current)
    for source in ['state-changes.jsonl','main-leaf-concurrency-history.jsonl','main-leaf-concurrency.json']:
        path=STATE/source
        if path.is_file():shutil.copyfile(path,HERE/('精听-'+source))
    # 只列自己拥有的审计文件，绝不把同目录考试调度/其他staged修改混进提交。
    own=['精听任务监控.py','精听主任务并发记录.py','精听缓存核齐与组装调度.py','精听自动组装激活冻结.json','精听45完整审核登记冻结.json','精听登记投影冻结正反例.json',
         '精听单叶中断恢复监控.py','精听单次恢复选择正反例.json','精听2024-A单次重试请求.json','精听2024-A单次恢复核验.json',
         '精听只读API失败记录.jsonl',
         '精听独立单叶恢复监控.py','精听2024-A独立恢复运行登记.json','精听2024-A独立恢复编排核验.json','精听原runPOST策略已停用.json',
         '精听复合producer正反例.json','精听复合来源2009-A真实严格核验.json',
         '精听2024-A独立恢复失败运行登记.json','精听2024-A第二次runner中断核验.json','精听2024-A-run43544278676-job132293554239-connector.log',
         '精听2022-A-runner失联核验.json','精听2022-A-原始job.json','精听2022-A-原始annotations.json','精听2022-A-原始checkrun.json',
         '精听独立恢复期间新失败.json',
         '精听43已成品严格核验.py','精听43已成品严格核验.json',
         '精听两条两步恢复运行登记.json','精听两条两步恢复监控.py','精听两条两步恢复完成核验.json','精听2022-A原失败已解决归档.json',
         '精听仅两条新审批冻结迁接核验.json',
         '精听43加两条实际producer冻结核验.json',
         '精听根批准两条producer正反例.json',
         '精听2024-A-runner中断核验.json','精听2024-A-run43528080039-job132238965743-connector.log','精听2024-A原失败已解决归档.json',
         '精听失败时-failure-alert.json','精听失败时-latest-intensive-status.json','精听失败时-main-leaf-concurrency.json',
         '精听45当前持久缓存严格核验.json','精听45正式叶全部成功.json',
         '精听-state-changes.jsonl','精听-main-leaf-concurrency-history.jsonl','精听-main-leaf-concurrency.json']
    paths=[str((HERE/n).relative_to(ROOT)) for n in own if (HERE/n).is_file()]
    control_rel=str(CONTROL.relative_to(ROOT))
    gitdir=Path(git('rev-parse','--git-dir'))
    if not gitdir.is_absolute():gitdir=ROOT/gitdir
    with (gitdir/'tem8-control-publish.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        frozen();all_success()
        for path,digest in pin['frozen_files'].items():
            assert hashlib.sha256(subprocess.check_output(['git','show','HEAD:'+path],cwd=ROOT)).hexdigest()==digest, '发布触发提交尚未包含已批准冻结文件：'+path
        assert not CONTROL.exists(),'整套控制已存在，交root核是否已触发，禁止重复提交'
        CONTROL.write_bytes(READY.read_bytes())
        subprocess.run(['git','add','--sparse','--',control_rel,*paths],cwd=ROOT,check=True)
        subprocess.run(['git','commit','--only','-m','在45份当前精听子段及独立恢复来源严格核齐后启动15年整套组装','--',control_rel,*paths],cwd=ROOT,check=True)
        commit=git('rev-parse','HEAD')
        changed=git('diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines()
        # git name quoting默认可能转义汉字；用-z比较真实路径。
        changed=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-z','-r','HEAD'],cwd=ROOT).decode().rstrip('\0').split('\0')
        assert set(changed)<=set([control_rel,*paths]) and control_rel in changed
        subprocess.run(['git','push','origin','HEAD:refs/heads/'+pin['branch']],cwd=ROOT,check=True)
    activation={'schema':1,'status':'pushed','commit':commit,'original_run':pin['production_run'],
                'producer_manifest':producer_manifest(),'pushed_at':now(),
                'control_sha256':pub.sha(CONTROL),'strict_cache_count':cache['strict_cache_count'],'workflow_run':None}
    pub.dump(STATE/'assembly-activation-result.json',activation)
    for _ in range(20):
        # 首次在非默认分支触发时workflow文件名查询可短暂404；按完整提交查run不依赖该注册。
        result=json.loads(subprocess.check_output(['gh','api','repos/'+pin['repository']+'/actions/runs?head_sha='+commit+'&per_page=100'],cwd=ROOT,text=True))['workflow_runs']
        result=[r for r in result if r['path']=='.github/workflows/assemble-tem8-intensive-full.yml']
        if result:
            assert all(r['head_sha']==commit for r in result)
            r=result[0];activation['workflow_run']={'databaseId':r['id'],'status':r['status'],'headSha':r['head_sha'],'url':r['html_url']};break
        time.sleep(15)
    pub.dump(STATE/'assembly-activation-result.json',activation)
    print('ASSEMBLY_ACTIVATED '+json.dumps(activation,ensure_ascii=False),flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--preflight',action='store_true');args=ap.parse_args()
    frozen()
    if args.preflight:
        print('PREFLIGHT_FROZEN45_OK_CONTROL_NOT_CREATED',flush=True);return
    while not (STATE/'45-current-cache-complete.json').exists():
        if (STATE/'failure-alert.json').exists():raise RuntimeError('叶任务失败，停止自动激活，交root处理')
        time.sleep(30)
    activate()


if __name__=='__main__':
    try:main()
    except Exception as exc:
        pub.dump(STATE/'assembly-activation-failure.json',{'status':'rejected','at':now(),'reason':repr(exc)})
        raise
