"""只读真实旧2009-A已审PNG/帧表，复现旧时钟、新时钟和故意错页；不编码正式视频。"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]/'tools'
sys.path.insert(0, str(TOOLS))
import 图片时钟核验 as C


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();stage=args.stage.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    meta=json.loads((stage/'meta.json').read_text())
    assert meta['id']=='2009-A' and meta['kind']=='intensive'
    work=stage/'evidence/工作记录';shots=stage/'evidence/已审截图/shots'
    fr=json.loads((work/'states.json').read_text())
    tm=json.loads((work/'audio/timings.json').read_text())['cet4_male']['2009-A']
    nfr=round(tm['duration']*30)
    inputs=['evidence/工作记录/states.json','evidence/工作记录/audio/timings.json']
    inputs += ['evidence/已审截图/shots/'+k+'.png' for _,k in fr]
    for path in inputs:
        assert C.sha(stage/path)==meta['evidence'][path],path
    sources={'stage_meta_sha256':C.sha(stage/'meta.json'),'source_commit':meta['source_commit'],
             'source_run_id':meta['run_id'],'states_file_sha256':C.sha(work/'states.json'),
             'timings_file_sha256':C.sha(work/'audio/timings.json'),
             'script_sha256':C.sha(__file__)}
    (out/'实际帧表.json').write_text(json.dumps(fr,ensure_ascii=False,indent=2)+'\n')
    summary={'source':sources,'source_mp4_unchanged_sha256':meta['mp4_sha256'],
             'scope':'只读旧stage已审PNG/真实states；只做无音轨诊断，不冒签旧MP4或生成正式成品',
             'states':len(fr),'total_frames':nfr,'modes':{}}
    for mode in ['old-default25','new-explicit30-fpsfilter','wrong-first-page']:
        listing=[]
        for i,((a,key),b) in enumerate(zip(fr,[f for f,_ in fr[1:]]+[nfr])):
            used=fr[1][1] if mode=='wrong-first-page' and i==0 else key
            listing.append(f"file '{shots/(used+'.png')}'")
            if mode!='old-default25':listing.append('option framerate 30')
            listing.append(f'duration {(b-a)/30:.9f}')
        for duration in [True,False]:
            listing.append(f"file '{shots/(fr[-1][1]+'.png')}'")
            if mode!='old-default25':listing.append('option framerate 30')
            if duration:listing.append('duration 1')
        listing_path=out/(mode+'.txt');listing_path.write_text('\n'.join(listing)+'\n')
        video=out/(mode+'.mp4')
        cmd=['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing_path),
             '-vf','scale=480:270'+('' if mode=='old-default25' else ',fps=30:start_time=0:round=near'),
             '-fps_mode','cfr','-r','30','-frames:v',str(nfr),'-c:v','libx264','-preset','ultrafast',
             '-tune','stillimage','-crf','18','-threads','2','-pix_fmt','yuv420p','-g','900',
             '-x264-params','scenecut=0','-an',str(video)]
        print('ENCODE',mode,flush=True);subprocess.run(cmd,check=True)
        report=out/(mode+'-report.json')
        try:
            record=C.check(video,fr,shots,nfr,report,sources)
        except ValueError:
            record=json.loads(report.read_text())
        assert record['status']==('pass' if mode=='new-explicit30-fpsfilter' else 'rejected'),mode
        if mode=='new-explicit30-fpsfilter':
            C.require_pass(video,fr,shots,nfr,report,sources)
        summary['modes'][mode]={'status':record['status'],'failures':len(record.get('failures',[])),
            'probes':record.get('probes'),'max_mean_difference':record.get('max_mean_difference'),
            'report_sha256':C.sha(report),'video_sha256':C.sha(video),'command':cmd}
        print(mode,json.dumps(summary['modes'][mode],ensure_ascii=False),flush=True)
    (out/'真实2009A旧新与错页对照.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
