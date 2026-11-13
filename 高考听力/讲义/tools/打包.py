"""核对成品后分别打包学习资料、小店上传素材；不把卖家素材混入买家资料。"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE.parent
ROOT = D.parents[1]
DIST = D / '下载包'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pack(path, items):
    assert len(items) == len({n for n, _ in items})
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as z:
        for name, src in items:
            assert src.is_file() and src.stat().st_size
            z.writestr(zipfile.ZipInfo(name, (2026, 11, 13, 0, 0, 0)), src.read_bytes())
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        assert [i.filename for i in z.infolist()] == [n for n, _ in items]
        for info, (name, src) in zip(z.infolist(), items):
            assert name.isascii() or info.flag_bits & 0x800, name
            assert hashlib.sha256(z.read(info)).hexdigest() == sha(src), name
    return {'file': path.name, 'bytes': path.stat().st_size, 'sha256': sha(path), 'entries': len(items)}


def materials():
    source = D / '成品'
    manifest = json.loads((source / '文件清单与核验.json').read_text())
    root = '高考英语听力资料包'
    files = []
    for row in sorted(manifest['files'].values(), key=lambda v: v['file']):
        p = source / row['file']
        assert sha(p) == row['sha256'] and p.stat().st_size == row['bytes'], p
        assert p.read_bytes().startswith(b'%PDF-')
        files.append((f'{root}/{p.name}', p))
    assert len(files) == 8 and manifest['case_count'] == len(manifest['cases'])
    assert manifest['questions'] == sum(x['questions'] for x in manifest['cases'])
    files += [(f'{root}/先读我.txt', D / '先读我.txt'), (f'{root}/收录试卷清单.txt', D / '收录试卷清单.txt'), (f'{root}/文件清单与核验.json', source / '文件清单与核验.json')]
    return pack(DIST / 'GAOKAO-listening-materials.zip', files)


def shop():
    source = D / '商品图'
    images = sorted((source / '成品').glob('*.png'))
    assert len(images) == 9, f'商品图应为9张，实际{len(images)}'
    from struct import unpack
    for image in images:
        b = image.read_bytes()
        assert b[:8] == b'\x89PNG\r\n\x1a\n'
        w, h = unpack('>II', b[16:24])
        assert w == h and w >= 1000 and len(b) <= 5*1024*1024, (image.name, w, h, len(b))
    proof = json.loads((source / '图文核对.json').read_text())
    assert len(proof['images']) == 9
    assert {x['file'] for x in proof['images']} == {x.name for x in images}
    for row in proof['images']:
        assert sha(source / '成品' / row['file']) == row['sha256'] and row['reviewed'] is True
    files = [(f'小店上传素材/商品图/{p.name}', p) for p in images]
    for p in sorted((source / '真实内页').glob('*.png')):
        files.append((f'小店上传素材/真实PDF样图/{p.name}', p))
    for name in ['商品标题.txt', '商品简介.txt', '上传顺序与填写说明.txt', '图文核对.json']:
        files.append((f'小店上传素材/{name}', source / name))
    sample = source / '真实内页预览.pdf'
    if sample.exists():
        files.append((f'小店上传素材/{sample.name}', sample))
    return pack(DIST / 'GAOKAO-listening-shop.zip', files)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--materials-only', action='store_true')
    a = ap.parse_args()
    result = [materials()]
    if not a.materials_only:
        result.append(shop())
    DIST.mkdir(exist_ok=True)
    (DIST / 'SHA256SUMS').write_text(''.join(f'{x["sha256"]}  {x["file"]}\n' for x in result), 'utf-8')
    (DIST / '打包核验.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
