"""480p无音轨图片时钟诊断：逐状态首/末/邻帧按真实帧号解码。

python 图片时钟核验.py --video fast.mp4 --fr states.json --shotdir shots \
    --totalframes 12345 --report clock-precheck.json [--source-fingerprints sources.json]

仅验证图片时钟，不代替4K成品/原音核验。与考试已实测的关卡同一算法、同一3灰阶阈值。
"""
from __future__ import annotations
import argparse
import bisect
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

FPS, WIDTH, HEIGHT, THRESHOLD = 30, 480, 270, 3


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def dump(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', 'utf-8')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def normalize_frames(fr, totalframes):
    require(type(totalframes) is int and totalframes > 0, '总帧数须为正整数')
    require(isinstance(fr, list) and fr, '真实状态帧表为空')
    for row in fr:
        require(isinstance(row, (list, tuple)) and len(row) == 2 and
                type(row[0]) is int and isinstance(row[1], str) and
                re.fullmatch(r'[A-Za-z0-9_-]+', row[1]), '状态帧/截图key格式错误')
    normalized = [[f, key] for f, key in fr]
    starts = [f for f, _ in normalized]
    require(starts[0] == 0 and starts[-1] < totalframes and
            all(b > a for a, b in zip(starts, starts[1:])), '帧表越界或含零帧状态')
    return normalized


def frame_sha(fr):
    return hashlib.sha256(json.dumps(fr, separators=(',', ':')).encode()).hexdigest()


def probes(fr, totalframes):
    fr = normalize_frames(fr, totalframes)
    starts = [f for f, _ in fr]
    return sorted({n for i, (f, _) in enumerate(fr)
                   for n in [max(0, f-1), f,
                             min(f+1, (starts[i+1] if i+1 < len(fr) else totalframes)-1),
                             min(f+2, (starts[i+1] if i+1 < len(fr) else totalframes)-1),
                             (starts[i+1] if i+1 < len(fr) else totalframes)-1]})


def select_expression(targets):
    ranges = []
    for n in targets:
        if ranges and n == ranges[-1][1]+1:
            ranges[-1][1] = n
        else:
            ranges.append([n, n])
    def balanced(items):
        if len(items) == 1:
            return items[0]
        k = len(items)//2
        return '('+balanced(items[:k])+'+'+balanced(items[k:])+')'
    require(bool(ranges), '精确探针为空')
    return balanced([f'between(n,{a},{b})' for a, b in ranges])


def png_hashes(fr, shotdir):
    shotdir = Path(shotdir)
    result = {}
    for key in sorted({key for _, key in fr}):
        path = shotdir/(key+'.png')
        require(path.is_file(), '缺少真实截图：'+str(path))
        result[key+'.png'] = sha(path)
    return result


def check(video, fr, shotdir, totalframes, report, source_fingerprints=None):
    """完整实解码；任何参数/解码异常也落拒绝报告，绝不留下旧pass。"""
    import numpy as np
    from PIL import Image
    video, shotdir, report = Path(video), Path(shotdir), Path(report)
    record = {'schema': 1, 'status': 'rejected', 'source_fingerprints': source_fingerprints or {},
              'checker_sha256': sha(__file__), 'threshold_unchanged': THRESHOLD,
              'scope': '480p无音轨诊断；逐状态首帧/末帧/邻帧，select n精确解码；不代替4K和原音核验'}
    dump(report, record)
    try:
        fr = normalize_frames(fr, totalframes)
        target = probes(fr, totalframes)
        record.update(states=len(fr), probes=len(target), total_frames=totalframes,
                      frames_sha256=frame_sha(fr), PNG_sha256=png_hashes(fr, shotdir),
                      video_sha256=sha(video))
        info = json.loads(subprocess.check_output([
            'ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(video)]))
        videos = [s for s in info['streams'] if s['codec_type'] == 'video']
        require(len(videos) == 1 and not any(s['codec_type'] == 'audio' for s in info['streams']),
                '图片时钟诊断须恰有一个视频流且无音轨')
        metadata = videos[0]
        require((metadata['width'], metadata['height']) == (WIDTH, HEIGHT) and
                metadata['r_frame_rate'] == f'{FPS}/1' and int(metadata['nb_frames']) == totalframes,
                '快片分辨率、帧率或完整帧数不符')
        refs = {}
        for key in sorted({key for _, key in fr}):
            with Image.open(shotdir/(key+'.png')) as image:
                refs[key] = np.asarray(image.convert('L').resize((WIDTH, HEIGHT)), dtype=np.int16)
        cmd = ['ffmpeg', '-v', 'error', '-i', str(video), '-vf',
               f"select='{select_expression(target)}',format=gray", '-vsync', '0', '-f', 'rawvideo', '-']
        rows, starts = [], [f for f, _ in fr]
        with tempfile.TemporaryFile() as errors:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errors)
            try:
                for n in target:
                    raw = proc.stdout.read(WIDTH*HEIGHT)
                    require(len(raw) == WIDTH*HEIGHT, f'快片精确解码缺帧：{n}')
                    actual = np.frombuffer(raw, dtype=np.uint8).reshape(HEIGHT, WIDTH).astype(np.int16)
                    i = bisect.bisect_right(starts, n)-1
                    key = fr[i][1]
                    difference = float(np.abs(actual-refs[key]).mean())
                    rows.append({'frame': n, 'state_start_frame': starts[i], 'key': key,
                                 'mean_difference': round(difference, 6), 'ok': difference <= THRESHOLD})
                require(not proc.stdout.read(1), '快片解码出现未登记探针')
                exit_code = proc.wait()
                errors.seek(0)
                require(exit_code == 0, '快片精确抽帧失败：'+errors.read().decode(errors='replace')[-2000:])
            finally:
                proc.stdout.close()
                if proc.poll() is None:
                    proc.kill(); proc.wait()
        failed = [r for r in rows if not r['ok']]
        record.update(status='pass' if not failed else 'rejected', failures=failed, all_probes=rows,
                      max_mean_difference=max(r['mean_difference'] for r in rows))
        dump(report, record)
        require(not failed, '快片逐状态边界不符：'+str(failed[:8]))
        return record
    except Exception as exc:
        record['status'] = 'rejected'; record['error'] = str(exc)
        dump(report, record)
        raise


def require_pass(video, fr, shotdir, totalframes, report, source_fingerprints=None):
    """正式编码紧前核绑定，禁止复用源/程序/帧表/PNG/快片任一过期的pass。"""
    fr = normalize_frames(fr, totalframes)
    record = json.loads(Path(report).read_text('utf-8'))
    require(record.get('schema') == 1 and record.get('status') == 'pass' and
            record.get('failures') == [] and record.get('threshold_unchanged') == THRESHOLD and
            record.get('checker_sha256') == sha(__file__) and
            record.get('source_fingerprints') == (source_fingerprints or {}), '快片未过或程序/源已改变')
    require(record.get('total_frames') == totalframes and record.get('frames_sha256') == frame_sha(fr),
            '正式帧表与已验快片不同')
    require(record.get('PNG_sha256') == png_hashes(fr, shotdir), '正式截图与已验快片不同')
    require(Path(video).is_file() and record.get('video_sha256') == sha(video), '已验快片丢失或改变')
    target = probes(fr, totalframes)
    rows = record.get('all_probes', [])
    require(record.get('states') == len(fr) and record.get('probes') == len(target) and
            [r.get('frame') for r in rows] == target and all(r.get('ok') is True and
            isinstance(r.get('mean_difference'), (int, float)) and 0 <= r['mean_difference'] <= THRESHOLD
            for r in rows), '快片完整探针记录不符')
    return record


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--video', type=Path, required=True)
    ap.add_argument('--fr', type=Path, required=True)
    ap.add_argument('--shotdir', type=Path, required=True)
    ap.add_argument('--totalframes', '--nfr', type=int, required=True)
    ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--source-fingerprints', type=Path)
    ap.add_argument('--require-pass', action='store_true')
    args = ap.parse_args()
    fr = json.loads(args.fr.read_text('utf-8'))
    sources = json.loads(args.source_fingerprints.read_text('utf-8')) if args.source_fingerprints else None
    fn = require_pass if args.require_pass else check
    result = fn(args.video, fr, args.shotdir, args.totalframes, args.report, sources)
    print(json.dumps({k: result[k] for k in ['status', 'states', 'probes', 'total_frames', 'max_mean_difference']},
                     ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
