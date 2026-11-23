"""Transfer an already verified study ZIP to a release runner using its published slide PDFs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
import zipfile
import zlib


CHUNK_SIZE = 6 * 1024 * 1024
SLIDE = '视频逐屏讲义.pdf'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare(archive, receipt, output):
    if archive.stat().st_size != receipt['zip_bytes'] or digest(archive) != receipt['zip_sha256']:
        raise ValueError('Transfer source differs from the verified release')
    gaps = []
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryFile() as retained, archive.open('rb') as stream, zipfile.ZipFile(archive) as zipped:
        previous = 0
        for article in receipt['contents']:
            info = zipped.getinfo(article['folder'] + '/' + SLIDE)
            stream.seek(info.header_offset + 26)
            name_size, extra_size = struct.unpack('<HH', stream.read(4))
            offset = info.header_offset + 30 + name_size + extra_size
            if info.compress_type != zipfile.ZIP_DEFLATED or offset < previous:
                raise ValueError('Unexpected ZIP member order or compression')
            stream.seek(previous)
            retained.write(stream.read(offset - previous))
            packed = stream.read(info.compress_size)
            gaps.append(dict(lesson=article['lesson'], start=offset, size=len(packed),
                             packed_sha256=hashlib.sha256(packed).hexdigest()))
            previous = stream.tell()
        shutil.copyfileobj(stream, retained)
        retained.seek(0)
        parts = []
        while chunk := retained.read(CHUNK_SIZE):
            filename = f'part-{len(parts):03}.bin'
            (output / filename).write_bytes(chunk)
            parts.append({'name': filename, 'sha256': hashlib.sha256(chunk).hexdigest()})
    (output / 'index.json').write_text(json.dumps({'parts': parts, 'slides': gaps}, indent=1) + '\n')


def restore(transfer, receipt, slides, target):
    index = json.loads((transfer / 'index.json').read_text())
    if [gap['lesson'] for gap in index['slides']] != [a['lesson'] for a in receipt['contents']]:
        raise ValueError('Slide order differs from the release receipt')
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.with_suffix('.partial')
    with tempfile.TemporaryFile() as retained, stage.open('wb') as output:
        for i, part in enumerate(index['parts']):
            name = f'part-{i:03}.bin'
            if part['name'] != name:
                raise ValueError('Invalid transfer part')
            chunk = (transfer / name).read_bytes()
            if hashlib.sha256(chunk).hexdigest() != part['sha256']:
                raise ValueError('Transfer part digest differs')
            retained.write(chunk)
        retained.seek(0)
        for gap in index['slides']:
            position = gap['start'] - output.tell()
            if position < 0:
                raise ValueError('Overlapping ZIP members')
            output.write(retained.read(position))
            if output.tell() != gap['start']:
                raise ValueError('Incomplete ZIP header')
            codec = zlib.compressobj(3, zlib.DEFLATED, -15)
            packed = codec.compress((slides / (gap['lesson'] + '.pdf')).read_bytes()) + codec.flush()
            if len(packed) != gap['size'] or hashlib.sha256(packed).hexdigest() != gap['packed_sha256']:
                raise ValueError('Slide data differs for ' + gap['lesson'])
            output.write(packed)
        shutil.copyfileobj(retained, output)
    if stage.stat().st_size != receipt['zip_bytes'] or digest(stage) != receipt['zip_sha256']:
        raise ValueError('Restored archive differs from the complete verified file')
    stage.replace(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    make = sub.add_parser('prepare')
    make.add_argument('archive', type=Path)
    make.add_argument('receipt', type=Path)
    make.add_argument('output', type=Path)
    build = sub.add_parser('restore')
    build.add_argument('transfer', type=Path)
    build.add_argument('receipt', type=Path)
    build.add_argument('slides', type=Path)
    build.add_argument('target', type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text())
    if args.mode == 'prepare':
        prepare(args.archive, receipt, args.output)
    else:
        restore(args.transfer, receipt, args.slides, args.target)
