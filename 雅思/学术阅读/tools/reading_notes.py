"""Export one full-bleed, lossless PDF page from the middle of each final video screen."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import img2pdf
import pymupdf
from PIL import Image
from lesson import LESSON, PID, PROJECT, save

FPS = 30
PAGE = (960, 540)


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


def verify_pdf(filename, records, dimensions):
    with pymupdf.open(filename) as pdf:
        if len(pdf) != len(records):
            raise ValueError('PDF page count differs from the screen count')
        for page,record in zip(pdf,records):
            images = page.get_images(full=True)
            if len(images) != 1 or page.get_text().strip() or tuple(page.rect)[2:] != PAGE:
                raise ValueError(f"Unexpected PDF content or page size on page {record['page']}")
            xref = images[0][0]
            boxes = page.get_image_rects(xref)
            if len(boxes) != 1 or max(abs(a-b) for a,b in zip(boxes[0],page.rect)) > .01:
                raise ValueError(f"Page {record['page']} is cropped or contains margins")
            pix = pymupdf.Pixmap(pdf,xref)
            if (pix.width,pix.height) != dimensions or pix.n != 3 or hashlib.sha256(pix.samples_mv).hexdigest() != record['rgb_sha256']:
                raise ValueError(f"Page {record['page']} pixels differ from its source frame")


def write_pages(frames, output, dimensions):
    records = []
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        tmp = Path(tmp)
        images = []
        for im,entry in frames:
            record = dict(entry)
            if im.size != dimensions or im.mode != 'RGB':
                raise ValueError(f'Unexpected source image on page {len(images)+1}')
            record['rgb_sha256'] = hashlib.sha256(im.tobytes()).hexdigest()
            path = tmp/f"page-{record['page']:03}.png"
            im.save(path,format='PNG',compress_level=3)
            im.close()
            images.append(str(path))
            records.append(record)
        if not images:
            raise ValueError('No video screens')
        candidate = tmp/'screens.pdf'
        with candidate.open('wb') as dest:
            img2pdf.convert(*images,outputstream=dest,engine=img2pdf.Engine.internal,
                            layout_fun=img2pdf.get_layout_fun(pagesize=PAGE,fit=img2pdf.FitMode.exact),
                            title='剑桥雅思20 · The kākāpō · 逐屏精读',nodate=True)
        verify_pdf(candidate,records,dimensions)
        os.replace(candidate,output)
    return records


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
    records = write_pages(video_images(video,pages,*size),output,size)
    save(proof,{'pages':len(records),'source':'final_mp4','pixel_dimensions':size,'layout':'16:9, full bleed',
                'rgb_pixels_identical_on_every_page':True,'frames':records})
    print(f'{len(records)} pages, all full-frame pixels match the final MP4',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('video',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('proof',type=Path)
    parser.add_argument('--timings',type=Path,default=PROJECT/'audio/timings.json')
    a=parser.parse_args()
    main(a.video,a.output,a.proof,a.timings)
