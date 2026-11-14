"""专八考试五题同屏专项修复：新画面编码，既有完整AAC原样复制。

独立源/截图/成品门禁。review不编码正式视频；审批必须由真实审图后登记。
旧考试/精听发布器和审核登记不参与本修复的放行。
"""
from __future__ import annotations
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[2]
AUDITS = BASE / '核验/五题同屏修复'
SOURCES = AUDITS / '16年来源清单.json'
REGISTRY = AUDITS / '审核登记.json'
CONTROL = ROOT / '.github/tem8-five-question-screen.json'
WORKFLOW = ROOT / '.github/workflows/repair-tem8-five-question-screen.yml'
YEARS = list(range(2009, 2020)) + list(range(2021, 2026))
REPAIR_YEARS = [y for y in YEARS if y != 2025]
REPO = 'AlienCodes/university-entrance-examination'
REVIEW_TAG = 'tem8-listening-five-question-screen-review'
CACHE_TAG = 'tem8-listening-five-question-screen-cache'
FINAL_TAG = 'tem8-listening-exam-five-question-fixed-2009-2025'
LIMIT = int(1.8 * 2**30)
ZIP_DATE = (2026, 11, 14, 0, 0, 0)
if str(HERE) not in sys.path: sys.path.insert(0, str(HERE))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


A = load('tem8_five_screen_adapter', HERE / '考试视频.py')
P = load('tem8_five_screen_publish_helpers', HERE / '发布汇集.py')
C = load('tem8_five_screen_clock', HERE / '图片时钟核验.py')


def need(ok, message):
    if not ok: raise ValueError(message)


def read(path): return json.loads(Path(path).read_text('utf-8'))


def dump(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def jsha(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def rel(path): return Path(path).resolve().relative_to(ROOT).as_posix()


def year_value(year):
    year = int(year); need(year in YEARS, '只接受实际16个考试年份，无2020')
    return year


def source_row(year):
    year = year_value(year); manifest = read(SOURCES)
    rows = manifest['rows']
    need(len(rows) == 16 and {r['year'] for r in rows} == set(YEARS), '来源清单必须恰有16年')
    need(set(manifest['repair_years']) == set(REPAIR_YEARS) and manifest['passthrough_years'] == [2025], '必须仅修15年，2025原样直通')
    row = next(r for r in rows if r['year'] == year)
    need(row['repair_required'] is (year != 2025), '来源修复范围与用户排除2025的要求不符')
    need(row['name'] == f'{year} 听力真题.mp4' and re.fullmatch('[a-f0-9]{64}', row['sha256']), '来源名称或SHA无效')
    return row


def payload(year):
    year = year_value(year); folder = BASE / '数据' / str(year)
    need(year in REPAIR_YEARS, '2025已由用户排除修复，只允许原MP4字节直通')
    paths = [folder / '试卷.json', folder / '时间轴.json']
    paper, timeline = [read(p) for p in paths]
    A.validate(paper, timeline)
    dependencies = [*P.dependencies('exam'), Path(__file__), HERE / '图片时钟核验.py', WORKFLOW]
    need(all(p.is_file() for p in dependencies), '缺少渲染依赖')
    return {'schema': 1, 'kind': 'exam-five-question-screen', 'year': year,
            'source': {k: v for k, v in source_row(year).items() if k != 'local_path_for_root_checks'},
            'source_manifest_sha256': sha(SOURCES),
            'inputs': {rel(p): sha(p) for p in paths},
            'programs': {rel(p): sha(p) for p in sorted(set(dependencies))}}


def screenshots(work):
    work = Path(work)
    return {p.relative_to(work).as_posix(): sha(p) for p in sorted((work / 'shots').glob('*.png')) if not p.name.endswith('.bad.png')}


def gate(year, work=None):
    current = payload(year); row = read(REGISTRY)['entries'][str(year)]
    need(row['status'] == 'approved' and len(row.get('evidence', '').strip()) >= 10, '尚无实际审图批准')
    need(row['payload'] == current and row['payload_sha256'] == jsha(current), '程序、输入或来源改变，原审图失效')
    need(row.get('shots'), '没有实际已审截图')
    if work is not None:
        need(Counter(screenshots(work).values()) == Counter(row['shots'].values()), '完整实际PNG与已审多重集不一致')
        validate_review(year, work)
    return row


def run(argv, **kwargs):
    return subprocess.run([str(a) for a in argv], check=True, **kwargs)


def gh(*args, parsed=False):
    try: result = subprocess.run(['gh', *map(str, args)], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or '')[-4000:]
        message = re.sub(r'\b(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]+', '[REDACTED]', message)
        print('GitHub操作失败：' + message, file=sys.stderr, flush=True)
        raise
    return json.loads(result.stdout) if parsed else result.stdout


def release(tag): return gh('api', f'repos/{REPO}/releases/tags/{tag}', parsed=True)


def ensure_release(tag, title, notes):
    result = subprocess.run(['gh', 'api', f'repos/{REPO}/releases/tags/{tag}'], capture_output=True, text=True)
    if result.returncode == 0: return
    need('HTTP 404' in result.stderr, '不能将查询或认证失败视为Release不存在')
    branch = os.getenv('GITHUB_REF_NAME') or subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
    need(branch and branch != 'HEAD', 'Release目标必须为分支')
    try: gh('release', 'create', tag, '-R', REPO, '--target', branch, '--title', title, '--notes', notes)
    except subprocess.CalledProcessError:
        # 并发初建只接受已经存在的同一tag，不对未知POST结果盲重试。
        release(tag)


def upload(tag, path, label=None):
    path = Path(path); assets = {a['name']: a for a in release(tag)['assets']}
    if path.name in assets:
        asset = assets[path.name]
        need(asset['digest'] == 'sha256:' + sha(path) and asset['size'] == path.stat().st_size,
             '同名资产已有其他字节，拒绝覆盖')
        return
    gh('release', 'upload', tag, str(path) + ('#' + label if label else ''), '-R', REPO)
    asset = next(a for a in release(tag)['assets'] if a['name'] == path.name)
    need(asset['digest'] == 'sha256:' + sha(path) and asset['size'] == path.stat().st_size, '上传后服务器摘要不符')


def probe(path, packets=None, raw=False):
    argv = ['ffprobe', '-v', 'error']
    if raw: argv += ['-ignore_editlist', '1']
    if packets:
        argv += ['-select_streams', packets, '-show_packets', '-show_entries',
                 'packet=pts,dts,duration,size,pos,flags,data_hash,side_data_list', '-show_data_hash', 'sha256']
    else: argv += ['-show_streams', '-show_format', '-show_data_hash', 'sha256']
    return json.loads(subprocess.check_output([*argv, '-of', 'json', str(path)]))


def stream(data, kind):
    rows = [s for s in data['streams'] if s['codec_type'] == kind]
    need(len(rows) == 1, '必须恰有一个' + kind + '流')
    return rows[0]


def movie_timescale(path):
    """沿用原MP4的movie clock，避免旧2025的毫秒edit-list在重封装时被舍入。"""
    with Path(path).open('rb') as f:
        end = Path(path).stat().st_size
        while f.tell() < end:
            start = f.tell(); header = f.read(8)
            need(len(header) == 8, 'MP4 box头截断')
            size, kind = struct.unpack('>I4s', header); extra = 0
            if size == 1: size = struct.unpack('>Q', f.read(8))[0]; extra = 8
            if size == 0: size = end - start
            need(size >= 8 + extra and start + size <= end, 'MP4 box大小无效')
            if kind == b'moov':
                data = f.read(size - 8 - extra); offset = 0
                while offset < len(data):
                    n, typ = struct.unpack('>I4s', data[offset:offset + 8])
                    need(n >= 8 and offset + n <= len(data), 'moov子box无效')
                    if typ == b'mvhd':
                        body = data[offset + 8:offset + n]; pos = 20 if body[0] == 1 else 12
                        timescale = struct.unpack('>I', body[pos:pos + 4])[0]
                        need(timescale > 0, '原movie timescale无效'); return timescale
                    offset += n
            f.seek(start + size)
    raise ValueError('原MP4缺mvhd')


def check_source(year, path):
    row = source_row(year); path = Path(path)
    need(path.is_file() and path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], '旧成品来源SHA/字节数不符')
    metadata = probe(path); video, audio = stream(metadata, 'video'), stream(metadata, 'audio')
    need(video['codec_name'] == 'h264' and (video['width'], video['height']) == (3840, 2160), '来源不是已核4K H264')
    need(Fraction(video['r_frame_rate']) == Fraction(video['avg_frame_rate']) == 30
         and int(video['nb_frames']) == row['source_video_frames']
         and Fraction(video['time_base']) == Fraction(1, 15360) and int(video.get('start_pts', 0)) == 0,
         '来源帧数/帧率/时间基/起点不符')
    need(audio['codec_name'] == 'aac' and int(audio['sample_rate']) == int(row['streams']['audio']['sample_rate'])
         and audio['channels'] == row['streams']['audio']['channels'], '来源音轨格式不同')
    return {'row': row, 'video': video, 'audio': audio, 'movie_timescale': movie_timescale(path)}


def fetch(year, out):
    year = year_value(year); row = source_row(year); out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists(): check_source(year, out); return out
    temp = out.with_suffix('.part')
    if row.get('source_download_url'):
        url = row['source_download_url']
        need(url.startswith(f'https://github.com/{REPO}/releases/download/') and url.endswith('.mp4'), '来源URL不在本仓库已核成品域')
        run(['curl', '--fail', '--location', '--retry', '3', '--retry-delay', '3', '--output', temp, url])
    else:
        need(year == 2025 and len(row['git_parts']) == 2, '无直接URL时只能恢复2025两个原Git分片')
        with temp.open('wb') as target:
            for path in row['git_parts']:
                need(path.startswith('专八/听力/最终视频/'), 'Git来源不在既有成品目录')
                run(['git', 'show', 'HEAD:' + path], cwd=ROOT, stdout=target)
    temp.replace(out); check_source(year, out)
    return out


def plan(year, work):
    work = Path(work).resolve(); A.configure(BASE / '数据' / str(year), work)
    raw, total, timing = A.states(); A.validate_group_states(A.PAPER, raw)
    frames = round((total + A.B.LEAD) * A.B.FPS)
    need(frames == source_row(year)['source_video_frames'], '新图帧数与旧视频不同，禁止静默截断/延长')
    states = [{'frame': round((t + A.B.LEAD) * 30), 'key': A.B.key(s), 'state': s} for t, s in raw]
    C.normalize_frames([[r['frame'], r['key']] for r in states], frames)
    data = {'schema': 1, 'year': int(year), 'total_frames': frames, 'fps': 30,
            'duration_seconds': frames / 30, 'states': states, 'source_timing': timing,
            'payload_sha256': jsha(payload(year))}
    dump(work / 'states.json', data)
    return data


def validate_review(year, work):
    work = Path(work); data = read(work / 'states.json')
    need(data['year'] == int(year) and data['payload_sha256'] == jsha(payload(year)), '截图状态程序指纹已失效')
    need(data['total_frames'] == source_row(year)['source_video_frames'], '截图状态总帧不符')
    A.configure(BASE / '数据' / str(year), work)
    raw, current_total, timing = A.states()
    current_states = [{'frame': round((t + A.B.LEAD) * 30), 'key': A.B.key(s), 'state': s} for t, s in raw]
    need(data['states'] == current_states and data['total_frames'] == round((current_total + A.B.LEAD) * 30),
         '工作帧表偏离当前原时间轴，不能仅凭截图正确而错误换屏')
    A.validate_group_states(A.PAPER, [s['state'] for s in data['states']])
    report = read(work / '核验/排版核验.json')
    need(report['sample'] is False and report['draft'] is False and report['problems'] == [], '须完整实际DOM核验，不收样片或待核预览')
    need(report['source_fingerprints'] == A.fingerprints(), '实际排版报告程序指纹已变')
    expected = {A.B.key(s['state']) for s in data['states']}
    need(set(p.stem for p in (work / 'shots').glob('*.png')) == expected, '完整截图缺失或含未知PNG')
    rows = report['fitted_layouts']
    need(len(rows) == len(expected) and {A.B.key(r['state']) for r in rows} == expected, 'DOM报告未覆盖全部实际状态')
    choice_count = 0
    for row in rows:
        state = row['state']
        if state['kind'] not in ('plist', 'q'): continue
        snapshot = row.get('group_snapshot')
        need(snapshot and snapshot['status'] == 'PASS' and snapshot['actual_question_count'] == 5
             and snapshot['actual_option_count'] == 20 and snapshot['minimum_option_font_size'] >= 40,
             '缺少整组五题/20选项实际DOM通过记录')
        A.validate_group_snapshot(A.PAPER, state, snapshot); choice_count += 1
    need(choice_count > 0, '没有选择题实际DOM记录')
    return {'states': len(expected), 'complete_group_DOM_states': choice_count, 'shots': screenshots(work)}


def zip_files(path, entries):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    need(len(entries) == len({n for n, _ in entries}), 'ZIP成员重复')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED, allowZip64=True) as z:
        for name, src in entries:
            need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'ZIP路径越界')
            item = zipfile.ZipInfo(name, ZIP_DATE); item.compress_type = zipfile.ZIP_STORED; item.external_attr = 0o644 << 16
            with Path(src).open('rb') as source, z.open(item, 'w', force_zip64=True) as target:
                shutil.copyfileobj(source, target, 1 << 20)
    need(path.stat().st_size < LIMIT, 'ZIP超1.8GiB')
    with zipfile.ZipFile(path) as z:
        need(z.testzip() is None and z.namelist() == [n for n, _ in entries], 'ZIP CRC/顺序错误')
        for info, (_, src) in zip(z.infolist(), entries):
            need(info.compress_type == zipfile.ZIP_STORED and info.date_time == ZIP_DATE
                 and (info.filename.isascii() or info.flag_bits & 0x800), 'ZIP格式或中文UTF8标记错误')
            with z.open(info) as f: need(hashlib.file_digest(f, 'sha256').hexdigest() == sha(src), 'ZIP成员SHA不符')
    return {'name': path.name, 'bytes': path.stat().st_size, 'sha256': sha(path)}


def review(year, source, work):
    year = year_value(year); work = Path(work).resolve(); work.mkdir(parents=True, exist_ok=True)
    identity = check_source(year, source); dump(work / 'source.json', identity)
    plan(year, work); A.render(sample=False, layout_only=False)
    checked = validate_review(year, work); current = payload(year)
    row = {'status': 'pending', 'payload': current, 'payload_sha256': jsha(current), 'shots': checked['shots'],
           'review_scope': checked, 'evidence': '待根真实审图后填写，不得自动批准'}
    dump(work / 'candidate.json', row)
    entries = [('candidate.json', work / 'candidate.json')]
    entries += [(p.relative_to(work).as_posix(), p) for p in sorted(work.rglob('*.json')) if p.name != 'candidate.json']
    entries += [(name, work / name) for name in row['shots']]
    archive = work / f'tem8-five-review-{year}-{row["payload_sha256"][:16]}.zip'
    zip_files(archive, entries)
    ensure_release(REVIEW_TAG, '专八考试五题同屏待审完整截图', '仅实际排版截图与待审候选；非正式视频，不代表已经批准。')
    upload(REVIEW_TAG, archive)
    print(json.dumps({'status': 'REVIEW_READY_NOT_APPROVED', 'year': year, 'archive': archive.name, **checked}, ensure_ascii=False), flush=True)
    return row


def concat_file(states, total, work):
    C.normalize_frames(states, total); rows = []
    need("'" not in str(work), '工作路径不能含单引号')
    for (first, key), end in zip(states, [x[0] for x in states[1:]] + [total]):
        rows.append(f"file '{work / 'shots' / (key + '.png')}'\noption framerate 30\nduration {(end-first)/30:.9f}")
    last = work / 'shots' / (states[-1][1] + '.png')
    rows += [f"file '{last}'\noption framerate 30\nduration 1", f"file '{last}'\noption framerate 30"]
    path = work / 'concat.txt'; path.write_text('\n'.join(rows) + '\n', 'utf-8')
    return path


def packet_summary(path, selector, raw=False):
    packets = probe(path, selector, raw)['packets']
    fields = ['pts', 'dts', 'duration', 'size', 'data_hash']
    rows = [{**{k: p[k] for k in fields}, 'flags': p.get('flags', ''),
             'side_data_list': p.get('side_data_list', [])} for p in packets]
    return rows


def mux_argv(picture, source, output, timescale):
    return ['ffmpeg', '-y', '-v', 'error', '-copyts', '-i', picture, '-i', source, '-map', '0:v:0', '-map', '1:a:0',
            '-c:v', 'copy', '-c:a', 'copy', '-video_track_timescale', '15360',
            '-movie_timescale', str(timescale), '-movflags', '+faststart', output]


def full_picture_check(video, fr, work):
    """4K解码每个实际状态的中间帧，逐像素灰阶对对应批准PNG。"""
    import numpy as np
    from PIL import Image
    total = int(stream(probe(video), 'video')['nb_frames'])
    targets = [(a + (b-a-1)//2, key) for (a, key), b in zip(fr, [x[0] for x in fr[1:]] + [total])]
    expression = C.select_expression([f for f, _ in targets])
    cmd = ['ffmpeg', '-v', 'error', '-i', str(video), '-vf', f"select='{expression}',format=gray", '-vsync', '0', '-f', 'rawvideo', '-']
    checks = []
    with tempfile.TemporaryFile() as error:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=error)
        try:
            for frame, key in targets:
                raw = proc.stdout.read(3840 * 2160); need(len(raw) == 3840 * 2160, '4K实际状态解码缺帧')
                actual = np.frombuffer(raw, dtype=np.uint8).reshape(2160, 3840).astype('int16')
                with Image.open(work / 'shots' / (key + '.png')) as im: reference = np.asarray(im.convert('L'), dtype='int16')
                need(reference.shape == actual.shape, '批准PNG不是4K')
                difference = float(np.abs(actual-reference).mean()); need(difference <= 3, f'4K状态画面不符：{frame}/{key}/{difference}')
                checks.append({'frame': frame, 'key': key, 'mean_difference': difference, 'ok': True})
            need(not proc.stdout.read(1) and proc.wait() == 0, '4K状态探针解码异常')
        finally:
            proc.stdout.close()
            if proc.poll() is None: proc.kill(); proc.wait()
    return {'status': 'PASS', 'threshold': 3, 'states': len(checks), 'checks': checks}


def render(year, source, work):
    year = year_value(year); work = Path(work).resolve(); source = Path(source).resolve()
    identity = check_source(year, source)
    # 独立重放真实完整截图；任何程序或字体变化均在PNG门禁被拦。
    plan(year, work); A.render(sample=False, layout_only=False); approved = gate(year, work)
    data = read(work / 'states.json'); fr = [[r['frame'], r['key']] for r in data['states']]; total = data['total_frames']
    listing = concat_file(fr, total, work)
    bindings = {'payload_sha256': approved['payload_sha256'], 'states_sha256': sha(work / 'states.json'),
                'concat_sha256': sha(listing), 'source_mp4_sha256': identity['row']['sha256'],
                'fps': 30, 'full_filter': 'format=yuv420p,fps=30:start_time=0:round=near'}
    dump(work / 'picture-contract.json', bindings)
    fast = work / 'clock-fast.mp4'
    fast_cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', listing,
                '-vf', 'scale=480:270,fps=30:start_time=0:round=near', '-fps_mode', 'cfr', '-r', '30',
                '-frames:v', str(total), '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'stillimage',
                '-crf', '18', '-threads', '2', '-pix_fmt', 'yuv420p', '-g', '300', '-x264-params', 'scenecut=0',
                '-an', '-t', f'{total/30:.9f}', fast]
    run(fast_cmd); C.check(fast, fr, work / 'shots', total, work / 'clock-precheck.json', bindings)
    C.require_pass(fast, fr, work / 'shots', total, work / 'clock-precheck.json', bindings)
    picture = work / 'picture.mp4'
    picture_cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', listing,
                   '-vf', bindings['full_filter'], '-fps_mode', 'cfr', '-r', '30', '-frames:v', str(total),
                   '-c:v', 'libx264', '-preset', 'medium', '-tune', 'stillimage', '-crf', '18',
                   '-threads', '2', '-pix_fmt', 'yuv420p', '-g', '300', '-x264-params', 'scenecut=0',
                   '-an', '-t', f'{total/30:.9f}', '-video_track_timescale', '15360', '-movflags', '+faststart', picture]
    run(picture_cmd)
    output = work / f'{year} 听力真题.mp4'
    mux_cmd = mux_argv(picture, source, output, identity['movie_timescale'])
    run(mux_cmd)
    dump(work / 'encoding.json', {'picture': list(map(str, picture_cmd)), 'mux': list(map(str, mux_cmd)),
          'audio': 'existing AAC stream copy; no synthesis, decoding, normalization or reencoding', 'source': identity['row']['sha256']})
    meta = verify(year, source, output, work)
    dump(work / 'meta.json', meta); store(work)
    return meta


def verify(year, source, video, work):
    work, video = Path(work), Path(video); approved = gate(year, work); source_info = check_source(year, source)
    data = read(work / 'states.json'); total = data['total_frames']; fr = [[r['frame'], r['key']] for r in data['states']]
    info = probe(video); v, a = stream(info, 'video'), stream(info, 'audio')
    need(v['codec_name'] == 'h264' and (v['width'], v['height']) == (3840, 2160), '成品不是4K H264')
    need(v['r_frame_rate'] == '30/1' and Fraction(v['avg_frame_rate']) == 30 and int(v['nb_frames']) == total, '成品总帧/恒定帧率不符')
    need(v['time_base'] == source_info['video']['time_base'] == '1/15360'
         and abs(float(v['duration']) - total / 30) < 1e-6, '视频时间基/时长不符')
    vp = packet_summary(video, 'v:0')
    need(len(vp) == total and sorted(p['pts'] for p in vp) == list(range(0, total*512, 512))
         and all(p['duration'] == 512 for p in vp), '成品视频PTS不是从零精确30fps')
    need(all(x['dts'] < y['dts'] for x, y in zip(vp, vp[1:])), '成品视频DTS不递增')
    need(a['codec_name'] == 'aac' and a['sample_rate'] == source_info['audio']['sample_rate']
         and a['channels'] == source_info['audio']['channels'], '成品音轨采样率或声道改变')
    audio_fields = ['time_base', 'profile', 'channel_layout', 'extradata_hash', 'start_pts', 'start_time', 'duration_ts']
    need(all(a.get(k) == source_info['audio'].get(k) for k in audio_fields), 'AAC时间基、呈现时长、priming或codec配置改变')
    original_audio, actual_audio = packet_summary(source, 'a:0'), packet_summary(video, 'a:0')
    need(original_audio == actual_audio, 'AAC载荷、时间戳或包时长发生变化')
    need(abs(float(v['duration']) - float(a['duration'])) < .05, '声画总时长不一致')
    need(abs(float(v.get('start_time', 0))) < 1e-9 and a.get('start_time') == source_info['audio'].get('start_time'), '成品起点发生变化')
    C.require_pass(work / 'clock-fast.mp4', fr, work / 'shots', total, work / 'clock-precheck.json',
                   {'payload_sha256': approved['payload_sha256'], 'states_sha256': sha(work / 'states.json'),
                    'concat_sha256': sha(work / 'concat.txt'), 'source_mp4_sha256': source_info['row']['sha256'],
                    'fps': 30, 'full_filter': 'format=yuv420p,fps=30:start_time=0:round=near'})
    picture_checks = full_picture_check(video, fr, work)
    evidence = {'schema': 1, 'status': 'PASS', 'year': year, 'payload_sha256': approved['payload_sha256'],
                'mp4_sha256': sha(video), 'mp4_bytes': video.stat().st_size, 'total_frames': total,
                'video_exact_pts_30fps': True, 'source_mp4_sha256': source_info['row']['sha256'],
                'audio_all_packets_and_pts_exact': True, 'source_audio_packet_count': len(original_audio),
                'source_audio_packets_sha256': jsha(original_audio), 'audio_sample_rate': int(a['sample_rate']),
                'audio_channels': a['channels'], 'audio_stream_copy': True, 'group_DOM_verified': True,
                'source_audio_properties': {k: source_info['audio'].get(k) for k in audio_fields},
                'output_audio_properties': {k: a.get(k) for k in audio_fields},
                'all_approved_PNG_sha256': screenshots(work), 'picture_checks': picture_checks,
                'clock_report_sha256': sha(work / 'clock-precheck.json'),
                'source_commit': os.getenv('GITHUB_SHA'), 'run_id': os.getenv('GITHUB_RUN_ID')}
    dump(work / 'verification.json', evidence)
    return {'schema': 1, 'kind': 'exam-five-question-screen', 'year': year, 'filename': f'{year} 听力真题.mp4',
            'asset': f'tem8-five-fixed-{year}.mp4', 'sha256': sha(video), 'bytes': video.stat().st_size,
            'payload_sha256': approved['payload_sha256'], 'verification_sha256': sha(work / 'verification.json'),
            'source_mp4_sha256': source_info['row']['sha256'], 'source_commit': os.getenv('GITHUB_SHA'), 'run_id': os.getenv('GITHUB_RUN_ID')}


def validate_cached_record(year, work, meta):
    """发布不凭全局PASS放行；将生产证据逐项重新绑定当前源、审批和真实PNG。"""
    work = Path(work); approved = gate(year, work); source = source_row(year)
    data = read(work / 'states.json'); total = data['total_frames']
    fr = C.normalize_frames([[r['frame'], r['key']] for r in data['states']], total)
    need(meta['schema'] == 1 and meta['kind'] == 'exam-five-question-screen'
         and meta['year'] == int(year) and meta['filename'] == f'{year} 听力真题.mp4'
         and meta['payload_sha256'] == approved['payload_sha256']
         and meta['source_mp4_sha256'] == source['sha256']
         and type(meta['bytes']) is int and meta['bytes'] > 0
         and re.fullmatch('[a-f0-9]{64}', meta['sha256'])
         and re.fullmatch('[a-f0-9]{40}', meta.get('source_commit') or '')
         and str(meta.get('run_id') or '').isdigit(), '缓存媒体元数据未绑定当前年份、来源和批准')
    report = read(work / 'verification.json')
    need(sha(work / 'verification.json') == meta['verification_sha256'], '缓存核验报告摘要改变')
    need(report['schema'] == 1 and report['status'] == 'PASS'
         and report['year'] == int(year) and report['payload_sha256'] == approved['payload_sha256']
         and report['mp4_sha256'] == meta['sha256'] and report['mp4_bytes'] == meta['bytes']
         and report['source_mp4_sha256'] == source['sha256']
         and report['total_frames'] == total == source['source_video_frames']
         and report['source_commit'] == meta['source_commit'] and report['run_id'] == meta['run_id'],
         '核验报告与媒体、源、帧表或生产来源不一致')
    need(all(report.get(k) is True for k in ['video_exact_pts_30fps', 'audio_all_packets_and_pts_exact',
                                          'audio_stream_copy', 'group_DOM_verified']), '缓存缺少逐项生产通过证据')
    audio = source['streams']['audio']; source_audio = report['source_audio_properties']
    need(source_audio == report['output_audio_properties']
         and all(source_audio.get(k) == audio[k] for k in source_audio if k in audio)
         and report['audio_sample_rate'] == int(audio['sample_rate'])
         and report['audio_channels'] == audio['channels']
         and type(report['source_audio_packet_count']) is int and report['source_audio_packet_count'] > 0
         and (not str(audio.get('nb_frames', '')).isdigit() or report['source_audio_packet_count'] == int(audio['nb_frames']))
         and re.fullmatch('[a-f0-9]{64}', report['source_audio_packets_sha256']), '缓存AAC原包、时间基或配置证据不全')
    need(set(source_audio) == {'time_base', 'profile', 'channel_layout', 'extradata_hash', 'start_pts', 'start_time', 'duration_ts'},
         '缓存AAC属性证据缺字段')
    need(report['all_approved_PNG_sha256'] == screenshots(work), '核验报告未覆盖全部实际批准PNG')
    pictures = report['picture_checks']; targets = [(a + (b-a-1)//2, key) for (a, key), b in zip(fr, [x[0] for x in fr[1:]] + [total])]
    need(pictures['status'] == 'PASS' and pictures['threshold'] == 3 and pictures['states'] == len(fr)
         and [(r.get('frame'), r.get('key')) for r in pictures['checks']] == targets
         and all(r.get('ok') is True and isinstance(r.get('mean_difference'), (int, float))
                 and math.isfinite(r['mean_difference']) and 0 <= r['mean_difference'] <= 3 for r in pictures['checks']),
         '缓存4K实际画面核验缺状态或含失败项')
    clock_path = work / 'clock-precheck.json'; clock = read(clock_path); contract = read(work / 'picture-contract.json')
    need(report['clock_report_sha256'] == sha(clock_path) and contract == clock['source_fingerprints']
         and contract['payload_sha256'] == approved['payload_sha256']
         and contract['states_sha256'] == sha(work / 'states.json')
         and contract['source_mp4_sha256'] == source['sha256']
         and contract['fps'] == 30 and contract['full_filter'] == 'format=yuv420p,fps=30:start_time=0:round=near'
         and re.fullmatch('[a-f0-9]{64}', contract['concat_sha256']), '缓存快片合同未绑定当前批准、帧表与来源')
    probes = C.probes(fr, total); rows = clock.get('all_probes', [])
    need(clock.get('schema') == 1 and clock.get('status') == 'pass' and clock.get('failures') == []
         and clock.get('checker_sha256') == sha(HERE / '图片时钟核验.py') and clock.get('threshold_unchanged') == 3
         and clock.get('total_frames') == total and clock.get('frames_sha256') == C.frame_sha(fr)
         and clock.get('PNG_sha256') == C.png_hashes(fr, work / 'shots')
         and clock.get('states') == len(fr) and clock.get('probes') == len(probes)
         and [r.get('frame') for r in rows] == probes
         and all(r.get('ok') is True and isinstance(r.get('mean_difference'), (int, float))
                 and math.isfinite(r['mean_difference']) and 0 <= r['mean_difference'] <= 3 for r in rows)
         and re.fullmatch('[a-f0-9]{64}', clock.get('video_sha256', '')), '缓存完整换屏时钟核验不符')
    return report


def store(work):
    work = Path(work); meta = read(work / 'meta.json'); year = meta['year']; approved = gate(year, work)
    need(meta['payload_sha256'] == approved['payload_sha256'] and sha(work / meta['filename']) == meta['sha256'], '待存档媒体或审批已变')
    need(re.fullmatch('[a-f0-9]{40}', meta.get('source_commit') or '') and str(meta.get('run_id') or '').isdigit(), '缺少真实生产commit/run来源')
    validate_cached_record(year, work, meta)
    # producer run纳入名字：相同视频字节的不同成功尝试可以各自存证，互不覆盖。
    prefix = f'tem8-five-fixed-{year}-{approved["payload_sha256"][:16]}-{meta["sha256"][:12]}-{meta["run_id"]}'
    media = work / (prefix + '.mp4'); shutil.copyfile(work / meta['filename'], media)
    evidence = work / (prefix + '-evidence.zip')
    evidence_json = [work / n for n in ['states.json', 'picture-contract.json', 'clock-precheck.json',
                                     'encoding.json', 'verification.json', 'meta.json']]
    evidence_json += sorted((work / '核验').glob('*.json'))
    need(all(p.is_file() for p in evidence_json), '业务证据缺失，拒绝制作缓存包')
    files = [(p.relative_to(work).as_posix(), p) for p in evidence_json]
    files += [(name, work / name) for name in screenshots(work)]
    zip_files(evidence, files)
    ensure_release(CACHE_TAG, '专八考试五题完整同屏已核新视频', '每项完整截图门禁与声音原包复制核验通过；正式发布必须收齐15个修复视频及2025原样视频。')
    upload(CACHE_TAG, media, meta['filename']); upload(CACHE_TAG, evidence)
    index = work / (prefix + '-index.json')
    dump(index, {'schema': 1, 'status': 'PASS', 'meta': meta,
                 'media_asset': media.name, 'evidence_asset': evidence.name, 'evidence_sha256': sha(evidence),
                 'source_fingerprint': approved['payload_sha256'], 'all_render_checks_passed': True})
    upload(CACHE_TAG, index)
    print(json.dumps({'status': 'RENDERED_VERIFIED_AND_STORED', 'year': year, 'video': media.name, 'evidence': evidence.name}, ensure_ascii=False), flush=True)


def cached_ready(year, cache):
    """只有media和完整证据均持久上传成功后才有index；最终发布仍重读完整证据。"""
    approval = gate(year); assets = {a['name']: a for a in cache['assets']}
    prefix = f'tem8-five-fixed-{year}-{approval["payload_sha256"][:16]}-'
    for name in sorted(assets):
        if not name.startswith(prefix) or not name.endswith('-index.json'): continue
        try:
            with tempfile.TemporaryDirectory(prefix='tem8fiveindex_') as td:
                gh('release', 'download', CACHE_TAG, '-R', REPO, '-p', name, '-D', td)
                path = Path(td) / name; need(sha(path) == assets[name]['digest'].removeprefix('sha256:'), 'index服务器摘要不符')
                data = read(path); meta = data['meta']
                need(data['status'] == 'PASS' and data['all_render_checks_passed'] is True, 'index不是通过状态')
                need(meta['kind'] == 'exam-five-question-screen' and meta['year'] == int(year)
                     and meta['payload_sha256'] == data['source_fingerprint'] == approval['payload_sha256']
                     and meta['source_mp4_sha256'] == source_row(year)['sha256'], '缓存来源/审批不同')
                need(assets[data['media_asset']]['digest'] == 'sha256:' + meta['sha256']
                     and assets[data['media_asset']]['size'] == meta['bytes']
                     and assets[data['evidence_asset']]['digest'] == 'sha256:' + data['evidence_sha256'], '成品或证据未完整上传')
            return True
        except (ValueError, KeyError):
            continue
    return False


def unpack(path, target):
    target = Path(target); target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        need(z.testzip() is None, '证据ZIP CRC不符')
        for info in z.infolist():
            out = target / info.filename
            need(not Path(info.filename).is_absolute() and '..' not in Path(info.filename).parts and out.resolve().is_relative_to(target.resolve()), '证据ZIP路径越界')
            if info.is_dir(): out.mkdir(parents=True, exist_ok=True); continue
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, out.open('wb') as dst: shutil.copyfileobj(src, dst, 1 << 20)


def publish(out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True); cache = release(CACHE_TAG); assets = {a['name']: a for a in cache['assets']}
    records = []
    for year in sorted(YEARS, reverse=True):
        if year == 2025:
            original = fetch(2025, out / '2025' / '2025 听力真题.mp4')
            original_row = source_row(2025)
            need(original_row['repair_required'] is False and sha(original) == original_row['passthrough_expected_sha256'], '2025并非用户要求的原样直通')
            records.append((original, {'schema': 1, 'kind': 'verified-original-passthrough', 'year': 2025,
                'filename': '2025 听力真题.mp4', 'sha256': sha(original), 'bytes': original.stat().st_size,
                'source_mp4_sha256': original_row['sha256'], 'video_and_audio_bytes_unchanged': True,
                'reason': '用户明确2025无问题；仅修其余15年，2025不重新排版、编码或封装。'}))
            continue
        approval = gate(year); prefix = f'tem8-five-fixed-{year}-{approval["payload_sha256"][:16]}-'
        candidates = [(n, n[:-4] + '-evidence.zip') for n in assets if n.startswith(prefix) and n.endswith('.mp4') and n[:-4] + '-evidence.zip' in assets]
        need(candidates, '缺少五题同屏新成品：' + str(year))
        recovered = None
        for media_name, evidence_name in sorted(candidates):
            folder = out / str(year); folder.mkdir(exist_ok=True)
            gh('release', 'download', CACHE_TAG, '-R', REPO, '-p', evidence_name, '-p', media_name, '-D', folder, '--clobber')
            need(sha(folder / evidence_name) == assets[evidence_name]['digest'].removeprefix('sha256:'), '缓存证据服务器摘要不符')
            unpack(folder / evidence_name, folder)
            m = read(folder / 'meta.json'); validate_cached_record(year, folder, m)
            need(sha(folder / media_name) == m['sha256'] == assets[media_name]['digest'].removeprefix('sha256:') and (folder / media_name).stat().st_size == m['bytes'], '缓存媒体SHA不符')
            target = folder / m['filename']; shutil.copyfile(folder / media_name, target)
            recovered = (target, m); break
        need(recovered is not None, '没有可用新成品：' + str(year)); records.append(recovered)
    need(len(records) == 16 and sum(m['kind'] == 'verified-original-passthrough' for _, m in records) == 1,
         '必须15个修复新视频及2025一个原样成品全部核齐才发布')
    archive = out / 'TEM8-listening-exam-five-question-fixed-2009-2025.zip'
    pack = zip_files(archive, [(m['filename'], p) for p, m in records])
    manifest = {'schema': 1, 'status': 'PASS', 'scope': '2009—2024实际15年修复五题完整同屏；2025按用户明确要求原MP4字节直通。',
                'videos': 16, 'years': sorted(YEARS, reverse=True), 'cancelled_years': [2020], 'archive': pack,
                'repaired_videos': 15, 'unchanged_passthrough_years': [2025],
                'source_archive_unchanged': True, 'audio_streams_reencoded': False, 'files': [m for _, m in records]}
    dump(out / 'TEM8-manifest.json', manifest)
    sums = out / 'SHA256SUMS'; sums.write_text(''.join(f'{sha(p)}  {p.name}\n' for p in [archive, out / 'TEM8-manifest.json']), 'utf-8')
    notes = '修复2009—2024实际15年的同一采访五道选择题被分成2+3或单题换页问题。预览、采访播放、念题及作答完整显示同组五题与全部选项。\n\n2025由用户明确排除修复，原MP4逐字节放入新包，不重新排版、编码或封装。共16个真实考试年份，2020停考；原文精读视频不变。15个修复视频只重做考试画面，原有完整AAC音轨逐包与时间戳相同，没有重编码、增益或声道采样率变更。\n\n文件统一为“YYYY 听力真题.mp4”，中文ZIP按2025到2009排列。2009—2015仍为原材料的新题型优化版；2014题源冲突题保留不计分说明。'
    ensure_release(FINAL_TAG, '专八听力真题｜五题完整同屏修复版｜2025—2009', notes)
    for p in [archive, out / 'TEM8-manifest.json', sums]: upload(FINAL_TAG, p)
    with tempfile.TemporaryDirectory(prefix='tem8fiveback_') as td:
        gh('release', 'download', FINAL_TAG, '-R', REPO, '-p', archive.name, '-D', td)
        back = Path(td) / archive.name
        need(sha(back) == pack['sha256'] and back.stat().st_size == pack['bytes'], '正式ZIP实际回下载不符')
        with zipfile.ZipFile(back) as z:
            need(z.testzip() is None and z.namelist() == [m['filename'] for _, m in records], '回下载CRC/名称/顺序不符')
            for info, (_, m) in zip(z.infolist(), records):
                need(info.flag_bits & 0x800 and info.file_size == m['bytes'], '回下载中文UTF8/大小不符')
                with z.open(info) as f: need(hashlib.file_digest(f, 'sha256').hexdigest() == m['sha256'], '回下载成员SHA不符')
    report = {'status': 'PASS', 'videos': 16, 'tag': FINAL_TAG, 'archive': pack, 'server_sha256': True,
              'actual_download_crc_utf8_order_member_sha256': True, 'all_source_audio_packets_preserved': True,
              'all15_current_PNG_and_group_DOM_gates': True,
              'year2025_original_MP4_bytes_unchanged': True}
    dump(out / 'TEM8-download-verification.json', report); upload(FINAL_TAG, out / 'TEM8-download-verification.json')
    print(json.dumps(report, ensure_ascii=False), flush=True)


def control():
    c = read(CONTROL); need(c['stage'] in ('review', 'render'), '未知阶段')
    years = [year_value(y) for y in c['years']]
    need(years and len(years) == len(set(years)), '年份清单为空或重复')
    need(set(years) <= set(REPAIR_YEARS), '2025不允许进入review/render修复矩阵')
    need(type(c.get('publish', False)) is bool, 'publish必须布尔值')
    if c.get('publish'): need(c['stage'] == 'render' and set(years) == set(REPAIR_YEARS), '正式发布必须收齐15修复年份，2025原样补入')
    if c['stage'] == 'render':
        for year in years: gate(year)
    return c, years


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['matrix', 'fetch', 'review', 'render', 'gate', 'store', 'publish'])
    p.add_argument('year', nargs='?', type=int); p.add_argument('--work', type=Path); p.add_argument('--source', type=Path); p.add_argument('--out', type=Path)
    args = p.parse_args()
    if args.command == 'matrix':
        c, years = control()
        if c['stage'] == 'render' and not c.get('force_render', False):
            try: cache = release(CACHE_TAG)
            except subprocess.CalledProcessError as exc:
                need('HTTP 404' in (exc.stderr or ''), '缓存查询失败，不可将网络/认证失败当作缓存不存在')
                cache = None
            if cache: years = [y for y in years if not cached_ready(y, cache)]
        print(json.dumps([{'year': y, 'stage': c['stage']} for y in years])); return
    if args.command == 'publish':
        c, years = control(); need(c.get('publish') is True, '本控制不授权正式发布'); return publish(args.out)
    if args.command == 'store':
        need(args.work is not None, '存档恢复必须给work'); return store(args.work)
    year = year_value(args.year)
    if args.command == 'fetch': return fetch(year, args.out)
    if args.command == 'gate': return gate(year, args.work)
    need(args.work and args.source, '必须给work和原source')
    return (review if args.command == 'review' else render)(year, args.source, args.work)


if __name__ == '__main__': main()
