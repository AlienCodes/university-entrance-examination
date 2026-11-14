"""只读验收实际15整套精听Release；prepare绝不访问网络或声称成品已通过。

verify须在正式发布后显式调用。验证实际下载的15个完整来源包、当前45子段
门禁与producer、全部中文ZIP分包及每个成员；不修改Release或生成任何视频。
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
D = ROOT / '专八/听力/批量'
TAG = 'tem8-listening-intensive-2009-2024'
REPORT_ASSET = 'TEM8-intensive-download-verification.json'
YEARS = list(range(2009, 2020)) + list(range(2021, 2025))
IDS = [f'{y}-{s}' for y in YEARS for s in ('A', 'B1', 'B2')]
STRICT_CACHE = D / '核验/发布调度/精听45当前持久缓存严格核验.json'
FINAL_AUDIT = HERE / '正式Release独立回下载核验.json'


def need(value, why):
    if not value:
        raise ValueError(why)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    tmp.replace(path)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def hexsha(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def load_helpers():
    spec = importlib.util.spec_from_file_location('tem8_full_finalaudit_helpers', D / 'tools/整套精听发布.py')
    full = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(full)
    return full, full.pub


def validate_manifest(m, report):
    need(m['schema'] == 1 and m['kind'] == 'intensive_full' and m['mode'] == 'complete_intensive_full'
         and m['tag'] == TAG, '正式manifest模式/身份不符')
    need(m['delivery_videos'] == 15 and m['internal_parts'] == 45 and m['years'] == YEARS,
         '交付应为实际15年整套，45片段仅内部来源，2020不存在')
    videos = m['videos']
    need(len(videos) == 15 and [v['id'] for v in videos] == [str(y) for y in reversed(YEARS)],
         'manifest须按实际15年从新到旧排列且每年恰一次')
    children = []
    for v in videos:
        y = v['id']
        need(v['schema'] == 1 and v['kind'] == 'intensive_full' and v['year'] == int(y), '整套身份/年份错误')
        need(v['mp4'] == f'tem8-intensive-full-{y}.mp4' and v['label'] == f'{y}年 专八听力 精听.mp4',
             '整套资产名/中文名不符，不能交付子段')
        need(hexsha(v['mp4_sha256']) and type(v['mp4_bytes']) is int and v['mp4_bytes'] > 8,
             '整套视频摘要/字节不合法')
        expected = [f'{y}-{s}' for s in ('A', 'B1', 'B2')]
        need([p['id'] for p in v['parts']] == expected, '每年必须A→B1→B2，不能跨年、遗漏或换序')
        for p in v['parts']:
            need(all(hexsha(p[k]) for k in ('mp4_sha256', 'source_sha256', 'approval_payload_sha256')),
                 '子段来源摘要非法')
        need(v['verification']['ok'] is True and v['verification']['draft'] is False, '存在未通过/草稿整套')
        children += expected
    need(len(children) == len(set(children)) == 45 and set(children) == set(IDS), '45来源片段不唯一或错误归年')
    need(report['tag'] == TAG and report['mode'] == m['mode'] and report['kind'] == m['kind'], '发布报告身份不同')
    need(report['videos'] == 15 and report['internal_parts'] == 45 and report['years'] == YEARS,
         '发布报告数量/年份不符')
    need(report['server_digest'] is True and report['download_sha_crc_utf8_member_sha'] is True,
         '发布器尚未完成实际回下载核验')
    archives = report['archives']
    need(archives and [a['file'] for a in archives] ==
         [f'TEM8-listening-intensive-2009-2024-part{i:02d}.zip' for i in range(1, len(archives) + 1)],
         '正式分包缺失、重名或顺序错误')
    need(all(hexsha(a['sha256']) and type(a['bytes']) is int and a['bytes'] > 8 for a in archives),
         '正式分包摘要/大小非法')
    return videos


def asset_map(release):
    rows = release['assets']
    need(len(rows) == len({a['name'] for a in rows}), '服务器资产重名')
    for a in rows:
        need(a.get('state') == 'uploaded' and type(a['size']) is int and a['size'] > 0,
             '服务器含上传未完成/空资产')
        need(re.fullmatch(r'sha256:[0-9a-f]{64}', a.get('digest') or ''), '服务器缺少实际SHA256摘要')
    return {a['name']: a for a in rows}


def validate_inventory(assets, videos, archives, sums):
    names = {m['mp4'] for m in videos} | {m['mp4'][:-4] + '-evidence.zip' for m in videos}
    names |= {a['file'] for a in archives} | {'TEM8-manifest.json', 'TEM8-filenames.txt'}
    need(set(sums) == names, 'SHA256SUMS漏项/多项（report及SHA256SUMS本身除外）')
    need(set(assets) == names | {'SHA256SUMS', REPORT_ASSET}, '正式Release有缺失或异常额外资产')
    for name, digest in sums.items():
        need(hexsha(digest) and assets[name]['digest'] == 'sha256:' + digest, '服务器与SUMS摘要不同：' + name)
    for m in videos:
        a = assets[m['mp4']]
        need(a['digest'] == 'sha256:' + m['mp4_sha256'] and a['size'] == m['mp4_bytes']
             and a.get('label') == m['label'], '实际年度MP4与manifest摘要/字节/中文label不符')
    for a in archives:
        need(assets[a['file']]['size'] == a['bytes'] and sums[a['file']] == a['sha256'], '分包服务器字节/摘要不符')


def parse_sums(path):
    rows = []
    for line in path.read_text('utf-8').splitlines():
        digest, name = line.split('  ', 1)
        need(hexsha(digest) and name and Path(name).name == name, 'SUMS格式/路径非法')
        rows.append((name, digest))
    need(len(rows) == len(dict(rows)), 'SUMS重名')
    return dict(rows)


class Downloads:
    def __init__(self, assets, destination):
        self.assets, self.destination = assets, Path(destination)
        self.destination.mkdir(parents=True, exist_ok=True)

    def fetch(self, name):
        need(name in self.assets and Path(name).name == name, '下载资产不存在/路径非法')
        asset = self.assets[name]
        path = self.destination / name
        expected = asset['digest'].removeprefix('sha256:')
        if not (path.is_file() and path.stat().st_size == asset['size'] and sha(path) == expected):
            part = path.with_suffix(path.suffix + '.part')
            part.unlink(missing_ok=True)
            request = urllib.request.Request(asset['browser_download_url'], headers={'User-Agent': 'tem8-full-finalaudit'})
            with urllib.request.urlopen(request, timeout=120) as source, part.open('wb') as target:
                shutil.copyfileobj(source, target, length=1 << 20)
            need(part.stat().st_size == asset['size'] and sha(part) == expected, '真实下载服务器摘要/字节不符：' + name)
            part.replace(path)
        return path


def extract_evidence(path, folder):
    """逐文件安全提取；所有证据均绑定meta，拒绝隐藏文件/重名/链接。"""
    folder = Path(folder)
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        need(len(infos) == len({i.filename for i in infos}) and z.testzip() is None, '证据ZIP重名/CRC失败')
        meta = json.loads(z.read('meta.json'))
        need(set(z.namelist()) == {'meta.json'} | set(meta['evidence']), '证据ZIP缺项/异常附加文件')
        for info in infos:
            p = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            need(not p.is_absolute() and '..' not in p.parts and '\\' not in info.filename
                 and not info.is_dir() and not stat.S_ISLNK(mode), '证据ZIP路径/链接非法')
            target = folder.joinpath(*p.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as source, target.open('wb') as out:
                shutil.copyfileobj(source, out, length=1 << 20)
            if info.filename != 'meta.json':
                need(sha(target) == meta['evidence'][info.filename], '实际证据SHA不符：' + info.filename)
    return meta


def validate_cache_record(record, pub):
    need(record['status'] == 'pass' and record['strict_cache_count'] == 45 and record['current_cache_tag'] == pub.CACHE_TAG,
         '没有已完成的45当前持久缓存严格核验')
    rows = record['rows']
    need(len(rows) == len({r['id'] for r in rows}) == 45 and {r['id'] for r in rows} == set(IDS), '严格缓存审计缺年/重名')
    need(set(record['producer_manifest']) == set(IDS), 'producer登记未完整覆盖45来源')
    return {r['id']: r for r in rows}


def validate_stats(stats):
    need(stats['ok'] is True and stats['samples'] > 0 and stats['tested_active_seconds'] > 0, '音频测量未实际通过')
    values = [stats['snr_db'], stats['gain_db'], stats['max_1second_level_difference_db']]
    need(all(type(x) in (int, float) and math.isfinite(x) for x in values), '音频测量非有限数')
    need(stats['snr_db'] >= 30 and abs(stats['gain_db']) <= .05
         and 0 <= stats['max_1second_level_difference_db'] <= 1, '真实音频阈值不符，不能只信全局ok')


def validate_assembly_details(report, child_data):
    """复核已绑定真实测量报告的数值；这里不虚称重新解码了完整画面/音频。"""
    ids = [c['meta']['id'] for c in child_data]
    frames = [round(c['tm']['duration'] * 30) for c in child_data]
    need(all(abs(n / 30 - c['tm']['duration']) < 1e-8 for n, c in zip(frames, child_data)), '子段不是30fps整帧')
    sr, ch = child_data[0]['tm']['sample_rate'], child_data[0]['tm']['channels']
    need(all((c['tm']['sample_rate'], c['tm']['channels']) == (sr, ch) for c in child_data), '子段原格式不一致')
    packets = report['video_packets']
    need(packets['frames'] == packets['packet_count'] == sum(frames) and packets['pts_exact_30fps'] is True
         and packets['dts_contiguous'] is True and Fraction(packets['duration']) == Fraction(sum(frames), 30)
         and Fraction(packets['last_pts']) == Fraction(sum(frames) - 1, 30), '全视频帧数/PTS/DTS测量不同')
    vcl = report['video_vcl']
    need(len(vcl['parts']) == 3 and vcl['nal_count'] == sum(p['nal_count'] for p in vcl['parts'])
         and vcl['vcl_bytes'] > 0 and hexsha(vcl['sha256'])
         and all(p['nal_count'] > 0 and hexsha(p['sha256']) for p in vcl['parts'])
         and vcl['parameter_sets_sha256'] and all(hexsha(h) for h in vcl['parameter_sets_sha256']), '无损VCL证据不完整')
    pcm, audio = report['pcm'], report['audio']
    need((pcm['sample_rate'], pcm['channels']) == (audio['sample_rate'], audio['channels']) == (sr, ch), '整套改变原采样率/声道')
    need([p['id'] for p in pcm['parts']] == [p['id'] for p in audio['parts']] == ids, 'PCM/音频测量顺序错误')
    need(audio['thresholds'] == {'min_snr_db': 30.0, 'max_abs_gain_db': .05,
                                 'max_1second_level_difference_db': 1.0}, '原声质量阈值被改变')
    need(hexsha(pcm['pcm_sha256']) and hexsha(pcm['wav_sha256']), '重建PCM无摘要')
    validate_stats(audio['full'])
    need(audio['full']['samples'] == pcm['frames'] == audio['source_samples'], '整套测量样本数不同')
    need(0 <= audio['aac_padding_samples'] < 2048 and audio['decoded_samples'] - pcm['frames'] == audio['aac_padding_samples']
         and 0 <= audio['aac_padding_peak'] < .001 and abs(audio['audio_video_duration_difference_seconds']) < .05,
         'AAC补帧/静音/声画时长差异常')
    timing = audio['packet_timing']
    need(timing['packet_count'] > 0 and timing['continuous'] is True
         and Fraction(timing['native_time_base']) == Fraction(1, sr)
         and int(timing['first_packet_pts']) + timing['priming_skip_samples'] == timing['effective_first_sample_pts'] == 0,
         'AAC priming或接缝包时序异常')
    cursor, video_cursor = 0, 0
    for c, p, a, n, chapter in zip(child_data, pcm['parts'], audio['parts'], frames, report['chapters']):
        tm, ident = c['tm'], c['meta']['id']
        intervals = [[round(x * sr), round(y * sr)] for x, y in tm['kept_intervals']]
        body = sum(y - x for x, y in intervals)
        samples = round(tm['duration'] * sr)
        need(intervals and all(0 <= x < y for x, y in intervals)
             and all(y <= u for (_, y), (u, _) in zip(intervals, intervals[1:])), '原音区间错序/重叠')
        need(p['source_intervals_samples'] == intervals and p['frames'] == samples
             and p['start_sample'] == cursor and p['end_sample'] == cursor + samples
             and p['lead_samples'] == round(1.5 * sr) and p['body_samples'] == body
             and p['tail_samples'] == samples - p['lead_samples'] - body and p['tail_samples'] >= round(2.2 * sr) - 1
             and p['wav_sha256'] == tm['audio_sha256'] and hexsha(p['pcm_sha256']), '重建PCM不是已审原样子段')
        need(a['start_sample'] == cursor and a['end_sample'] == cursor + samples and a['video_start_frame'] == video_cursor,
             '章节音频/画面来源边界不对应')
        delta = Fraction(cursor, sr) - Fraction(video_cursor, 30)
        need(abs(delta) <= Fraction(2, sr) and abs(a['av_offset_native_samples']) <= 2
             and abs(a['av_offset_native_samples'] - float(delta * sr)) < 1e-8
             and abs(a['av_offset_seconds'] - float(delta)) < 1e-8
             and 0 <= a['lead_silence_peak'] < .001 and 0 <= a['tail_silence_peak'] < .001, '章节接缝偏移/静音异常')
        validate_stats(a['all_samples']); validate_stats(a['source_body'])
        need(a['all_samples']['samples'] == samples and a['source_body']['samples'] == body, '逐部分测量样本数不同')
        protection = a['source_protection']
        need(protection['registration'] == tm.get('audio_protection'), '2022等原音保护登记不同')
        lo, hi = [round(x * sr) for x in tm['window']]
        coverage = []
        for x, y in tm.get('protected_source_intervals', []):
            x, y = max(lo, round(x * sr)), min(hi, round(y * sr))
            if x < y:
                count = sum(max(0, min(y, v) - max(x, u)) for u, v in intervals)
                need(count == y - x, '受保护等待信号没有完整保留')
                coverage.append({'source_samples': [x, y], 'covered_samples': count})
        need(protection['coverage'] == coverage, '信号保护测量缺失')
        title = {'A': 'Section A 讲座精听', 'B1': 'Section B 采访精听（一）', 'B2': 'Section B 采访精听（二）'}[ident.split('-')[1]]
        need(chapter['tags']['title'] == title and abs(float(chapter['start_time']) - video_cursor / 30) <= .001
             and abs(float(chapter['end_time']) - (video_cursor + n) / 30) <= .001, '章节名/顺序/时长不符')
        reps = [r for r in report['decoded_representative_frames'] if r['id'] == ident]
        need({0, 1, n - 2, n - 1} <= {r['part_frame'] for r in reps}
             and all(0 <= r['part_frame'] < n and r['whole_frame'] == video_cursor + r['part_frame']
                     and hexsha(r['decoded_yuv420p_sha256']) for r in reps), '实际解码代表帧缺少头尾/章节接缝')
        cursor += samples; video_cursor += n
    need(len(report['chapters']) == 3 and cursor == pcm['frames'], '章节/PCM完整数量不符')
    need({r['id'] for r in report['decoded_representative_frames']} == set(ids), '代表帧混入别年子段')
    command = report['assembly_command']
    argv = command['argv']
    bitrate = max(int(c['tm'].get('aac_bitrate', '192k')[:-1]) for c in child_data)
    need(bitrate in (192, 256, 320) and (not ids[0].startswith('2015-') or bitrate >= 256), 'AAC策略未继承最高明确码率')
    for key, value in [('-c:v', 'copy'), ('-c:a', 'aac'), ('-b:a', f'{bitrate}k')]:
        need(argv.count(key) == 1 and argv[argv.index(key) + 1] == value, '组装未无损复制视频/原声只AAC一次')
    need(command['aac_bitrate'] == f'{bitrate}k' and not any(k in argv for k in
         ('-ar', '-ac', '-af', '-filter:a', '-filter_complex')), '组装含采样率/声道/增益处理')
    return {'frames': sum(frames), 'native_sample_rate': sr, 'native_channels': ch,
            'source_samples': cursor, 'representative_frames': len(report['decoded_representative_frames']),
            'full_snr_db': audio['full']['snr_db'], 'aac_bitrate': f'{bitrate}k'}


def verify_archive(path, videos, expected_date):
    expected = {'专八听力精听/' + m['label']: m for m in videos}
    members = []
    with zipfile.ZipFile(path) as z:
        need(z.testzip() is None, '正式分包实际CRC失败')
        for info in z.infolist():
            need(info.filename in expected and info.filename not in members, '分包有非整套/重名成员')
            need(info.flag_bits & 0x800 and info.compress_type == zipfile.ZIP_STORED and info.date_time == expected_date,
                 '中文成员非UTF8、压缩方式/固定日期不同')
            digest, first = hashlib.sha256(), b''
            with z.open(info) as f:
                for block in iter(lambda: f.read(1 << 20), b''):
                    if not first:
                        first = block[:8]
                    digest.update(block)
            m = expected[info.filename]
            need(first[4:8] == b'ftyp' and digest.hexdigest() == m['mp4_sha256'] and info.file_size == m['mp4_bytes'],
                 '分包内实际MP4类型/SHA/字节不符')
            members.append(info.filename)
    return members


def verify(args):
    full, pub = load_helpers()
    args.state.mkdir(parents=True, exist_ok=True)
    FINAL_AUDIT.unlink(missing_ok=True)
    script_sha256 = sha(__file__)
    cache_record_sha256 = sha(args.cache_record)
    cache_record = read(args.cache_record)
    cache_rows = validate_cache_record(cache_record, pub)
    initial_projection = {ident: pub.gate('intensive', ident) for ident in IDS}
    release = pub.release(TAG)  # 404/401等明确失败；不会把尚未发布误写为PASS。
    need(release['tag_name'] == TAG and release.get('draft') is False, '正式Release不存在或仍为草稿')
    assets = asset_map(release)
    downloads = Downloads(assets, args.state / 'downloads')
    manifest_file, report_file = downloads.fetch('TEM8-manifest.json'), downloads.fetch(REPORT_ASSET)
    manifest, report = read(manifest_file), read(report_file)
    videos = validate_manifest(manifest, report)
    sums = parse_sums(downloads.fetch('SHA256SUMS'))
    validate_inventory(assets, videos, report['archives'], sums)
    mapping = downloads.fetch('TEM8-filenames.txt').read_text('utf-8')
    expected_mapping = '资产名\t中文文件名\tSHA256\t字节\n' + ''.join(
        f'{m["mp4"]}\t{m["label"]}\t{m["mp4_sha256"]}\t{m["mp4_bytes"]}\n' for m in videos)
    need(mapping == expected_mapping, '文件名映射的内容/顺序与manifest不同')
    cache_assets = asset_map(pub.release(pub.CACHE_TAG))
    producer_runs = {}

    def producer_check(run, commit):
        run = str(run)
        if run not in producer_runs:
            r = pub.gh('api', f'repos/{pub.REPO}/actions/runs/{run}', json_output=True)
            producer_runs[run] = {'run_id': run, 'head_sha': r['head_sha'], 'html_url': r['html_url'],
                                  'status': r['status'], 'conclusion': r['conclusion']}
        need(producer_runs[run]['head_sha'] == commit, '来源run实际commit与media meta不同')

    child_rows, whole_rows = [], []
    for m in videos:
        year = m['id']
        ev_name = full.evidence_asset(year)
        evidence = downloads.fetch(ev_name)
        with tempfile.TemporaryDirectory(prefix='tem8-final-evidence-', dir=args.state) as td:
            folder = Path(td)
            actual_meta = extract_evidence(evidence, folder)
            need(actual_meta == m, '完整来源ZIP meta与正式manifest不同')
            payload = full.assembly_payload(year)
            full.validate_stage(folder, year, payload, verify_video=False)
            part_dirs = folder / 'evidence/parts'
            need({p.name for p in part_dirs.iterdir()} == set(full.part_ids(year)), '证据中有跨年/重复/多余子段')
            child_data = []
            for ident in full.part_ids(year):
                part = part_dirs / ident
                cm = read(part / 'meta.json')
                current = pub.gate('intensive', ident)
                need(read(part / 'evidence/审核登记.json') == current, '完整子段审批不是当前原值')
                for source in pub.input_paths('intensive', ident):
                    need(sha(part / 'evidence/实际输入' / source.name) == sha(source), '真实输入快照不是当前源')
                r = cache_rows[ident]
                producer = cache_record['producer_manifest'][ident]
                need(r['cached_ready'] is True and r['full_current_review_inputs_png_sources_equal'] is True
                     and r['payload_sha256'] == current['payload_sha256'] == cm['approval_payload_sha256']
                     and r['mp4_sha256'] == cm['mp4_sha256'] and r['mp4_bytes'] == cm['mp4_bytes']
                     and str(r['producer_run']) == str(cm['run_id']) == str(producer['run_id'])
                     and r['producer_commit'] == cm['source_commit'] == producer['commit'], '45严格缓存/media/producer不对应')
                need((r['mp4'], r['evidence']) in pub.cache_pairs(
                    {'assets': list(cache_assets.values())}, 'intensive', ident, current['payload_sha256']), '当前缓存真实资产对缺失')
                need(cache_assets[r['mp4']]['digest'] == 'sha256:' + cm['mp4_sha256']
                     and cache_assets[r['mp4']]['size'] == cm['mp4_bytes']
                     and cache_assets[r['evidence']]['digest'] == 'sha256:' + r['evidence_sha256'], '子段服务器缓存摘要不符')
                work = part / 'evidence/工作记录'
                clock, states = read(work / 'clock-precheck.json'), read(work / 'states.json')
                pngs = {n.removeprefix('evidence/已审截图/shots/'): h for n, h in cm['evidence'].items()
                        if n.startswith('evidence/已审截图/shots/')}
                need(clock['status'] == 'pass' and clock['failures'] == [] and clock['threshold_unchanged'] == 3
                     and clock['checker_sha256'] == sha(D / 'tools/图片时钟核验.py')
                     and clock['PNG_sha256'] == pngs
                     and Counter(pngs.values()) == Counter(current['shots'].values())
                     and clock['states'] == len(states) and len(clock['all_probes']) == clock['probes']
                     and clock['frames_sha256'] == hashlib.sha256(json.dumps(states, separators=(',', ':')).encode()).hexdigest()
                     and all(p['ok'] is True and p['mean_difference'] <= 3 for p in clock['all_probes'])
                     and r['clock_report_sha256'] == sha(work / 'clock-precheck.json'), '图片时钟实际全状态证据不符')
                proof = pub.validate_two_stage_proof(ident, lambda n: read(work / n))
                need(bool(proof) == r['two_stage_proof_verified'], '两步恢复证明审计不符')
                if proof:
                    need(proof['mp4_sha256'] == cm['mp4_sha256'] and proof['source_sha256'] == cm['source_sha256']
                         and r['two_stage_proof_sha256'] == sha(work / 'two-stage-encoding.json'), '两步原声/时钟证明未绑定成品')
                producer_check(cm['run_id'], cm['source_commit'])
                tm = read(work / 'audio/timings.json')['cet4_male'][ident]
                need(tm['mode'] == '原音不动' and tm['source_sha256'] == cm['source_sha256'], '子段不属原声/原音不符')
                child_data.append({'meta': cm, 'tm': tm})
                child_rows.append({'id': ident, 'year': int(year), 'payload_sha256': current['payload_sha256'],
                                   'mp4_sha256': cm['mp4_sha256'], 'mp4_bytes': cm['mp4_bytes'],
                                   'source_sha256': cm['source_sha256'], 'producer_run': str(cm['run_id']),
                                   'producer_commit': cm['source_commit'], 'meta_sha256': sha(part / 'meta.json'),
                                   'actual_png_count': len(pngs), 'clock_states': clock['states'],
                                   'two_stage_proof_verified': bool(proof)})
            measured = read(folder / m['verification']['report'])
            details = validate_assembly_details(measured, child_data)
            producer_check(m['run_id'], m['source_commit'])
            whole_rows.append({'id': year, 'label': m['label'], 'mp4_sha256': m['mp4_sha256'], 'mp4_bytes': m['mp4_bytes'],
                               'assembly_payload_sha256': m['assembly_payload_sha256'], 'source_sha256': m['source_sha256'],
                               'evidence_sha256': sha(evidence), 'evidence_bytes': evidence.stat().st_size,
                               'assembly_verification_sha256': sha(folder / m['verification']['report']),
                               'parts_order': full.part_ids(year), **details})
        if not args.keep_evidence:
            evidence.unlink()
        print(json.dumps({'verified_evidence_year': year, 'whole_count': len(whole_rows), 'child_count': len(child_rows)}), flush=True)
    need(len(child_rows) == len({r['id'] for r in child_rows}) == 45 and {r['id'] for r in child_rows} == set(IDS), '最终45映射不完整')
    members, archives = [], []
    for a in report['archives']:
        file = downloads.fetch(a['file'])
        need(sha(file) == a['sha256'] == sums[file.name] and file.stat().st_size == a['bytes'], '实际分包摘要/体积不符')
        found = verify_archive(file, videos, pub.DATE)
        members += found
        archives.append({**a, 'download_url': assets[file.name]['browser_download_url'],
                         'actual_download_crc_utf8_member_sha256_verified': True, 'members': found})
        print(json.dumps({'verified_archive': file.name, 'cumulative_whole_videos': len(members)}), flush=True)
    need(members == ['专八听力精听/' + m['label'] for m in videos] and len(set(members)) == 15,
         '跨分包成员遗漏/重复/实际顺序与manifest不同')
    # 最后再核一次服务器资产身份/摘要，避免长下载期间正式包被替换。
    latest = asset_map(pub.release(TAG))
    selected = lambda rows: {n: (a['id'], a['digest'], a['size'], a.get('label')) for n, a in rows.items()}
    need(selected(latest) == selected(assets), '验收期间正式服务器资产发生变化')
    projection = {ident: pub.gate('intensive', ident) for ident in IDS}
    need(projection == initial_projection and sha(args.cache_record) == cache_record_sha256
         and sha(__file__) == script_sha256, '验收期间当前审核、严格缓存审计或验收程序变化')
    audit = {'schema': 1, 'status': 'PASS', 'checked_at': now(), 'tag': TAG, 'release_url': release['html_url'],
             'mode': 'complete_intensive_full', 'delivery_videos': 15, 'internal_parts': 45, 'years': YEARS,
             'script_sha256': script_sha256, 'manifest_source_commit': manifest['source_commit'],
             'manifest_sha256': sha(manifest_file), 'publisher_report_sha256': sha(report_file),
             'strict_cache_record_sha256': cache_record_sha256, 'current_45_entries_sha256': pub.hash_json(projection),
             'server_digest_verified': True, 'downloaded_full_evidence_zips': 15,
             'all_evidence_sha256_current_child_gate_producer_verified': True,
             'actual_download_zip_crc_utf8_member_sha256_order_verified': True,
             'whole_rows': whole_rows, 'child_rows': child_rows, 'archives': archives,
             'producer_runs': list(producer_runs.values()), 'unexpected_assets': [],
             'server_assets': [{'name': n, 'asset_id': a['id'], 'sha256': a['digest'][7:], 'bytes': a['size']}
                               for n, a in sorted(assets.items())],
             'scope': '实际下载全部15来源ZIP及全部正式视频分包；逐证据/逐成员核验。测量数值复核绑定的真实组装报告；未重新渲染或声称重新全片解码。'}
    dump(FINAL_AUDIT, audit)
    dump(args.state / '正式Release独立回下载核验.json', audit)
    print(json.dumps({'status': 'PASS', 'url': release['html_url'], 'delivery_videos': 15, 'internal_parts': 45,
                      'archives': len(archives), 'report': str(FINAL_AUDIT)}, ensure_ascii=False), flush=True)


def prepare():
    record = {'schema': 1, 'status': 'PREPARED_NOT_EXECUTED', 'prepared_at': now(), 'tag': TAG,
              'expected_delivery_videos': 15, 'expected_internal_parts': 45, 'years': YEARS,
              'script_sha256': sha(__file__), 'actual_release_queried': False,
              'actual_media_downloaded': False, 'media_pass_claimed': False,
              'command': 'python 专八/听力/批量/核验/整套精听正式发布/整套正式Release验收.py verify --state /workspace/tem8-intensive-final-validation',
              'scope': '仅准备：正式发布通知后显式执行verify；不存在Release/未完成下载不会生成PASS。'}
    dump(HERE / '验收准备.json', record)
    print(json.dumps(record, ensure_ascii=False))


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('prepare')
    p = sub.add_parser('verify')
    p.add_argument('--state', type=Path, required=True)
    p.add_argument('--cache-record', type=Path, default=STRICT_CACHE)
    p.add_argument('--keep-evidence', action='store_true', help='保留全部来源ZIP下载；默认每年核完删除ZIP节省磁盘')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    else:
        verify(args)


if __name__ == '__main__':
    cli()
