"""未裁切的历年原音→机器识别词时间、纯能量停顿候选与核验记录。

python 识别批量.py /tmp/tem8/2009 --model tools/tts/models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8

识别结果只用于对齐，绝不替代解析原文；不修改词语、不生成最终音乐剪切点。
mono/16k重采样只作用于ASR内存，不写回用于视频的原音。
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def pauses(samples, sr=16000):
    hop = int(sr * .02); n = len(samples) // hop
    assert n > 100
    db = 10 * np.log10((samples[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    threshold = float(np.percentile(db, 10) + 12)
    silent = db < threshold
    changes = np.flatnonzero(np.diff(np.r_[False, silent, False].astype(np.int8)))
    runs = [(int(a) * .02, int(b) * .02) for a, b in zip(changes[::2], changes[1::2])]
    return threshold, db, runs


def chunks(duration, runs):
    # 与2025底座一致，优先在静音中点切块；连续音乐/讲话没有静音时也硬限25秒。
    mids = [(s + e) / 2 for s, e in runs if e - s >= .25]
    cuts = [0.0]
    while duration - cuts[-1] > 25:
        lo = cuts[-1]
        candidates = [m for m in mids if lo + 12 <= m <= lo + 25]
        cuts.append(max(candidates) if candidates else lo + 25)
    if duration > cuts[-1] + .001:
        cuts.append(duration)
    assert all(0 < b - a <= 25.001 for a, b in zip(cuts, cuts[1:]))
    return list(zip(cuts, cuts[1:]))


def run(out, model, threads=2):
    import sherpa_onnx
    out, model = Path(out), Path(model)
    prep = json.loads((out / '原音准备.json').read_text('utf-8'))
    src = out / prep['canonical']['file']
    assert sha(src) == prep['canonical']['sha256'], '原音准备后文件改变'
    original_hash = sha(src); started = time.monotonic()
    audio, rate = sf.read(src, dtype='float32', always_2d=True)
    assert rate == prep['canonical']['sample_rate'] and audio.shape[1] == prep['canonical']['channels']
    assert len(audio) == prep['canonical']['frames'] and np.isfinite(audio).all()
    # 仅识别副本混音/重采样，视频仍取原采样率、原声道的src。
    mono = audio.mean(1); del audio
    a = soxr.resample(mono, rate, 16000) if rate != 16000 else mono
    del mono
    duration = len(a) / 16000; threshold, db, runs = pauses(a)
    dump(out / '停顿.json', {'阈值dB': round(threshold, 2), '帧秒': .02,
                            '静音': [[round(s, 2), round(e, 2)] for s, e in runs if e - s >= 1],
                            '用途': '能量静音候选，音乐/背景音可能影响结果；不能据此自动裁正式语音。'})
    needed = ['encoder.int8.onnx', 'decoder.int8.onnx', 'joiner.int8.onnx', 'tokens.txt']
    assert all((model / n).is_file() for n in needed), 'Parakeet模型缺文件'
    asr = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(model / needed[0]), decoder=str(model / needed[1]), joiner=str(model / needed[2]),
        tokens=str(model / needed[3]), model_type='nemo_transducer', num_threads=threads)
    words, records = [], []; windows = chunks(duration, runs)
    for index, (start, end) in enumerate(windows):
        voiced = int((db[int(start / .02):min(len(db), int(end / .02) + 1)] >= threshold).sum())
        if voiced < 10:
            records.append({'start': start, 'end': end, 'skipped': '能量静音', 'words': 0})
            continue
        stream = asr.create_stream()
        stream.accept_waveform(16000, a[int(start * 16000):int(end * 16000)])
        asr.decode_stream(stream); result = stream.result
        assert len(result.tokens) == len(result.timestamps), 'ASR词元与时刻数量不一致'
        chunk_words, current = [], None
        for token, timestamp in zip(result.tokens, result.timestamps):
            t = start + float(timestamp)
            assert math.isfinite(t) and start - .05 <= t <= end + .1, (index, token, t, start, end)
            if token.startswith(' ') or current is None:
                if current:
                    chunk_words.append(current)
                current = [token.strip(), round(max(0, t), 3), round(min(duration, t + .08), 3)]
            else:
                current[0] += token
                current[2] = round(min(duration, t + .08), 3)
        if current:
            chunk_words.append(current)
        chunk_words = [w for w in chunk_words if w[0]]
        words.extend(chunk_words)
        records.append({'start': start, 'end': end, 'words': len(chunk_words),
                        'text': result.text, 'voiced_frames': voiced})
        if index % 10 == 0:
            print(f'{prep["year"]}: {index + 1}/{len(windows)}块，{len(words)}词', flush=True)
    assert len(words) >= 100, '识别结果过少，不能作为有效转写'
    assert all(0 <= w[1] < w[2] <= duration + .005 for w in words), '识别时刻越界'
    assert all(b[1] >= a[1] for a, b in zip(words, words[1:])), '识别开口时刻倒序'
    assert sha(src) == original_hash, '识别过程不应改动原音'
    dump(out / '识别.json', words)
    dump(out / '识别分块.json', records)
    audit = {'year': prep['year'], 'source_archive_sha256': prep['archive_sha256'],
             'source_commit': os.getenv('GITHUB_SHA'), 'workflow_run_id': os.getenv('GITHUB_RUN_ID'),
             'canonical_sha256': original_hash, 'duration': duration, 'words': len(words), 'chunks': len(windows),
             'elapsed_seconds': round(time.monotonic() - started, 2), 'threads': threads,
             'model': model.name, 'model_files': {n: sha(model / n) for n in needed},
             'packages': {p: importlib.metadata.version(p) for p in ['sherpa-onnx', 'numpy', 'soundfile', 'soxr']},
             'script_sha256': sha(__file__), 'word_end_estimate_seconds': .08,
             'source_unchanged': True, 'music_trim_applied': False,
             'status': '机器转写及时间候选，仅用于对齐；解析原文、题型与音乐剪切点尚须核对。'}
    audit['outputs'] = {n: {'sha256': sha(out / n), 'bytes': (out / n).stat().st_size}
                        for n in ['原音准备.json', '停顿.json', '识别.json', '识别分块.json']}
    dump(out / 'ASR核验.json', audit)
    print(json.dumps({k: audit[k] for k in ['year', 'words', 'chunks', 'duration', 'elapsed_seconds']}, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('out', type=Path); p.add_argument('--model', type=Path, required=True)
    p.add_argument('--threads', type=int, default=int(os.getenv('TEM8_ASR_THREADS', '2')))
    args = p.parse_args(); assert 1 <= args.threads <= 8
    run(args.out, args.model, args.threads)
