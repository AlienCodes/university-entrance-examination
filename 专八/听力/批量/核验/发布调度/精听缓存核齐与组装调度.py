"""已授权的窄调度：45叶全部成功→现有cached_ready严格核齐→锁内仅提交整套控制及本审计。

不生成或重试子片，不改core/输入/审核，不下载MP4，只一次核持久证据ZIP和服务器MP4摘要。
--preflight只核冻结/预备控制，不等待、不创建控制、不写Git。
"""
import argparse
import datetime
import fcntl
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import time

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
    assert str(done['run'])==pin['production_run'] and done['head_sha']==pin['production_commit']
    assert done['summary']['success']==done['summary']['persistent_store_passed']==done['summary']['fastclock_fullverify_passed']==45
    current=pub.read(STATE/'latest-intensive-status.json')
    assert current['head_sha']==pin['production_commit'] and set(current['rows'])==set(pin['expected_payload_sha256'])
    assert all(r['status']=='completed' and r['conclusion']=='success' and
               r['fastclock_fullverify']==r['persistent_store']=='success' for r in current['rows'].values())
    assert not (STATE/'failure-alert.json').exists(),'监控已有失败，禁止激活'
    return current


def strict_cache():
    rel=pub.release(pub.CACHE_TAG);have={a['name']:a for a in rel['assets']};rows=[]
    for ident,fp in sorted(pin['expected_payload_sha256'].items()):
        # 复用生产既有严格门：证据ZIP CRC、meta/每个证据SHA、审核、成品报告、原音来源、MP4服务器摘要。
        assert pub.cached_ready(rel,'intensive',ident,fp),ident+'当前持久cache未严格通过'
        pairs=[]
        for video,evidence in pub.cache_pairs(rel,'intensive',ident,fp):
            pairs.append({'mp4':video,'mp4_bytes':have[video]['size'],'mp4_digest':have[video]['digest'],
                          'evidence':evidence,'evidence_bytes':have[evidence]['size'],'evidence_digest':have[evidence]['digest']})
        assert pairs
        rows.append({'id':ident,'payload_sha256':fp,'cached_ready':True,'server_pairs':pairs})
        print(json.dumps({'utc':now(),'strict_cache_passed':ident,'count':len(rows)},ensure_ascii=False),flush=True)
    record={'schema':1,'status':'pass','production_run':pin['production_run'],'production_commit':pin['production_commit'],
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
         '精听45当前持久缓存严格核验.json','精听45正式叶全部成功.json',
         '精听-state-changes.jsonl','精听-main-leaf-concurrency-history.jsonl','精听-main-leaf-concurrency.json']
    paths=[str((HERE/n).relative_to(ROOT)) for n in own if (HERE/n).is_file()]
    control_rel=str(CONTROL.relative_to(ROOT))
    gitdir=Path(git('rev-parse','--git-dir'))
    if not gitdir.is_absolute():gitdir=ROOT/gitdir
    with (gitdir/'tem8-control-publish.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        frozen();all_success()
        assert not CONTROL.exists(),'整套控制已存在，交root核是否已触发，禁止重复提交'
        CONTROL.write_bytes(READY.read_bytes())
        subprocess.run(['git','add','--sparse','--',control_rel,*paths],cwd=ROOT,check=True)
        subprocess.run(['git','commit','--only','-m','在45份当前精听子段严格核齐后启动15年整套组装','--',control_rel,*paths],cwd=ROOT,check=True)
        commit=git('rev-parse','HEAD')
        changed=git('diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines()
        # git name quoting默认可能转义汉字；用-z比较真实路径。
        changed=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-z','-r','HEAD'],cwd=ROOT).decode().rstrip('\0').split('\0')
        assert set(changed)<=set([control_rel,*paths]) and control_rel in changed
        subprocess.run(['git','push','origin','HEAD:refs/heads/'+pin['branch']],cwd=ROOT,check=True)
    activation={'schema':1,'status':'pushed','commit':commit,'production_run':pin['production_run'],'pushed_at':now(),
                'control_sha256':pub.sha(CONTROL),'strict_cache_count':cache['strict_cache_count'],'workflow_run':None}
    pub.dump(STATE/'assembly-activation-result.json',activation)
    for _ in range(20):
        result=json.loads(subprocess.check_output(['gh','run','list','--repo',pin['repository'],'--workflow','assemble-tem8-intensive-full.yml',
                      '--commit',commit,'--limit','5','--json','databaseId,status,headSha,url'],cwd=ROOT,text=True))
        if result:
            assert all(r['headSha']==commit for r in result)
            activation['workflow_run']=result[0];break
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
