"""专八历年视频：来源/截图门禁、成品存档、续收、分包发布与回下载。

本程序只做发布与核验，绝不调用视频生成程序。
控制文件.github/tem8-listening-history-render.json：
  {"mode":"sample","sample_id":"trial-1","stage":"render","exam":[2009],
   "intensive":["2009-A"],"collect_runs":[],"render":true}
mode=complete须与批量/全批清单.json严格相同；stage=review只持久保存待看截图，
不制作/发布正式MP4。render=false只汇集，或render_exam/render_intensive指定失败项重做。

审核登记：批量/审核登记.json中的entries["exam:2009"或"intensive:2009-A"]。
先用candidate获取输入/程序指纹，实际审后status改approved并写evidence；截图阶段
review命令另产截图候选，实际看过后才把shots登记。生产会逐PNG核SHA，不能空审批。
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE.parent
ROOT = D.parents[2]
CONTROL = ROOT / '.github/tem8-listening-history-render.json'
REGISTRY = D / '审核登记.json'
YEARS = list(range(2009, 2020)) + list(range(2021, 2025))
LIMIT = int(1.8 * (1 << 30))
DATE = (2026, 11, 13, 0, 0, 0)
CACHE_TAG = 'tem8-listening-render-cache-2009-2024'
REVIEW_TAG = 'tem8-listening-review-2009-2024'
REPO = os.getenv('GITHUB_REPOSITORY', 'AlienCodes/university-entrance-examination')


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def hash_json(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def dump(path, value):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def gh(*args, json_output=False):
    p = subprocess.run(['gh', *map(str, args)], check=True, capture_output=True, text=True)
    return json.loads(p.stdout) if json_output else p.stdout


def relative(path):
    return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()


def validate_id(kind, ident):
    ident = str(ident)
    assert kind in ('exam', 'intensive')
    assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', ident), 'ID只能用ASCII字母数字短横线下划线'
    assert int(ident[:4]) in YEARS, '年份不在实际考试清单'
    if kind == 'exam': assert ident == str(int(ident))
    return ident


def input_paths(kind, ident):
    ident = validate_id(kind, ident)
    if kind == 'exam':
        folder = D / '数据' / ident
        paths = [folder / '试卷.json', folder / '时间轴.json']
    else:
        paths = [D / '精听数据' / (ident + '.json')]
    if int(ident[:4]) == 2022:
        paths.append(D / '核验/2022-补充音源.json')
        if kind == 'intensive':
            paths.append(D / '核验/2022-停顿边界复核.json')
    return paths


def selected_sources(year):
    spec = importlib.util.spec_from_file_location('tem8_original_source', HERE / '原音准备.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.select(year)


def validate_source_preparation(prep, year, canonical_sha):
    """核来源登记和实际解码记录，拦下2022回抓缺头原包或伪用基础包SHA。"""
    expected = selected_sources(year)
    assert prep['year'] == year and prep['canonical']['sha256'] == canonical_sha
    actual = prep['source_entries']
    assert len(actual) == len(expected)
    for row, source in zip(actual, expected):
        assert all(row[k] == source[k] for k in ['file', 'bytes', 'sha256']), '所选源字节记录与当前登记不符'
        assert row['audio']['sample_rate'] == prep['canonical']['sample_rate']
        assert row['audio']['channels'] == prep['canonical']['channels']
        if year == 2022:
            assert row['origin'] == source['origin']
            assert row['supplement_registration_sha256'] == source['supplement_registration_sha256']
    assert prep['intro_trim']['applied'] is False
    if year == 2022:
        assert prep['archive_sha256'] is None and prep['archive_verified_here'] is False
        assert prep['source_release'] == 'tem8-listening-raw-supplement' and prep['source_asset'] == expected[0]['file']
        assert prep['source_supplement_sha256'] == expected[0]['sha256']
        assert prep['source_supplement_registration_sha256'] == sha(D / '核验/2022-补充音源.json')
        assert prep['source_origin'] == expected[0]['origin']
    else:
        assert prep['archive_sha256'] == '919d6009b39286e2aadc8cc5eed9d4b15cc207be9f6bd3a3b7852a5be1065925'
        assert prep['source_release'] == 'tem8-listening-raw' and prep['source_asset'] == 'default.zip'
    return {'release': prep['source_release'], 'asset': prep['source_asset'],
            'archive_sha256': prep['archive_sha256'],
            'supplement_sha256': prep.get('source_supplement_sha256'),
            'supplement_registration_sha256': prep.get('source_supplement_registration_sha256'),
            'entries': [{'file':r['file'],'bytes':r['bytes'],'sha256':r['sha256'],
                         **({'origin':r['origin']} if 'origin' in r else {})} for r in actual]}


def dependencies(kind):
    paths = [HERE / '原音准备.py', ROOT / 'tools/题目间隔.py',
             ROOT / '.github/actions/cet6-chalk-env/action.yml', ROOT / '.github/cet6-render-requirements.txt',
             ROOT / '.github/workflows/render-tem8-history.yml']
    if kind == 'exam':
        paths += [HERE / '考试视频.py', ROOT / '专八/听力/tools/听力视频.py',
                  ROOT / '专八/听力/tools/取字体.py', ROOT / '专八/真题/2025年 英语专业八级真题.pdf']
        bases = [ROOT / '四级/tools/fonts']
    else:
        paths += [HERE / '精听.py', HERE / '精听数据.py',
                  ROOT / '专八/听力/原文/tools/原音音轨.py', ROOT / '高考听力/精读/tools/本机预览.py']
        bases = [ROOT / '专八/tools', ROOT / '四级/tools', ROOT / '六级/tools',
                 ROOT / '中考/tools/画面核查', ROOT / 'tools/video']
        paths += [ROOT / 'tools/text_rules.py']
    extensions = {'.py', '.css', '.json', '.txt', '.woff', '.woff2', '.ttf', '.otf', '.svg'}
    # 仅跟踪仓库中的依赖；不将流水线临时JSON、缓存或pycache纳入指纹。
    tracked = subprocess.check_output(['git', 'ls-files', '-z', '--', *[relative(b) for b in bases]], cwd=ROOT).decode().split('\0')
    paths += [ROOT / n for n in tracked if n and Path(n).suffix.lower() in extensions]
    return sorted(set(paths))


def annotation_semantics(unit):
    """逐单元比较定稿，防插说明或并行审校把已修词句退回旧版本。"""
    return {'title':unit['title'],'names':unit.get('names',[]),
            'manual_splits':[{k:r[k] for k in ['en','at','zh']} for r in unit.get('manual_splits',[])],
            'sentences':[{key:sentence[key] for key in ['en','zh','w']}
                         for sentence in unit['sentences']]}


def validate_annotation_snapshot(final, mother):
    assert annotation_semantics(final)==annotation_semantics(mother), '精听输入未同步当前母稿英文/中文/词注/标题；须刷新或重新对齐，不能发布旧版'
    return hash_json(annotation_semantics(mother))


def payload(kind, ident):
    paths = input_paths(kind, ident)
    for p in paths:
        assert p.is_file(), '缺少输入：' + str(p)
        value = read(p)
        assert not value.get('待核'), '输入有待核项：' + str(p)
    dep = dependencies(kind)
    assert all(p.is_file() for p in dep), '渲染依赖未完整检出：' + str([relative(p) for p in dep if not p.is_file()][:10])
    result={'kind': kind, 'id': str(ident), 'inputs': {relative(p): sha(p) for p in paths},
            'render_sources': {relative(p): sha(p) for p in dep}}
    if kind=='intensive':
        mother_path=D/'译注草稿'/f'{str(ident)[:4]}.json'
        mother=next(u for u in read(mother_path)['units'] if u['id']==str(ident))
        result['annotation_source']={'file':relative(mother_path),
                                     'unit_sha256':validate_annotation_snapshot(read(paths[0]),mother)}
    return result


def candidate(kind, ident, work=None):
    p = payload(kind, ident)
    row = {'status': 'pending', 'payload_sha256': hash_json(p), **p,
           'evidence': '填写实际原卷/解析/录音及译注核对记录，不得提前批准。'}
    if work:
        row['shots'] = shots(work)
        assert row['shots'], '工作目录没有实际截图'
        row['evidence'] = '填写实际已看样片/新情况截图及机械关卡结果。'
    return row


def gate(kind, ident, work=None):
    p = payload(kind, ident); registry = read(REGISTRY)
    row = registry['entries'][kind + ':' + str(ident)]
    assert row.get('status') == 'approved' and len(row.get('evidence', '').strip()) >= 10, '缺少真实审核登记'
    assert row['payload_sha256'] == hash_json(p), '审核指纹已过期'
    assert row['inputs'] == p['inputs'] and row['render_sources'] == p['render_sources'], '审核所指源文件已经改变'
    if work is not None:
        # HTML指纹含本机绝对字体路径，可能改变PNG文件名；比较完整图片字节的多重集合。
        assert row.get('shots') and Counter(shots(work).values()) == Counter(row['shots'].values()), '当前完整截图与已审PNG不一致或尚未审截图'
    return row


def shots(work):
    work = Path(work)
    return {p.relative_to(work).as_posix(): sha(p) for p in sorted((work / 'shots').rglob('*.png'))}


def load_control(path=CONTROL):
    c = read(path)
    assert c['mode'] in ('sample', 'complete')
    assert c.get('stage', 'render') in ('render', 'review')
    c.setdefault('stage', 'render'); c.setdefault('exam', []); c.setdefault('intensive', [])
    assert c['exam'] or c['intensive'], '目标清单为空'
    c['exam'] = [str(x) for x in c['exam']]; c['intensive'] = [str(x) for x in c['intensive']]
    for kind in ['exam', 'intensive']:
        assert len(c[kind]) == len(set(c[kind])), '目标ID重复'
        for ident in c[kind]: validate_id(kind, ident)
    if c['mode'] == 'sample':
        assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,50}', c.get('sample_id', '')), '样片须有独立sample_id'
    else:
        full = read(D / '全批清单.json')
        assert full.get('status') == 'approved' and full.get('cancelled_years') == [2020]
        assert set(map(str, full['exam'])) == set(map(str, YEARS)) == set(c['exam']), '完整考试清单必须是实际15年'
        assert set(full['intensive']) == set(c['intensive']) and c['intensive'], '精听未覆盖已核定的完整单元清单'
        assert {int(i[:4]) for i in c['intensive']} == set(YEARS), '精听缺年份'
    for rid in c.get('collect_runs', []): assert re.fullmatch(r'\d+', str(rid))
    for tags in c.get('reuse_releases', {}).values():
        assert isinstance(tags, list) and all(re.fullmatch(r'[A-Za-z0-9_.-]+', t) for t in tags)
    return c


def matrix(c):
    result = []
    cached = None
    if c.get('stage') == 'render' and not c.get('force_render'):
        try: cached = release(CACHE_TAG)
        except subprocess.CalledProcessError: pass
    if c.get('render', True):
        for kind in ['exam', 'intensive']:
            selected = list(map(str, c.get('render_' + kind, c[kind])))
            assert set(selected).issubset(c[kind])
            for ident in selected:
                row = gate(kind, ident)
                if cached is not None and cached_ready(cached, kind, ident, row['payload_sha256']):
                    print(f'复用已核资产 {kind}/{ident}，不重新制作', file=__import__('sys').stderr)
                    continue
                result.append({'kind': kind, 'id': ident, 'year': int(ident[:4])})
    return result


def tag(c, kind):
    if c['mode'] == 'sample': return f'tem8-listening-{kind}-sample-{c["sample_id"]}'
    return f'tem8-listening-{kind}-2009-2024'


def asset(kind, ident, fingerprint=None, video_sha=None):
    validate_id(kind, ident)
    version = '-' + fingerprint[:16] if fingerprint else ''
    if video_sha: version += '-' + video_sha[:12]
    return f'tem8-{kind}-{ident}{version}.mp4'


def cache_evidence(kind, ident, fingerprint, video_sha=None):
    return asset(kind, ident, fingerprint, video_sha)[:-4] + '-evidence.zip'


def cache_pairs(rel, kind, ident, fp):
    have = {a['name']: a for a in rel['assets']}
    prefix = asset(kind, ident, fp)[:-4]
    pairs = [(n, n[:-4] + '-evidence.zip') for n in sorted(have, reverse=True)
             if n.startswith(prefix) and n.endswith('.mp4') and n[:-4] + '-evidence.zip' in have]
    plain = asset(kind, ident)
    if plain in have and plain[:-4] + '-evidence.zip' in have:
        pairs.append((plain, plain[:-4] + '-evidence.zip'))
    return pairs


def cached_ready(rel, kind, ident, fp):
    have = {a['name']: a for a in rel['assets']}
    for video, ev in cache_pairs(rel, kind, ident, fp):
        try:
            with tempfile.TemporaryDirectory(prefix='tem8cached_') as td:
                gh('release', 'download', rel['tag_name'], '-R', REPO, '-p', ev, '-D', td)
                p = Path(td) / ev
                assert have[ev].get('digest') == 'sha256:' + sha(p)
                with zipfile.ZipFile(p) as z:
                    assert z.testzip() is None
                    m = json.loads(z.read('meta.json'))
                    assert m['kind'] == kind and m['id'] == ident and m['approval_payload_sha256'] == fp
                    assert m['verification']['ok'] and not m['verification']['draft']
                    assert have[video].get('digest') == 'sha256:' + m['mp4_sha256'] and have[video]['size'] == m['mp4_bytes']
                    for n, digest in m['evidence'].items():
                        assert hashlib.sha256(z.read(n)).hexdigest() == digest
                    review = json.loads(z.read('evidence/审核登记.json'))
                    assert review['status'] == 'approved' and review['payload_sha256'] == fp and review.get('shots')
                    report = json.loads(z.read('evidence/工作记录/' + m['verification']['report']))
                    if kind == 'exam': assert report.get('问题') == [] and report.get('原音模式') is True and report['成品sha256'] == m['mp4_sha256']
                    else: assert report.get('ok') is True and report.get('draft') is False and report['sha256'] == m['mp4_sha256']
                    source = json.loads(z.read('evidence/工作记录/源音频准备.json'))
                    assert m['source_record'] == validate_source_preparation(source, int(ident[:4]), m['source_sha256'])
            return True
        except (AssertionError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError):
            continue
    return False


def zip_files(path, files, limit=LIMIT):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    assert len(files) == len(set(n for n, _ in files)), 'ZIP文件名重复'
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for name, source in files:
            assert '..' not in Path(name).parts and not Path(name).is_absolute()
            zi = zipfile.ZipInfo(name, DATE); zi.compress_type = zipfile.ZIP_STORED; zi.external_attr = 0o644 << 16
            with Path(source).open('rb') as src, z.open(zi, 'w', force_zip64=True) as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
    assert path.stat().st_size <= limit, f'{path.name}超过1.8GiB'
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for info, (name, source) in zip(z.infolist(), files):
            assert info.filename == name and info.date_time == DATE and info.compress_type == zipfile.ZIP_STORED
            assert name.isascii() or info.flag_bits & 0x800
            h = hashlib.sha256()
            with z.open(info) as f:
                for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
            assert h.hexdigest() == sha(source)
    return {'file': path.name, 'sha256': sha(path), 'bytes': path.stat().st_size}


def ensure_release(release_tag, title, notes):
    found = subprocess.run(['gh', 'release', 'view', release_tag, '-R', REPO], capture_output=True)
    if found.returncode:
        branch = os.getenv('GITHUB_REF_NAME') or subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
        try: gh('release', 'create', release_tag, '-R', REPO, '--target', branch, '--title', title, '--notes', notes)
        except subprocess.CalledProcessError:
            # 并行叶任务可能同时初建存档；只在对方已经建成时接受，不吞掉真实权限错误。
            gh('release', 'view', release_tag, '-R', REPO)


def release(release_tag):
    return gh('api', f'repos/{REPO}/releases/tags/{release_tag}', json_output=True)


def upload(release_tag, path, label=None):
    path = Path(path); expected = sha(path)
    existing = next((a for a in release(release_tag)['assets'] if a['name'] == path.name), None)
    if existing and existing.get('digest') == 'sha256:' + expected and existing['size'] == path.stat().st_size:
        if label is not None and existing.get('label') != label:
            gh('api', '-X', 'PATCH', f'repos/{REPO}/releases/assets/{existing["id"]}', '-f', 'label=' + label)
        return
    argument = str(path) + ('#' + label if label is not None else '')
    gh('release', 'upload', release_tag, argument, '-R', REPO, '--clobber')


def evidence_files(work):
    work = Path(work)
    return [(p.relative_to(work).as_posix(), p) for p in sorted(work.rglob('*.json'))
            if p.is_file() and not any(x in p.parts for x in ['.git', '__pycache__'])]


def review_bundle(kind, ident, work, out):
    gate(kind, ident); work, out = Path(work), Path(out); out.mkdir(parents=True, exist_ok=True)
    row = candidate(kind, ident, work); dump(out / '审核候选.json', row)
    files = [('审核候选.json', out / '审核候选.json')]
    files += [('工作记录/' + n, p) for n, p in evidence_files(work)]
    files += [(n, work / n) for n in row['shots']]
    for p in input_paths(kind, ident): files.append(('实际输入/' + p.name, p))
    archive = out / f'TEM8-review-{kind}-{ident}-{row["payload_sha256"][:16]}.zip'
    zip_files(archive, files)
    ensure_release(REVIEW_TAG, '专八历年听力待审截图与机械核验', '本页是待审截图，不是正式成品。审核通过并登记后才允许编码发布。')
    upload(REVIEW_TAG, archive)
    print(str(archive))


def stage(kind, ident, work, out):
    row = gate(kind, ident, work); work, out = Path(work), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    payload_sha = row['payload_sha256']
    if kind == 'exam':
        paper = read(input_paths(kind, ident)[0]); name = paper.get('filename') or f'{ident}年 专八听力 考试.mp4'
        report_path = work / '核验/核查报告.json'; report = read(report_path)
        assert report.get('问题') == [] and report.get('原音模式') is True
        expected = report['成品sha256']; source_sha = read(work / '核验/原音来源核验.json')['sha256']
    else:
        original_meta = read(work / 'meta.json'); report_path = work / 'verification.json'; report = read(report_path)
        assert original_meta['kind'] == 'text' and original_meta['id'] == ident
        assert report.get('ok') is True and report.get('draft') is False
        name = original_meta['mp4']; expected = original_meta['mp4_sha256']; source_sha = original_meta['原音_sha256']
    p = work / name
    source_record = validate_source_preparation(read(work / '源音频准备.json'), int(ident[:4]), source_sha)
    assert Path(name).name == name, '中文成品名必须是单个文件名'
    assert p.resolve().is_relative_to(work.resolve()) and p.is_file() and sha(p) == expected
    with p.open('rb') as f: assert f.read(8)[4:] == b'ftyp', '成品不是MP4'
    assert p.stat().st_size < LIMIT - (1 << 20), '单视频过大，不能按约定安全分包'
    assert not name.startswith('技术预览_') and name.endswith('.mp4')
    dest = out / asset(kind, ident)
    if dest.exists(): dest.unlink()
    try: os.link(p, dest)
    except OSError: shutil.copyfile(p, dest)
    ev = out / 'evidence'; ev.mkdir(exist_ok=True)
    for n, src in evidence_files(work):
        target = ev / '工作记录' / n; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src, target)
    for src in input_paths(kind, ident):
        target = ev / '实际输入' / src.name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src, target)
    dump(ev / '审核登记.json', row)
    for n in shots(work):
        target = ev / '已审截图' / n
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(work / n, target)
    meta = {'schema': 1, 'id': ident, 'year': int(ident[:4]), 'kind': kind, 'mp4': dest.name,
            'label': name, 'mp4_bytes': dest.stat().st_size, 'mp4_sha256': expected,
            'source_sha256': source_sha, 'source_record': source_record, 'approval_payload_sha256': payload_sha,
            'source_commit': os.getenv('GITHUB_SHA'), 'run_id': os.getenv('GITHUB_RUN_ID'),
            'verification': {'ok': True, 'draft': False, 'report': report_path.relative_to(work).as_posix()},
            'evidence': {p.relative_to(out).as_posix(): sha(p) for p in sorted(ev.rglob('*')) if p.is_file()}}
    dump(out / 'meta.json', meta)
    validate_stage(out, kind, ident, payload_sha)
    return meta


def validate_stage(folder, kind, ident, fingerprint):
    folder = Path(folder); m = read(folder / 'meta.json')
    assert m['schema'] == 1 and m['kind'] == kind and m['id'] == str(ident)
    assert m['approval_payload_sha256'] == fingerprint and m['verification'] == {**m['verification'], 'ok': True, 'draft': False}
    assert Path(m['mp4']).name == m['mp4'] and m['mp4'] == asset(kind, ident)
    p = folder / m['mp4']
    assert p.is_file() and p.stat().st_size == m['mp4_bytes'] and sha(p) == m['mp4_sha256']
    assert m['evidence'] and all((folder / n).resolve().is_relative_to(folder.resolve()) and sha(folder / n) == digest for n, digest in m['evidence'].items())
    registry = read(folder / 'evidence/审核登记.json')
    assert registry['status'] == 'approved' and registry['payload_sha256'] == fingerprint and registry.get('shots')
    report_path = folder / 'evidence/工作记录' / m['verification']['report']
    assert report_path.resolve().is_relative_to(folder.resolve())
    r = read(report_path)
    assert (r.get('问题') == [] and r.get('原音模式') is True and r['成品sha256'] == m['mp4_sha256']) if kind == 'exam' else (r.get('ok') is True and r.get('draft') is False and r['sha256'] == m['mp4_sha256'])
    source = read(folder / 'evidence/工作记录/源音频准备.json')
    assert m['source_record'] == validate_source_preparation(source, int(str(ident)[:4]), m['source_sha256'])
    return m


def store_stage(folder):
    folder = Path(folder); m = read(folder / 'meta.json'); fp = m['approval_payload_sha256']
    validate_stage(folder, m['kind'], m['id'], fp)
    ensure_release(CACHE_TAG, '专八历年听力已核验成品与来源存档', '按输入指纹保存已通过的独立视频与核验资料；完整正式发布见考试/精听专用Release。不是全批完成声明。')
    versioned = folder / asset(m['kind'], m['id'], fp, m['mp4_sha256'])
    if versioned.exists(): versioned.unlink()
    try: os.link(folder / m['mp4'], versioned)
    except OSError: shutil.copyfile(folder / m['mp4'], versioned)
    evzip = folder / cache_evidence(m['kind'], m['id'], fp, m['mp4_sha256'])
    entries = [('meta.json', folder / 'meta.json')] + [(n, folder / n) for n in m['evidence']]
    zip_files(evzip, entries)
    upload(CACHE_TAG, versioned, m['label']); upload(CACHE_TAG, evzip)


def unpack_evidence(path, target):
    target = Path(target); target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for i in z.infolist():
            p = target / i.filename
            assert not Path(i.filename).is_absolute() and '..' not in Path(i.filename).parts and p.resolve().is_relative_to(target.resolve())
            if i.is_dir(): p.mkdir(parents=True, exist_ok=True)
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                with z.open(i) as src, p.open('wb') as dst: shutil.copyfileobj(src, dst, 1 << 20)


def recover(c, art):
    art = Path(art); art.mkdir(parents=True, exist_ok=True)
    for rid in c.get('collect_runs', []):
        all_art = gh('api', f'repos/{REPO}/actions/runs/{rid}/artifacts?per_page=100', json_output=True)['artifacts']
        for a in all_art:
            if a['expired'] or not a['name'].startswith('tem8h-'): continue
            dest = art / ('run-' + str(rid)) / a['name']
            if not dest.exists(): gh('run', 'download', str(rid), '-R', REPO, '-n', a['name'], '-D', dest)
    for kind in ['exam', 'intensive']:
        for ident in c[kind]:
            row = gate(kind, ident); fp = row['payload_sha256']
            if find_stage(art, kind, ident, fp, required=False): continue
            for release_tag in [CACHE_TAG, *c.get('reuse_releases', {}).get(kind, [])]:
                try:
                    rel = release(release_tag)
                    pairs = cache_pairs(rel, kind, ident, fp)
                    if not pairs: continue
                    recovered = False
                    for video_name, evidence_name in pairs:
                        dest = art / ('release-' + release_tag) / f'tem8h-{kind}-{ident}'; dest.mkdir(parents=True, exist_ok=True)
                        gh('release', 'download', release_tag, '-R', REPO, '-p', evidence_name, '-p', video_name, '-D', dest, '--clobber')
                        unpack_evidence(dest / evidence_name, dest)
                        m = read(dest / 'meta.json')
                        if m['approval_payload_sha256'] != fp: continue
                        (dest / video_name).replace(dest / m['mp4'])
                        validate_stage(dest, kind, ident, fp); recovered = True; break
                    if recovered: break
                except (subprocess.CalledProcessError, AssertionError, KeyError, FileNotFoundError) as e:
                    print(f'无法复用 {release_tag}/{kind}/{ident}: {e}', flush=True)


def find_stage(art, kind, ident, fp, required=True):
    errors = []
    for p in sorted(Path(art).rglob('meta.json')):
        try:
            m = read(p)
            if m.get('schema') != 1 or m.get('kind') != kind or m.get('id') != ident: continue
            validate_stage(p.parent, kind, ident, fp)
            return p.parent
        except (AssertionError, KeyError, FileNotFoundError, json.JSONDecodeError) as e: errors.append(str(e))
    assert not required, f'缺少当前审核指纹的成功结果：{kind}/{ident}；{errors[:2]}'


def groups(rows):
    result, current, size = [], [], 0
    for row in rows:
        assert row['mp4_bytes'] < LIMIT - (1 << 20)
        if current and size + row['mp4_bytes'] >= LIMIT - (1 << 20):
            result.append(current); current = []; size = 0
        current.append(row); size += row['mp4_bytes']
    if current: result.append(current)
    return result


def verify_release_digest(release_tag, expected):
    have = {a['name']: a for a in release(release_tag)['assets']}
    for name, digest, size, label in expected:
        a = have[name]
        assert a.get('digest') == 'sha256:' + digest and a['size'] == size, '服务器资产不匹配：' + name
        if label is not None: assert a.get('label') == label


def publish(c, art, out):
    assert c['stage'] == 'render', '待审阶段不能发布正式MP4'
    art, out = Path(art), Path(out); out.mkdir(parents=True, exist_ok=True)
    recover(c, art)
    # 先一次性收齐两种目标并验证，任何缺项不开始更新任何正式Release。
    complete = {}
    for kind in ['exam', 'intensive']:
        rows = []
        order = {ident: n for n, ident in enumerate(c[kind])}
        for ident in sorted(c[kind], key=lambda x: (-int(x[:4]), order[x])):
            fp = gate(kind, ident)['payload_sha256']; folder = find_stage(art, kind, ident, fp)
            rows.append((folder, validate_stage(folder, kind, ident, fp)))
        complete[kind] = rows
    for kind, data in complete.items():
        if not data: continue
        target = out / kind; target.mkdir(exist_ok=True); release_tag = tag(c, kind); planned = []
        title = ('专八听力考试' if kind == 'exam' else '专八听力原声精听（水墨主题）')
        title += '｜样片 ' + c['sample_id'] if c['mode'] == 'sample' else '｜2009—2024实际15年'
        for folder, m in data:
            dest = target / m['mp4']
            if dest.exists(): dest.unlink()
            try: os.link(folder / m['mp4'], dest)
            except OSError: shutil.copyfile(folder / m['mp4'], dest)
            evidence = target / (m['mp4'][:-4] + '-evidence.zip')
            zip_files(evidence, [('meta.json', folder / 'meta.json')] + [(n, folder / n) for n in m['evidence']])
            planned.append({'meta': m, 'video': dest, 'evidence': evidence})
        notes = ('本页为独立样片，仅含本次试跑单元，不代表全批完成。\n\n' if c['mode'] == 'sample' else '2009—2024实际考试材料；2020因疫情取消考试，没有虚构2020试卷。\n\n')
        notes += '考试沿用2025白底黑字规格；精听沿用专八阅读书卷水墨主题。原声不增益、不改采样率或声道，仅执行核定音乐剪切；精听另压缩经确认的长纯静音。原文/解析核对、截图登记和成品核验均随来源包保存。\n\n'
        notes += '单个MP4使用ASCII资产名，中文名见标签与包内文件名。下载中文ZIP分包即可按原中文名使用。\n\n'
        notes += '|资产|中文文件名|字节|\n|---|---|---:|\n' + ''.join(f'|{m["mp4"]}|{m["label"]}|{m["mp4_bytes"]}|\n' for _, m in data)
        notes_file = target / 'notes.md'; notes_file.write_text(notes, 'utf-8')
        manifest = {'mode': c['mode'], 'tag': release_tag, 'source_commit': os.getenv('GITHUB_SHA'), 'videos': [m for _, m in data]}
        dump(target / 'TEM8-manifest.json', manifest)
        mapping = target / 'TEM8-filenames.txt'
        mapping.write_text('资产名\t中文文件名\tSHA256\t字节\n' + ''.join(f'{m["mp4"]}\t{m["label"]}\t{m["mp4_sha256"]}\t{m["mp4_bytes"]}\n' for _, m in data), 'utf-8')
        archives = []
        folder_by_id = {m['id']: folder for folder, m in data}
        for i, part in enumerate(groups([m for _, m in data]), 1):
            zname = f'TEM8-listening-{kind}-{c["sample_id"] if c["mode"] == "sample" else "2009-2024"}-part{i:02d}.zip'
            files = [(('专八听力考试/' if kind == 'exam' else '专八听力精听/') + m['label'], folder_by_id[m['id']] / m['mp4']) for m in part]
            archives.append((target / zname, zip_files(target / zname, files)))
        all_files = [(r['video'], r['meta']['label']) for r in planned] + [(r['evidence'], None) for r in planned]
        all_files += [(target / 'TEM8-manifest.json', None), (mapping, None)] + [(p, None) for p, _ in archives]
        sums = target / 'SHA256SUMS'
        sums.write_text(''.join(f'{sha(p)}  {p.name}\n' for p, _ in all_files), 'utf-8')
        all_files.append((sums, None))
        ensure_release(release_tag, title, notes)
        for p, label in all_files: upload(release_tag, p, label)
        gh('release', 'edit', release_tag, '-R', REPO, '--title', title, '--notes-file', notes_file)
        verify_release_digest(release_tag, [(p.name, sha(p), p.stat().st_size, label) for p, label in all_files])
        # 正式包回下载后逐成员核SHA、CRC、中文名、UTF8、顺序和固定日期。
        for local, zrow in archives:
            with tempfile.TemporaryDirectory(prefix='tem8download_') as td:
                gh('release', 'download', release_tag, '-R', REPO, '-p', local.name, '-D', td)
                back = Path(td) / local.name
                assert sha(back) == zrow['sha256']
                with zipfile.ZipFile(local) as expected, zipfile.ZipFile(back) as actual:
                    assert actual.testzip() is None
                    assert [(i.filename, i.CRC, i.file_size, i.flag_bits, i.date_time, i.compress_type) for i in actual.infolist()] == [(i.filename, i.CRC, i.file_size, i.flag_bits, i.date_time, i.compress_type) for i in expected.infolist()]
                    for n in actual.namelist():
                        h = hashlib.sha256()
                        with actual.open(n) as f:
                            for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
                        member = next(m for _, m in data if n.endswith('/' + m['label']))
                        assert h.hexdigest() == member['mp4_sha256']
        dump(target / '发布回下载核验.json', {'tag': release_tag, 'mode': c['mode'], 'videos': len(data), 'archives': [r for _, r in archives], 'server_digest': True, 'download_sha_crc_utf8': True})
        upload(release_tag, target / '发布回下载核验.json')
        print(f'{release_tag}: {len(data)}成品、{len(archives)}分包，回下载核验通过', flush=True)


def cli():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='cmd', required=True)
    for name in ['candidate', 'gate', 'review', 'stage']:
        q = sub.add_parser(name); q.add_argument('kind', choices=['exam', 'intensive']); q.add_argument('id')
        q.add_argument('--work', type=Path); q.add_argument('--out', type=Path); q.add_argument('--record', type=Path)
    sub.add_parser('--自检')
    q = sub.add_parser('matrix'); q.add_argument('--control', type=Path, default=CONTROL)
    q = sub.add_parser('store'); q.add_argument('folder', type=Path)
    q = sub.add_parser('publish'); q.add_argument('--control', type=Path, default=CONTROL); q.add_argument('--art', type=Path, required=True); q.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.cmd == 'candidate': print(json.dumps(candidate(a.kind, a.id, a.work), ensure_ascii=False, indent=2))
    elif a.cmd == 'gate':
        row = gate(a.kind, a.id, a.work)
        if a.record: dump(a.record, row)
        print(json.dumps({'approved':True,'kind':a.kind,'id':a.id,'payload_sha256':row['payload_sha256'],'inputs':len(row['inputs']),'shots':len(row.get('shots',{}))},ensure_ascii=False))
    elif a.cmd == '--自检': selftest()
    elif a.cmd == 'matrix': print(json.dumps(matrix(load_control(a.control))))
    elif a.cmd == 'review': assert a.work and a.out; review_bundle(a.kind, a.id, a.work, a.out)
    elif a.cmd == 'stage': assert a.work and a.out; stage(a.kind, a.id, a.work, a.out)
    elif a.cmd == 'store': store_stage(a.folder)
    elif a.cmd == 'publish': publish(load_control(a.control), a.art, a.out)


def selftest():
    """只验证发布关卡；不生成媒体、不访问GitHub。"""
    with tempfile.TemporaryDirectory(prefix='tem8publish_test_') as t:
        t = Path(t); a = t / 'a.mp4'; a.write_bytes(b'\x00\x00\x00\x20ftyp' + b'a' * 8192)
        b = t / 'b.mp4'; b.write_bytes(b'\x00\x00\x00\x20ftyp' + b'b' * 4096)
        files = [('专八听力考试/2009年 专八听力 考试.mp4', a), ('专八听力考试/2010年 专八听力 考试.mp4', b)]
        zip_files(t / 'good.zip', files)
        def rejected(fn, label):
            try: fn()
            except (AssertionError, KeyError, FileNotFoundError): return
            raise AssertionError('负例未拦：' + label)
        import copy
        unit={'title':'正文','names':[],'sentences':[{'en':'Good morning.','zh':'早上好。','w':[{'h':'morning','sp':[[5,12]]}]}]}
        assert validate_annotation_snapshot(copy.deepcopy(unit),unit)==hash_json(annotation_semantics(unit))
        changed=copy.deepcopy(unit);changed['sentences'][0]['en']='Good evening.'
        rejected(lambda: validate_annotation_snapshot(unit,changed),'母稿已改英文而输入退回旧稿')
        changed=copy.deepcopy(unit);changed['sentences'][0]['w'][0]['h']='evening'
        rejected(lambda: validate_annotation_snapshot(unit,changed),'母稿词注修正未同步')
        changed=copy.deepcopy(unit);changed['manual_splits']=[{'en':'Good morning.','at':'morning','zh':['早上','好。']}]
        rejected(lambda: validate_annotation_snapshot(unit,changed),'已审人工分屏只留侧表而最终输入丢失')
        same=copy.deepcopy(changed)
        assert validate_annotation_snapshot(same,changed)==hash_json(annotation_semantics(changed))
        def test_prep(year):
            rows = [{**r, 'audio':{'sample_rate':44100,'channels':2}} for r in selected_sources(year)]
            prep = {'year':year,'canonical':{'sha256':'7'*64,'sample_rate':44100,'channels':2},
                    'source_entries':rows,'intro_trim':{'applied':False},'archive_verified_here':False,
                    'archive_sha256':'919d6009b39286e2aadc8cc5eed9d4b15cc207be9f6bd3a3b7852a5be1065925',
                    'source_release':'tem8-listening-raw','source_asset':'default.zip'}
            if year == 2022:
                prep.update(archive_sha256=None,source_release='tem8-listening-raw-supplement',source_asset=rows[0]['file'],
                            source_supplement_sha256=rows[0]['sha256'],source_origin=rows[0]['origin'],
                            source_supplement_registration_sha256=sha(D / '核验/2022-补充音源.json'))
            return prep
        supplemental = test_prep(2022); validate_source_preparation(supplemental,2022,'7'*64)
        supplemental['archive_sha256']='919d6009b39286e2aadc8cc5eed9d4b15cc207be9f6bd3a3b7852a5be1065925'
        rejected(lambda: validate_source_preparation(supplemental,2022,'7'*64), '补充源冒充原ZIP来源')
        supplemental = test_prep(2022); supplemental['source_entries'][0]['sha256']='0'*64
        rejected(lambda: validate_source_preparation(supplemental,2022,'7'*64), '2022回抓错误原音')
        rejected(lambda: zip_files(t / 'bad.zip', [('../bad.mp4', a)]), 'ZIP路径穿越')
        rejected(lambda: zip_files(t / 'bad.zip', [files[0], files[0]]), '重复名称')
        rejected(lambda: zip_files(t / 'huge.zip', files, limit=20), '超体积')
        stage_dir = t / 'stage'; (stage_dir / 'evidence/工作记录/核验').mkdir(parents=True)
        video = stage_dir / asset('exam', '2009'); shutil.copyfile(a, video); fp = '1' * 64
        dump(stage_dir / 'evidence/审核登记.json', {'status':'approved','payload_sha256':fp,'shots':{'x.png':'2'*64}})
        report = stage_dir / 'evidence/工作记录/核验/核查报告.json'
        dump(report, {'问题':[],'原音模式':True,'成品sha256':sha(video)})
        prep = test_prep(2009); dump(stage_dir / 'evidence/工作记录/源音频准备.json', prep)
        m = {'schema':1,'kind':'exam','id':'2009','approval_payload_sha256':fp,
             'mp4':video.name,'mp4_sha256':sha(video),'mp4_bytes':video.stat().st_size,
             'source_sha256':'7'*64,'source_record':validate_source_preparation(prep,2009,'7'*64),
             'verification':{'ok':True,'draft':False,'report':'核验/核查报告.json'},
             'evidence':{p.relative_to(stage_dir).as_posix():sha(p) for p in stage_dir.rglob('*.json')}}
        dump(stage_dir / 'meta.json', m); validate_stage(stage_dir, 'exam', '2009', fp)
        rejected(lambda: validate_stage(stage_dir, 'exam', '2009', '3' * 64), '审核过期')
        video.write_bytes(b'broken')
        rejected(lambda: validate_stage(stage_dir, 'exam', '2009', fp), '成品损坏')
        shutil.copyfile(a, video); r = read(report); r['问题'] = ['坏画面']; dump(report, r)
        m['evidence'][report.relative_to(stage_dir).as_posix()] = sha(report); dump(stage_dir / 'meta.json', m)
        rejected(lambda: validate_stage(stage_dir, 'exam', '2009', fp), '成品报告失败')
        rejected(lambda: find_stage(t / 'empty', 'exam', '2009', fp), '缺成品')
        assert len(groups([{'mp4_bytes':LIMIT//2},{'mp4_bytes':LIMIT//2}])) == 2
        assert tag({'mode':'sample','sample_id':'x'},'exam') != tag({'mode':'complete'},'exam')
    print('发布自检通过：正常包/成品核验＋路径、重名、体积、过期、损坏、失败报告、缺项及样片隔离。')


if __name__ == '__main__':
    if len(__import__('sys').argv) == 2 and __import__('sys').argv[1] == '--自检': selftest()
    else: cli()
