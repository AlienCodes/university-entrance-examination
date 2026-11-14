"""完整15年精听的独立续收、组装缓存和正式发布；45个子段仅作为来源。

不修改子段gate，不把整年伪装成子段，不生成或重新编码子段。
组装/独立核验由整套精听.py执行；本程序只接受它已核验的完整年度输出。
"""
from __future__ import annotations

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
spec = importlib.util.spec_from_file_location('tem8_full_pub_helpers', HERE / '发布汇集.py')
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)
ROOT, D = pub.ROOT, pub.D
YEARS = list(pub.YEARS)
BRANCH = 'codex/tem8-listening-2009-2024'
REPOSITORY = 'AlienCodes/university-entrance-examination'
CONTROL = ROOT / '.github/tem8-listening-intensive-full.json'
CACHE_TAG = 'tem8-listening-intensive-full-cache-2009-2024'
FINAL_TAG = 'tem8-listening-intensive-2009-2024'
WORKFLOW = ROOT / '.github/workflows/assemble-tem8-intensive-full.yml'
KIND = 'intensive_full'
sha, read, dump, hash_json = pub.sha, pub.read, pub.dump, pub.hash_json


def need(ok, message):
    if not ok:
        raise ValueError(message)


def hexsha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def year_id(value):
    text = str(value)
    need(text in set(map(str, YEARS)), '仅接受实际15年，不存在2020年或子段交付ID')
    return text


def part_ids(year):
    y = year_id(year)
    return [y + '-' + suffix for suffix in ['A', 'B1', 'B2']]


def label(year):
    return f'{year_id(year)}年 专八听力 精听.mp4'


def asset(year, fingerprint=None, video_sha=None):
    suffix = '-' + fingerprint[:16] if fingerprint else ''
    if video_sha:
        suffix += '-' + video_sha[:12]
    return f'tem8-intensive-full-{year_id(year)}{suffix}.mp4'


def evidence_asset(year, fingerprint=None, video_sha=None):
    return asset(year, fingerprint, video_sha)[:-4] + '-evidence.zip'


def branch_guard():
    branch = os.getenv('GITHUB_REF_NAME') or subprocess.check_output(
        ['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
    need(branch == BRANCH, '整套精听只允许在指定工作分支发布')
    need(os.getenv('GITHUB_REPOSITORY', REPOSITORY) == REPOSITORY and pub.REPO == REPOSITORY,
         '整套精听发布仓库不匹配')


def load_control(path=CONTROL):
    c = read(path)
    need(c.get('mode') == 'complete_intensive_full', '整套精听发布必须使用complete_intensive_full模式')
    need(isinstance(c.get('years'), list), '必须列出完整15个年份')
    years = [year_id(y) for y in c['years']]
    need(len(years) == len(set(years)) == 15 and set(years) == set(map(str, YEARS)),
         '整套精听目标必须完整且仅有实际15年')
    need(not c.get('exam') and not c.get('intensive'), '整套控制不接受考试或45子段作为最终目标')
    c['years'] = years
    c.setdefault('assemble', True)
    need(type(c['assemble']) is bool, 'assemble必须是布尔值')
    if 'assemble_years' in c:
        need(isinstance(c['assemble_years'], list), '重试组装年份须为列表')
        selected = [year_id(y) for y in c['assemble_years']]
        need(len(selected) == len(set(selected)) and set(selected) <= set(years), '重试组装年份重复或越界')
        c['assemble_years'] = selected
    need(isinstance(c.get('collect_runs', []), list), '整套artifact运行号须为列表')
    for rid in c.get('collect_runs', []):
        need(re.fullmatch('[0-9]+', str(rid)) is not None, '无效整套artifact运行号')
    need(isinstance(c.get('reuse_child_releases', []), list), '子段复用Release须为列表')
    for tag in c.get('reuse_child_releases', []):
        need(isinstance(tag, str) and re.fullmatch('[A-Za-z0-9_.-]+', tag) is not None, '无效子段Release标签')
    return c


def assembly_payload(year):
    y = year_id(year)
    children = []
    for ident in part_ids(y):
        row = pub.gate('intensive', ident)
        children.append({'id': ident, 'approval_payload_sha256': row['payload_sha256']})
    # 发布文案、打包及工作流调度不改变音画。它们不纳入生成指纹，避免只改发布便重做视频。
    # 实际封装/PCM/AAC参数、canonical准备和导入的保护区间契约变化才撤销旧组装缓存。
    dependencies = [HERE / '整套精听.py', HERE / '原音准备.py', HERE / '精听数据.py']
    need(all(p.is_file() for p in dependencies), '整套组装依赖未完整检出')
    return {'schema': 1, 'assembly_contract': 'three-parts-current-gate-pcm-once-video-copy-v1',
            'kind': KIND, 'id': y, 'parts': children,
            'assembly_sources': {pub.relative(p): sha(p) for p in dependencies}}


def link_or_copy(source, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    try:
        os.link(source, dest)
    except OSError:
        shutil.copyfile(source, dest)
    return str(dest)


def safe_file(folder, relative):
    rel = Path(relative)
    path = Path(folder) / rel
    need(not rel.is_absolute() and '..' not in rel.parts and path.resolve().is_relative_to(Path(folder).resolve()),
         '证据路径越界')
    need(path.is_file(), '缺少真实文件：' + str(relative))
    return path


def collect_parts(c, year, out):
    """只从子段已核缓存续收当前三个stage；音源准备前执行，缺一即止。"""
    y = year_id(year)
    out = Path(out)
    need(not out.exists() or not any(out.iterdir()), '子段输出目录须为空，避免混入旧版本')
    out.mkdir(parents=True, exist_ok=True)
    expected = assembly_payload(y)
    with tempfile.TemporaryDirectory(prefix='tem8parts_', dir=out.parent) as td:
        child_control = {'stage': 'render', 'exam': [], 'intensive': part_ids(y), 'collect_runs': [],
                         'reuse_releases': {'intensive': c.get('reuse_child_releases', [])}}
        pub.recover(child_control, Path(td))
        rows = []
        for part in expected['parts']:
            ident, fp = part['id'], part['approval_payload_sha256']
            source = pub.find_stage(td, 'intensive', ident, fp)
            meta = pub.validate_stage(source, 'intensive', ident, fp)
            shutil.copytree(source, out / ident, copy_function=link_or_copy)
            pub.validate_stage(out / ident, 'intensive', ident, fp)
            rows.append({'id': ident, 'approval_payload_sha256': fp, 'mp4_sha256': meta['mp4_sha256'],
                         'meta_sha256': sha(out / ident / 'meta.json'), 'source_sha256': meta['source_sha256']})
    need(len({r['source_sha256'] for r in rows}) == 1, '三个子段原音不是同一年度canonical')
    dump(out / '子段收集核验.json', {'kind': KIND, 'id': y, 'parts': rows,
                                   'assembly_payload': expected, 'assembly_payload_sha256': hash_json(expected)})
    return rows


def child_snapshot(folder, ident, expected_fp):
    """完整来源包里不重复塞子段MP4；核其真实meta、已审图、源记录和独立成品报告。"""
    folder = Path(folder)
    m = read(folder / 'meta.json')
    need(m['schema'] == 1 and m['kind'] == 'intensive' and m['id'] == ident,
         '整套来源必须恰为当前年份的A/B1/B2精听子段')
    need(m['approval_payload_sha256'] == expected_fp and hexsha(m['mp4_sha256']), '子段审核已过期')
    need(m['verification'].get('ok') is True and m['verification'].get('draft') is False, '子段成品未核验通过')
    need(m['evidence'] and all(hexsha(s) and sha(safe_file(folder, n)) == s for n, s in m['evidence'].items()),
         '子段来源证据损坏')
    registry = read(safe_file(folder, 'evidence/审核登记.json'))
    need(registry['status'] == 'approved' and registry['payload_sha256'] == expected_fp and registry.get('shots'),
         '缺少子段真实截图审批')
    current = pub.gate('intensive', ident)
    need(registry['inputs'] == current['inputs'] and registry['render_sources'] == current['render_sources']
         and Counter(registry['shots'].values()) == Counter(current['shots'].values()), '子段不是当前完整截图审批')
    actual_shots = [sha(folder / n) for n in m['evidence']
                    if n.startswith('evidence/已审截图/') and n.endswith('.png')]
    need(Counter(actual_shots) == Counter(registry['shots'].values()), '来源包的实际PNG与完整审批不符')
    report = read(safe_file(folder, 'evidence/工作记录/' + m['verification']['report']))
    need(report.get('ok') is True and report.get('draft') is False and report['sha256'] == m['mp4_sha256'],
         '子段核验报告与视频摘要不一致')
    prep = read(safe_file(folder, 'evidence/工作记录/源音频准备.json'))
    need(m['source_record'] == pub.validate_source_preparation(prep, int(ident[:4]), m['source_sha256']),
         '子段原音来源登记不一致')
    return m


def validate_engine_meta(meta, report, year, children, child_meta_sha256):
    """逐项契约由组装器实际测量；不能用全局ok替代原声/无损画面证明。"""
    y = year_id(year)
    need(meta.get('kind') == KIND and str(meta.get('id')) == y and meta.get('year') == int(y), '组装输出不是本年整套')
    need(meta.get('label') == label(y), '整套中文文件名不符')
    need(meta.get('verification', {}).get('ok') is True and meta['verification'].get('draft') is False,
         '组装器未登记通过的真实独立核验')
    need([r['id'] for r in meta.get('parts', [])] == part_ids(y), '子段顺序须严格A→B1→B2且各一次')
    need([r['mp4_sha256'] for r in meta['parts']] == [r['mp4_sha256'] for r in children], '组装使用的子段视频不同')
    need([r.get('approval_payload_sha256') for r in meta['parts']]
         == [r['approval_payload_sha256'] for r in children], '组装使用的子段审批不同')
    need([r.get('source_sha256') for r in meta['parts']] == [r['source_sha256'] for r in children],
         '组装记录的各子段canonical不同')
    need([r.get('meta_sha256') for r in meta['parts']] == child_meta_sha256, '组装使用的子段meta与实际来源不同')
    need(meta['source_sha256'] == children[0]['source_sha256'] and len({r['source_sha256'] for r in children}) == 1,
         '整套源音canonical不符')
    need(report.get('ok') is True and report.get('draft') is False and report.get('sha256') == meta['mp4_sha256'],
         '整套独立核验未通过')
    need(report.get('source_sha256') == meta['source_sha256'], '独立核验没有绑定实际canonical原音')
    need(report.get('parts') == meta['parts'],
         '独立核验没有绑定实际三个子段视频')
    need(report.get('engine_sha256') == sha(HERE / '整套精听.py'), '独立核验由旧版组装器产生，不能盖上新指纹')
    need(meta.get('source_record') == children[0]['source_record'], '组装器原音登记与子段不同')
    need(report.get('parts_order') == part_ids(y), '整套核验未证实三部分完整顺序')
    for field in ['video_lossless', 'pcm_reconstruction_verified', 'audio_verified', 'av_sync_verified']:
        need(report.get(field) is True, '缺少实际独立核验：' + field)


def stage(year, parts, work, out):
    y = year_id(year)
    parts, work, out = Path(parts), Path(work), Path(out)
    need(not out.exists() or not any(out.iterdir()), '整套stage输出目录须为空')
    payload = assembly_payload(y)
    children = [pub.validate_stage(parts / p['id'], 'intensive', p['id'], p['approval_payload_sha256'])
                for p in payload['parts']]
    original = read(work / 'meta.json')
    verification = original['verification']
    report_path = safe_file(work, verification['report'])
    report = read(report_path)
    validate_engine_meta(original, report, y, children, [sha(parts / p['id'] / 'meta.json') for p in payload['parts']])
    video = safe_file(work, original['mp4'])
    need(sha(video) == original['mp4_sha256'] and video.stat().st_size == original['mp4_bytes'], '组装MP4损坏')
    out.mkdir(parents=True, exist_ok=True)
    link_or_copy(video, out / asset(y))
    assembly = out / 'evidence/assembly'
    for rel, path in pub.evidence_files(work):
        target = assembly / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    for p in payload['parts']:
        target = out / 'evidence/parts' / p['id']
        target.mkdir(parents=True)
        shutil.copyfile(parts / p['id'] / 'meta.json', target / 'meta.json')
        shutil.copytree(parts / p['id'] / 'evidence', target / 'evidence')
    dump(out / 'evidence/assembly-input.json', payload)
    records = [{k: child[k] for k in ['id', 'approval_payload_sha256', 'mp4_sha256', 'source_sha256']}
               for child in children]
    meta = {'schema': 1, 'kind': KIND, 'id': y, 'year': int(y), 'label': label(y), 'mp4': asset(y),
            'mp4_sha256': sha(video), 'mp4_bytes': video.stat().st_size,
            'source_sha256': original['source_sha256'], 'source_record': children[0]['source_record'],
            'assembly_payload_sha256': hash_json(payload), 'parts': records,
            'source_commit': os.getenv('GITHUB_SHA'), 'run_id': os.getenv('GITHUB_RUN_ID'),
            'verification': {'ok': True, 'draft': False, 'report': 'evidence/assembly/' + verification['report']},
            'evidence': {p.relative_to(out).as_posix(): sha(p) for p in sorted((out / 'evidence').rglob('*')) if p.is_file()}}
    dump(out / 'meta.json', meta)
    validate_stage(out, y, payload)
    return meta


def validate_stage(folder, year, payload=None, verify_video=True):
    y = year_id(year)
    folder = Path(folder)
    payload = payload or assembly_payload(y)
    m = read(folder / 'meta.json')
    need(m.get('schema') == 1 and m.get('kind') == KIND and m.get('id') == y and m.get('year') == int(y),
         '整套stage身份错误')
    need(m['mp4'] == asset(y) and m['label'] == label(y), '只允许整年ASCII资产名与规范中文名')
    need(m['assembly_payload_sha256'] == hash_json(payload), '整套组装指纹已过期')
    need(hexsha(m['mp4_sha256']) and type(m['mp4_bytes']) is int and 8 < m['mp4_bytes'] < pub.LIMIT - (1 << 20),
         '整套视频过大或摘要/大小不合法')
    if verify_video:
        video = safe_file(folder, m['mp4'])
        need(video.stat().st_size == m['mp4_bytes'] and sha(video) == m['mp4_sha256'], '整套视频损坏')
        with video.open('rb') as f:
            need(f.read(8)[4:] == b'ftyp', '整套视频不是MP4')
    need(m['evidence'] and all(hexsha(s) and sha(safe_file(folder, n)) == s for n, s in m['evidence'].items()),
         '整套核验证据损坏')
    need(read(safe_file(folder, 'evidence/assembly-input.json')) == payload, '整套来源依赖快照不符')
    child_meta = [child_snapshot(folder / 'evidence/parts' / p['id'], p['id'], p['approval_payload_sha256'])
                  for p in payload['parts']]
    expected_parts = [{k: child[k] for k in ['id', 'approval_payload_sha256', 'mp4_sha256', 'source_sha256']}
                      for child in child_meta]
    need(m['parts'] == expected_parts, '整套来源不是当前三子段各一次')
    engine = read(safe_file(folder, 'evidence/assembly/meta.json'))
    need(m['verification'].get('ok') is True and m['verification'].get('draft') is False, '整套未通过独立核验')
    report = read(safe_file(folder, m['verification']['report']))
    validate_engine_meta(engine, report, y, child_meta,
                         [sha(folder / 'evidence/parts' / p['id'] / 'meta.json') for p in payload['parts']])
    need(engine['mp4_sha256'] == m['mp4_sha256'] and engine['mp4_bytes'] == m['mp4_bytes'], '组装报告与stage视频不符')
    need(m['source_sha256'] == engine['source_sha256'] and m['source_record'] == child_meta[0]['source_record'],
         '整套来源被替换')
    return m


def cache_pairs(rel, year, fingerprint):
    have = {a['name']: a for a in rel['assets']}
    prefix = asset(year, fingerprint)[:-4] + '-'
    return [(n, n[:-4] + '-evidence.zip') for n in sorted(have, reverse=True)
            if n.startswith(prefix) and n.endswith('.mp4') and n[:-4] + '-evidence.zip' in have]


def cached_ready(rel, year, payload):
    have = {a['name']: a for a in rel['assets']}
    for video, evidence in cache_pairs(rel, year, hash_json(payload)):
        try:
            with tempfile.TemporaryDirectory(prefix='tem8fullcheck_') as td:
                pub.gh('release', 'download', CACHE_TAG, '-R', pub.REPO, '-p', evidence, '-D', td)
                ev = Path(td) / evidence
                need(have[evidence].get('digest') == 'sha256:' + sha(ev), '整套缓存证据服务器SHA不符')
                pub.unpack_evidence(ev, td)
                m = validate_stage(td, year, payload, verify_video=False)
                need(have[video].get('digest') == 'sha256:' + m['mp4_sha256'] and have[video]['size'] == m['mp4_bytes'],
                     '整套缓存MP4服务器SHA或体积不符')
            return True
        except (ValueError, AssertionError, KeyError, FileNotFoundError, zipfile.BadZipFile, subprocess.CalledProcessError):
            continue
    return False


def matrix(c):
    if not c['assemble']:
        return []
    try:
        rel = pub.release(CACHE_TAG)
    except subprocess.CalledProcessError:
        rel = None
    rows = []
    for y in c.get('assemble_years', c['years']):
        payload = assembly_payload(y)
        if rel is not None and cached_ready(rel, y, payload):
            print(f'复用已核整套 {y}，不重复组装', file=__import__('sys').stderr)
            continue
        rows.append({'year': y})
    return rows


def store(folder):
    branch_guard()
    folder = Path(folder)
    m = read(folder / 'meta.json')
    validate_stage(folder, m['id'])
    fp = m['assembly_payload_sha256']
    pub.ensure_release(CACHE_TAG, '专八听力15年整套精听已核成品与来源缓存',
                       '按年度完整A→B1→B2组装；原子段、原声PCM、画面与成品独立核验随来源包保留。正式15套下载见独立精听Release。')
    video = folder / asset(m['id'], fp, m['mp4_sha256'])
    link_or_copy(folder / m['mp4'], video)
    evidence = folder / evidence_asset(m['id'], fp, m['mp4_sha256'])
    pub.zip_files(evidence, [('meta.json', folder / 'meta.json')] + [(n, folder / n) for n in m['evidence']])
    pub.upload(CACHE_TAG, video, m['label'])
    pub.upload(CACHE_TAG, evidence)
    pub.verify_release_digest(CACHE_TAG, [(video.name, sha(video), video.stat().st_size, m['label']),
                                          (evidence.name, sha(evidence), evidence.stat().st_size, None)])
    return m


def find_stage(art, year, payload=None, required=True):
    for path in sorted(Path(art).rglob('meta.json')):
        try:
            m = read(path)
            if m.get('kind') == KIND and m.get('id') == year_id(year):
                validate_stage(path.parent, year, payload)
                return path.parent
        except (ValueError, AssertionError, KeyError, FileNotFoundError, json.JSONDecodeError):
            continue
    need(not required, '缺少当前指纹的已核整套成品：' + year_id(year))


def recover(c, art):
    art = Path(art)
    art.mkdir(parents=True, exist_ok=True)
    for rid in c.get('collect_runs', []):
        artifacts = pub.gh('api', f'repos/{pub.REPO}/actions/runs/{rid}/artifacts?per_page=100', json_output=True)['artifacts']
        for a in artifacts:
            if a['expired'] or a['name'] not in {'tem8full-' + str(y) for y in YEARS}:
                continue
            dest = art / ('run-' + str(rid)) / a['name']
            if not dest.exists():
                pub.gh('run', 'download', str(rid), '-R', pub.REPO, '-n', a['name'], '-D', dest)
    rel = None
    for year in c['years']:
        payload = assembly_payload(year)
        if find_stage(art, year, payload, required=False):
            continue
        if rel is None:
            rel = pub.release(CACHE_TAG)
        for video, evidence in cache_pairs(rel, year, hash_json(payload)):
            dest = art / ('release-' + CACHE_TAG) / year
            dest.mkdir(parents=True, exist_ok=True)
            try:
                pub.gh('release', 'download', CACHE_TAG, '-R', pub.REPO, '-p', evidence, '-p', video, '-D', dest, '--clobber')
                pub.unpack_evidence(dest / evidence, dest)
                (dest / video).replace(dest / asset(year))
                validate_stage(dest, year, payload)
                break
            except (ValueError, AssertionError, KeyError, FileNotFoundError, zipfile.BadZipFile, subprocess.CalledProcessError) as e:
                print(f'不能复用整套缓存 {year}: {e}', flush=True)


def collect_complete(c, art):
    """在任何正式Release写操作前，强制15完整年度及每年全部三子段证据齐全。"""
    need(set(c['years']) == set(map(str, YEARS)) and len(c['years']) == 15, '正式精听必须是完整15年')
    rows = []
    for y in sorted(c['years'], reverse=True):
        payload = assembly_payload(y)
        folder = find_stage(art, y, payload)
        rows.append((folder, validate_stage(folder, y, payload)))
    need(len(rows) == 15 and len({m['year'] for _, m in rows}) == 15, '完整整套数量不符')
    need(len({p['id'] for _, m in rows for p in m['parts']}) == 45, '整套到子段来源映射不完整')
    return rows


def verify_download(local, back, members):
    need(sha(local) == sha(back), '正式ZIP回下载SHA不同')
    with zipfile.ZipFile(local) as expected, zipfile.ZipFile(back) as actual:
        need(actual.testzip() is None, '正式ZIP回下载CRC失败')
        fields = lambda z: [(i.filename, i.CRC, i.file_size, i.flag_bits, i.date_time, i.compress_type) for i in z.infolist()]
        need(fields(actual) == fields(expected), '正式ZIP回下载成员/顺序/UTF8/时间/压缩方式不同')
        need(set(actual.namelist()) <= set(members), 'ZIP含非完整年度成员')
        for info in actual.infolist():
            need(info.flag_bits & 0x800 and info.compress_type == zipfile.ZIP_STORED and info.date_time == pub.DATE,
                 '中文ZIP必须UTF8、不压缩且使用固定日期')
            h = hashlib.sha256()
            with actual.open(info) as src:
                for chunk in iter(lambda: src.read(1 << 20), b''):
                    h.update(chunk)
            need(h.hexdigest() == members[info.filename], 'ZIP内整套MP4摘要不符')


def publish(c, art, out):
    branch_guard()
    recover(c, art)
    rows = collect_complete(c, art)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    title = '专八听力整套精听｜2009—2024实际15年'
    notes = ('每年一个完整精听视频，共15套。每套按讲座A、采访B1、采访B2顺序组装；45个内部片段不是最终下载数量。\n\n'
             '沿用已审专八阅读书卷水墨主题及真实原声；画面无损拼接，声音从已核canonical PCM及保留区间重建后整套编码一次，逐项核验来源、帧/时间、声音及声画同步。\n\n'
             '2020年取消考试，未虚构该年试卷。2009—2015采用上传材料中的“新题型优化版”，不是当年未经改编的原始题型。'
             '2022使用补充完整音源。2014题源冲突题按已核定的不计分说明保留。\n\n'
             'MP4资产使用ASCII名称；下载中文ZIP分包后，每年为“YYYY年 专八听力 精听.mp4”。原始输入、三个子段来源与组装/独立核验记录随证据包存档。\n\n')
    notes += '|资产|中文文件名|字节|\n|---|---|---:|\n' + ''.join(
        f'|{m["mp4"]}|{m["label"]}|{m["mp4_bytes"]}|\n' for _, m in rows)
    notes_file = out / 'notes.md'
    notes_file.write_text(notes, 'utf-8')
    manifest = {'schema': 1, 'mode': c['mode'], 'kind': KIND, 'tag': FINAL_TAG,
                'delivery_videos': 15, 'internal_parts': 45, 'years': YEARS,
                'source_commit': os.getenv('GITHUB_SHA'), 'videos': [m for _, m in rows]}
    dump(out / 'TEM8-manifest.json', manifest)
    mapping = out / 'TEM8-filenames.txt'
    mapping.write_text('资产名\t中文文件名\tSHA256\t字节\n' + ''.join(
        f'{m["mp4"]}\t{m["label"]}\t{m["mp4_sha256"]}\t{m["mp4_bytes"]}\n' for _, m in rows), 'utf-8')
    files = []
    for folder, m in rows:
        video = out / m['mp4']
        link_or_copy(folder / m['mp4'], video)
        evidence = out / evidence_asset(m['id'])
        pub.zip_files(evidence, [('meta.json', folder / 'meta.json')] + [(n, folder / n) for n in m['evidence']])
        files += [(video, m['label']), (evidence, None)]
    folder_by_id = {m['id']: folder for folder, m in rows}
    archives = []
    for n, group in enumerate(pub.groups([m for _, m in rows]), 1):
        path = out / f'TEM8-listening-intensive-2009-2024-part{n:02d}.zip'
        entries = [('专八听力精听/' + m['label'], folder_by_id[m['id']] / m['mp4']) for m in group]
        archives.append((path, pub.zip_files(path, entries)))
    files += [(out / 'TEM8-manifest.json', None), (mapping, None)] + [(p, None) for p, _ in archives]
    sums = out / 'SHA256SUMS'
    sums.write_text(''.join(f'{sha(p)}  {p.name}\n' for p, _ in files), 'utf-8')
    files.append((sums, None))
    pub.ensure_release(FINAL_TAG, title, notes)
    for path, display in files:
        pub.upload(FINAL_TAG, path, display)
    pub.gh('release', 'edit', FINAL_TAG, '-R', pub.REPO, '--title', title, '--notes-file', notes_file)
    pub.verify_release_digest(FINAL_TAG, [(p.name, sha(p), p.stat().st_size, display) for p, display in files])
    members = {'专八听力精听/' + m['label']: m['mp4_sha256'] for _, m in rows}
    for local, _ in archives:
        with tempfile.TemporaryDirectory(prefix='tem8fullback_') as td:
            pub.gh('release', 'download', FINAL_TAG, '-R', pub.REPO, '-p', local.name, '-D', td)
            verify_download(local, Path(td) / local.name, members)
    report = out / 'TEM8-intensive-download-verification.json'
    dump(report, {'tag': FINAL_TAG, 'mode': c['mode'], 'kind': KIND, 'videos': 15, 'internal_parts': 45,
                  'years': YEARS, 'archives': [r for _, r in archives], 'server_digest': True,
                  'download_sha_crc_utf8_member_sha': True})
    pub.upload(FINAL_TAG, report)
    pub.verify_release_digest(FINAL_TAG, [(report.name, sha(report), report.stat().st_size, None)])
    print(f'{FINAL_TAG}: 15整套精听、{len(archives)}个中文分包，服务器与回下载核验通过', flush=True)


def cli():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--control', type=Path, default=CONTROL)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('matrix')
    q = sub.add_parser('collect'); q.add_argument('year'); q.add_argument('--out', type=Path, required=True)
    q = sub.add_parser('stage'); q.add_argument('year'); q.add_argument('--parts', type=Path, required=True)
    q.add_argument('--work', type=Path, required=True); q.add_argument('--out', type=Path, required=True)
    q = sub.add_parser('store'); q.add_argument('folder', type=Path)
    q = sub.add_parser('publish'); q.add_argument('--art', type=Path, required=True); q.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.command == 'stage':
        stage(a.year, a.parts, a.work, a.out)
    elif a.command == 'store':
        store(a.folder)
    else:
        c = load_control(a.control)
        if a.command == 'matrix':
            print(json.dumps(matrix(c)))
        elif a.command == 'collect':
            need(year_id(a.year) in c['years'], '目标年不在控制清单')
            collect_parts(c, a.year, a.out)
        elif a.command == 'publish':
            publish(c, a.art, a.out)


if __name__ == '__main__':
    cli()
