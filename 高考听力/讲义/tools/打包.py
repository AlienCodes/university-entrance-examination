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
    source = D / '分套资料'
    manifest = json.loads((D / '分套资料清单与核验.json').read_text())
    root = '高考英语听力资料包'
    files = []
    assert manifest['case_count'] == len(manifest['cases']) == 50
    assert manifest['pdf_count'] == 450 and len(manifest['pdf_types']) == 9
    assert manifest['questions'] == sum(x['questions'] for x in manifest['cases'])
    assert {p.name for p in source.iterdir() if p.is_dir()} == {r['folder'] for r in manifest['cases']}
    for case in manifest['cases']:
        folder = source / case['folder']
        assert case['detail_sha256'] == sha(D / '逐题详解' / (case['id']+'.json')), '详解已更改，需重制PDF'
        assert set(case['files']) == set(manifest['pdf_types'])
        expected = {r['file'] for r in case['files'].values()} | {r['file'] for r in case['originals']} | {'本套使用说明.txt'}
        assert {p.name for p in folder.iterdir() if p.is_file()} == expected
        for row in case['files'].values():
            p = folder / row['file']
            assert sha(p) == row['sha256'] and p.stat().st_size == row['bytes'], p
            assert p.read_bytes().startswith(b'%PDF-')
        for row in case['originals']:assert sha(folder / row['file']) == row['sha256']
        files += [(f'{root}/{case["folder"]}/{p.name}', p) for p in sorted(folder.iterdir()) if p.is_file()]
    originals = json.loads((D / '原卷解析来源核验.json').read_text('utf-8'))
    assert originals['document_count'] == originals['source_document_count'] == len(originals['files'])
    raw_files = []
    for row in originals['files']:
        p = (D / '真题原卷与解析' / row['file']).resolve()
        assert p.is_relative_to((D / '真题原卷与解析').resolve())
        assert p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], p
        raw_files.append((f'完整原始资料/{row["file"]}', p))
    raw_files += [(f'完整原始资料/{n}', D/n) for n in ['原卷解析文件清单.txt','原卷解析来源核验.json']]
    archive = DIST/'历年真题与解析_完整原始资料.zip'
    pack(archive,raw_files)
    files.append((f'{root}/{archive.name}',archive))
    files += [(f'{root}/先读我.txt', D / '先读我.txt'), (f'{root}/收录试卷清单.txt', D / '收录试卷清单.txt'), (f'{root}/分套资料清单与核验.json', D / '分套资料清单与核验.json')]
    files += [(f'{root}/原卷解析文件清单.txt', D / '原卷解析文件清单.txt'), (f'{root}/原卷解析来源核验.json', D / '原卷解析来源核验.json')]
    result = pack(DIST / 'GAOKAO-listening-materials.zip', files)
    with zipfile.ZipFile(DIST/result['file']) as z:
        assert len({Path(i.filename).parts[1] for i in z.infolist() if len(Path(i.filename).parts)>2})==50
        assert sum(i.filename.endswith('.pdf') for i in z.infolist())==450
    return result


def shop():
    source = D / '商品图'
    images = sorted((source / '成品').glob('*.png'))
    assert len(images) == 13, f'商品图应为13张，实际{len(images)}'
    from struct import unpack
    for image in images:
        b = image.read_bytes()
        assert b[:8] == b'\x89PNG\r\n\x1a\n'
        w, h = unpack('>II', b[16:24])
        assert w == h and w >= 1000 and len(b) <= 5*1024*1024, (image.name, w, h, len(b))
    proof = json.loads((source / '图文核对.json').read_text())
    assert proof['materials_sha256'] == sha(DIST / 'GAOKAO-listening-materials.zip'), '打开后的文件清单须对应本次实际交付包'
    assert len(proof['images']) == 13 and proof['pdf_source_count'] == 9
    manifest = json.loads((D / '分套资料清单与核验.json').read_text())
    case = next(r for r in manifest['cases'] if r['id']==proof['sample_case'])
    assert {r['key'] for r in proof['pdf_sources']} == set(manifest['pdf_types']), '每套九份PDF都必须展示真实内页'
    for row in proof['pdf_sources']:
        book = case['files'][row['key']]
        assert row['pdf'] == book['file'] and row['pdf_sha256'] == book['sha256']
        for image_field, digest_field in [('full_png', 'full_sha256'), ('detail_png', 'detail_sha256')]:
            image_path = (source / row[image_field]).resolve()
            assert image_path.is_relative_to(source.resolve()) and sha(image_path) == row[digest_field], '真实PDF截图缺失或已变'
    assert {x['file'] for x in proof['images']} == {x.name for x in images}
    for row in proof['images']:
        assert sha(source / '成品' / row['file']) == row['sha256'] and row['reviewed'] is True
    files = [(f'小店上传素材/商品图/{p.name}', p) for p in images]
    for p in sorted((source / '真实内页').rglob('*.png')):
        files.append((f'小店上传素材/真实PDF样图/{p.relative_to(source / "真实内页").as_posix()}', p))
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
