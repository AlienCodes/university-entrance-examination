"""历年专八：核对原始资料，按年准备未裁切的无损PCM音频。

python 原音准备.py 2009 --out /tmp/tem8/2009 --archive /tmp/default.zip
python 原音准备.py 2018 --out /tmp/tem8/2018 --input-root /workspace/tem8-input

默认从老师的 tem8-listening-raw Release 下载原包。只解码，不改变采样率、
声道、增益或时长，不在预处理阶段裁音乐。2018按mini-lecture→interview拼接，
逐段登记精确PCM边界；其余每年只能有一个去重后的音源。
"""
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

D = Path(__file__).resolve().parents[1]
MANIFEST = D / '原始材料清单.json'
ARCHIVE_SHA = '919d6009b39286e2aadc8cc5eed9d4b15cc207be9f6bd3a3b7852a5be1065925'
ARCHIVE_BYTES = 1339407935
URL = 'https://github.com/AlienCodes/university-entrance-examination/releases/download/tem8-listening-raw/default.zip'
YEARS = list(range(2009, 2020)) + list(range(2021, 2025))


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def dump(path, value):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def name(info):
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode('cp437').decode('gbk')
    except UnicodeError:
        return info.filename


def select(year):
    assert year in YEARS, '仅制作2009—2019及2021—2024，2020取消考试'
    m = json.loads(MANIFEST.read_text('utf-8'))
    assert m['archive_sha256'] == ARCHIVE_SHA and m['archive_bytes'] == ARCHIVE_BYTES
    candidates = [r for r in m['files'] if r['suffix'] in ('.mp3', '.wma')
                  and re.search(r'(?<!\d)' + str(year) + r'(?!\d)', r['file'])]
    by_sha = {}
    for row in sorted(candidates, key=lambda r: ('(1)' in r['file'], len(r['file']), r['file'])):
        by_sha.setdefault(row['sha256'], row)
    rows = list(by_sha.values())
    if year == 2018:
        assert len(rows) == 2, (year, '2018必须有讲座与采访两个不同音源', rows)
        mini = [r for r in rows if 'mini-lecture' in r['file'].lower()]
        interview = [r for r in rows if 'interview' in r['file'].lower()]
        assert len(mini) == len(interview) == 1
        rows = mini + interview
    else:
        assert len(rows) == 1, (year, '音源不唯一或缺失', rows)
    return rows


def probe(path):
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                              '-show_format', '-of', 'json', str(path)]))
    streams = [s for s in info['streams'] if s['codec_type'] == 'audio']
    assert len(streams) == 1, (path, '必须恰好一个音频流')
    s = streams[0]
    return {'codec': s['codec_name'], 'sample_rate': int(s['sample_rate']),
            'channels': int(s['channels']), 'channel_layout': s.get('channel_layout'),
            'container_duration': float(info['format']['duration'])}


def get_archive(path):
    path = Path(path)
    if path.exists():
        assert path.stat().st_size == ARCHIVE_BYTES and sha(path) == ARCHIVE_SHA, '现有原包SHA不符'
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + '.partial')
    with urllib.request.urlopen(URL, timeout=120) as src, partial.open('wb') as dst:
        shutil.copyfileobj(src, dst, length=1 << 20)
    assert partial.stat().st_size == ARCHIVE_BYTES and sha(partial) == ARCHIVE_SHA, '下载原包SHA不符'
    partial.replace(path)
    return path


def wave_header(frames, rate, channels):
    # 确定性IEEE float32 WAV；不写会随FFmpeg版本改变的Lavf标签。
    size = frames * channels * 4
    assert size < 0xffffffff - 64, 'WAV过大，不能写32位RIFF长度'
    fmt = struct.pack('<HHIIHHH', 3, channels, rate, rate * channels * 4, channels * 4, 32, 0)
    chunks = b'fmt ' + struct.pack('<I', len(fmt)) + fmt
    chunks += b'fact' + struct.pack('<II', 4, frames)
    chunks += b'data' + struct.pack('<I', size)
    return b'RIFF' + struct.pack('<I', 4 + len(chunks) + size) + b'WAVE' + chunks


def prepare(year, out, archive=None, input_root=None):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    selected = select(year)
    archive_verified = False
    if input_root is None:
        archive = get_archive(archive or out.parent / 'tem8-default.zip')
        archive_verified = True
    with tempfile.TemporaryDirectory(prefix='tem8pcm_', dir=out) as temp:
        temp = Path(temp); sources = []
        if input_root is not None:
            for row in selected:
                source = (Path(input_root) / row['file']).resolve()
                assert source.is_relative_to(Path(input_root).resolve())
                sources.append(source)
        else:
            with zipfile.ZipFile(archive) as z:
                entries = {name(i): i for i in z.infolist() if not i.is_dir()}
                for index, row in enumerate(selected):
                    source = temp / ('source' + str(index) + row['suffix'])
                    with z.open(entries[row['file']]) as src, source.open('wb') as dst:
                        shutil.copyfileobj(src, dst, length=1 << 20)  # also checks ZIP CRC
                    sources.append(source)
        records = []; joined = temp / 'joined.f32'; samples = 0; signature = None
        with joined.open('wb') as combined:
            for index, (row, source) in enumerate(zip(selected, sources)):
                assert source.stat().st_size == row['bytes'] and sha(source) == row['sha256'], ('原音SHA不符', row['file'])
                info = probe(source); sig = (info['sample_rate'], info['channels'])
                if signature is None:
                    signature = sig
                assert sig == signature, '分段采样率或声道不同，禁止自动重采样/改声道'
                pcm = temp / f'{index}.f32'
                subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                                '-i', str(source), '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le',
                                '-f', 'f32le', str(pcm)], check=True)
                frames = pcm.stat().st_size // (4 * sig[1])
                assert frames > sig[0] * 30 and frames * 4 * sig[1] == pcm.stat().st_size
                records.append({**row, 'audio': info, 'decoded_pcm_sha256': sha(pcm), 'decoded_frames': frames,
                                'canonical_start': samples / sig[0], 'canonical_end': (samples + frames) / sig[0]})
                with pcm.open('rb') as f:
                    shutil.copyfileobj(f, combined, length=1 << 20)
                samples += frames
        rate, channels = signature; target = out / '原音.wav'
        with target.open('wb') as dst, joined.open('rb') as src:
            dst.write(wave_header(samples, rate, channels)); shutil.copyfileobj(src, dst, length=1 << 20)
        decoded = temp / 'verify.f32'
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(target),
                        '-map', '0:a:0', '-c:a', 'pcm_f32le', '-f', 'f32le', str(decoded)], check=True)
        assert decoded.stat().st_size == joined.stat().st_size and sha(decoded) == sha(joined), 'WAV封装改变了PCM'
        info = probe(target)
        assert (info['sample_rate'], info['channels']) == signature
        result = {'year': year, 'archive_sha256': ARCHIVE_SHA, 'archive_verified_here': archive_verified,
                  'source_release': 'tem8-listening-raw', 'source_asset': 'default.zip', 'source_entries': records,
                  'canonical': {'file': target.name, 'sha256': sha(target), 'bytes': target.stat().st_size,
                                'sample_rate': rate, 'channels': channels, 'frames': samples,
                                'duration': samples / rate, 'pcm_format': 'float32le', 'pcm_sha256': sha(joined)},
                  'processing': '仅解码为float32 PCM；原采样率、声道、增益保持；2018按讲座→采访无损顺接，PCM逐样本哈希一致。',
                  'intro_trim': {'applied': False, 'status': '片头音乐起点待原文/原音核实，本预处理未裁切'},
                  'ffmpeg': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0]}
        dump(out / '原音准备.json', result)
    print(json.dumps({'year': year, 'duration': result['canonical']['duration'], 'sources': len(records),
                      'sample_rate': rate, 'channels': channels, 'sha256': result['canonical']['sha256']}, ensure_ascii=False))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('year', type=int, choices=YEARS); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--archive', type=Path); p.add_argument('--input-root', type=Path)
    a = p.parse_args(); prepare(a.year, a.out, a.archive, a.input_root)


if __name__ == '__main__':
    main()
