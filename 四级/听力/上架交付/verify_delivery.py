#!/usr/bin/env python3
"""Verify existing release videos against source digests and inspect all 70 streams."""
import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for data in iter(lambda:f.read(2**20),b''):h.update(data)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-metadata',type=Path,required=True)
    p.add_argument('--video-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    releases=json.loads(args.source_metadata.read_text())
    source=next(r for r in releases if r['tag_name']=='cet4-listening')
    assets={a['name']:a for a in source['assets']}
    expected={k:v for k,v in assets.items() if k.endswith('.mp4')}
    seen=set();records=[];packs=[]
    scratch=args.video_dir/'inspect';scratch.mkdir(exist_ok=True)
    for index in range(1,4):
        name=f'cet4-listening-{index}.zip';path=args.video_dir/name
        checksum=digest(path)
        assert path.stat().st_size==assets[name]['size']
        assert 'sha256:'+checksum==assets[name]['digest'],name
        with ZipFile(path) as z:
            items=z.infolist();assert len(items)==[26,26,18][index-1]
            for item in items:
                assert item.flag_bits & 0x800
                m=re.fullmatch(r'四级听力/(\d{4})-(\d{1,2})-([12])(考试|原文)\.mp4',item.filename)
                assert m,item.filename
                year,month,number,kind=m.groups()
                sid=f'{year}{int(month):02}-{number}'
                mode='exam' if kind=='考试' else 'text'
                asset=f'cet4-listening-{sid}-{mode}.mp4'
                assert asset not in seen and asset in expected,asset
                dest=scratch/'inspect.mp4'
                with z.open(item) as src,dest.open('wb') as out:shutil.copyfileobj(src,out)
                # Reading each member to EOF also checks its ZIP CRC.
                got=digest(dest)
                assert expected[asset]['size']==item.file_size
                assert expected[asset]['digest']=='sha256:'+got,asset
                result=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(dest)],capture_output=True,text=True,check=True)
                probe=json.loads(result.stdout)
                vs=[s for s in probe['streams'] if s['codec_type']=='video'];aus=[s for s in probe['streams'] if s['codec_type']=='audio']
                assert len(vs)==1 and len(aus)==1,asset
                assert (vs[0]['width'],vs[0]['height'])==(3840,2160),asset
                duration=float(probe['format']['duration']);assert 600<duration<3600,(asset,duration)
                assert vs[0]['codec_name']=='h264' and aus[0]['codec_name']=='aac'
                seen.add(asset)
                records.append(dict(file=item.filename,source_asset=asset,size=item.file_size,sha256=got,duration_seconds=duration,resolution='3840x2160',video_codec='h264',audio_codec='aac',frame_rate=vs[0]['r_frame_rate']))
                # Retain two real examples for promotional thumbnails, without re-encoding.
                if sid=='202606-2':shutil.copyfile(dest,scratch/f'{mode}.mp4')
                dest.unlink()
        packs.append(dict(file=name,size=path.stat().st_size,sha256=checksum,video_count=len(items)))
    assert seen==set(expected),(len(seen),len(expected))
    assert len(records)==70
    report=dict(checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_release=source['html_url'],sets=35,videos=70,archives=packs,files=records,checks=['Release archive SHA256','UTF-8 filenames','ZIP member CRC','All 70 video SHA256 against published individual assets','Audio and video streams','4K resolution','Plausible duration','H264/AAC codecs'],scope='Structural integrity and source identity checks; this run does not repeat the historical sentence-by-sentence listening audit or fully decode every frame.')
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(dict(videos=70,sets=35,total_bytes=sum(r['size'] for r in records),passed=True),ensure_ascii=False))

if __name__=='__main__':main()
