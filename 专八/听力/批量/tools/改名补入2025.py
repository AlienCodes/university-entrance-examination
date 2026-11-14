"""只改中文文件名并补入既有2025成品；不调用任何媒体生成或处理程序。

pack exam|text --out DIR；publish exam|text --out DIR。
2025原文按用户要求从既有三段复制载荷合成单片；前15年及2025考试逐字节不变。
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import zipfile

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[2]
REPO = 'AlienCodes/university-entrance-examination'
FINAL_RECORD = BASE / '核验/发布调度/全部视频最终交付核验.json'
SOURCE_ZIPS = {
    'exam': Path('/workspace/tem8-exam-release-monitor/final-download/TEM8-listening-exam-2009-2024-part01.zip'),
    'text': Path('/workspace/tem8-intensive-final-validation/downloads/TEM8-listening-intensive-2009-2024-part01.zip'),
}
SOURCE_2025 = Path('/workspace/tem8-rename-2025')
MERGE_PROOF = BASE / '核验/改名补入2025/2025原文合并核验.json'
YEARS = list(range(2009, 2020)) + list(range(2021, 2026))
DATE = (2026, 11, 14, 0, 0, 0)
LIMIT = int(1.8 * 2**30)
MEDIA_2025 = {
    'exam': [('exam-2025.mp4', '2025 听力真题.mp4', 'df6e5f3a8995f8e416db36cae8316d8bc232ee64ecfbe9ba7f28359c1ea58ba4', 101065473,
              ['5ec954e304d5c54ef1bfd15551f7dd8a3bf729b0', '4db4d703a06cbb9669fc9ebce8be2e03e4011f3c'])],
    'text': [('text-2025-A.mp4', '2025 听力原文（讲座）.mp4', '692c098dc03fd03e120320895b5ab18ba6942b8bdb727d6b36e24b243c91d31d', 30754126, ['86fc6cc269975cec6979623bf847ed6e107509ad']),
             ('text-2025-B1.mp4', '2025 听力原文（访谈一）.mp4', '8885b85720d1a626f0b00235e88e18f6018b685e4e8b6ec16c7695615bebf405', 19450143, ['e4ea0f3d92f0fb40d8eb9873e462ac1850f75ded']),
             ('text-2025-B2.mp4', '2025 听力原文（访谈二）.mp4', '8143cf6e78b9ac87ae4f7815e0ccc7d27720e4ea6d3ede8399e42417f20c3661', 20849161, ['332200457e18172f76d913919b2f1ee2599d7083'])],
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def dump(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def digest(source):
    if hasattr(source, 'read'):
        return hashlib.file_digest(source, 'sha256').hexdigest()
    with Path(source).open('rb') as f:
        return digest(f)


def gh(*args, parsed=False):
    result = subprocess.run(['gh', *map(str, args)], check=True, capture_output=True, text=True)
    return json.loads(result.stdout) if parsed else result.stdout


def tag(kind):
    return f'tem8-listening-{kind}-2009-2025'


def archive_name(kind):
    return f'TEM8-listening-{kind}-2009-2025.zip'


def source_record(kind):
    return read(FINAL_RECORD)['deliveries']['exam' if kind == 'exam' else 'intensive']


def expected_rows(kind):
    source = source_record(kind)
    old = {int(a['name'].rsplit('-', 1)[1][:4]): a for a in source['video_files']}
    need(set(old) == set(YEARS) - {2025} and len(old) == 15, '旧清单必须恰有15个真实年份')
    rows = []
    if kind == 'text':
        proof = read(MERGE_PROOF)
        need(proof['status'] == 'PASS' and proof['video_packets_preserved'] is True and proof['audio_packets_preserved'] is True, '2025原文合并缺少真实载荷保持核验')
        output = proof['output']
        need(Path(output['file']).name == 'text-2025-full.mp4', '合并输出文件不符')
        rows.append({'year': 2025, 'name': '2025 听力原文.mp4', 'bytes': output['bytes'], 'sha256': output['sha256'],
                     'source': {'type': 'authorized_packet_copy_concatenation', 'local_name': 'text-2025-full.mp4',
                                'original_sources': [{'local_name': filename, 'sha256': sha, 'bytes': size, 'git_blob_ids': blobs}
                                                     for filename, name, sha, size, blobs in MEDIA_2025['text']],
                                'verification_report': MERGE_PROOF.relative_to(ROOT).as_posix(),
                                'verification_report_sha256': digest(MERGE_PROOF),
                                'video_and_audio_packets_preserved': True, 'container_bytes_changed': True}})
    else:
        for filename, name, sha, size, blobs in MEDIA_2025[kind]:
            rows.append({'year': 2025, 'name': name, 'bytes': size, 'sha256': sha,
                         'source': {'type': 'existing_git_video', 'local_name': filename,
                                    'git_blob_ids': blobs, 'source_list': '.github/tem8-listening-release.txt'}})
    for year in sorted(old, reverse=True):
        a = old[year]
        rows.append({'year': year, 'name': f'{year} 听力' + ('真题.mp4' if kind == 'exam' else '原文.mp4'),
                     'bytes': a['size'], 'sha256': a['digest'].removeprefix('sha256:'),
                     'source': {'type': 'verified_release_zip_member', 'release_tag': source['tag'],
                                'asset': source['archives'][0]['name'], 'archive_sha256': source['archives'][0]['digest'].removeprefix('sha256:'),
                                'original_name': a['label'], 'video_asset': a['name'], 'video_url': a['browser_download_url']}})
    need(len(rows) == 16, '成品文件数量不符')
    need(len(rows) == len({r['name'] for r in rows}), '新名称重复')
    need({r['year'] for r in rows} == set(YEARS), '年份缺漏或包含2020')
    return rows


def verify_package(kind, out):
    out = Path(out)
    manifest = read(out / 'TEM8-manifest.json')
    need(manifest['kind'] == kind and manifest['tag'] == tag(kind), '包类型不符')
    need(manifest['files'] == expected_rows(kind), '清单并非当前逐字节复用来源')
    archive = out / archive_name(kind)
    need(archive.stat().st_size == manifest['archive']['bytes'] and digest(archive) == manifest['archive']['sha256'], 'ZIP摘要/大小不符')
    need(archive.stat().st_size < LIMIT, 'ZIP超过1.8GiB')
    with zipfile.ZipFile(archive) as z:
        need(z.testzip() is None, 'ZIP CRC不符')
        need(z.namelist() == [r['name'] for r in manifest['files']], '成员名称或最新优先顺序不符')
        for info, row in zip(z.infolist(), manifest['files']):
            need(info.file_size == row['bytes'] and info.flag_bits & 0x800 and info.compress_type == zipfile.ZIP_STORED and info.date_time == DATE, 'ZIP中文名/字节/格式不符')
            with z.open(info) as f:
                need(digest(f) == row['sha256'], '视频字节改变：' + row['name'])
    return manifest


def pack(kind, out, source_zip=None, source_2025=None):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    source_zip = Path(source_zip or SOURCE_ZIPS[kind]); source_2025 = Path(source_2025 or SOURCE_2025)
    source = source_record(kind); source_archive = source['archives'][0]
    need(source_zip.stat().st_size == source_archive['size'] and digest(source_zip) == source_archive['digest'].removeprefix('sha256:'), '旧源ZIP摘要不符')
    rows = expected_rows(kind); archive = out / archive_name(kind); temporary = archive.with_suffix('.tmp')
    if kind == 'text':
        for filename, _, sha, size, _ in MEDIA_2025['text']:
            p = source_2025 / filename
            need(p.stat().st_size == size and digest(p) == sha, '2025合并的原始三段来源不同')
    with zipfile.ZipFile(source_zip) as old, zipfile.ZipFile(temporary, 'w', zipfile.ZIP_STORED, allowZip64=True) as new:
        need(len(old.infolist()) == 15 and old.testzip() is None, '旧ZIP不是15个已核视频或CRC错误')
        member_by_name = {Path(n).name: n for n in old.namelist()}
        need(len(member_by_name) == 15 and set(member_by_name) == {r['source']['original_name'] for r in rows if r['year'] != 2025}, '旧成员完整名单不符')
        for row in rows:
            if row['year'] == 2025:
                p = source_2025 / row['source']['local_name']
                need(p.stat().st_size == row['bytes'] and digest(p) == row['sha256'], '2025现成文件不符：' + p.name)
                src = p.open('rb')
            else:
                src = old.open(member_by_name[row['source']['original_name']])
            zi = zipfile.ZipInfo(row['name'], DATE); zi.compress_type = zipfile.ZIP_STORED; zi.external_attr = 0o644 << 16
            h = hashlib.sha256(); size = 0
            with src, new.open(zi, 'w', force_zip64=True) as target:
                while chunk := src.read(1 << 20):
                    h.update(chunk); size += len(chunk); target.write(chunk)
            need(h.hexdigest() == row['sha256'] and size == row['bytes'], '改名拷贝后源字节不一致')
    temporary.replace(archive)
    manifest = {'schema': 1, 'kind': kind, 'tag': tag(kind), 'scope': '2009—2024仅改中文文件名，原MP4逐字节不变；补入现成2025。2025原文经用户授权只复制原三段载荷合成单片，未重编码。',
                'years': sorted(YEARS, reverse=True), 'cancelled_years': [2020], 'videos': len(rows),
                'text_2025_mode': 'authorized_packet_copy_concatenation' if kind == 'text' else None,
                'source_record_file': FINAL_RECORD.relative_to(ROOT).as_posix(), 'source_record_sha256': digest(FINAL_RECORD),
                'files': rows, 'archive': {'name': archive.name, 'bytes': archive.stat().st_size, 'sha256': digest(archive)}}
    dump(out / 'TEM8-manifest.json', manifest)
    (out / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in [archive, out / 'TEM8-manifest.json']), 'utf-8')
    verify_package(kind, out)
    print(json.dumps({'status': 'PACKED_AND_VERIFIED', 'kind': kind, 'videos': len(rows), 'archive': manifest['archive']}, ensure_ascii=False), flush=True)
    return manifest


def release(release_tag):
    return gh('api', f'repos/{REPO}/releases/tags/{release_tag}', parsed=True)


def upload(release_tag, path):
    path = Path(path); assets = {a['name']: a for a in release(release_tag)['assets']}
    if path.name in assets:
        a = assets[path.name]
        need(a.get('digest') == 'sha256:' + digest(path) and a['size'] == path.stat().st_size, '目标已存在不同字节，拒绝覆盖：' + path.name)
        return
    gh('release', 'upload', release_tag, path, '-R', REPO)


def server_matches(release_tag, files):
    assets = {a['name']: a for a in release(release_tag)['assets']}
    for p in files:
        a = assets[p.name]
        need(a.get('digest') == 'sha256:' + digest(p) and a['size'] == p.stat().st_size, '服务器摘要/大小不符：' + p.name)


def publish(kind, out):
    out = Path(out); manifest = verify_package(kind, out); release_tag = tag(kind)
    label = '听力真题' if kind == 'exam' else '听力原文'
    notes = f'2009—2025专八{label}，最新年份在前。2009—2024原15个MP4只改中文文件名，视频字节完全不变；补入2025既有成品。\n\n'
    if kind == 'text': notes += '2025原文按用户要求将原有讲座、访谈一、访谈二三段顺序复制载荷合成一个视频，画面与声音均未重编码；新MP4容器字节与原三文件不同。\n\n'
    notes += '2020年停考。2009—2015沿用原上传材料的新题型优化版；2014题源冲突题的原有不计分标注保留。\n\n'
    notes += '|中文文件名|字节|SHA256|\n|---|---:|---|\n' + ''.join(f'|{r["name"]}|{r["bytes"]}|{r["sha256"]}|\n' for r in manifest['files'])
    notes_path = out / 'notes.md'; notes_path.write_text(notes, 'utf-8')
    view = subprocess.run(['gh', 'api', f'repos/{REPO}/releases/tags/{release_tag}'], capture_output=True, text=True)
    if view.returncode:
        need('HTTP 404' in view.stderr, '查询Release失败，不能据此创建：' + view.stderr)
        # 创建操作仅执行一次；读操作失败或未知创建结果不会盲目重发POST。
        branch = os.getenv('GITHUB_REF_NAME') or subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
        need(branch and branch != 'HEAD', '发布目标必须是分支名')
        gh('release', 'create', release_tag, '-R', REPO, '--target', branch, '--title', f'专八{label}｜2025—2009｜统一文件名', '--notes-file', notes_path)
    files = [out / archive_name(kind), out / 'TEM8-manifest.json', out / 'SHA256SUMS']
    for p in files: upload(release_tag, p)
    server_matches(release_tag, files)
    with tempfile.TemporaryDirectory(prefix=f'tem8rename-{kind}-') as td:
        gh('release', 'download', release_tag, '-R', REPO, '-p', archive_name(kind), '-D', td)
        back = Path(td) / archive_name(kind)
        need(digest(back) == manifest['archive']['sha256'] and back.stat().st_size == manifest['archive']['bytes'], '回下载ZIP摘要不同')
        # 复用同一逐成员核查，清单和摘要均由原成品固定。
        shutil.copyfile(out / 'TEM8-manifest.json', Path(td) / 'TEM8-manifest.json')
        verify_package(kind, td)
    report = {'schema': 1, 'status': 'PASS', 'tag': release_tag, 'release_url': f'https://github.com/{REPO}/releases/tag/{release_tag}',
              'kind': kind, 'videos': manifest['videos'], 'years': manifest['years'], 'archive': manifest['archive'],
              'original_2009_2024_video_bytes_unchanged': True, 'year2025_mode': manifest['text_2025_mode'] or 'existing_exam_bytes_unchanged', 'source_to_target_names_verified': True,
              'server_digest_and_size_verified': True, 'actual_download_zip_crc_utf8_order_member_sha_verified': True}
    report_path = out / 'TEM8-download-verification.json'; dump(report_path, report)
    upload(release_tag, report_path); server_matches(release_tag, [*files, report_path])
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['pack', 'publish', 'verify'])
    parser.add_argument('kind', choices=['exam', 'text'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source-zip', type=Path)
    parser.add_argument('--source-2025', type=Path)
    args = parser.parse_args()
    if args.command == 'pack': pack(args.kind, args.out, args.source_zip, args.source_2025)
    elif args.command == 'publish': publish(args.kind, args.out)
    else: verify_package(args.kind, args.out)


if __name__ == '__main__':
    main()
