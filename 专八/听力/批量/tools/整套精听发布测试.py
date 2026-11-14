"""完整年度发布的离线双向验证；所有媒体、审批、服务端均为临时合成测试夹具。"""
from __future__ import annotations

import copy
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('tem8_full_publish_test', HERE / '整套精听发布.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
pub = m.pub


def technical_sample(report_path, out, video=None):
    """真实历史长视频只做技术包对接；不创建生产meta、不调用gate替代或GitHub写入。"""
    report_path, out = Path(report_path), Path(out)
    proof = pub.read(report_path)
    m.need(proof.get('technical_only') is True and proof.get('not_current_approval') is True
           and proof.get('ok') is True, '只允许明确标记的历史技术核验样例')
    video = Path(video) if video else report_path.parent / 'tem8-intensive-full-2009.mp4'
    m.need(video.is_file() and pub.sha(video) == proof['sha256'], '真实2009技术样例MP4摘要不同')
    m.need(proof['video_packets'].get('pts_exact_30fps') is True
           and proof['audio']['full'].get('ok') is True and len(proof['representative_frames']) == 15,
           '技术样例缺少实际音画检查')
    try:
        m.validate_engine_meta(proof, proof, 2009, [], [])
    except ValueError:
        production_rejected = True
    else:
        raise AssertionError('技术报告被误认作正式生产输出')
    out.mkdir(parents=True, exist_ok=True)
    name = '技术样例（非正式交付）/' + m.label(2009)
    local = out / 'TECHNICAL-ONLY-2009-roundtrip.zip'
    archive = pub.zip_files(local, [(name, video)])
    with tempfile.TemporaryDirectory(prefix='tem8_full_real_back_', dir=out) as td:
        back = Path(td) / local.name
        shutil.copyfile(local, back)
        m.verify_download(local, back, {name: proof['sha256']})
    result = {'technical_only': True, 'not_current_approval': True, 'year': 2009,
              'production_stage_created': False, 'production_contract_rejected': production_rejected,
              'github_writes': False, 'network_download_verified': False,
              'local_real_file_roundtrip_verified': True, 'archive': archive,
              'video': {'file': video.name, 'sha256': proof['sha256'], 'bytes': video.stat().st_size},
              'member': name, 'utf8_crc_member_sha_fixed_date_store': True,
              'original_technical_report_sha256': pub.sha(report_path),
              'actual_pts_frames': proof['video_packets']['frames'],
              'actual_full_audio_measurements': proof['audio']['full'],
              'test_code_sha256': pub.sha(Path(__file__)),
              'publisher_code_sha256': pub.sha(HERE / '整套精听发布.py')}
    pub.dump(out / '真实技术样例打包对接核验.json', result)
    return result


class FullPublication(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tem8_full_test_')
        self.root = Path(self.temp.name)
        self.registry = {}
        self.gate_patch = patch.object(pub, 'gate', side_effect=lambda kind, ident: self.registry[ident])
        self.gate_patch.start()
        self.actual_payload = m.assembly_payload
        self.payload_patch = patch.object(m, 'assembly_payload', side_effect=self.payload)
        self.payload_patch.start()

    def tearDown(self):
        self.payload_patch.stop()
        self.gate_patch.stop()
        self.temp.cleanup()

    def payload(self, year):
        y = m.year_id(year)
        return {'schema': 1, 'kind': m.KIND, 'id': y,
                'parts': [{'id': ident, 'approval_payload_sha256': self.registry[ident]['payload_sha256']}
                          for ident in m.part_ids(y)],
                'assembly_sources': {'test-fixture-only': 'd' * 64}}

    def prep(self, year):
        rows = [{**r, 'audio': {'sample_rate': 44100, 'channels': 2}} for r in pub.selected_sources(year)]
        p = {'year': year, 'canonical': {'sha256': 'c' * 64, 'sample_rate': 44100, 'channels': 2},
             'source_entries': rows, 'intro_trim': {'applied': False}, 'archive_verified_here': False,
             'archive_sha256': '919d6009b39286e2aadc8cc5eed9d4b15cc207be9f6bd3a3b7852a5be1065925',
             'source_release': 'tem8-listening-raw', 'source_asset': 'default.zip'}
        if year == 2022:
            p.update(archive_sha256=None, source_release='tem8-listening-raw-supplement',
                     source_asset=rows[0]['file'], source_supplement_sha256=rows[0]['sha256'],
                     source_origin=rows[0]['origin'],
                     source_supplement_registration_sha256=pub.sha(pub.D / '核验/2022-补充音源.json'))
        return p

    def child(self, ident, root):
        folder = root / ident
        folder.mkdir(parents=True)
        name = pub.asset('intensive', ident)
        video = folder / name
        video.write_bytes(b'\x00\x00\x00\x20ftyp' + (ident.encode() + b'TEST-ONLY') * 8)
        shot = folder / 'evidence/已审截图/shots/test.png'
        shot.parent.mkdir(parents=True)
        shot.write_bytes(b'TEST-ONLY-NOT-A-REAL-SCREENSHOT-' + ident.encode())
        fp = pub.hash_json({'fixture_id': ident})
        row = {'status': 'approved', 'payload_sha256': fp, 'shots': {'shots/test.png': pub.sha(shot)},
               'inputs': {'test-only': 'a' * 64}, 'render_sources': {'test-only': 'b' * 64},
               'evidence': '仅用于临时离线测试，不是实际审批或成品'}
        self.registry[ident] = row
        pub.dump(folder / 'evidence/审核登记.json', row)
        verification = {'ok': True, 'draft': False, 'sha256': pub.sha(video)}
        pub.dump(folder / 'evidence/工作记录/verification.json', verification)
        if ident in pub.INTENSIVE_TWO_STAGE_IDS:
            self.two_stage_schema_fixture(ident, folder / 'evidence/工作记录', video, verification)
        source = self.prep(int(ident[:4]))
        pub.dump(folder / 'evidence/工作记录/源音频准备.json', source)
        meta = {'schema': 1, 'id': ident, 'year': int(ident[:4]), 'kind': 'intensive', 'mp4': name,
                'label': 'TEST-ONLY.mp4', 'mp4_bytes': video.stat().st_size, 'mp4_sha256': pub.sha(video),
                'source_sha256': 'c' * 64,
                'source_record': pub.validate_source_preparation(source, int(ident[:4]), 'c' * 64),
                'approval_payload_sha256': fp,
                'verification': {'ok': True, 'draft': False, 'report': 'verification.json'},
                'evidence': {p.relative_to(folder).as_posix(): pub.sha(p)
                             for p in sorted((folder / 'evidence').rglob('*')) if p.is_file()}}
        pub.dump(folder / 'meta.json', meta)
        pub.validate_stage(folder, 'intensive', ident, fp)
        return meta

    def two_stage_schema_fixture(self, ident, work, video, report):
        """完整结构夹具，全部写临时目录；不代表真实PCM/媒体检验或任何生产审批。"""
        sample_rate, channels, duration, frames = 44100, 2, 10.0, 300
        input_sha = pub.hash_json({'offline-schema-fixture': ident})
        pcm_sha, source_sha = 'd' * 64, 'c' * 64
        adapter_sha = pub.sha(HERE / '精听两步编码.py')
        base_fingerprint = pub.hash_json({'test-only-base': ident})
        fingerprint = pub.hash_json({'base_fingerprint': base_fingerprint,
                                    'two_step_adapter_sha256': adapter_sha})
        tm = {'file': 'TEST-ONLY-native.wav', 'duration': duration,
              'sample_rate': sample_rate, 'channels': channels,
              'audio_sha256': pcm_sha, 'source_sha256': source_sha,
              'window': [100, 106.3],
              'protected_source_intervals': [[102, 103]] if ident == '2022-A' else []}
        picture_file = str(work / 'video-only-two-step.mp4')
        picture = ['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(work / 'concat.txt'),
                   '-vf', 'format=yuv420p,fps=30:start_time=0:round=near', '-fps_mode', 'cfr', '-r', '30',
                   '-frames:v', str(frames), '-c:v', 'libx264', '-preset', 'veryfast', '-tune', 'stillimage',
                   '-crf', '18', '-threads', '2', '-pix_fmt', 'yuv420p', '-g', '900', '-x264-params', 'scenecut=0',
                   '-an', '-t', f'{frames / 30:.9f}', '-movflags', '+faststart', picture_file]
        mux = ['ffmpeg', '-y', '-v', 'error', '-i', picture_file, '-i', str(work / 'audio' / tm['file']),
               '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
               '-video_track_timescale', '15360', '-movie_timescale', str(sample_rate), '-movflags', '+faststart', str(video)]
        checks = ['图片时钟全状态首尾及邻帧', '4K 16:9', '30帧恒定/帧数', '声画等长', '原采样率与声道',
                  '原声逐样本核对', '片头1.5秒静音', '片尾至少2秒静音',
                  '逐屏画面与截图一致（每屏中间一帧）', '成品附件大小']
        if tm['protected_source_intervals']:
            checks.append('2022窗口内低电平信号保护段完整保留')
        report.update(id=ident, fingerprint=fingerprint, duration=duration, source_sha256=source_sha,
                      checks=[{'item': item, 'ok': True, 'detail': 'OFFLINE SCHEMA FIXTURE ONLY'} for item in checks])
        records = {
            'verification.json': report,
            'audio/timings.json': {'cet4_male': {ident: tm}},
            'prepared.json': {'draft': False, 'input_sha256': input_sha, 'test_fixture_only': True},
            'audio-precheck.json': {'ok': True, 'raw_exact_before_encoding': True,
                                    'audio_sha256': pcm_sha, 'source_sha256': source_sha,
                                    'sample_rate': sample_rate, 'channels': channels, 'test_fixture_only': True},
            'meta.json': {'id': ident, 'kind': 'text', 'mp4': video.name,
                          'mp4_sha256': pub.sha(video), '原音_sha256': source_sha,
                          'input_sha256': input_sha, 'fingerprint': fingerprint, 'test_fixture_only': True},
            'two-stage-encoding.json': {
                'schema': 1, 'id': ident, 'adapter_sha256': adapter_sha,
                'original_engine_sha256': pub.sha(HERE / '精听.py'),
                'base_fingerprint': base_fingerprint, 'fingerprint': fingerprint,
                'prepared_pcm_sha256': pcm_sha, 'source_sha256': source_sha,
                'mp4_sha256': pub.sha(video), 'sample_rate': sample_rate, 'channels': channels,
                'frames': frames, 'aac_bitrate': '192k', 'picture_argv': picture, 'mux_argv': mux,
                'test_fixture_only': True}}
        for name, value in records.items():
            pub.dump(work / name, value)

    def full(self, year):
        year = m.year_id(year)
        base = self.root / ('fixture-' + year)
        parts, work, final = base / 'parts', base / 'work', self.root / 'art' / year
        children = [self.child(ident, parts) for ident in m.part_ids(year)]
        records = [{'id': r['id'], 'mp4_sha256': r['mp4_sha256'],
                    'approval_payload_sha256': r['approval_payload_sha256'],
                    'source_sha256': r['source_sha256'],
                    'meta_sha256': pub.sha(parts / r['id'] / 'meta.json')} for r in children]
        work.mkdir(parents=True)
        video = work / m.asset(year)
        video.write_bytes(b'\x00\x00\x00\x20ftyp' + b'FULL-YEAR-TEST-ONLY-' + year.encode() * 32)
        report = {'ok': True, 'draft': False, 'sha256': pub.sha(video), 'parts_order': m.part_ids(year),
                  'source_sha256': 'c' * 64,
                  'parts': records, 'engine_sha256': pub.sha(HERE / '整套精听.py'),
                  'video_lossless': True, 'pcm_reconstruction_verified': True,
                  'audio_verified': True, 'av_sync_verified': True}
        pub.dump(work / 'verification.json', report)
        meta = {'schema': 1, 'kind': m.KIND, 'id': year, 'year': int(year), 'mp4': video.name,
                'label': m.label(year), 'mp4_sha256': pub.sha(video), 'mp4_bytes': video.stat().st_size,
                'source_sha256': 'c' * 64, 'source_record': children[0]['source_record'],
                'parts': records,
                'verification': {'ok': True, 'draft': False, 'report': 'verification.json'}}
        pub.dump(work / 'meta.json', meta)
        m.stage(year, parts, work, final)
        return final

    def control(self, **changes):
        value = {'mode': 'complete_intensive_full', 'years': m.YEARS, 'assemble': True,
                 'collect_runs': [], 'reuse_child_releases': []}
        value.update(changes)
        path = self.root / 'control.json'
        pub.dump(path, value)
        return m.load_control(path)

    def update_evidence(self, folder, rel, transform):
        path = folder / rel
        value = pub.read(path)
        transform(value)
        pub.dump(path, value)
        meta = pub.read(folder / 'meta.json')
        meta['evidence'][rel] = pub.sha(path)
        pub.dump(folder / 'meta.json', meta)

    def test_01_complete_scope_positive_and_negatives(self):
        self.assertEqual(len(self.control()['years']), 15)
        for change in [{'mode': 'complete'}, {'years': m.YEARS[:-1]}, {'years': m.YEARS + [2020]},
                       {'years': m.YEARS[:-1] + [2009]}, {'years': ['2009-A']},
                       {'intensive': ['2009-A']}, {'exam': [2009]}, {'assemble': 'false'},
                       {'assemble_years': [2009, 2009]}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.control(**change)

    def test_02_real_stage_structure_and_corruption(self):
        folder = self.full(2009)
        self.assertEqual(m.validate_stage(folder, 2009)['kind'], 'intensive_full')
        before = pub.read(folder / 'meta.json')
        for field, bad in [('kind', 'intensive'), ('id', '2009-A'), ('year', 2010),
                           ('mp4', '../escape.mp4'), ('label', '2009年 专八听力 A.mp4'),
                           ('assembly_payload_sha256', '0' * 64), ('mp4_bytes', pub.LIMIT),
                           ('parts', list(reversed(before['parts']))), ('source_sha256', 'e' * 64)]:
            altered = copy.deepcopy(before)
            altered[field] = bad
            pub.dump(folder / 'meta.json', altered)
            with self.subTest(field=field), self.assertRaises((ValueError, KeyError)):
                m.validate_stage(folder, 2009)
        pub.dump(folder / 'meta.json', before)
        (folder / before['mp4']).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            m.validate_stage(folder, 2009)

    def test_03_measurement_flags_cannot_be_replaced_by_global_ok(self):
        folder = self.full(2009)
        rel = 'evidence/assembly/verification.json'
        for key in ['video_lossless', 'pcm_reconstruction_verified', 'audio_verified', 'av_sync_verified']:
            self.update_evidence(folder, rel, lambda d: d.update({key: False}))
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.validate_stage(folder, 2009)
            self.update_evidence(folder, rel, lambda d: d.update({key: True}))
        self.update_evidence(folder, rel, lambda d: d.update(parts_order=['2009-B1', '2009-A', '2009-B2']))
        with self.assertRaises(ValueError):
            m.validate_stage(folder, 2009)

    def test_04_current_child_approval_and_actual_png_are_required(self):
        folder = self.full(2009)
        row = self.registry['2009-A']
        row['shots'] = {'shots/test.png': 'f' * 64}
        with self.assertRaises(ValueError):
            m.validate_stage(folder, 2009)
        self.registry['2009-A']['payload_sha256'] = 'e' * 64
        with self.assertRaises(ValueError):
            m.validate_stage(folder, 2009)

    def test_05_missing_year_stops_before_any_release_write(self):
        self.full(2009)
        # 全15当前审批存在，但只交一份完整视频，禁止冒称全批。
        for year in m.YEARS[1:]:
            for ident in m.part_ids(year):
                self.registry[ident] = {'payload_sha256': pub.hash_json(ident)}
        with patch.object(m, 'recover'), patch.object(m, 'branch_guard'), \
             patch.object(pub, 'ensure_release') as write, patch.object(pub, 'gh') as network:
            with self.assertRaises(ValueError):
                m.publish(self.control(), self.root / 'art', self.root / 'out')
            write.assert_not_called()
            network.assert_not_called()

    def test_06_child_stage_cannot_replace_full_year(self):
        folder = self.root / 'art'
        self.child('2009-A', folder)
        self.assertIsNone(m.find_stage(folder, 2009, required=False))
        with self.assertRaises(ValueError):
            m.find_stage(folder, 2009)

    def test_07_cached_readiness_checks_server_sha_and_current_evidence(self):
        folder = self.full(2009)
        meta = pub.read(folder / 'meta.json')
        fp = meta['assembly_payload_sha256']
        vn = m.asset(2009, fp, meta['mp4_sha256'])
        en = m.evidence_asset(2009, fp, meta['mp4_sha256'])
        archive = self.root / en
        pub.zip_files(archive, [('meta.json', folder / 'meta.json')] + [(n, folder / n) for n in meta['evidence']])
        remote = {'assets': [{'name': vn, 'digest': 'sha256:' + meta['mp4_sha256'], 'size': meta['mp4_bytes']},
                             {'name': en, 'digest': 'sha256:' + pub.sha(archive), 'size': archive.stat().st_size}]}
        def gh(*args, **kwargs):
            self.assertEqual(args[:2], ('release', 'download'))
            shutil.copyfile(archive, Path(args[args.index('-D') + 1]) / en)
        with patch.object(pub, 'gh', side_effect=gh):
            self.assertTrue(m.cached_ready(remote, 2009, self.payload(2009)))
            remote['assets'][0]['digest'] = 'sha256:' + '0' * 64
            self.assertFalse(m.cached_ready(remote, 2009, self.payload(2009)))

    def test_08_final_fifteen_years_pack_and_download_roundtrip(self):
        for year in m.YEARS:
            self.full(year)
        remote = {}
        writes = []
        def upload(tag, path, label=None):
            self.assertEqual(tag, m.FINAL_TAG)
            path = Path(path)
            remote[path.name] = {'bytes': path.read_bytes(), 'digest': 'sha256:' + pub.sha(path),
                                 'size': path.stat().st_size, 'label': label}
        def release(tag):
            self.assertEqual(tag, m.FINAL_TAG)
            return {'assets': [{'name': n, **{k: r[k] for k in ['digest', 'size', 'label']}} for n, r in remote.items()]}
        def gh(*args, **kwargs):
            if args[:2] == ('release', 'edit'):
                writes.append(args)
                return ''
            self.assertEqual(args[:2], ('release', 'download'))
            filename = args[args.index('-p') + 1]
            (Path(args[args.index('-D') + 1]) / filename).write_bytes(remote[filename]['bytes'])
            return ''
        with patch.object(m, 'recover'), patch.object(m, 'branch_guard'), \
             patch.object(pub, 'ensure_release', side_effect=lambda *args: writes.append(args)), \
             patch.object(pub, 'upload', side_effect=upload), patch.object(pub, 'release', side_effect=release), \
             patch.object(pub, 'gh', side_effect=gh):
            out = self.root / 'out'
            m.publish(self.control(), self.root / 'art', out)
        manifest = pub.read(out / 'TEM8-manifest.json')
        self.assertEqual(manifest['delivery_videos'], 15)
        self.assertEqual(len(manifest['videos']), 15)
        self.assertEqual({r['kind'] for r in manifest['videos']}, {'intensive_full'})
        self.assertEqual(len([n for n in remote if n.endswith('.mp4')]), 15)
        names = []
        for z in out.glob('TEM8-listening-intensive-*-part*.zip'):
            with zipfile.ZipFile(z) as archive:
                names.extend(archive.namelist())
        self.assertEqual(set(names), {'专八听力精听/' + m.label(y) for y in m.YEARS})
        self.assertEqual(len(names), 15)
        self.assertEqual(pub.read(out / 'TEM8-intensive-download-verification.json')['videos'], 15)
        self.assertIn('TEM8-intensive-download-verification.json', remote)
        self.assertTrue(writes)

    def test_09_download_member_sha_and_archive_corruption_rejected(self):
        p = self.root / 'video.mp4'
        p.write_bytes(b'TEST-ONLY')
        z = self.root / 'good.zip'
        name = '专八听力精听/2009年 专八听力 精听.mp4'
        pub.zip_files(z, [(name, p)])
        m.verify_download(z, z, {name: pub.sha(p)})
        with self.assertRaises(ValueError):
            m.verify_download(z, z, {name: 'f' * 64})
        with self.assertRaises(ValueError):
            m.verify_download(z, z, {'专八听力精听/2009-A.mp4': pub.sha(p)})
        bad = self.root / 'bad.zip'
        bad.write_bytes(z.read_bytes() + b'CORRUPT')
        with self.assertRaises(ValueError):
            m.verify_download(z, bad, {name: pub.sha(p)})

    def test_10_max_parallel_and_no_child_rendering(self):
        text = m.WORKFLOW.read_text('utf-8')
        self.assertIn('max-parallel: 15', text)
        self.assertIn("paths: ['.github/tem8-listening-intensive-full.json']", text)
        for forbidden in ['/tools/精听.py ', '/tools/考试视频.py ', 'spacy', 'cet6-chalk-env', 'workflow_dispatch']:
            self.assertNotIn(forbidden, text)
        self.assertIn('整套精听.py build', text)
        self.assertIn('独立重读gate/PCM/NAL/PTS/AAC并调用verify', text)
        self.assertIn('整套精听发布.py store', text)

    def test_11_publishing_changes_do_not_invalidate_audio_video_payload(self):
        self.full(2009)
        actual = self.actual_payload
        # 使用独立临时组装源码测指纹，不写仓库或任何已审输入。
        deps = self.root / 'producer-code'
        deps.mkdir()
        (deps / '整套精听.py').write_text('# producer one\n')
        (deps / '原音准备.py').write_text('# source preparation\n')
        (deps / '精听数据.py').write_text('# imported audio protection contract\n')
        with patch.object(m, 'HERE', deps), patch.object(pub, 'relative', side_effect=lambda p: p.name):
            first = actual(2009)
            self.assertEqual(set(first['assembly_sources']), {'整套精听.py', '原音准备.py', '精听数据.py'})
            self.assertNotIn('整套精听发布.py', first['assembly_sources'])
            self.assertNotIn(m.WORKFLOW.name, first['assembly_sources'])
            (deps / '整套精听.py').write_text('# producer two\n')
            self.assertNotEqual(pub.hash_json(first), pub.hash_json(actual(2009)))

    def test_12_old_engine_or_unbound_source_report_cannot_be_restamped(self):
        folder = self.full(2009)
        rel = 'evidence/assembly/verification.json'
        original = pub.read(folder / rel)
        for field, bad in [('engine_sha256', '0' * 64), ('source_sha256', 'e' * 64),
                           ('parts', [{**original['parts'][0], 'mp4_sha256': 'f' * 64},
                                      *original['parts'][1:]])]:
            self.update_evidence(folder, rel, lambda d: d.update({field: bad}))
            with self.subTest(field=field), self.assertRaises(ValueError):
                m.validate_stage(folder, 2009)
            self.update_evidence(folder, rel, lambda d: d.update(copy.deepcopy(original)))


if __name__ == '__main__':
    if '--technical-report' in __import__('sys').argv:
        parser = argparse.ArgumentParser()
        parser.add_argument('--technical-report', type=Path, required=True)
        parser.add_argument('--out', type=Path, required=True)
        parser.add_argument('--video', type=Path)
        args = parser.parse_args()
        print(json.dumps(technical_sample(args.technical_report, args.out, args.video), ensure_ascii=False, indent=2))
    else:
        unittest.main(verbosity=2)
