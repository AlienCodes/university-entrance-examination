"""合并已核2025三原文：H.264/AAC载荷复制，MP4 edit list处理原有AAC延迟。

仅复制现成媒体；不渲染、不重编码、不变速/变声道/重采样/归一化。
需要ffmpeg/ffprobe与numpy；Python3.12、FFmpeg6.1或7.1均重新实际核验。
"""
from __future__ import annotations
import argparse
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = [
    ('A', '692c098dc03fd03e120320895b5ab18ba6942b8bdb727d6b36e24b243c91d31d', 30754126, 16157, 12624),
    ('B1', '8885b85720d1a626f0b00235e88e18f6018b685e4e8b6ec16c7695615bebf405', 19450143, 10656, 8326),
    ('B2', '8143cf6e78b9ac87ae4f7815e0ccc7d27720e4ea6d3ede8399e42417f20c3661', 20849161, 10442, 8159),
]
FPS, SR = 30, 24000


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def dump(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')


def probe(p, packets=False, raw=False):
    cmd = ['ffprobe', '-v', 'error']
    if raw:
        cmd += ['-ignore_editlist', '1']
    cmd += ['-show_packets' if packets else '-show_streams', '-show_data_hash', 'sha256', '-of', 'json', str(p)]
    return json.loads(subprocess.check_output(cmd))


def stream(info, kind):
    rows = [s for s in info['streams'] if s['codec_type'] == kind]
    assert len(rows) == 1
    return rows[0]


def boxes(d):
    at = 0
    while at < len(d):
        size, kind = struct.unpack_from('>I4s', d, at)
        assert 8 <= size <= len(d) - at, '本次小MP4只接受普通32位box'
        yield kind, d[at:at + size]
        at += size
    assert at == len(d)


def box(kind, payload):
    return struct.pack('>I4s', len(payload) + 8, kind) + payload


def patch_duration(b, offset, duration):
    out = bytearray(b)
    assert out[8] == 0, 'version0 duration expected'
    struct.pack_into('>I', out, offset, duration)
    return bytes(out)


def patch_edits(src, dest, entries, total):
    original = src.read_bytes()
    top = list(boxes(original))
    assert top[-1][0] == b'moov', 'moov须在mdat后，保证所有chunk offset不变'
    assert any(t == b'mdat' for t, _ in top[:-1])
    edits = box(b'elst', b'\0' * 4 + struct.pack('>I', len(entries)) + b''.join(
        struct.pack('>IiHH', duration, media, 1, 0) for duration, media in entries))
    result = []
    patched_audio = 0
    for typ, data in top:
        if typ != b'moov':
            result.append(data)
            continue
        children = []
        for ct, c in boxes(data[8:]):
            if ct == b'mvhd':
                assert struct.unpack_from('>I', c, 20)[0] == SR
                c = patch_duration(c, 24, total)
            if ct == b'trak':
                mdia = next(v for k, v in boxes(c[8:]) if k == b'mdia')
                hdlr = next(v for k, v in boxes(mdia[8:]) if k == b'hdlr')
                kind = hdlr[16:20]
                items = []
                for kt, v in boxes(c[8:]):
                    if kt == b'tkhd':
                        v = patch_duration(v, 28, total)
                    if kt == b'edts' and kind == b'soun':
                        v = box(b'edts', edits)
                        patched_audio += 1
                    items.append(v)
                c = box(b'trak', b''.join(items))
            children.append(c)
        result.append(box(b'moov', b''.join(children)))
    assert patched_audio == 1
    dest.write_bytes(b''.join(result))
    assert [b for t, b in boxes(dest.read_bytes()) if t != b'moov'] == [b for t, b in top if t != b'moov'], 'mdat或chunk位置变化'


def payload_hash(path, packets):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for p in packets:
            f.seek(int(p['pos']))
            b = f.read(int(p['size']))
            assert 'SHA256:' + hashlib.sha256(b).hexdigest() == p['data_hash']
            h.update(b)
    return h.hexdigest()


def frame_md5(path, frame):
    seek = max(0., (frame - .25) / FPS)
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{seek:.12f}', '-i', str(path), '-map', '0:v:0',
           '-an', '-frames:v', '1', '-f', 'framemd5', '-']
    text = subprocess.check_output(cmd, text=True)
    lines = [s for s in text.splitlines() if s and not s.startswith('#')]
    assert len(lines) == 1
    return lines[0].split(',')[-1].strip()


def run(args):
    args.source_dir, args.output, args.proof = args.source_dir.resolve(), args.output.resolve(), args.proof.resolve()
    args.proof.unlink(missing_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    work = args.output.parent / '2025-streamcopy-work'
    work.mkdir(exist_ok=True)
    sources = []
    for ident, digest, size, nv, na in SOURCE:
        p = args.source_dir / f'text-2025-{ident}.mp4'
        assert p.stat().st_size == size and sha(p) == digest
        info = probe(p); v, a = stream(info, 'video'), stream(info, 'audio')
        assert (v['width'], v['height'], v['r_frame_rate'], int(v['nb_frames'])) == (3840, 2160, '30/1', nv)
        assert (a['codec_name'], int(a['sample_rate']), a['channels'], int(a['nb_frames'])) == ('aac', SR, 1, na)
        sources.append({'id': ident, 'path': p, 'sha256': digest, 'bytes': size, 'frames': nv, 'audio_packets': na,
                        'info': info, 'raw_packets': probe(p, True, True)['packets']})
    for key in ['codec_name', 'profile', 'level', 'width', 'height', 'pix_fmt', 'time_base', 'extradata_hash']:
        assert len({stream(s['info'], 'video').get(key) for s in sources}) == 1
    for key in ['codec_name', 'sample_rate', 'channels', 'channel_layout', 'time_base', 'extradata_hash']:
        assert len({stream(s['info'], 'audio').get(key) for s in sources}) == 1
    listing = work / 'video-native.ffconcat'; audio_list = work / 'audio-physical.ffconcat'
    for path, audio in [(listing, False), (audio_list, True)]:
        rows = ['ffconcat version 1.0']
        for s in sources:
            seconds = s['audio_packets'] * 1024 / SR if audio else s['frames'] / FPS
            assert "'" not in str(s['path'])
            rows += [f"file '{s['path']}'", f'duration {seconds:.12f}']
        path.write_text('\n'.join(rows) + '\n')
    video, audio, mux = work / 'video.mp4', work / 'audio.m4a', work / 'before-edit.mp4'
    commands = [
        ['ffmpeg', '-y', '-v', 'warning', '-copyts', '-f', 'concat', '-safe', '0', '-auto_convert', '0',
         '-i', str(listing), '-map', '0:v:0', '-an', '-c:v', 'copy', '-video_track_timescale', '15360', '-use_editlist', '1', str(video)],
        ['ffmpeg', '-y', '-v', 'warning', '-copyts', '-f', 'concat', '-safe', '0', '-auto_convert', '0',
         '-i', str(audio_list), '-map', '0:a:0', '-vn', '-c:a', 'copy', '-movie_timescale', str(SR), '-use_editlist', '1', str(audio)],
        ['ffmpeg', '-y', '-v', 'warning', '-copyts', '-i', str(video), '-i', str(audio), '-map', '0:v:0', '-map', '1:a:0',
         '-c', 'copy', '-movie_timescale', str(SR), '-video_track_timescale', '15360', '-use_editlist', '1', str(mux)],
    ]
    logs = []
    for cmd in commands:
        q = subprocess.run(cmd, capture_output=True, text=True)
        logs.append({'argv': cmd, 'returncode': q.returncode, 'stderr': q.stderr})
        assert q.returncode == 0 and 'non-monoton' not in q.stderr.lower(), q.stderr
    total_frames = sum(s['frames'] for s in sources)
    assert total_frames == 37255
    entries = []; coded = 0
    for s in sources:
        entries.append((s['frames'] * (SR // FPS), coded + 1024))
        coded += s['audio_packets'] * 1024
    patch_edits(mux, args.output, entries, total_frames * (SR // FPS))
    info = probe(args.output); v, a = stream(info, 'video'), stream(info, 'audio')
    assert int(v['nb_frames']) == total_frames and v['r_frame_rate'] == v['avg_frame_rate'] == '30/1'
    assert float(v['start_time']) == float(a['start_time']) == 0
    assert abs(float(v['duration']) - total_frames / FPS) < 1e-6
    assert abs(float(v['duration']) - float(a['duration'])) < 1e-6
    assert int(a['sample_rate']) == SR and a['channels'] == 1
    output_raw = probe(args.output, True, True)['packets']; payloads = {}
    for kind in ['video', 'audio']:
        expected = [p for s in sources for p in s['raw_packets'] if p['codec_type'] == kind]
        actual = [p for p in output_raw if p['codec_type'] == kind]
        assert [(p['size'], p['data_hash']) for p in expected] == [(p['size'], p['data_hash']) for p in actual]
        h = hashlib.sha256()
        for s in sources:
            pp = [p for p in s['raw_packets'] if p['codec_type'] == kind]
            with s['path'].open('rb') as f:
                for p in pp:
                    f.seek(int(p['pos'])); b = f.read(int(p['size']))
                    assert 'SHA256:' + hashlib.sha256(b).hexdigest() == p['data_hash']; h.update(b)
        output_hash = payload_hash(args.output, actual)
        assert h.hexdigest() == output_hash
        payloads[kind] = {'packets': len(actual), 'all_packet_sizes_and_sha256_equal_in_order': True,
                          'concatenated_payload_sha256': output_hash}
    presentation = probe(args.output, True)['packets']
    vp = [p for p in presentation if p['codec_type'] == 'video']
    ap = [p for p in presentation if p['codec_type'] == 'audio' and 'D' not in p['flags']]
    assert sorted(p['pts'] for p in vp) == list(range(0, total_frames * 512, 512))
    for packets in [vp, ap]:
        assert all(x['dts'] < y['dts'] for x, y in zip(packets, packets[1:]))
    assert min(p['pts'] for p in ap) == 0 and max(p['pts'] + p['duration'] for p in ap) == total_frames * 800
    # 多edit的AAC demuxer会显式回读并丢弃约1s预滚包；D标记包不属于播放时间线。
    discarded = [p for p in presentation if p['codec_type'] == 'audio' and 'D' in p['flags']]
    # 首帧、两个接缝的两侧、末帧均解码成YUV帧哈希；不编码新视频。
    checks = []; offset = 0
    for s in sources:
        for n in [0, s['frames'] - 1]:
            checks.append((s['path'], n, offset + n))
        offset += s['frames']
    def match_frame(item):
        path, local, full = item
        x, y = frame_md5(path, local), frame_md5(args.output, full)
        assert x == y, (str(path), local, full)
        return {'source': str(path), 'source_frame': local, 'output_frame': full, 'decoded_yuv_md5': x, 'equal': True}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        frame_checks = list(pool.map(match_frame, checks))
    decoded = []
    for i, p in enumerate([s['path'] for s in sources] + [args.output]):
        pcm = work / f'decoded-{i}.f32'
        cmd = ['ffmpeg', '-y', '-v', 'warning', '-i', str(p), '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', str(pcm)]
        q = subprocess.run(cmd, capture_output=True, text=True)
        assert q.returncode == 0 and 'non-monoton' not in q.stderr.lower(), q.stderr
        decoded.append(np.fromfile(pcm, dtype='<f4')); pcm.unlink()
    merged = decoded[-1]; cursor = 0; audio_checks = []; presentation_offset = 0
    for s, ref in zip(sources, decoded[:-1]):
        act = merged[cursor:cursor + len(ref)]
        assert len(act) == len(ref)
        x, y = ref.astype('float64'), act.astype('float64'); error = x - y
        snr = 10 * np.log10(max(1e-30, np.dot(x, x)) / max(1e-30, np.dot(error, error)))
        gain = 20 * np.log10(max(1e-30, np.sqrt(np.mean(y * y))) / max(1e-30, np.sqrt(np.mean(x * x))))
        lag = cursor - presentation_offset
        assert snr >= 30 and abs(gain) <= .05 and abs(lag / SR) < .05
        tail = ref[s['frames'] * 800:]
        assert len(tail) == 0 or np.abs(tail).max() < 1e-7
        audio_checks.append({'id': s['id'], 'decoded_source_samples': len(ref), 'decoded_snr_db': float(snr),
                             'decoded_gain_db': float(gain), 'pcm_writer_lag_samples': lag,
                             'pcm_writer_lag_seconds': lag / SR, 'source_padding_is_digital_silence': True})
        cursor += len(ref); presentation_offset += s['frames'] * 800
    assert len(merged) == cursor
    for s in sources:
        assert sha(s['path']) == s['sha256']
    result = {
        'schema': 1, 'status': 'PASS', 'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'script_sha256': sha(Path(__file__)), 'ffmpeg_version': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0],
        'output': {'path': str(args.output), 'file': str(args.output), 'sha256': sha(args.output), 'bytes': args.output.stat().st_size},
        'video_stream_copy': True, 'audio_stream_copy': True, 'ordered_source_payloads_verified': True,
        'video_packets_preserved': True, 'audio_packets_preserved': True, 'payloads': payloads,
        'sources': [{k: v for k, v in s.items() if k not in ['raw_packets', 'info']} for s in sources],
        'commands': logs, 'video_frames': total_frames, 'fps': FPS, 'duration_seconds': total_frames / FPS,
        'video_frame_pts_exact_30fps': True, 'video_dts_strictly_increasing': True,
        'effective_audio_dts_strictly_increasing': True, 'audio_presented_samples': total_frames * 800,
        'av_container_duration_difference_seconds': abs(float(v['duration']) - float(a['duration'])),
        'audio_edit_list': {'movie_timescale': SR, 'entries': [{'duration': n, 'media_time': t, 'rate': 1} for n, t in entries],
                            'purpose': '每段仅跳过已有1024-sample AAC priming与尾部数字静音padding；所有原AAC载荷仍在mdat中且逐包严格等序。',
                            'discarded_preroll_demux_packets': len(discarded),
                            'normal_demux_packet_order_note': 'MOV解码预滚会回读并带D丢弃标记，真实播放包DTS严格递增；raw media全AAC包顺序与来源串接严格相同。'},
        'frame_checks': frame_checks, 'decoded_audio_checks': audio_checks,
        'decoded_audio_note': '多段独立AAC连接后，PNS解码器随机状态可有细微波形差异；有效编码载荷原样。PCM连续写出时A末尾352个数字静音padding使后续最大滞后14.67ms（小于半个30fps画面），末尾另192个数字静音padding；MP4按native帧边界的edit list呈现时长严格一致。没有AAC二次编码或内容/增益/采样率/声道改动。',
        'no_video_render_or_audio_reencode': True,
    }
    # Path只在来源记录中序列化，输出证明最后一次性落盘，失败绝不留旧PASS。
    for s in result['sources']:
        s['path'] = str(s['path'])
    dump(args.proof, result)
    print(json.dumps({'status': result['status'], 'output': result['output'], 'frames': total_frames}, ensure_ascii=False), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir', type=Path, default=Path('/workspace/tem8-rename-2025'))
    p.add_argument('--output', type=Path, default=Path('/workspace/tem8-rename-2025/text-2025-full.mp4'))
    p.add_argument('--proof', type=Path, default=HERE / '2025原文合并核验.json')
    args = p.parse_args()
    try:
        run(args)
    except Exception as exc:
        dump(args.proof, {'schema': 1, 'status': 'FAIL', 'error': repr(exc), 'script_sha256': sha(Path(__file__))})
        raise


if __name__ == '__main__':
    main()
