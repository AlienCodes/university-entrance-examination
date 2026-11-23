"""Finish Aiden readings with their verified, passage-specific illustration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unicodedata
import zipfile

from lesson import PROJECT
from release_assets import fetch, inventory, upload as upload_asset

ART = PROJECT/'导入插图'
CACHE = 'ielts-academic-aiden-cache-13-6'
POLICY = 'article-illustration-30-frames-v1'


def read(file):
    return json.loads(file.read_text(encoding='utf-8'))


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC',text).casefold().replace('’',"'").split())


def illustration(pid):
    design = read(ART/'篇目.json')[pid]
    paper = read(PROJECT/'原稿'/(pid+'.json'))
    anchor = design['source']
    text = paper['paragraphs'][anchor['paragraph']-1][anchor['sentence']-1]
    if (design['title'],design['book'],design['test'],design['passage']) != (paper['title'],paper['book'],paper.get('printed_test',paper['test']),paper['passage']) or normalized(anchor['anchor']) not in normalized(text):
        raise ValueError(f'{pid} illustration/source mismatch')
    proof = read(ART/'画面核对.json')[pid]
    asset = ART/'插画'/(pid+'.webp')
    if ((proof['source_paragraph'],proof['source_sentence'])!=(anchor['paragraph'],anchor['sentence'])
        or hashlib.sha256(text.encode('utf-8')).hexdigest()!=proof['source_sentence_sha256']
        or digest(asset)!=proof['sha256'] or not proof['review']):
        raise ValueError(f'{pid} artwork differs from the visually reviewed image')
    return proof['sha256']


def movie_name(pid, core_hash, painted, video_hash):
    return f'{pid}-illustrated-{core_hash[:16]}-{painted[:16]}-{video_hash[:16]}.mp4'


def page_plan(pages, source_frames):
    if not pages or pages[0]['screen']!='片头' or not 0<=pages[0]['frame']<45:
        raise ValueError('The verified title page is missing')
    result=[dict(page=1,screen='片头',frame=pages[0]['frame']),dict(page=2,screen='篇目插图',frame=60)]
    for page in pages[1:]:
        if not 45<=page['frame']<source_frames:
            raise ValueError('Source reading frame outside the video')
        result.append(dict(page=len(result)+1,screen=page['screen'],frame=page['frame']+30))
    if any(a['frame']>=b['frame'] for a,b in zip(result,result[1:])):
        raise ValueError('Duplicate or unsorted lecture screens')
    return result


def checked(pid, core, report, assets):
    painted=illustration(pid)
    current_name=movie_name(pid,core['video_sha256'],painted,report['video_sha256'])
    prior_name=f"{pid}-illustrated-{core['video_sha256'][:16]}-{painted[:16]}.mp4"
    movie=report.get('filename')
    if movie not in (current_name,prior_name):
        raise ValueError(pid+' illustrated file name does not identify this source and picture')
    item=assets.get(movie,{})
    ending=report.get('ending',{})
    required_tail={report['frames']-120,report['frames']-60}
    actual_tail={round(seconds*30) for seconds in ending.get('tail_keyframes',[])}
    audio=report.get('audio',{})
    if (report.get('policy')!=POLICY or report.get('lesson')!=pid or report.get('full_movie') is not True
        or report.get('core_sha256')!=core['video_sha256'] or report.get('illustration_sha256')!=painted
        or report.get('core_material_sha256')!=core['material_sha256']
        or (report['plate_start'],report['plate_frames'],report['first_reading_frame'])!=(45,30,75)
        or report['frames']!=report['source_frames']+30 or (report['width'],report['height'])!=(3840,2160)
        or abs(report['video_seconds']-core['video_seconds']-1)>.002
        or not audio.get('original_aac_packets') or report.get('source_phrases')!=core['verified_phrases']
        or ending.get('decoded_last_three_seconds_frames')!=90 or not ending.get('desktop_html5_playback',{}).get('ended')
        or not required_tail<=actual_tail
        or len(report['screens'])!=core['pages']+1 or report['screens'][1]!=dict(page=2,screen='篇目插图',frame=60)
        or item.get('digest')!='sha256:'+report['video_sha256'] or item.get('size')!=report['video_bytes']):
        raise ValueError(pid+' illustrated master or its remote receipt does not match the current text, picture and audio')
    return item


def cached_movie(pid, core, assets, work):
    receipt=assets.get(pid+'-illustrated.json')
    if not receipt or not receipt.get('digest'):
        return None
    report=read(fetch(receipt,work))
    try:
        return checked(pid,core,report,assets)
    except (ValueError, KeyError, TypeError, IndexError):
        # A changed illustration, replaced source, or missing hosted file needs a fresh render.
        return None


def upload(source_dir, pid):
    from aiden_profile import PAUSE_POLICY
    from check_ending import inspect
    from illustrated_video import build
    painted=illustration(pid)
    assets=inventory(CACHE)
    core=read(fetch(assets[pid+'-receipt.json'],source_dir))
    if core.get('speaker')!='Aiden' or core.get('pause_policy')!=PAUSE_POLICY:
        raise ValueError(pid+' is not the approved Aiden narration')
    if cached_movie(pid,core,assets,source_dir):
        print(pid,'reused checked illustrated master',flush=True)
        return
    receipt=pid+'-illustrated.json'
    core_receipt_digest=assets[pid+'-receipt.json']['digest']
    version=f"{pid}-{core['material_sha256'][:16]}.zip"
    archive=fetch(assets[version],source_dir)
    video=source_dir/(pid+'-core.mp4')
    with zipfile.ZipFile(archive) as z:
        with z.open(pid+'.mp4') as original,video.open('wb') as f:
            shutil.copyfileobj(original,f,1<<20)
        proof=json.loads(z.read('verification.json'))
        voice=json.loads(z.read('source/narration.json'))
    if (proof['receipt']!=core or not proof['ok'] or digest(video)!=core['video_sha256']
        or not voice['mp4_check']['passed'] or voice['mp4_check']['sha256']!=core['video_sha256']
        or voice['mp4_check']['phrases']!=core['verified_phrases']):
        raise ValueError(pid+' failed its source film check')
    outfile=source_dir/(pid+'-illustrated.mp4')
    path=source_dir/receipt
    result=build(pid,video,outfile,path,threads=min(4,os.cpu_count() or 2))
    name=movie_name(pid,core['video_sha256'],painted,result['video_sha256'])
    outfile=outfile.rename(source_dir/name)
    last_end=voice['mp3_check']['checks'][-1]['end']+1
    result.update(policy=POLICY,source_zip_sha256=assets[version]['digest'][7:],core_material_sha256=core['material_sha256'],
                  filename=name,source_phrases=core['verified_phrases'],ending=inspect(outfile,{'narrator':voice['profile'],'sentences':[{'end':last_end}]}),
                  screens=page_plan(proof['pdf']['frames'],result['source_frames']))
    result['screen_source']='decoded_final_mp4'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if name not in assets:
        upload_asset(CACHE,outfile)
    inventory.cache_clear()
    assets=inventory(CACHE)
    checked(pid,core,result,assets)
    if assets[pid+'-receipt.json']['digest']!=core_receipt_digest:
        raise ValueError(pid+' source was updated during rendering')
    with tempfile.TemporaryDirectory(dir=source_dir) as d:
        if digest(fetch(assets[name],Path(d)))!=result['video_sha256']:
            raise ValueError('The downloaded illustrated film does not match')
    upload_asset(CACHE,path,replace=True)
    print(pid,name,result['frames'],'frames checked and remote download verified',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pid')
    parser.add_argument('work',type=Path)
    args=parser.parse_args()
    args.work.mkdir(exist_ok=True,parents=True)
    upload(args.work,args.pid)


if __name__=='__main__':
    main()
