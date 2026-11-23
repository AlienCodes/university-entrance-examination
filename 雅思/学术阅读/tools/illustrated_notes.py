"""Export the same screens that actually play in a finished illustrated reading."""
import argparse
import json
from pathlib import Path

from compact_notes import write_compact
from illustration_stage import POLICY, digest, illustration
from reading_notes import video_images


def export(movie, receipt, output):
    output=Path(output)
    checked=json.loads(receipt.read_text(encoding='utf-8'))
    pages=checked['screens']
    if (checked['policy']!=POLICY or not checked['full_movie'] or digest(movie)!=checked['video_sha256']
        or checked['illustration_sha256']!=illustration(checked['lesson'])
        or pages[1]!=dict(page=2,screen='篇目插图',frame=60)):
        raise ValueError('The handout must come from the verified illustrated movie')
    result=write_compact(video_images(movie,pages,checked['width'],checked['height']),output,
                         checked['lesson']+' · 逐屏精读')
    result.update(lesson=checked['lesson'],video_sha256=checked['video_sha256'],
                  illustration_sha256=checked['illustration_sha256'],sha256=digest(output))
    evidence=output.with_suffix('.slides.json')
    partial=evidence.with_suffix('.partial')
    partial.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    partial.replace(evidence)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('movie','receipt','output'):
        parser.add_argument(name,type=Path)
    a=parser.parse_args()
    print(json.dumps(export(a.movie,a.receipt,a.output),ensure_ascii=False))
