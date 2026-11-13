"""把当前已核的 A/B1/B2 缓存组装为一个完整年度精听；不重编码画面。

视频只复制 H.264，声音从 canonical FLOAT PCM 按子段已核样本区间重建，
整年仅编码一次 AAC。build 和 verify 都重新检查当前三个 child gate。
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('tem8_full_children', HERE / '发布汇集.py')
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)
from 精听数据 import LEAD, TAIL, FPS, audio_protection

sha, read, dump = pub.sha, pub.read, pub.dump
MIN_SNR, MAX_GAIN, MAX_SECOND_DB = 30.0, .05, 1.0
SUFFIXES = ('A', 'B1', 'B2')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_chapters', '-show_format',
        '-show_data_hash', 'sha256', '-of', 'json', str(path)]))


def stream(info, kind):
    rows = [s for s in info['streams'] if s['codec_type'] == kind]
    need(len(rows) == 1, f'必须恰有一个{kind}流')
    return rows[0]


def year_id(year):
    y = int(year)
    need(y in pub.YEARS, '只接受实际15个考试年份（没有2020年）')
    return y


def check_protected(tm, data, sr):
    protected, registration = audio_protection(data)
    need(tm.get('protected_source_intervals', []) == protected, '子段信号保护区间与当前原音登记不同')
    need(tm.get('audio_protection') == registration, '子段信号保护证据已过期')
    kept = [(round(a * sr), round(b * sr)) for a, b in tm['kept_intervals']]
    lo, hi = (round(t * sr) for t in data['audio']['window'])
    covered = []
    for a, b in protected:
        a, b = max(lo, round(a * sr)), min(hi, round(b * sr))
        if a >= b:
            continue
        count = sum(max(0, min(b, v) - max(a, u)) for u, v in kept)
        need(count == b - a, '受保护等待信号未逐样本保留')
        covered.append({'source_samples': [a, b], 'covered_samples': count})
    return {'registration': registration, 'coverage': covered}


def load_parts(year, parts):
    """生产入口始终以当前 gate 验证；不提供跳过当前审批的参数。"""
    year = year_id(year)
    parts = Path(parts).resolve()
    records = []
    for suffix in SUFFIXES:
        ident = f'{year}-{suffix}'
        folder = parts / ident
        gate = pub.gate('intensive', ident)
        meta = pub.validate_stage(folder, 'intensive', ident, gate['payload_sha256'])
        registry = read(folder / 'evidence/审核登记.json')
        need(registry['inputs'] == gate['inputs'] and registry['render_sources'] == gate['render_sources'],
             ident + '缓存与当前输入/依赖不同')
        need(Counter(registry['shots'].values()) == Counter(gate['shots'].values()), ident + '截图审批不同')
        actual_shots = [sha(folder / n) for n in meta['evidence']
                        if n.startswith('evidence/已审截图/') and n.endswith('.png')]
        need(Counter(actual_shots) == Counter(gate['shots'].values()), ident + '实际截图不符')
        current = pub.input_paths('intensive', ident)[0]
        snapshot = folder / f'evidence/实际输入/{ident}.json'
        need(sha(snapshot) == sha(current), ident + '缓存不是当前完整输入')
        data = read(snapshot)
        tm_path = folder / 'evidence/工作记录/audio/timings.json'
        tm = read(tm_path)['cet4_male'][ident]
        prepared = read(folder / 'evidence/工作记录/prepared.json')
        need(prepared['draft'] is False and prepared['id'] == ident, ident + '为草稿或身份错误')
        need(tm['source_sha256'] == prepared['source_sha256'] == meta['source_sha256'], '原音SHA不一致')
        need(tm['audio_sha256'] == prepared['audio_sha256'], '子段PCM摘要不一致')
        need(tm['mode'] == '原音不动' and tm['channels'] in range(1, 9), '不接受变声/变声道子段')
        sr = tm['sample_rate']
        need(isinstance(sr, int) and sr > 0, '采样率非法')
        video = folder / meta['mp4']
        info = probe(video)
        v, a = stream(info, 'video'), stream(info, 'audio')
        frames = round(tm['duration'] * FPS)
        need(abs(frames / FPS - tm['duration']) < 1e-8, '子段时长不是整帧')
        check_video(v, frames)
        need(int(a['sample_rate']) == sr and a['channels'] == tm['channels'], '子段原音格式变化')
        need(len(tm['kept_intervals']) > 0, '缺少已核原音保留区间')
        expected_bitrate = data['audio'].get('aac_bitrate', '192k')
        need(tm.get('aac_bitrate', '192k') == expected_bitrate, '子段AAC策略不同')
        protection = check_protected(tm, data, sr)
        records.append({'id': ident, 'folder': folder, 'video': video, 'meta': meta, 'tm': tm,
                        'frames': frames, 'video_stream': v, 'audio_protection': protection,
                        'record': {'id': ident, 'approval_payload_sha256': gate['payload_sha256'],
                                   'mp4_sha256': meta['mp4_sha256'], 'mp4_bytes': meta['mp4_bytes'],
                                   'meta_sha256': sha(folder / 'meta.json'),
                                   'source_sha256': meta['source_sha256'],
                                   'input_sha256': sha(snapshot), 'timings_sha256': sha(tm_path),
                                   'source_commit': meta.get('source_commit'), 'run_id': meta.get('run_id'),
                                   'revalidated_commit': meta.get('revalidated_commit'),
                                   'source_record': meta['source_record']}})
    need(len({r['meta']['source_sha256'] for r in records}) == 1, '三段不是同一canonical原音')
    need(len({(r['tm']['sample_rate'], r['tm']['channels']) for r in records}) == 1, '三段原音格式不同')
    # 相同编码参数集是复制后仍按相同规则解码的必要条件；不兼容时明确失败。
    compatibility = ['codec_name', 'profile', 'level', 'width', 'height', 'pix_fmt', 'time_base',
                     'field_order', 'extradata_hash']
    first = records[0]['video_stream']
    need(all(all(r['video_stream'].get(k) == first.get(k) for k in compatibility) for r in records),
         '三段H.264参数集不兼容；未重编码，请先检查真实编码参数')
    return records


def check_video(v, frames):
    need(v['codec_name'] == 'h264' and (v['width'], v['height']) == (3840, 2160), '不是4K H.264')
    need(v['pix_fmt'] == 'yuv420p' and Fraction(v['r_frame_rate']) == FPS, '视频格式/帧率错误')
    need(Fraction(v['avg_frame_rate']) == FPS and int(v['nb_frames']) == frames, '帧数/平均帧率错误')
    need(abs(float(v['duration']) - frames / FPS) < 1e-5, '视频时长与帧数不同')


def check_original(year, original, prepare, records):
    original = Path(original).resolve()
    prepare = Path(prepare) if prepare else original.parent / '原音准备.json'
    prep = read(prepare)
    digest = sha(original)
    source = pub.validate_source_preparation(prep, year, digest)
    need(digest == records[0]['meta']['source_sha256'], '实际canonical WAV不是三个已核子段所用原音')
    info = sf.info(original)
    c = prep['canonical']
    need(info.samplerate == c['sample_rate'] == records[0]['tm']['sample_rate'], '原采样率不同')
    need(info.channels == c['channels'] == records[0]['tm']['channels'], '原声道不同')
    need(info.frames == c['frames'] and original.stat().st_size == c['bytes'], 'canonical样本/字节数不同')
    need(info.subtype == 'FLOAT', '只接受已核FLOAT32 canonical WAV')
    h = hashlib.sha256()
    with sf.SoundFile(original) as f:
        for x in f.blocks(blocksize=65536, dtype='float32', always_2d=True):
            need(np.isfinite(x).all(), '原音含非有限样本')
            h.update(x.astype('<f4', copy=False).tobytes())
    need(h.hexdigest() == c['pcm_sha256'], 'canonical PCM逐样本摘要不同')
    return {'sha256': digest, 'pcm_sha256': h.hexdigest(), 'sample_rate': info.samplerate,
            'channels': info.channels, 'frames': info.frames, 'prepare_sha256': sha(prepare),
            'source_record': source}


class FloatWriter:
    """与子段 float_wav 完全相同的确定性头；不加入PEAK时间戳。"""
    def __init__(self, path, frames, sr, channels):
        size = frames * channels * 4
        need(0 < size + 48 < 2 ** 32, '重建PCM超过RIFF上限')
        self.f = open(path, 'wb')
        self.f.write(struct.pack('<4sI4s', b'RIFF', size + 48, b'WAVE'))
        self.f.write(struct.pack('<4sIHHIIHH', b'fmt ', 16, 3, channels, sr, sr * channels * 4, channels * 4, 32))
        self.f.write(struct.pack('<4sII', b'fact', 4, frames))
        self.f.write(struct.pack('<4sI', b'data', size))
        self.remaining = frames
        self.h = hashlib.sha256()
        self.channels = channels

    def write(self, x):
        x = np.ascontiguousarray(x, dtype='<f4')
        need(x.ndim == 2 and x.shape[1] == self.channels and len(x) <= self.remaining, 'PCM写入样本数错误')
        b = x.tobytes()
        self.f.write(b)
        self.h.update(b)
        self.remaining -= len(x)

    def zeros(self, n):
        while n:
            count = min(n, 65536)
            self.write(np.zeros((count, self.channels), dtype='<f4'))
            n -= count

    def close(self):
        self.f.close()
        need(self.remaining == 0, 'PCM样本未写完整')
        return self.h.hexdigest()


def reconstruct(records, original, out):
    """按源样本索引复原已审每段，再拼接；逐段字节SHA须等于原已审PCM。"""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sr, ch = records[0]['tm']['sample_rate'], records[0]['tm']['channels']
    total = sum(round(r['tm']['duration'] * sr) for r in records)
    whole_path = out / '全年原样PCM.wav'
    whole = FloatWriter(whole_path, total, sr, ch)
    writer = None
    try:
        result, cursor = [], 0
        with sf.SoundFile(original) as source:
            for r in records:
                tm = r['tm']
                n, lead = round(tm['duration'] * sr), round(LEAD * sr)
                intervals = [(round(a * sr), round(b * sr)) for a, b in tm['kept_intervals']]
                need(all(0 <= a < b <= len(source) for a, b in intervals), '原音区间越界')
                need(all(b <= c for (_, b), (c, _) in zip(intervals, intervals[1:])), '原音区间重复/错序')
                body = sum(b - a for a, b in intervals)
                tail = n - lead - body
                need(tail >= round(TAIL * sr) - 1, '子段尾部保留时长不足')
                part_path = out / (r['id'] + '.wav')
                writer = FloatWriter(part_path, n, sr, ch)
                writer.zeros(lead)
                whole.zeros(lead)
                for a, b in intervals:
                    source.seek(a)
                    remaining = b - a
                    while remaining:
                        count = min(remaining, 65536)
                        x = source.read(count, dtype='float32', always_2d=True)
                        need(len(x) == count, '源音读取不足')
                        writer.write(x)
                        whole.write(x)
                        remaining -= count
                writer.zeros(tail)
                whole.zeros(tail)
                pcm_digest = writer.close()
                need(sha(part_path) == tm['audio_sha256'], r['id'] + '重建PCM不是已审子段原样PCM')
                result.append({'id': r['id'], 'frames': n, 'start_sample': cursor, 'end_sample': cursor + n,
                               'lead_samples': lead, 'body_samples': body, 'tail_samples': tail,
                               'source_intervals_samples': [list(x) for x in intervals],
                               'pcm_sha256': pcm_digest, 'wav_sha256': sha(part_path),
                               'aac_bitrate': tm.get('aac_bitrate', '192k')})
                cursor += n
        pcm_digest = whole.close()
    except BaseException:
        whole.f.close()
        if writer is not None:
            writer.f.close()
        raise
    return {'file': whole_path.name, 'frames': total, 'sample_rate': sr, 'channels': ch,
            'pcm_sha256': pcm_digest, 'wav_sha256': sha(whole_path), 'parts': result}


def ffconcat_quote(path):
    return "'" + str(Path(path).resolve()).replace("'", "'\\''") + "'"


def chapter_title(ident):
    return {'A': 'Section A 讲座精听', 'B1': 'Section B 采访精听（一）',
            'B2': 'Section B 采访精听（二）'}[ident.split('-', 1)[1]]


def selected_bitrate(records, year):
    bitrate = max(int(r['tm'].get('aac_bitrate', '192k')[:-1]) for r in records)
    need(bitrate in (192, 256, 320) and (year != 2015 or bitrate >= 256), '整套AAC码率未沿用子段最高明确策略')
    return f'{bitrate}k'


def assemble(records, pcm, out, year):
    out = Path(out)
    intermediate = out / 'video-copy'
    intermediate.mkdir(exist_ok=True)
    entries = ['ffconcat version 1.0']
    for r in records:
        target = intermediate / (r['id'] + '.mp4')
        # Removing the old AAC first keeps its encoder padding out of concat's timebase.
        run(['ffmpeg', '-y', '-v', 'error', '-i', r['video'], '-map', '0:v:0', '-an',
             '-c:v', 'copy', '-map_metadata', '-1', '-video_track_timescale', '15360', target])
        entries += ['file ' + ffconcat_quote(target), f"duration {r['frames'] / FPS:.12f}"]
    listing = intermediate / 'concat.txt'
    listing.write_text('\n'.join(entries) + '\n', encoding='utf-8')
    chapters = out / 'chapters.ffmetadata'
    lines, cursor = [';FFMETADATA1'], 0
    for r in records:
        lines += ['[CHAPTER]', 'TIMEBASE=1/30', f'START={cursor}', f"END={cursor + r['frames']}",
                  'title=' + chapter_title(r['id'])]
        cursor += r['frames']
    chapters.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    bitrate = selected_bitrate(records, year)
    video = out / f'tem8-intensive-full-{year}.mp4'
    args = ['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', listing,
            '-i', out / 'pcm' / pcm['file'], '-f', 'ffmetadata', '-i', chapters,
            '-map', '0:v:0', '-map', '1:a:0', '-map_metadata', '2', '-map_chapters', '2',
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', bitrate, '-threads', '2',
            '-video_track_timescale', '15360', '-movie_timescale', str(math.lcm(pcm['sample_rate'], FPS)),
            '-movflags', '+faststart', video]
    run(args)
    command = {'argv': [str(a) for a in args], 'video_encoding': 'stream copy; no picture encoder',
               'audio_encoding': 'one AAC encode from canonical FLOAT32 samples', 'aac_bitrate': bitrate,
               'ffmpeg': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0]}
    dump(out / '组装命令.json', command)
    return video


def packet_proof(path, frames):
    """检查所有包的时间戳，不对整片画面做解码或模型审图。"""
    info = probe(path)
    v = stream(info, 'video')
    check_video(v, frames)
    raw = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_packets',
                                   '-show_entries', 'packet=pts,dts,duration', '-of', 'json', str(path)])
    packets = json.loads(raw)['packets']
    tb = Fraction(v['time_base'])
    need(len(packets) == frames, '全量视频包数不等于帧数')
    pts = sorted(Fraction(int(p['pts'])) * tb for p in packets)
    need(all(t == Fraction(k, FPS) for k, t in enumerate(pts)), '存在视频PTS缺帧/重帧/接缝漂移')
    dts = [Fraction(int(p['dts'])) * tb for p in packets]
    need(all(b - a == Fraction(1, FPS) for a, b in zip(dts, dts[1:])), '视频DTS不连续')
    need(all(Fraction(int(p['duration'])) * tb == Fraction(1, FPS) for p in packets), '视频包时长不是1/30秒')
    return {'frames': frames, 'packet_count': len(packets), 'pts_exact_30fps': True,
            'dts_contiguous': True, 'first_dts': str(dts[0]), 'last_pts': str(pts[-1]),
            'duration': str(Fraction(frames, FPS)), 'extradata_hash': v['extradata_hash']}


START_CODE = re.compile(b'\x00\x00(?:\x00)?\x01')


def nal_iter(path):
    """从复制得到的Annex B流提取NAL；保留VCL全部字节，不解码图像。"""
    command = ['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:v:0', '-an', '-c:v', 'copy',
               '-bsf:v', 'h264_mp4toannexb', '-f', 'h264', 'pipe:1']
    p = subprocess.Popen(command, stdout=subprocess.PIPE)
    pending = b''
    try:
        while True:
            block = p.stdout.read(1 << 20)
            pending += block
            marks = list(START_CODE.finditer(pending))
            for first, second in zip(marks, marks[1:]):
                yield pending[first.end():second.start()]
            if marks:
                pending = pending[marks[-1].start():]
            need(len(pending) < 64 << 20, '异常大H.264 NAL')
            if not block:
                last = START_CODE.match(pending)
                if last and len(pending) > last.end():
                    yield pending[last.end():]
                break
        need(p.wait() == 0, 'NAL提取失败')
    finally:
        p.stdout.close()
        if p.poll() is None:
            p.kill()
            p.wait()


def vcl_summary(paths, counts=None):
    whole, part, results, parameter_sets = hashlib.sha256(), hashlib.sha256(), [], set()
    n, total, bytes_count = 0, 0, 0
    group = 0
    for path in paths:
        for payload in nal_iter(path):
            kind = payload[0] & 31
            if kind in (7, 8):
                parameter_sets.add(hashlib.sha256(payload).hexdigest())
            if not 1 <= kind <= 5:
                continue
            item = struct.pack('>I', len(payload)) + payload
            whole.update(item)
            part.update(item)
            n += 1
            total += 1
            bytes_count += len(payload)
            if counts and n == counts[group]:
                results.append({'nal_count': n, 'sha256': part.hexdigest()})
                group += 1
                n, part = 0, hashlib.sha256()
                need(group <= len(counts), '整套额外视频VCL')
        if not counts:
            results.append({'nal_count': n, 'sha256': part.hexdigest()})
            n, part = 0, hashlib.sha256()
    need(not counts or (n == 0 and group == len(counts)), '整套缺少/增加VCL')
    return {'nal_count': total, 'vcl_bytes': bytes_count, 'sha256': whole.hexdigest(),
            'parts': results, 'parameter_sets_sha256': sorted(parameter_sets)}


def frame_hash(path, frame):
    # Input seeking decodes only the preceding GOP, not all frames before this image.
    command = ['ffmpeg', '-v', 'error', '-threads', '2', '-ss', f'{frame / FPS:.12f}', '-i', str(path),
               '-map', '0:v:0', '-an', '-frames:v', '1', '-pix_fmt', 'yuv420p', '-f', 'rawvideo', 'pipe:1']
    raw = subprocess.check_output(command)
    need(len(raw) == 3840 * 2160 * 3 // 2, '代表帧未完整解码')
    return hashlib.sha256(raw).hexdigest()


def representative_frames(records, video):
    rows, offset = [], 0
    for r in records:
        # First/last frames cover both sides of both chapter joins; middle IDR is representative.
        middle = min((r['frames'] // 2 // 900) * 900, r['frames'] - 1)
        choices = sorted({0, 1, middle, r['frames'] - 2, r['frames'] - 1})
        for local in choices:
            a, b = frame_hash(r['video'], local), frame_hash(video, offset + local)
            need(a == b, f"{r['id']}代表帧{local}复制后像素不同")
            rows.append({'id': r['id'], 'part_frame': local, 'whole_frame': offset + local,
                         'decoded_yuv420p_sha256': a})
        offset += r['frames']
    return rows


def compare_audio(reference, decoded, start, count):
    """与子段原声核验相同阈值，逐个实际一秒窗核电平；不取整后判定。"""
    energy, dot, error = 0., 0., 0.
    max_second, seconds = 0., 0
    with sf.SoundFile(reference) as a, sf.SoundFile(decoded) as b:
        sr = a.samplerate
        need((b.samplerate, b.channels) == (sr, a.channels), '解码音频改变原格式')
        a.seek(start)
        b.seek(start)
        remain = count
        while remain:
            n = min(sr, remain)
            x, y = a.read(n, dtype='float64', always_2d=True), b.read(n, dtype='float64', always_2d=True)
            need(len(x) == len(y) == n and np.isfinite(y).all(), '最终AAC丢失原音样本')
            e = float(np.sum(x * x))
            energy += e
            dot += float(np.sum(x * y))
            error += float(np.sum((y - x) ** 2))
            if n == sr and math.sqrt(e / x.size) > 10 ** (-50 / 20):
                delta = abs(20 * math.log10(max(math.sqrt(float(np.mean(y * y))), 1e-12) / math.sqrt(e / x.size)))
                max_second = max(max_second, delta)
                seconds += 1
            remain -= n
    need(energy > 0, '原音比较窗没有信号')
    gain = 20 * math.log10(max(dot / energy, 1e-12))
    snr = 10 * math.log10(energy / max(error, 1e-30))
    need(abs(gain) <= MAX_GAIN and snr >= MIN_SNR and max_second <= MAX_SECOND_DB,
         f'原声核验失败：gain={gain:.8f} dB SNR={snr:.8f} dB max1s={max_second:.8f} dB')
    return {'samples': count, 'gain_db': gain, 'snr_db': snr, 'max_1second_level_difference_db': max_second,
            'tested_active_seconds': seconds, 'ok': True}


def peak_range(path, a, b):
    peak = 0.
    with sf.SoundFile(path) as f:
        need(0 <= a <= b <= len(f), '静音检测越界')
        f.seek(a)
        remain = b - a
        while remain:
            x = f.read(min(65536, remain), dtype='float32', always_2d=True)
            peak = max(peak, float(np.abs(x).max(initial=0)))
            remain -= len(x)
    return peak


def audio_proof(records, pcm, video, out):
    sr, ch, expected = pcm['sample_rate'], pcm['channels'], pcm['frames']
    info = probe(video)
    v, a = stream(info, 'video'), stream(info, 'audio')
    need(a['codec_name'] == 'aac' and int(a['sample_rate']) == sr and a['channels'] == ch,
         '整套AAC改变原采样率/声道')
    need(Fraction(a['time_base']) == Fraction(1, sr) and a['start_pts'] == v['start_pts'] == 0,
         '音画轨道不是同时从0开始')
    need(abs(float(a['duration']) - float(v['duration'])) < .05, '音画总时长差超过0.05秒')
    audio_packets = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_packets',
        '-show_entries', 'packet=pts,dts,duration,side_data_list', '-of', 'json', str(video)]))['packets']
    first = audio_packets[0]
    skip = sum(s.get('skip_samples', 0) for s in first.get('side_data_list', []))
    need(int(first['pts']) + skip == 0, 'AAC priming没有在原时间零点正确跳过')
    need(all(int(p['pts']) == int(p['dts']) for p in audio_packets), 'AAC PTS/DTS不一致')
    need(all(int(b['pts']) == int(a['pts']) + int(a['duration'])
             for a, b in zip(audio_packets, audio_packets[1:])), 'AAC包接缝时间戳不连续')
    decoded = Path(out) / 'pcm/全年AAC解码.wav'
    run(['ffmpeg', '-y', '-v', 'error', '-i', video, '-map', '0:a:0', '-c:a', 'pcm_f32le', decoded])
    actual = sf.info(decoded)
    need(actual.frames >= expected and actual.frames - expected < 2048, 'AAC总样本数差异常')
    reference = Path(out) / 'pcm' / pcm['file']
    full = compare_audio(reference, decoded, 0, expected)
    parts, video_cursor = [], 0
    for r, p in zip(records, pcm['parts']):
        comparison = compare_audio(reference, decoded, p['start_sample'], p['frames'])
        body = compare_audio(reference, decoded, p['start_sample'] + p['lead_samples'], p['body_samples'])
        lead_end = p['start_sample'] + p['lead_samples'] - round(.03 * sr)
        tail_start = p['end_sample'] - p['tail_samples'] + round(.05 * sr)
        lead_peak = peak_range(decoded, p['start_sample'], lead_end)
        tail_peak = peak_range(decoded, tail_start, p['end_sample'])
        need(max(lead_peak, tail_peak) < .001, r['id'] + '接缝头尾静音污染')
        # Per-part native rounding is preserved; no sample resampling to fit a frame grid.
        delta = Fraction(p['start_sample'], sr) - Fraction(video_cursor, FPS)
        need(abs(delta) <= Fraction(2, sr), '章节接缝音画偏移超出原采样点取整')
        parts.append({'id': r['id'], 'all_samples': comparison, 'source_body': body,
                      'start_sample': p['start_sample'], 'end_sample': p['end_sample'],
                      'video_start_frame': video_cursor, 'av_offset_seconds': float(delta),
                      'av_offset_native_samples': float(delta * sr),
                      'lead_silence_peak': lead_peak, 'tail_silence_peak': tail_peak,
                      'source_protection': r['audio_protection']})
        video_cursor += r['frames']
    extra_peak = peak_range(decoded, expected, actual.frames)
    need(extra_peak < .001, 'AAC补帧尾部出现非静音')
    return {'sample_rate': sr, 'channels': ch, 'source_samples': expected, 'decoded_samples': actual.frames,
            'aac_padding_samples': actual.frames - expected, 'aac_padding_peak': extra_peak,
            'full': full, 'parts': parts,
            'packet_timing': {'packet_count': len(audio_packets), 'native_time_base': a['time_base'],
                              'first_packet_pts': first['pts'], 'priming_skip_samples': skip,
                              'effective_first_sample_pts': 0, 'continuous': True,
                              'stream_duration_samples': a['duration_ts']},
            'thresholds': {'min_snr_db': MIN_SNR, 'max_abs_gain_db': MAX_GAIN,
                           'max_1second_level_difference_db': MAX_SECOND_DB},
            'audio_video_duration_difference_seconds': float(a['duration']) - float(v['duration'])}


def verify(year, parts, original, out, prepare=None):
    """不信任build的布尔值：重读当前gate、源、PCM、NAL、全PTS及AAC独立测量。"""
    year, out = year_id(year), Path(out).resolve()
    # A stale successful report must not survive a failed re-verification.
    for name in ('meta.json', 'verification.json'):
        (out / name).unlink(missing_ok=True)
    records = load_parts(year, parts)
    source = check_original(year, original, prepare, records)
    pcm = reconstruct(records, original, out / 'pcm')
    dump(out / 'PCM重建核验.json', pcm)
    video = out / f'tem8-intensive-full-{year}.mp4'
    command = read(out / '组装命令.json')
    argv = command['argv']
    for option, value in [('-c:v', 'copy'), ('-c:a', 'aac'), ('-b:a', selected_bitrate(records, year))]:
        need(argv.count(option) == 1 and argv[argv.index(option) + 1] == value, '组装命令编码策略不符')
    need(command['aac_bitrate'] == selected_bitrate(records, year), '组装记录AAC码率不符')
    need(not any(x in argv for x in ['-ar', '-ac', '-af', '-filter:a', '-filter_complex']),
         '组装命令含改变原声格式/增益的处理')
    need(argv.count('-i') == 3 and argv[argv.index('-i', argv.index('-i') + 1) + 1]
         == str(out / 'pcm' / pcm['file']), 'AAC输入必须是新重建原样PCM')
    packets = packet_proof(video, sum(r['frames'] for r in records))
    original_vcl = vcl_summary([r['video'] for r in records])
    actual_vcl = vcl_summary([video], [p['nal_count'] for p in original_vcl['parts']])
    need(actual_vcl == original_vcl, 'H.264 VCL/参数集字节变化；不是无损画面复制')
    need(packets['extradata_hash'] == records[0]['video_stream']['extradata_hash'], '整套H.264参数集改变')
    reps = representative_frames(records, video)
    audio = audio_proof(records, pcm, video, out)
    info = probe(video)
    chapters = info.get('chapters', [])
    need(len(chapters) == 3, '整套必须有且仅有三个章节')
    cursor = 0
    for chapter, r in zip(chapters, records):
        need(chapter.get('tags', {}).get('title') == chapter_title(r['id']), '章节名称/顺序错误')
        need(abs(float(chapter['start_time']) - cursor / FPS) <= .001, '章节开始不在原子段边界')
        cursor += r['frames']
        need(abs(float(chapter['end_time']) - cursor / FPS) <= .001, '章节结束不在原子段边界')
    digest = sha(video)
    report = {'schema': 1, 'kind': 'intensive_full', 'id': str(year), 'ok': True, 'draft': False,
              'sha256': digest, 'source_sha256': source['sha256'], 'parts_order': [r['id'] for r in records],
              'video_lossless': True, 'pcm_reconstruction_verified': True,
              'audio_verified': True, 'av_sync_verified': True,
              'parts': [r['record'] for r in records], 'source': source,
              'video_packets': packets, 'video_vcl': actual_vcl, 'decoded_representative_frames': reps,
              'pcm': pcm, 'audio': audio,
              'assembly_command': command,
              'chapters': chapters,
              'ffmpeg': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0],
              'engine_sha256': sha(Path(__file__))}
    dump(out / 'verification.json', report)
    meta = {'schema': 1, 'kind': 'intensive_full', 'id': str(year), 'year': year,
            'label': f'{year}年 专八听力 精听.mp4', 'mp4': video.name,
            'mp4_bytes': video.stat().st_size, 'mp4_sha256': digest,
            'source_sha256': source['sha256'], 'source_record': source['source_record'],
            'parts': [r['record'] for r in records], 'frames': sum(r['frames'] for r in records),
            'verification': {'ok': True, 'draft': False, 'report': 'verification.json'}}
    dump(out / 'meta.json', meta)
    return meta


def build(year, parts, original, out, prepare=None):
    year, out = year_id(year), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    for name in ('meta.json', 'verification.json'):
        (out / name).unlink(missing_ok=True)
    records = load_parts(year, parts)
    check_original(year, original, prepare, records)
    pcm = reconstruct(records, original, out / 'pcm')
    assemble(records, pcm, out, year)
    return verify(year, parts, original, out, prepare)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['build', 'verify'])
    p.add_argument('year', type=int)
    p.add_argument('--parts', type=Path, required=True)
    p.add_argument('--original', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--prepare', type=Path)
    a = p.parse_args()
    result = globals()[a.command](a.year, a.parts, a.original, a.out, a.prepare)
    print(json.dumps({k: result[k] for k in ('id', 'kind', 'mp4_sha256', 'frames', 'verification')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
