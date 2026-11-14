"""离线正反例仅测试验收器；夹具不是实际视频，不生成媒体PASS。"""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
s = importlib.util.spec_from_file_location('full_finalaudit_tests', HERE / '整套正式Release验收.py')
v = importlib.util.module_from_spec(s)
s.loader.exec_module(v)
H = 'a' * 64


def fixture():
    videos = []
    for y in reversed(v.YEARS):
        videos.append({'schema': 1, 'id': str(y), 'year': y, 'kind': 'intensive_full',
                       'mp4': f'tem8-intensive-full-{y}.mp4', 'label': f'{y}年 专八听力 精听.mp4',
                       'mp4_sha256': H, 'mp4_bytes': 100,
                       'parts': [{'id': f'{y}-{s}', 'mp4_sha256': H, 'source_sha256': H,
                                  'approval_payload_sha256': H} for s in ['A', 'B1', 'B2']],
                       'verification': {'ok': True, 'draft': False}})
    manifest = {'schema': 1, 'kind': 'intensive_full', 'mode': 'complete_intensive_full', 'tag': v.TAG,
                'delivery_videos': 15, 'internal_parts': 45, 'years': v.YEARS, 'videos': videos}
    report = {'tag': v.TAG, 'kind': 'intensive_full', 'mode': 'complete_intensive_full',
              'videos': 15, 'internal_parts': 45, 'years': v.YEARS,
              'server_digest': True, 'download_sha_crc_utf8_member_sha': True,
              'archives': [{'file': 'TEM8-listening-intensive-2009-2024-part01.zip', 'sha256': H, 'bytes': 999}]}
    return manifest, report


results = []


def rejects(name, callback):
    try:
        callback()
    except (ValueError, KeyError, AssertionError):
        results.append({'case': name, 'expected_rejection_observed': True})
    else:
        raise AssertionError('未拦截：' + name)


m, r = fixture()
assert len(v.validate_manifest(m, r)) == 15
for name, mutation in [
    ('45片段冒充15整套', lambda d: d.update(delivery_videos=45)),
    ('虚构2020年', lambda d: d['years'].__setitem__(0, 2020)),
    ('年度重复', lambda d: d['videos'].__setitem__(1, copy.deepcopy(d['videos'][0]))),
    ('缺失年度', lambda d: d['videos'].pop()),
    ('子段跨年', lambda d: d['videos'][0]['parts'][0].update(id='2023-A')),
    ('B1与B2换序', lambda d: d['videos'][0]['parts'].reverse()),
    ('中文名为内部片段', lambda d: d['videos'][0].update(label='2024-B1.mp4')),
    ('子段摘要非法', lambda d: d['videos'][0]['parts'][0].update(mp4_sha256='bad')),
    ('草稿整套', lambda d: d['videos'][0]['verification'].update(draft=True)),
]:
    bad = copy.deepcopy(m); mutation(bad)
    rejects(name, lambda: v.validate_manifest(bad, r))

goodstats = {'ok': True, 'samples': 48000, 'tested_active_seconds': 1,
             'snr_db': 35, 'gain_db': .001, 'max_1second_level_difference_db': .1}
v.validate_stats(goodstats)
for name, field, value in [('SNR不足但全局ok', 'snr_db', 29.999999),
                           ('增益超标', 'gain_db', .0500001),
                           ('逐秒电平超标', 'max_1second_level_difference_db', 1.000001),
                           ('非有限测量', 'snr_db', float('nan'))]:
    bad = {**goodstats, field: value}
    rejects(name, lambda: v.validate_stats(bad))

assets, sums = {}, {}
for video in m['videos']:
    for name, size in [(video['mp4'], 100), (video['mp4'][:-4] + '-evidence.zip', 222)]:
        sums[name] = H
        assets[name] = {'name': name, 'digest': 'sha256:' + H, 'size': size, 'label': video['label'] if name.endswith('.mp4') else None}
for name, size in [('TEM8-manifest.json', 10), ('TEM8-filenames.txt', 20), (r['archives'][0]['file'], 999)]:
    sums[name] = H; assets[name] = {'name': name, 'digest': 'sha256:' + H, 'size': size}
for name in ['SHA256SUMS', v.REPORT_ASSET]:
    assets[name] = {'name': name, 'digest': 'sha256:' + H, 'size': 333}
v.validate_inventory(assets, m['videos'], r['archives'], sums)
rejects('异常额外资产', lambda: v.validate_inventory({**assets, '2024-B1.mp4': {}}, m['videos'], r['archives'], sums))
bad = copy.deepcopy(assets); bad[m['videos'][0]['mp4']]['digest'] = 'sha256:' + 'b' * 64
rejects('服务器与manifest摘要不同', lambda: v.validate_inventory(bad, m['videos'], r['archives'], sums))
rejects('SUMS漏来源证据', lambda: v.validate_inventory(assets, m['videos'], r['archives'],
                                                      {n: h for n, h in sums.items() if n != 'tem8-intensive-full-2024-evidence.zip'}))

with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    path = base / 'bad-evidence.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('meta.json', json.dumps({'evidence': {'../escape': H}}))
        z.writestr('../escape', b'bad')
    rejects('来源ZIP路径越界', lambda: v.extract_evidence(path, base / 'out'))
    path = base / 'extra-evidence.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('meta.json', json.dumps({'evidence': {}}))
        z.writestr('hidden.txt', b'x')
    rejects('来源ZIP隐藏附加文件', lambda: v.extract_evidence(path, base / 'out'))
    path = base / 'bad-whole.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('专八听力精听/2024-B1.mp4', b'not-a-real-video')
    rejects('正式ZIP混入子段', lambda: v.verify_archive(path, m['videos'], (2026, 11, 13, 0, 0, 0)))

record = {'status': 'OFFLINE_SELFTEST_PASSED', 'media_validation_executed': False,
          'media_pass_claimed': False, 'negative_cases': len(results), 'results': results,
          'script_sha256': v.sha(HERE / '整套正式Release验收.py'), 'test_sha256': v.sha(__file__),
          'scope': '仅离线契约/异常反例，不代表实际正式Release或任何媒体已通过。'}
v.dump(HERE / '验收器离线自检.json', record)
print(json.dumps(record, ensure_ascii=False))
