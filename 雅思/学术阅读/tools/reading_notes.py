"""Export one size-limited, full-bleed PDF page from the middle of each final video screen."""
import argparse
import json
from pathlib import Path
import subprocess

from PIL import Image
from compact_notes import write_compact
from lesson import LESSON, PID, PROJECT, save

FPS = 30


def screen_frames(timing, frame_count, splits):
    changes = {}
    for cut in splits:
        changes.setdefault(cut['sentence'], []).append((cut['part'], cut['screen_time']))
    starts = [(0, '片头')]
    for n, sentence in enumerate(timing['sentences'], 1):
        start = sentence['start'] if n == 1 else timing['sentences'][n-2]['end'] + 0.5
        parts = [start] + [t for _,t in sorted(changes.get(n, []))]
        for j,t in enumerate(parts, 1):
            label = f'第 {n} 句' + (f' 第 {j} 屏' if len(parts) > 1 else '')
            starts.append((round(t * FPS), label))
    pages = []
    for i,(start,label) in enumerate(starts):
        stop = starts[i+1][0] if i+1 < len(starts) else frame_count
        if not 0 <= start < stop <= frame_count:
            raise ValueError(f'Invalid interval for {label}: {start}–{stop}')
        pages.append({'page':i+1,'screen':label,'frame':(start+stop)//2})
    return pages


def video_images(video, pages, width, height):
    expression = '+'.join(f"eq(n\\,{p['frame']})" for p in pages)
    cmd = ['ffmpeg','-nostdin','-v','error','-xerror','-i',str(video),'-map','0:v:0','-an',
           '-vf','select='+expression+',format=rgb24','-fps_mode','passthrough','-f','rawvideo','pipe:1']
    with subprocess.Popen(cmd,stdout=subprocess.PIPE) as proc:
        try:
            size = width * height * 3
            for entry in pages:
                data = proc.stdout.read(size)
                if len(data) != size:
                    raise ValueError(f"MP4 missing decoded frame for page {entry['page']}")
                yield Image.frombytes('RGB',(width,height),data),entry
            if proc.stdout.read(1) or proc.wait() != 0:
                raise RuntimeError('Unexpected decoded frame count or incomplete video')
        finally:
            if proc.poll() is None:
                proc.kill()


def main(video, output, proof, timings):
    probe = subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-of','json',str(video)])
    v = json.loads(probe)['streams'][0]
    size = (int(v['width']),int(v['height']))
    if size != (3840,2160) or v['avg_frame_rate'] != '30/1':
        raise ValueError('Expected the verified 4K/30 master')
    timing = json.loads(timings.read_text())['cet4_male'][PID]
    splits = json.loads((LESSON/'分屏核对.json').read_text())['cuts']
    pages = screen_frames(timing,int(v['nb_frames']),splits)
    review = json.loads((PROJECT/'样片/review.json').read_text())
    if [x['screen'] for x in pages] != [x['label'] for x in review['screens']]:
        raise ValueError('PDF sequence differs from the approved video screens')
    info = write_compact(video_images(video,pages,*size),output,f'{PID} · 逐屏精读')
    save(proof,info)
    print(f"{info['pages']} screens, {info['bytes']:,} bytes",flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('video',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('proof',type=Path)
    parser.add_argument('--timings',type=Path,default=PROJECT/'audio/timings.json')
    a=parser.parse_args()
    main(a.video,a.output,a.proof,a.timings)
