"""只更新已发布视频的名称及ZIP目录，逐字节复用现有MP4。"""
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

REPO = 'AlienCodes/university-entrance-examination'
ROOT = Path(__file__).resolve().parents[1]
CONFIG = {
    'exam': ('gaokao-listening', '高考听力/tools/命名.py', 'gaokao-listening-filenames.txt'),
    'text': ('gaokao-text', '高考听力/精读/tools/命名.py', 'gaokao-text-filenames.txt'),
}


def run(args, capture=False):
    return subprocess.run(args, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def api(path, *args):
    return json.loads(run(['gh', 'api', path, *args], True))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def names(kind):
    spec = importlib.util.spec_from_file_location('names_' + kind, ROOT / CONFIG[kind][1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def entries(path, aliases, expected):
    found = []
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            p = PurePosixPath(info.filename)
            assert not p.is_absolute() and '..' not in p.parts, info.filename
            assert p.name in aliases, '未知旧文件名：' + p.name
            sid = aliases[p.name]
            assert info.file_size == expected[sid]['bytes'], sid + ' 字节数不符'
            found.append(sid)
    assert len(found) == len(set(found)), '压缩包内重复套号'
    return found


def rewrite(src, dst, aliases, expected):
    out_names = []
    with zipfile.ZipFile(src) as old, zipfile.ZipFile(dst, 'w', zipfile.ZIP_STORED, allowZip64=True) as new:
        for info in old.infolist():
            if info.is_dir():
                continue
            p = PurePosixPath(info.filename)
            sid = aliases[p.name]
            row = expected[sid]
            name = str(p.parent / row['label'])
            assert '视频版' not in name and '高考英语真题' not in name
            zi = zipfile.ZipInfo(name, info.date_time)
            zi.compress_type = zipfile.ZIP_STORED
            zi.external_attr = 0o644 << 16
            h = hashlib.sha256()
            size = 0
            with old.open(info) as r, new.open(zi, 'w', force_zip64=True) as w:
                for b in iter(lambda: r.read(1 << 20), b''):
                    h.update(b)
                    size += len(b)
                    w.write(b)
            assert h.hexdigest() == row['sha256'] and size == row['bytes'], sid + ' 原视频SHA256不符'
            out_names.append(name)
    assert Path(dst).stat().st_size < 2 * 1024**3
    return out_names


def check_download(path, expected_names, aliases, expected):
    with zipfile.ZipFile(path) as z:
        items = z.infolist()
        assert [i.filename for i in items] == expected_names, '回下载文件名/顺序不符'
        for info in items:
            assert info.flag_bits & 0x800 and info.compress_type == zipfile.ZIP_STORED
            sid = aliases[PurePosixPath(info.filename).name]
            h = hashlib.sha256()
            with z.open(info) as f:
                for b in iter(lambda: f.read(1 << 20), b''):
                    h.update(b)
            assert h.hexdigest() == expected[sid]['sha256'], sid + ' 回下载内容不符'


def main(kind, out):
    tag, _, list_name = CONFIG[kind]
    m = names(kind)
    out.mkdir(parents=True, exist_ok=True)
    before = api(f'repos/{REPO}/releases/tags/{tag}')
    (out / 'before.json').write_text(json.dumps(before, ensure_ascii=False))
    assets = {a['name']: a for a in before['assets']}
    rows = []
    aliases = {}
    for sid, _ in m.order([(s, kind) for s in m.SETS]):
        a = assets[m.asset(sid)]
        assert a['state'] == 'uploaded' and a['digest'].startswith('sha256:')
        rows.append({'套': sid, 'asset': a['name'], 'id': a['id'], 'label': m.label(sid),
                     'sha256': a['digest'].split(':', 1)[1], 'bytes': a['size']})
        for name in m.accepted_labels(sid):
            assert name not in aliases or aliases[name] == sid
            aliases[name] = sid
    assert len(rows) == 50 and not m.problems([r['label'] for r in rows])
    assert {a['name'] for a in before['assets'] if a['name'].endswith('.mp4')} == {r['asset'] for r in rows}
    expected = {r['套']: r for r in rows}
    (out / 'plan.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    for r in rows:
        if assets[r['asset']].get('label') != r['label']:
            api(f"repos/{REPO}/releases/assets/{r['id']}", '-X', 'PATCH', '-f', 'label=' + r['label'])
    print(tag, '50个显示名已统一；原视频资产ID和字节不变', flush=True)
    zips = sorted(a['name'] for a in before['assets'] if a['name'].startswith(tag + '-') and a['name'].endswith('.zip'))
    assert zips, '没有既有ZIP可复用'
    old_dir = out / 'old'
    old_dir.mkdir(exist_ok=True)

    def download(name):
        run(['gh', 'release', 'download', tag, '-R', REPO, '-p', name, '-D', str(old_dir), '--clobber'])
        digest = assets[name].get('digest')
        if digest:
            assert digest == 'sha256:' + sha(old_dir / name), name + ' 源ZIP哈希不符'
        return entries(old_dir / name, aliases, expected)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        parts = list(ex.map(download, zips))
    all_ids = [sid for part in parts for sid in part]
    assert len(all_ids) == 50 and set(all_ids) == set(expected), '既有ZIP缺套或重复'
    print(tag, '已取回50个既有成品的压缩包；开始只改包内名字', flush=True)
    summaries = []
    for zname in zips:
        dest = out / zname
        file_names = rewrite(old_dir / zname, dest, aliases, expected)
        (old_dir / zname).unlink()
        digest = sha(dest)
        if assets[zname].get('digest') != 'sha256:' + digest:
            run(['gh', 'release', 'upload', tag, '-R', REPO, str(dest), '--clobber'])
        dest.unlink()
        downloaded = out / 'downloaded'
        downloaded.mkdir(exist_ok=True)
        run(['gh', 'release', 'download', tag, '-R', REPO, '-p', zname, '-D', str(downloaded), '--clobber'])
        check = downloaded / zname
        assert sha(check) == digest, zname + ' 回下载ZIP哈希不符'
        check_download(check, file_names, aliases, expected)
        summaries.append({'zip': zname, 'files': len(file_names), 'sha256': digest, 'bytes': check.stat().st_size,
                          'names': file_names, 'download_verified': True})
        check.unlink()
        print('✅', tag, zname, len(file_names), '个：新名字、UTF-8、CRC、每个MP4原始SHA256、回下载均一致', flush=True)
    listing = out / list_name
    listing.write_text('资产名\t中文文件名\tsha256\t字节数\n' + ''.join(
        f"{r['asset']}\t{r['label']}\t{r['sha256']}\t{r['bytes']}\n" for r in rows), encoding='utf-8')
    run(['gh', 'release', 'upload', tag, '-R', REPO, str(listing), '--clobber'])
    body = before.get('body') or ''
    for r in rows:
        for old in m.accepted_labels(r['套']):
            body = body.replace(old, r['label'])
    body = body.replace('视频版真题考试', '考试').replace('视频版考试', '考试').replace('高考英语真题', '').replace('视频版', '')
    body = body.replace('官方解析 × 独立做题一致；没有解析答案的套是两次独立做题一致。', '上传解析与独立做题互核，分歧保留裁定记录。')
    notes = out / 'notes.md'
    notes.write_text(body, encoding='utf-8')
    title = '高考听力 ' + ('考试' if kind == 'exam' else '原文精读')
    run(['gh', 'release', 'edit', tag, '-R', REPO, '-t', title, '--notes-file', str(notes)])
    after = api(f'repos/{REPO}/releases/tags/{tag}')
    current = {a['name']: a for a in after['assets']}
    for r in rows:
        a = current[r['asset']]
        assert a['id'] == r['id'] and a['size'] == r['bytes'] and a['digest'] == 'sha256:' + r['sha256']
        assert a['label'] == r['label']
    for z in summaries:
        a = current[z['zip']]
        assert a['size'] == z['bytes'] and a['digest'] == 'sha256:' + z['sha256']
    (out / 'after.json').write_text(json.dumps(after, ensure_ascii=False))
    (out / 'summary.json').write_text(json.dumps({'tag': tag, 'kind': kind, 'videos': 50,
        'video_ids_hashes_sizes_unchanged': True, 'zips': summaries, 'passed': True}, ensure_ascii=False, indent=1))
    print('✅', tag, '50个视频新名称和全部下载包重新发布通过，视频字节未变。', flush=True)


def selftest():
    for kind in CONFIG:
        m = names(kind)
        assert not m.problems([m.label(s) for s in m.SETS])
        suffix = '考试' if kind == 'exam' else '原文精读'
        assert m.label('2026-zj1') == f'2026年 浙江卷（1月） {suffix}.mp4'
        ids = list(m.SETS)[:3]
        expected = {}
        aliases = {}
        for n, sid in enumerate(ids):
            data = bytes([n + 1]) * (1000 + n)
            expected[sid] = {'label': m.label(sid), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'data': data}
            aliases.update({x: sid for x in m.accepted_labels(sid)})
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            with zipfile.ZipFile(t / 'old.zip', 'w', zipfile.ZIP_STORED) as z:
                for sid in ids:
                    z.writestr('既有目录/' + m.previous_label(sid), expected[sid]['data'])
            assert set(entries(t / 'old.zip', aliases, expected)) == set(ids)
            good = rewrite(t / 'old.zip', t / 'new.zip', aliases, expected)
            check_download(t / 'new.zip', good, aliases, expected)
            expected[ids[0]]['sha256'] = '0' * 64
            try:
                rewrite(t / 'old.zip', t / 'bad.zip', aliases, expected)
            except AssertionError:
                pass
            else:
                raise AssertionError('改视频字节的错误未拦截')
    print('✅ 100个短文件名、既有ZIP只改名正例、MP4内容不符负例通过')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--kind', choices=CONFIG)
    p.add_argument('--out', type=Path, default=Path('rename-out'))
    p.add_argument('--selftest', action='store_true')
    a = p.parse_args()
    if a.selftest:
        selftest()
    else:
        assert a.kind
        main(a.kind, a.out)
