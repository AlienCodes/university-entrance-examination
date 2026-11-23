"""Export the same screens that actually play in a finished illustrated reading."""
import argparse
import json
from pathlib import Path

from compact_notes import write_compact
from illustration_stage import POLICY, digest
from reading_notes import video_images


def export(movie, receipt, output):
    checked=json.loads(receipt.read_text(encoding='utf-8'))
    pages=checked['screens']
    if (checked['policy']!=POLICY or not checked['full_movie'] or digest(movie)!=checked['video_sha256']
        or pages[1]!=dict(page=2,screen='篇目插图',frame=60)):
        raise ValueError('The handout must come from the verified illustrated movie')
    return write_compact(video_images(movie,pages,checked['width'],checked['height']),output,
                         checked['lesson']+' · 逐屏精读')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('movie','receipt','output'):
        parser.add_argument(name,type=Path)
    a=parser.parse_args()
    print(json.dumps(export(a.movie,a.receipt,a.output),ensure_ascii=False))
