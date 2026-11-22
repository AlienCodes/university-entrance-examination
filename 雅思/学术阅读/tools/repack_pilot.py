"""Repack verified screenshots from the existing pilot MP4 without encoding it again."""
import argparse
import hashlib
import json
from pathlib import Path

from compact_notes import write_compact
from reading_notes import video_images


def main(folder):
    video, = folder.glob('*.mp4')
    report_file = folder/'verification.json'
    report = json.loads(report_file.read_text())
    if not report['ok'] or report['pdf']['source'] != 'final_mp4':
        raise ValueError('Expected verified source frames')
    frames = report['pdf']['frames']
    if len(frames) != 57:
        raise ValueError('The pilot has 57 pages')
    report['pdf'] = write_compact(video_images(video,frames,3840,2160),folder/'Reading-notes.pdf','剑桥雅思20 · 鸮鹦鹉 · 逐屏精读')
    report_file.write_text(json.dumps(report,ensure_ascii=False,indent=1)+'\n')
    names = [video.name,'verification.json','Reading-notes.pdf']
    checks=[]
    for name in names:
        with (folder/name).open('rb') as f:
            checks.append(f"{hashlib.file_digest(f,'sha256').hexdigest()}  {name}\n")
    (folder/'SHA256SUMS').write_text(''.join(checks))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('folder',type=Path)
    main(parser.parse_args().folder)
