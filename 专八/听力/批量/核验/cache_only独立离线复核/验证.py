"""只在临时目录/内存远端复核真实publish分支；不建控制文件、不访问网络、不生成媒体。"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
B = HERE.parents[1]
spec = importlib.util.spec_from_file_location('publisher_under_review', B / 'tools/发布汇集.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
CODE_SHA = P.sha(B / 'tools/发布汇集.py')
YEARS = list(map(str, P.YEARS))
PARTS = [f'{y}-{part}' for y in YEARS for part in ('A', 'B1', 'B2')]
CONTROL_SENTINEL = Path('/__offline_in_memory_control_not_created__.json')
RESULTS = []


def forbidden(*args, **kwargs):
    raise AssertionError('离线试验不准调用子进程、真实网络、正式打包或生成入口')


def fp(kind, ident):
    return P.hash_json({'offline_fixture_current_clock': True, 'kind': kind, 'id': ident})


def config(**changes):
    c = {'mode': 'sample', 'sample_id': 'offline-cache-collection', 'stage': 'render',
         'cache_only': True, 'render': False, 'exam': YEARS, 'intensive': PARTS,
         'collect_runs': [], 'reuse_releases': {'exam': [], 'intensive': []}}
    c.update(changes)
    return c


def parsed(c):
    real_read = P.read
    def in_memory(path):
        return copy.deepcopy(c) if Path(path) == CONTROL_SENTINEL else real_read(path)
    with patch.object(P, 'read', side_effect=in_memory):
        return P.load_control(CONTROL_SENTINEL)


def fixtures(art):
    for kind, ids in [('exam', YEARS), ('intensive', PARTS)]:
        for ident in ids:
            folder = art / f'{kind}-{ident}'
            work = folder / 'evidence/工作记录'
            work.mkdir(parents=True)
            # 仅测试发布器的字节/证据契约，不把这些标识字节冒充可播放视频。
            video = folder / P.asset(kind, ident)
            video.write_bytes(b'OFFLINE-NOT-A-PLAYABLE-VIDEO\n' + f'{kind}:{ident}'.encode())
            prep = P.read(B / f'预处理/{ident[:4]}/原音准备.json')
            source_sha = prep['canonical']['sha256']
            P.dump(work / '源音频准备.json', prep)
            P.dump(folder / 'evidence/审核登记.json', {
                'status': 'approved', 'payload_sha256': fp(kind, ident),
                'shots': {'offline-fixture.png': '2' * 64}})
            report = ({'问题': [], '原音模式': True, '成品sha256': P.sha(video)} if kind == 'exam'
                      else {'ok': True, 'draft': False, 'sha256': P.sha(video)})
            P.dump(work / 'verification.json', report)
            meta = {'schema': 1, 'kind': kind, 'id': ident, 'year': int(ident[:4]),
                    'label': f'OFFLINE {ident}.mp4', 'approval_payload_sha256': fp(kind, ident),
                    'mp4': video.name, 'mp4_sha256': P.sha(video), 'mp4_bytes': video.stat().st_size,
                    'source_sha256': source_sha,
                    'source_record': P.validate_source_preparation(prep, int(ident[:4]), source_sha),
                    'verification': {'ok': True, 'draft': False, 'report': 'verification.json'},
                    'evidence': {p.relative_to(folder).as_posix(): P.sha(p) for p in folder.rglob('*.json')}}
            P.dump(folder / 'meta.json', meta)
            P.validate_stage(folder, kind, ident, fp(kind, ident))


def run_case(name, c, art, out, reject=False, corrupt_remote=None):
    events, assets = [], {}
    def release(tag):
        events.append({'op': 'read_release', 'tag': tag})
        assert tag == P.CACHE_TAG
        return {'assets': list(assets.values())}
    def ensure(tag, *args):
        events.append({'op': 'ensure_release', 'tag': tag})
        assert tag == P.CACHE_TAG
    def upload(tag, path, label=None):
        path = Path(path)
        events.append({'op': 'upload', 'tag': tag, 'name': path.name})
        assert tag == P.CACHE_TAG and path.suffix == '.json'
        assert path.name.startswith('tem8-render-collection-')
        assets[path.name] = {'name': path.name, 'digest': 'sha256:' + P.sha(path),
                             'size': path.stat().st_size, 'label': label}
        if corrupt_remote == 'digest': assets[path.name]['digest'] = 'sha256:' + '0' * 64
        if corrupt_remote == 'size': assets[path.name]['size'] += 1
    error, summary = None, None
    with patch.multiple(P, release=release, ensure_release=ensure, upload=upload,
                        gate=lambda kind, ident: {'payload_sha256': fp(kind, ident)},
                        gh=forbidden, tag=forbidden, zip_files=forbidden, groups=forbidden), \
         patch.object(P.subprocess, 'run', side_effect=forbidden), \
         patch.object(P.subprocess, 'check_output', side_effect=forbidden), \
         patch.object(P.subprocess, 'Popen', side_effect=forbidden):
        try:
            summary = P.publish(c, art, out)
        except (AssertionError, KeyError, FileNotFoundError) as ex:
            error = type(ex).__name__ + ': ' + str(ex)
    writes = [e for e in events if e['op'] in ('ensure_release', 'upload')]
    assert bool(error) == reject, (name, error)
    if reject and not corrupt_remote:
        assert not writes, (name, '缺项/非法模式在远端写前未拒绝', writes)
    if not reject:
        assert summary['counts'] == {'exam': 15, 'intensive': 45}
        assert summary['mode'] == 'internal_cache_only' and summary['official_release_updated'] is False
        assert {m['id'] for m in summary['videos']['exam']} == set(YEARS)
        assert {m['id'] for m in summary['videos']['intensive']} == set(PARTS)
        assert [e['op'] for e in events] == ['ensure_release', 'upload', 'read_release']
        assert len(list(out.iterdir())) == 1 and next(out.iterdir()).suffix == '.json'
    if corrupt_remote:
        assert error and '服务器资产不匹配' in error
        assert [e['op'] for e in events][-1] == 'read_release'
    RESULTS.append({'name': name, 'passed': True, 'rejected': reject, 'actual_error': error,
                    'remote_mutations': writes, 'remote_reads': len(events) - len(writes),
                    'real_subprocess_or_network_calls': 0,
                    'server_digest_verifier': '真实verify_release_digest未替换'})


def main():
    with tempfile.TemporaryDirectory(prefix='tem8-cache-only-independent-') as temp:
        temp = Path(temp); art = temp / 'art'; fixtures(art)
        c = parsed(config())
        run_case('60项齐全：仅CACHE_TAG上传一份汇集JSON并核服务器摘要', c, art, temp / 'positive')
        for kind, ident in [('exam', '2009'), ('intensive', '2009-B2')]:
            folder = art / f'{kind}-{ident}'; held = temp / f'held-{kind}'; folder.rename(held)
            try: run_case(f'缺一个{kind}目标：任何远端写之前拒绝', c, art, temp / f'missing-{kind}', reject=True)
            finally: held.rename(folder)
        changed = []
        for ident in YEARS[:10]:
            p = art / f'exam-{ident}/meta.json'; m = P.read(p); changed.append((p, copy.deepcopy(m)))
            m['approval_payload_sha256'] = '0' * 64; P.dump(p, m)
        try: run_case('10旧审批指纹＋5当前考试：不能充当15新精确时钟缓存', c, art, temp / 'stale-ten', reject=True)
        finally:
            for p, m in changed: P.dump(p, m)
        run_case('服务器digest篡改：真实校验拒绝', c, art, temp / 'bad-digest', reject=True, corrupt_remote='digest')
        run_case('服务器size篡改：真实校验拒绝', c, art, temp / 'bad-size', reject=True, corrupt_remote='size')
        old = config(mode='complete', cache_only=False)
        try: parsed(old)
        except AssertionError as ex: RESULTS.append({'name':'旧complete＋45子段：真实load_control拒绝，无控制文件', 'passed':True, 'actual_error':str(ex)})
        else: raise AssertionError('旧complete45入口未拒绝')
        run_case('绕过load_control直接旧complete45：publish在远端写前拒绝', old, art, temp / 'old-complete', reject=True)
        events = []
        with patch.object(P, 'release', side_effect=lambda tag: events.append(tag) or {'assets': []}), patch.object(P, 'gate', side_effect=forbidden):
            assert P.matrix(c) == [] and events == [P.CACHE_TAG]
        RESULTS.append({'name':'cache_only＋render=false：真实matrix为空，不启动媒体任务', 'passed':True})
    assert P.sha(B / 'tools/发布汇集.py') == CODE_SHA, '审查期间publisher变动，须重跑本次离线复核'
    report = {'status':'independent_offline_positive_and_negative_passed','publisher_sha256':CODE_SHA,
              'fixtures':{'exam':15,'intensive_internal_segments':45,'stage_validation':'实际validate_stage/find_stage/recover执行；仅gate为隔离的测试审批，MP4是显式不可播放字节，不是视频生产或成品审核。'},
              'case_count':len(RESULTS),'cases':RESULTS,
              'scope_limit':'真实远端以严格内存服务器替代；未触网，未创建任何控制文件，未改发布器/生产源/审核登记，未生成视频或正式Release。',
              'matrix_note':'cache_only控制发布分支；生产矩阵另由render控制，仅续收时必须render=false。'}
    P.dump(HERE / '结果.json', report)
    print(json.dumps({'cases':len(RESULTS),'passed':all(c['passed'] for c in RESULTS),'publisher_sha256':CODE_SHA}, ensure_ascii=False))


if __name__ == '__main__':
    main()
