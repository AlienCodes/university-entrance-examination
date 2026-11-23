"""Insert the passage illustration between the existing title and narration."""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from illustration_audio import pad

import numpy as np

FPS = 30
TITLE = 45
PLATE = 30
RATE = 16000
ART = Path(__file__).resolve().parents[1] / '导入插图'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def streams(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(path)
    ]))['streams']


def raw_audio(path, seconds):
    data = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:a:0',
        '-t', str(seconds), '-ac', '1', '-ar', str(RATE), '-f', 'f32le', '-'
    ])
    return np.frombuffer(data, dtype='<f4')


def check_audio(core, movie, frames):
    seconds = frames / FPS
    count = round(seconds * RATE)
    original = raw_audio(core, seconds)[:count]
    changed = raw_audio(movie, seconds + 1)[:count + RATE]
    if len(original) != count or len(changed) != count + RATE:
        raise ValueError('Incomplete decoded audio')
    if np.max(np.abs(changed[:RATE])) >= .003:
        raise ValueError('Unexpected sound before the shifted original audio')
    after = changed[RATE:]
    width = RATE // 40
    max_db, min_correlation, n = 0., 1., 0
    for start in range(0, count - width + 1, 40 * width):
        length = min(40, (count - start) // width) * width
        a = original[start:start+length].reshape(-1, width).astype('float64')
        b = after[start:start+length].reshape(-1, width).astype('float64')
        left, right = np.mean(a*a, axis=1), np.mean(b*b, axis=1)
        # Also check newly audible windows from formerly silent sections.
        voiced = np.maximum(left, right) > 1.e-6
        if not np.any(voiced):
            continue
        corr = (np.mean(a*b, axis=1) / np.sqrt((left+1.e-20)*(right+1.e-20)))[voiced]
        delta = np.abs(10*np.log10((left[voiced]+1.e-20)/(right[voiced]+1.e-20)))
        min_correlation = min(min_correlation, float(np.min(corr)))
        max_db = max(max_db, float(np.max(delta)))
        n += int(np.sum(voiced))
        if np.min(corr) < .93 or np.max(delta) > 1.6:
            raise ValueError(f'Audio differs near {1+start/RATE:.3f}s: correlation {min(corr):.4f}, level {max(delta):.2f} dB')
    if n == 0:
        raise ValueError('No speech in comparison')
    return dict(verified_voiced_windows=n, window_ms=25, offset_samples=RATE,
                minimum_correlation=round(min_correlation, 6), max_level_difference_db=round(max_db, 4))


def raw_frames(path, count, width, height):
    # Use the production geometry for the artwork and both masters before comparison.
    filters = f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},scale=128:72:flags=area,format=rgb24'
    return ['ffmpeg','-nostdin','-v','error','-xerror','-threads','2','-i',str(path),
            '-map','0:v:0','-an','-filter_threads','1','-vf',filters,
            '-frames:v',str(count),'-c:v','rawvideo','-threads','1','-f','rawvideo','-']


@contextmanager
def decoding(path, count, width, height):
    with subprocess.Popen(raw_frames(path,count,width,height), stdout=subprocess.PIPE) as proc:
        try:
            yield proc.stdout
            if proc.stdout.read(1) or proc.wait():
                raise ValueError(f'Incomplete or unexpected decoded frames in {path}')
        finally:
            if proc.poll() is None:
                proc.kill()


def picture(stream):
    data = stream.read(128 * 72 * 3)
    if len(data) != 128 * 72 * 3:
        raise ValueError('A frame is missing from the encoded video')
    return np.frombuffer(data,dtype='uint8').astype('int16')


def check_pictures(core, movie, art, count, width, height):
    plate = np.frombuffer(subprocess.check_output(raw_frames(art,1,width,height)), dtype='uint8').astype('int16')
    max_error = {'title': 0., 'illustration': 0., 'reading': 0.}
    with decoding(core,count,width,height) as before, decoding(movie,count+PLATE,width,height) as after:
        for i in range(count+PLATE):
            group = 'title' if i < TITLE else 'illustration' if i < TITLE+PLATE else 'reading'
            expected = plate if group == 'illustration' else picture(before)
            displayed = picture(after)
            diff = float(np.mean(np.abs(expected-displayed)))
            if diff > 4.0:
                raise ValueError(f'Frame {i} differs from the expected {group} picture ({diff:.2f}/255)')
            if i in (TITLE-1, TITLE+PLATE) and np.mean(np.abs(displayed-plate)) < 12:
                raise ValueError(f'The title/reading transition at frame {i} is ambiguous')
            max_error[group] = max(diff, max_error[group])
    return {k:round(v,4) for k,v in max_error.items()}


def encode(core, art, sound, output, count, width, height, threads):
    scale = f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,format=yuv420p'
    graphs = [
        f'[0:v]{scale},split=2[head][body]',
        f'[head]trim=end_frame={TITLE},setpts=PTS-STARTPTS[a]',
        f'[1:v]{scale},trim=end_frame={PLATE},setpts=PTS-STARTPTS[b]',
        f'[body]trim=start_frame={TITLE}:end_frame={count},setpts=PTS-STARTPTS[c]',
        '[a][b][c]concat=n=3:v=1:a=0,settb=1/30,setpts=N[v]'
    ]
    seconds = (count+PLATE)/FPS
    force = sorted({0., 1.5, 2.5, max(2.5,seconds-4), max(2.5,seconds-2)})
    subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-y','-threads',str(threads),'-t',f'{count/FPS:.9f}',
        '-i',str(core),'-loop','1','-framerate','30','-t','1','-i',str(art),'-i',str(sound),'-filter_complex_threads',str(min(threads,3)),
        '-filter_complex',';'.join(graphs),'-map','[v]','-map','2:a:0','-r','30','-fps_mode','cfr',
        '-c:v','libx264','-preset','veryfast','-crf','16','-threads',str(threads),'-pix_fmt','yuv420p',
        '-force_key_frames',','.join(f'{t:.6f}' for t in force),'-video_track_timescale','15360',
        '-c:a','copy','-movie_timescale','48000','-use_editlist','1','-movflags','+faststart',str(output)],check=True)


def build(pid, core, output, proof, excerpt=None, width=None, threads=3):
    art = ART/'插画'/(pid+'.webp')
    if core.resolve() == output.resolve():
        raise ValueError('Input and output must be different files')
    sv,sa = streams(core)
    if (sv['avg_frame_rate'],sv['codec_name'],sa['codec_name'],sa['sample_rate']) != ('30/1','h264','aac','48000'):
        raise ValueError('Unexpected core stream format')
    src_count = int(sv['nb_frames'])
    count = src_count if excerpt is None else min(src_count,round(excerpt*FPS))
    width = width or int(sv['width'])
    height = width*9//16
    if count < (TITLE+FPS) or height%2 or width*9!=height*16:
        raise ValueError('Invalid size or duration')
    output.parent.mkdir(parents=True,exist_ok=True)
    pending=output.with_suffix('.partial.mp4')
    with tempfile.TemporaryDirectory(dir=output.parent) as td:
        sound=Path(td)/'shifted.m4a'
        pad(core,sound,count*(48000//FPS))
        encode(core,art,sound,pending,count,width,height,threads)
    v,a = streams(pending)
    length = (count+PLATE)/FPS
    if (int(v['nb_frames'])!=count+PLATE or v['avg_frame_rate']!='30/1'
        or (int(v['width']),int(v['height']))!=(width,height)
        or any(abs(float(s['start_time']))>.001 or abs(float(s['duration'])-length)>.002 for s in (v,a))):
        raise ValueError('Audio/video stream lengths or frame rate disagree')
    rms=check_audio(core,pending,count)
    pictures=check_pictures(core,pending,art,count,width,height)
    receipt=dict(lesson=pid,full_movie=count==src_count,core_sha256=sha(core),illustration_sha256=sha(art),
                 video_sha256=sha(pending),video_bytes=pending.stat().st_size,video_seconds=round(length,6),
                 source_frames=count,frames=count+PLATE,width=width,height=height,plate_start=TITLE,
                 plate_frames=PLATE,first_reading_frame=TITLE+PLATE,frame_errors_255=pictures,audio=rms)
    pending.replace(output)
    proof.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lesson')
    for name in ('core','output','proof'):
        parser.add_argument(name,type=Path)
    parser.add_argument('--excerpt',type=float)
    parser.add_argument('--width',type=int)
    parser.add_argument('--threads',type=int,default=3)
    args=parser.parse_args()
    print(json.dumps(build(args.lesson,args.core,args.output,args.proof,args.excerpt,args.width,args.threads),ensure_ascii=False))
