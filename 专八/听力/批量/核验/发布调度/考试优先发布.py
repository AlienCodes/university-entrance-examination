"""已授权的考试优先发布串接；先并行运行考试任务监控.py，同传 --state/--run。

只提交本控制及小型审核记录；不修改渲染器、registry或主workflow。
遇失败即停。排队只记录请求优先处理，不取消任何生成任务。
"""
import argparse
import datetime
import fcntl
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location('pub', ROOT / '专八/听力/批量/tools/发布汇集.py')
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)
BRANCH = 'codex/tem8-listening-2009-2024'
CONTROL = ROOT / '.github/tem8-listening-exam-publish.json'
CACHE_AUDIT = ROOT / '专八/听力/批量/核验/考试正式发布/生产15缓存核验.json'
SIXTY_AUDIT = ROOT / '专八/听力/批量/核验/最终图片审批合并/独立全60复核.json'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('--production-commit', required=True)
    parser.add_argument('--producer-register', type=Path, required=True)
    args = parser.parse_args()
    state = args.state.resolve()
    state.mkdir(parents=True, exist_ok=True)
    common = ['--state', str(state), '--run', args.run, '--production-commit', args.production_commit]
    if args.producer_register:
        args.producer_register = args.producer_register.resolve()
        common += ['--producer-register', str(args.producer_register)]
    pushed_path = state / 'control-pushed.json'
    last_blocked = None
    while not (state / 'exam-all-success.json').is_file():
        if (state / 'exam-failed.json').exists():
            failed = [j['id'] for j in pub.read(state / 'exam-failed.json')]
            if failed != last_blocked:
                emit({'PUBLISH_BLOCKED_UNKNOWN_FAILURE': failed, 'action': '只读等待真实故障核定，不创建发布控制'})
                last_blocked = failed
        time.sleep(10)
    done = pub.read(state / 'exam-all-success.json')
    assert str(done['run_id']) == args.run and len(done['jobs']) == 15
    assert all(j['conclusion'] == 'success' for j in done['jobs'])
    if not pushed_path.exists():
        if not CACHE_AUDIT.exists() or str(pub.read(CACHE_AUDIT).get('production_run_id')) != args.run:
            subprocess.run([sys.executable, str(HERE / '考试缓存一次核验.py'), *common], check=True, cwd=ROOT)
        cache = pub.read(CACHE_AUDIT)
        assert cache['status'] == 'PASS' and cache['count'] == cache['cached_ready_checks'] == 15
        lock_path = Path(git('rev-parse', '--git-path', 'tem8-control-publish.lock'))
        if not lock_path.is_absolute():
            lock_path = ROOT / lock_path
        with lock_path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            assert git('branch', '--show-current') == BRANCH
            subprocess.run(['git', 'merge-base', '--is-ancestor', args.production_commit, 'HEAD'], cwd=ROOT, check=True)
            remote = git('ls-remote', 'origin', 'refs/heads/' + BRANCH).split()[0]
            assert remote == git('rev-parse', 'HEAD'), '本地与远端分支不一致；不能自动推送'
            for row in cache['rows']:
                assert pub.gate('exam', row['id'])['payload_sha256'] == row['approval_payload_sha256']
            sixty = pub.read(SIXTY_AUDIT)
            assert sixty['status'] == 'PASS' and sixty['count'] == 60 and not sixty['unknown_differences']
            assert sixty['registry_sha256'] == pub.sha(pub.REGISTRY)
            control = {'mode': 'complete_exam', 'stage': 'render', 'exam': pub.YEARS,
                       'intensive': [], 'render': False, 'collect_runs': [],
                       'reuse_releases': {'exam': [], 'intensive': []},
                       'production_run_id': args.run, 'production_commit': args.production_commit}
            if args.producer_register:
                control['registered_producer_runs'] = pub.read(args.producer_register)['runs']
            pub.dump(CONTROL, control)
            pub.load_control(CONTROL)
            paths = [CONTROL, SIXTY_AUDIT, CACHE_AUDIT,
                     *[HERE / n for n in ['考试优先发布.py', '考试缓存一次核验.py',
                                          '考试正式Release核验.py', '考试任务监控.py']]]
            if args.producer_register:
                assert args.producer_register.is_relative_to(ROOT)
                paths.append(args.producer_register)
            for year in pub.YEARS:
                failure_record = ROOT / f'专八/听力/批量/核验/考试正式发布/{year}-runner关闭证据.json'
                if failure_record.exists():
                    paths.append(failure_record)
            relatives = [p.relative_to(ROOT).as_posix() for p in paths]
            subprocess.run(['git', 'add', '--', *relatives], cwd=ROOT, check=True)
            subprocess.run(['git', 'diff', '--cached', '--check'], cwd=ROOT, check=True)
            subprocess.run(['git', 'commit', '--only', '-m', '优先发布已核验十五套专八考试视频并保存发布调度审计',
                            '--', *relatives], cwd=ROOT, check=True)
            commit = git('rev-parse', 'HEAD')
            subprocess.run(['git', 'push', 'origin', 'HEAD:refs/heads/' + BRANCH], cwd=ROOT, check=True)
            pushed = {'status': 'PUSHED', 'commit': commit, 'production_run_id': args.run,
                      'control': CONTROL.relative_to(ROOT).as_posix(), 'paths': relatives,
                      'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
            pub.dump(pushed_path, pushed)
            emit({'CONTROL_PUSHED': pushed})
            fcntl.flock(lock, fcntl.LOCK_UN)
    pushed = pub.read(pushed_path)
    commit = pushed['commit']
    workflow_run = None
    for _ in range(20):
        data = pub.gh('api', f'repos/{pub.REPO}/actions/workflows/publish-tem8-complete-exams.yml/runs?per_page=30&head_sha={commit}', json_output=True)
        workflow_run = next((r for r in data['workflow_runs'] if r['head_sha'] == commit), None)
        if workflow_run:
            break
        time.sleep(15)
    assert workflow_run, '控制已推送，但没有找到对应独立发布run'
    rid = workflow_run['id']
    pub.dump(state / 'exam-publish-run.json', {'run_id': rid, 'head_sha': commit, 'html_url': workflow_run['html_url']})
    emit({'PUBLISH_RUN': rid, 'url': workflow_run['html_url']})
    previous, queue_reported = None, False
    while True:
        run = pub.gh('api', f'repos/{pub.REPO}/actions/runs/{rid}', json_output=True)
        jobs = pub.gh('api', f'repos/{pub.REPO}/actions/runs/{rid}/jobs?per_page=100', json_output=True)['jobs']
        summary = {'run_id': rid, 'status': run['status'], 'conclusion': run['conclusion'],
                   'jobs': [{k: j[k] for k in ('id', 'name', 'status', 'conclusion')} for j in jobs]}
        pub.dump(state / 'publish-current.json', summary)
        if summary != previous:
            emit(summary)
            previous = summary
        if any(j['status'] == 'queued' for j in jobs) and not queue_reported:
            running = pub.gh('api', f'repos/{pub.REPO}/actions/runs?status=in_progress&per_page=100', json_output=True)['workflow_runs']
            active = 0
            for other in running:
                leaves = pub.gh('api', f'repos/{pub.REPO}/actions/runs/{other["id"]}/jobs?per_page=100', json_output=True)['jobs']
                active += sum(j['status'] == 'in_progress' for j in leaves)
            if active >= 20:
                record = {'run_id': rid, 'production_run_id': args.run, 'main_running': active,
                          'action': '通知root优先空槽；未取消任何任务'}
                pub.dump(state / 'publish-queued-needs-priority.json', record)
                emit({'PUBLISH_QUEUED_NEEDS_PRIORITY': record})
                queue_reported = True
        if run['status'] == 'completed':
            assert run['conclusion'] == 'success', '独立发布失败，保留run诊断，不重做成功视频'
            break
        time.sleep(55)
    subprocess.run([sys.executable, str(HERE / '考试正式Release核验.py'), *common], cwd=ROOT, check=True)
    result = pub.read(ROOT / '专八/听力/批量/核验/考试正式发布/正式Release独立回下载核验.json')
    assert result['status'] == 'PASS' and result['videos'] == 15
    pub.dump(state / 'final-release-verified.json', result)
    emit({'FORMAL_EXAM_RELEASE_VERIFIED': result['release_url'], 'videos': 15,
          'archives': result['archives']})


if __name__ == '__main__':
    main()
