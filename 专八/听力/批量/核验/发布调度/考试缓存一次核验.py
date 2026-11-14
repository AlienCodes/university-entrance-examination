"""15个有效生产叶成功后，只执行一轮cached_ready，旁路留存同次下载的真实meta。"""
import argparse
import datetime
import importlib.util
import hashlib
import json
from pathlib import Path
import zipfile
import shutil
from collections import Counter

a = argparse.ArgumentParser(description=__doc__)
a.add_argument('--state', type=Path, required=True)
a.add_argument('--run', required=True)
a.add_argument('--production-commit', required=True)
a.add_argument('--producer-register', type=Path, required=True)
args = a.parse_args()
root = Path(__file__).resolve().parents[5]
s = importlib.util.spec_from_file_location('pub', root / '专八/听力/批量/tools/发布汇集.py')
p = importlib.util.module_from_spec(s)
s.loader.exec_module(p)
done = p.read(args.state / 'exam-all-success.json')
assert str(done['run_id']) == args.run
assert len(done['jobs']) == 15 and all(j['conclusion'] == 'success' for j in done['jobs'])
registration=p.read(args.producer_register)
assert done['producer_register']==registration
allowed={str(r['run_id']):r for r in registration['runs'] if r.get('accept_media',True)}
rel = p.release(p.CACHE_TAG)
have = {a['name']: a for a in rel['assets']}
rows, captured, reviews, producer_heads = [], {}, {}, {}
real_gh = p.gh

def witness(*argv, **kwargs):
    # 真调用原helper；仅在其同次下载后读取meta，避免为记录producer再下载一次证据。
    reused = False
    if len(argv) > 1 and argv[:2] == ('release', 'download'):
        pattern = argv[argv.index('-p') + 1]
        saved = args.state / 'smoke-2009-validated' / pattern
        if saved.is_file() and have[pattern]['digest'] == 'sha256:' + p.sha(saved):
            target = Path(argv[argv.index('-D') + 1]) / pattern
            shutil.copyfile(saved, target)
            reused = True
    value = '' if reused else real_gh(*argv, **kwargs)
    if len(argv) > 1 and argv[:2] == ('release', 'download'):
        folder = Path(argv[argv.index('-D') + 1])
        pattern = argv[argv.index('-p') + 1]
        with zipfile.ZipFile(folder / pattern) as z:
            m = json.loads(z.read('meta.json'))
            captured[m['id']] = m
            reviews[m['id']] = {'review': json.loads(z.read('evidence/审核登记.json'))}
            reviews[m['id']]['actual_pngs'] = [hashlib.sha256(z.read(n)).hexdigest()
                for n in m['evidence'] if n.startswith('evidence/已审截图/') and n.endswith('.png')]
    return value

p.gh = witness
for year in p.YEARS:
    ident = str(year)
    gate = p.gate('exam', ident)
    fp = gate['payload_sha256']
    ready = p.cached_ready(rel, 'exam', ident, fp)
    assert ready, ident + '当前持久缓存未ready'
    m = captured[ident]
    producer=allowed[str(m['run_id'])]
    assert ident in producer['target_ids'] and m['source_commit']==producer['source_commit']
    producer_id = str(m['run_id'])
    if producer_id not in producer_heads:
        actual_run = real_gh('api', f'repos/{p.REPO}/actions/runs/{producer_id}', json_output=True)
        assert actual_run['head_sha'] == producer['source_commit']
        assert actual_run['repository']['full_name'] == p.REPO
        producer_heads[producer_id] = actual_run['head_sha']
    review = reviews[ident]['review']
    assert review['inputs'] == gate['inputs'] and review['render_sources'] == gate['render_sources']
    assert Counter(review['shots'].values()) == Counter(gate['shots'].values())
    assert Counter(reviews[ident]['actual_pngs']) == Counter(gate['shots'].values())
    assert m['approval_payload_sha256'] == fp
    candidates = []
    for video, ev in p.cache_pairs(rel, 'exam', ident, fp):
        candidates.append({'video': video, 'video_bytes': have[video]['size'],
                           'video_server_digest': have[video]['digest'], 'evidence': ev,
                           'evidence_bytes': have[ev]['size'], 'evidence_server_digest': have[ev]['digest']})
    rows.append({'id': ident, 'approval_payload_sha256': fp, 'ready': True,
                 'producer_run_id': str(m['run_id']), 'producer_source_commit': m['source_commit'],
                 'actual_producer_head_sha': producer_heads[producer_id],
                 'mp4_sha256': m['mp4_sha256'], 'mp4_bytes': m['mp4_bytes'],
                 'server_candidates': candidates})
    print(json.dumps({'id': ident, 'ready': True, 'producer_run_id': str(m['run_id'])}), flush=True)
p.dump(root / '专八/听力/批量/核验/考试正式发布/生产15缓存核验.json',
       {'status': 'PASS', 'production_run_id': args.run, 'production_commit': args.production_commit,
        'producer_register': registration, 'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'cache_tag': p.CACHE_TAG, 'cached_ready_checks': 15, 'count': len(rows), 'rows': rows})
print('ALL_15_CURRENT_CACHE_READY', flush=True)
