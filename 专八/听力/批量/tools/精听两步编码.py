"""独立精听两步编码入口；所有非编码阶段和成品严检仍调用原精听引擎。

命令行参数与精听.py相同。调度范围由外部审批与工作流决定，不在此硬编码单元。
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path: sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('tem8_original_intensive_for_two_step', HERE / '精听.py')
E = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = E
spec.loader.exec_module(E)
BASE_FINGERPRINT = E.fingerprint


def fingerprint(m, p, tm):
    bound = {'base_fingerprint': BASE_FINGERPRINT(m, p, tm),
             'two_step_adapter_sha256': E.sha(Path(__file__))}
    return hashlib.sha256(json.dumps(bound, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def encode(m, p, tm, out, input_file, draft=False):
    E.validate(json.loads(Path(input_file).read_text('utf-8')), draft)
    assert draft or not json.loads((out / 'prepared.json').read_text())['draft'], '未审预览不得生成正式成品'
    E.cached_check(m, p, tm, out)
    if not draft:
        approval = json.loads((out / 'approved-screens.json').read_text())
        assert approval['fingerprint'] == fingerprint(m, p, tm) and approval['screens_sha256'] == E.sha(out / 'screens.json'), '缺少当前截图核对登记'
    s = json.loads((out / 'states.json').read_text())
    frames = round(tm['duration'] * E.FPS)
    listing = E.concat_listing(s, frames, out)
    E.fast_clock(m, p, tm, out, s, frames, listing)
    E.clock.require_pass(out / 'clock-fast.mp4', s, out / 'shots', frames,
                         out / 'clock-precheck.json', E.clock_sources(m, p, tm, out))
    mp4 = out / (('技术预览_译注未定稿_' if draft else '') + m.video_name(p))
    picture = out / 'video-only-two-step.mp4'
    pcm = out / 'audio' / tm['file']
    assert E.sha(pcm) == tm['audio_sha256'], '准备原音改变，须重新预检'
    picture_cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing),
                   '-vf', 'format=yuv420p,fps=30:start_time=0:round=near', '-fps_mode', 'cfr', '-r', str(E.FPS),
                   '-frames:v', str(frames), '-c:v', 'libx264', '-preset', 'veryfast', '-tune', 'stillimage',
                   '-crf', '18', '-threads', os.environ.get('TEM8_THREADS', '2'), '-pix_fmt', 'yuv420p',
                   '-g', '900', '-x264-params', 'scenecut=0', '-an', '-t', f'{frames / E.FPS:.9f}',
                   '-movflags', '+faststart', str(picture)]
    subprocess.run(picture_cmd, check=True)
    mux_cmd = ['ffmpeg', '-y', '-v', 'error', '-i', str(picture), '-i', str(pcm),
               '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac',
               '-b:a', tm.get('aac_bitrate', '192k'), '-video_track_timescale', '15360',
               '-movie_timescale', str(math.lcm(tm['sample_rate'], E.FPS)), '-movflags', '+faststart', str(mp4)]
    subprocess.run(mux_cmd, check=True)
    E.dump(out / 'two-stage-encoding.json', {
        'schema': 1, 'id': p['id'],
        'adapter_sha256': E.sha(Path(__file__)), 'original_engine_sha256': E.sha(HERE / '精听.py'),
        'fingerprint': fingerprint(m, p, tm), 'base_fingerprint': BASE_FINGERPRINT(m, p, tm),
        'picture_argv': picture_cmd, 'mux_argv': mux_cmd,
        'prepared_pcm_sha256': E.sha(pcm), 'mp4_sha256': E.sha(mp4), 'source_sha256': tm['source_sha256'], 'frames': frames,
        'sample_rate': tm['sample_rate'], 'channels': tm['channels'], 'aac_bitrate': tm.get('aac_bitrate', '192k'),
        'video_encoding': 'one veryfast/crf18/g900/scenecut0 encode; stream copy at mux',
        'audio_encoding': 'one AAC encode from prepared FLOAT PCM; native sample rate and channels'})
    r = E.verify(m, p, tm, out, mp4, draft)
    if draft:
        print(f'{p["id"]}: 仅技术预览（未定稿，不得发布） {mp4}', flush=True)
        return
    E.dump(out / 'meta.json', {'id': p['id'], 'year': p['year'], 'kind': 'text', 'mp4': mp4.name, 'label': mp4.name,
                              'mp4_bytes': r['bytes'], 'mp4_sha256': r['sha256'], '原音_sha256': tm['source_sha256'],
                              'input_sha256': E.sha(input_file), 'fingerprint': r['fingerprint'], '成品核查': '全部通过',
                              '原音保护登记_sha256': (tm.get('audio_protection') or {}).get('registration_sha256')})
    print(f'{p["id"]}: 正式成品核验通过 {mp4}', flush=True)


# 仅替换本入口进程的函数，不更改原引擎文件或其他入口的运行行为。
E.fingerprint = fingerprint
E.encode = encode


if __name__ == '__main__':
    E.main()
