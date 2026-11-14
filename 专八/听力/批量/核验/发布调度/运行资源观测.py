"""只读记录托管运行器资源与输出增长，协助区分平台中断和媒体核验失败。"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import time


def snapshot(work):
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable', 'SwapFree'):
            memory[key] = value.strip()
    processes = subprocess.check_output(
        ['ps', '-eo', 'pid,comm,rss,pcpu,etime', '--sort=-rss'], text=True).splitlines()[:9]
    cgroup = {}
    for name in ('memory.events', 'memory.current', 'memory.peak', 'memory.max', 'cpu.max'):
        path = Path('/sys/fs/cgroup') / name
        cgroup[name] = path.read_text().strip() if path.is_file() else None
    return {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'memory': memory, 'loadavg': Path('/proc/loadavg').read_text().strip(),
            'processes': processes, 'cgroup': cgroup,
            'mp4_bytes': {p.name: p.stat().st_size for p in work.glob('*.mp4') if p.is_file()}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--release-tag')
    ap.add_argument('--asset-name')
    args = ap.parse_args()
    assert bool(args.release_tag) == bool(args.asset_name)
    if args.asset_name:
        assert Path(args.asset_name).name == args.asset_name and args.asset_name.endswith('.json')
    args.work.mkdir(parents=True, exist_ok=True)
    rows = []
    while True:
        record = snapshot(args.work)
        rows.append(record)
        report = args.work / '运行资源观测.json'
        temporary = report.with_suffix('.json.tmp')
        temporary.write_text(json.dumps({'scope': '只读诊断，不代替质量审核', 'samples': rows},
                                        ensure_ascii=False, indent=2) + '\n')
        temporary.replace(report)
        print('TEM8_RESOURCE ' + json.dumps(record, ensure_ascii=False), flush=True)
        if args.release_tag and (len(rows) - 1) % 4 == 0:
            asset = args.work / args.asset_name
            asset.write_bytes(report.read_bytes())
            result = subprocess.run(['gh', 'release', 'upload', args.release_tag, str(asset),
                                     '-R', 'AlienCodes/university-entrance-examination', '--clobber'],
                                    capture_output=True, text=True)
            print('TEM8_RESOURCE_ARCHIVE ' + json.dumps({'asset': asset.name,
                  'uploaded': result.returncode == 0, 'error': result.stderr[-500:]}), flush=True)
        if args.once:
            return
        time.sleep(30)


if __name__ == '__main__':
    main()
