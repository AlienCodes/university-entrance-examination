#!/usr/bin/env python3
"""错位短窗重新识别并生成独立ASR候选；不改主识别和正式原音。"""
import argparse
import difflib
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import subprocess
import time

import numpy as np
import sherpa_onnx

B = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def source_clip(prep, root, lo, hi, verified):
    pieces = []
    for entry in prep['source_entries']:
        start = entry.get('canonical_start', 0.)
        end = entry.get('canonical_end', prep['canonical']['duration'])
        a, z = max(lo, start), min(hi, end)
        if a >= z:
            continue
        path = root / entry['file']
        if path not in verified:
            assert sha(path) == entry['sha256'], f'原始输入哈希变更：{entry["file"]}'
            verified.add(path)
        pcm = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(a - start), '-t', str(z - a),
                                      '-i', str(path), '-f', 'f32le', '-ac', '1', '-ar', '16000', '-'])
        pieces.append(np.frombuffer(pcm, dtype='<f4'))
    assert pieces, ('no real audio for rerecognition', lo, hi)
    a = np.concatenate(pieces)
    assert abs(len(a) / 16000 - (hi - lo)) < .15, ('decoded analysis interval mismatch', lo, hi, len(a))
    return a


def words_from_tokens(tokens, timestamps, start, end):
    assert len(tokens) == len(timestamps)
    words, current = [], None
    for token, stamp in zip(tokens, timestamps):
        t = start + float(stamp)
        assert math.isfinite(t) and start - .05 <= t <= end + .1
        if token.startswith(' ') or current is None:
            if current:
                words.append(current)
            current = [token.strip(), round(max(start, t), 3), round(min(end, t + .08), 3)]
        else:
            current[0] += token
            current[2] = round(min(end, t + .08), 3)
    if current:
        words.append(current)
    return [w for w in words if w[0] and w[1] < w[2]]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', required=True, type=Path)
    p.add_argument('--input-root', default='/workspace/tem8-input', type=Path)
    p.add_argument('--jobs', type=Path, default=B / '核验/原文对齐/补词锚任务.json')
    p.add_argument('--threads', type=int, default=1)
    p.add_argument('--years', nargs='*', type=int)
    args = p.parse_args()
    assert 1 <= args.threads <= 2
    jobs = json.loads(args.jobs.read_text('utf-8'))['jobs']
    jobs = [j for j in jobs if not args.years or j['year'] in args.years]
    files = [args.model / f for f in ['encoder.int8.onnx', 'decoder.int8.onnx', 'joiner.int8.onnx', 'tokens.txt']]
    model_sha = {p.name: sha(p) for p in files}
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(files[0]), decoder=str(files[1]), joiner=str(files[2]), tokens=str(files[3]),
        model_type='nemo_transducer', num_threads=args.threads)
    verified = set()
    for year in sorted({j['year'] for j in jobs}):
        prep = json.loads((B / f'预处理/{year}/原音准备.json').read_text('utf-8'))
        primary_path = B / f'预处理/{year}/识别.json'
        primary = json.loads(primary_path.read_text('utf-8'))
        primary_sha = sha(primary_path)
        out = B / f'核验/补词锚/{year}'
        window_file = out / '窗口.json'
        records = json.loads(window_file.read_text('utf-8'))['windows'] if window_file.exists() else []
        for job in [j for j in jobs if j['year'] == year]:
            assert job['source_sha256'] == prep['canonical']['sha256']
            assert job['primary_asr_sha256'] == primary_sha
            key = hashlib.sha256(json.dumps({'unit': job['unit'], 'window': job['window'], 'primary': primary_sha}, sort_keys=True).encode()).hexdigest()
            if any(r['key'] == key for r in records):
                continue
            lo, hi = job['window']
            a = source_clip(prep, args.input_root, lo, hi, verified)
            stream = recognizer.create_stream()
            stream.accept_waveform(16000, a)
            started = time.monotonic()
            recognizer.decode_stream(stream)
            r = stream.result
            words = words_from_tokens(r.tokens, r.timestamps, lo, hi)
            original = [(i, w) for i, w in enumerate(primary) if lo <= w[1] < hi]
            old_text = ' '.join(w[0] for _, w in original)
            records.append({'key': key, 'unit': job['unit'], 'window': job['window'], 'reason': job['reason'],
                            'source_issues': job['issues'], 'tokens': r.tokens, 'timestamps': r.timestamps, 'words': words,
                            'primary_asr_indices': [i for i, _ in original], 'primary_text': old_text, 'new_text': r.text,
                            'diff': list(difflib.unified_diff(old_text.split(), r.text.split(), fromfile='primary', tofile='local', lineterm='')),
                            'elapsed_seconds': round(time.monotonic() - started, 3),
                            'status': 'machine_candidate_not_human_approved'})
            save(window_file, {'year': year, 'canonical_source_sha256': prep['canonical']['sha256'],
                               'primary_asr_sha256': primary_sha, 'model': args.model.name, 'model_files': model_sha,
                               'source_entries': [{'file': e['file'], 'sha256': e['sha256']} for e in prep['source_entries']],
                               'script_sha256': sha(__file__), 'analysis_only': '内存16k单声道分析副本；正式原音未修改',
                               'word_end_estimate_seconds': .08, 'windows': records})
            print(year, job['unit'], job['window'], r.text, flush=True)
        # 替换范围只用于独立组合候选，不触碰预处理/<year>/识别.json。
        # 窗口重叠时先合并任务重跑，不能让两个不同候选抢同一段录音。
        selected = sorted([r for r in records if r['words']], key=lambda r: r['window'][0])
        if any(a['window'][1] > z['window'][0] for a, z in zip(selected, selected[1:])):
            raise ValueError(f'{year}补识别窗相交，须先合并，不能任意丢弃其中一窗')
        combined = [w for w in primary if not any(r['window'][0] <= w[1] < r['window'][1] for r in selected)]
        combined.extend(w for r in selected for w in r['words'])
        combined.sort(key=lambda w: (w[1], w[2]))
        assert all(0 <= w[1] < w[2] <= prep['canonical']['duration'] + .1 for w in combined)
        assert sha(primary_path) == primary_sha
        save(out / '识别.json', combined)
        save(out / 'ASR核验.json', {'year': year, 'canonical_sha256': prep['canonical']['sha256'],
            'source_unchanged': True, 'music_trim_applied': False, 'model': args.model.name,
            'model_files': model_sha, 'word_end_estimate_seconds': .08,
            'primary_asr_sha256': primary_sha, 'primary_asr': f'预处理/{year}/识别.json',
            'window_evidence': f'核验/补词锚/{year}/窗口.json', 'window_evidence_sha256': sha(window_file),
            'script_sha256': sha(__file__), 'sherpa_onnx_version': importlib.metadata.version('sherpa-onnx'),
            'status': '错位短窗机器补识别组合候选；人工未审，不修改主ASR或正式原音。',
            'outputs': {'识别.json': {'sha256': sha(out / '识别.json')}}})


if __name__ == '__main__':
    main()
