"""只读追踪一套在线样片的已上传资源JSON；相同服务器摘要不重复下载。"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[5]
s = importlib.util.spec_from_file_location('pub', ROOT / '专八/听力/批量/tools/发布汇集.py')
p = importlib.util.module_from_spec(s)
s.loader.exec_module(p)
a = argparse.ArgumentParser(description=__doc__)
a.add_argument('--state', type=Path, required=True)
a.add_argument('--run', required=True)
a.add_argument('--year', required=True)
args = a.parse_args()
name = f'tem8-resource-exam-{args.year}-{args.run}.json'
assert args.run.isdigit() and args.year in map(str, p.YEARS)
folder = args.state / 'resources' / args.run
folder.mkdir(parents=True, exist_ok=True)
last_digest, history = None, []
while True:
    snapshot = args.state / ('run-' + args.run + '-jobs.json')
    jobs = p.read(snapshot)['jobs'] if snapshot.exists() else []
    leaves = [j for j in jobs if j['name'].startswith('render (exam, ' + args.year + ',')]
    encoding_started = leaves and any(s['name'].startswith('核当前截图') and s['status'] != 'pending'
                                      for s in leaves[0].get('steps', []))
    completed = leaves and leaves[0]['status'] == 'completed'
    if encoding_started:
        try:
            asset = next((x for x in p.release(p.CACHE_TAG)['assets'] if x['name'] == name), None)
            if asset and asset['digest'] != last_digest:
                p.gh('release', 'download', p.CACHE_TAG, '-R', p.REPO, '-p', name, '-D', folder, '--clobber')
                report = folder / name
                assert asset['digest'] == 'sha256:' + p.sha(report), '资源JSON服务器摘要不符'
                data = p.read(report)
                row = data['samples'][-1]
                summary = {'run_id': args.run, 'year': args.year, 'server_digest': asset['digest'],
                           'samples': len(data['samples']), 'last_sample': row}
                history.append(summary)
                p.dump(folder / '资源摘要历史.json', history)
                print(json.dumps(summary, ensure_ascii=False), flush=True)
                last_digest = asset['digest']
        except Exception as exc:
            print(json.dumps({'resource_read_error': type(exc).__name__, 'message': str(exc)}), flush=True)
    if completed:
        break
    # 与生产者每2分钟上传的频率相同；不阻塞主任务或占用runner。
    time.sleep(60)
    time.sleep(60)
