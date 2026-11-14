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
    return {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'memory': memory, 'loadavg': Path('/proc/loadavg').read_text().strip(),
            'processes': processes,
            'mp4_bytes': {p.name: p.stat().st_size for p in work.glob('*.mp4') if p.is_file()}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--once', action='store_true')
    args = ap.parse_args()
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
        if args.once:
            return
        time.sleep(30)


if __name__ == '__main__':
    main()
