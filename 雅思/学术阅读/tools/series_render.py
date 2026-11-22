"""Prepare reproducible per-lesson stage evidence and package the native CET media."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile

from lesson import LESSON, PID, PROJECT, TEXT, load, save
from pilot_video import REVIEW, SHOTS, engine, expected_screens, prepare


def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def lock_review():
    content=json.loads((LESSON/'content-review.json').read_text())
    if digest(TEXT)!=content['text_sha256']:
        raise ValueError('Reviewed lesson text changed')
    p=prepare()
    review=json.loads(REVIEW.read_text())
    wanted=expected_screens(p)
    if review['problems'] or len(review['screens'])!=len(wanted)+1:
        raise ValueError('Unresolved screen issues')
    for row,want in zip(review['screens'][1:],wanted):
        if any(row[k]!=want[k] for k in ('en','zh','heads')):
            raise ValueError(row['label'])
    for row in review['screens']:
        if digest(SHOTS/row['file'])!=row['sha256']:
            raise ValueError('Incorrect source screenshot: '+row['label'])
    save(LESSON/'visual-review.json',dict(lesson=PID,screens=len(wanted)+1,review_sha256=digest(REVIEW),
         reading_screens=len(wanted),fingerprint=review['fingerprint'],content_sha256=digest(TEXT),
         basis='Native CET layout bounds, glyph and reference comparisons on every screen.'))


def align():
    p=prepare();t=json.loads((PROJECT/'audio/timings.json').read_text())[engine.VOICE][PID]
    sentences=[s for para in p['paras'] for s in para];cuts=[]
    if len(sentences)!=len(t['sentences']):
        raise ValueError('Sentence count mismatch')
    for i,(s,ts) in enumerate(zip(sentences,t['sentences']),1):
        if ts['text']!=s['en']:
            raise ValueError(f'Audio sentence {i} differs from the approved lesson')
        last=ts['start']
        for j,(lo,hi,zh,_) in enumerate(engine.split_parts(PID,i,s)[1:],2):
            point=engine.switch_time(PROJECT/'audio'/t['file'],ts,s['en'],lo)
            if not last+.3<point<ts['end']-.3:
                raise ValueError(f'Sentence {i} has an invalid internal cut')
            cuts.append(dict(sentence=i,part=j,en=s['en'][lo:hi].strip(),zh=zh,screen_time=point))
            last=point
    save(LESSON/'分屏核对.json',dict(lesson=PID,mp3_sha256=t['certificate']['mp3_sha256'],sentences=len(sentences),
        reading_screens=len(sentences)+len(cuts),cuts=cuts))


def package(dest):
    original,=list((PROJECT/'最终视频').glob('*.mp4'))
    native,=list((PROJECT/'样片/成品核查').glob('*_核查.json'))
    checks=json.loads(native.read_text());ending=json.loads((dest/'ending.json').read_text());pdf=json.loads((dest/'pdf-proof.json').read_text())
    if not checks['ok'] or not all(c['ok'] for c in checks['checks']) or not ending['desktop_html5_playback']['ended']:
        raise ValueError('Media tests incomplete')
    presentation=json.loads(REVIEW.read_text())['screens']
    if len(presentation)!=pdf['pages'] or pdf['bytes']>20_000_000:
        raise ValueError('PDF does not cover all screens within its size limit')
    receipt=dict(lesson=PID,book=int(PID[1:PID.index('T')]),run=os.environ.get('GITHUB_RUN_ID'),video_sha256=digest(original),
                 pdf_sha256=digest(dest/'Reading-notes.pdf'),pdf_bytes=pdf['bytes'],pages=pdf['pages'],
                 video_seconds=checks['duration'],video_bytes=original.stat().st_size,content_sha256=digest(TEXT))
    meta=json.loads((LESSON/'篇目信息.json').read_text())
    receipt['title']=meta['title'];receipt['title_zh']=meta['title_zh']
    save(dest/'verification.json',dict(**checks,ending=ending,pdf=pdf,receipt=receipt))
    save(dest/f'{PID}-receipt.json',receipt)
    package=dest/f'{PID}.zip'
    with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        z.write(original,PID+'.mp4');z.write(dest/'Reading-notes.pdf',PID+'.pdf');z.write(dest/'verification.json','verification.json')
        for name in ('双语精读.tsv','篇目信息.json','content-review.json','分屏核对.json','visual-review.json'):
            file=LESSON/name
            if file.is_file():z.write(file,'source/'+name)
    with zipfile.ZipFile(package) as z:
        if z.testzip() is not None:raise ValueError('Invalid release archive')
    print(PID,receipt['video_seconds'],receipt['pages'],receipt['pdf_bytes'],flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['lock','align','package']);ap.add_argument('--out',type=Path)
    a=ap.parse_args()
    if a.stage=='lock':lock_review()
    elif a.stage=='align':align()
    else:package(a.out)
