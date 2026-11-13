import json,subprocess,hashlib,bisect,time,argparse
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--shots',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--modes',nargs='+',default=['default25','explicit30','fpsfilter30'],choices=['default25','explicit30','fpsfilter30']);args=ap.parse_args();shots=args.shots.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
fr=json.loads((HERE/'2019-真实修复run帧表.json').read_text());nfr=48007;manifest=json.loads((HERE/'2019-真实PNG摘要.json').read_text())
for n,h in manifest.items():assert hashlib.sha256((shots/n).read_bytes()).hexdigest()==h,'必须使用真实已审PNG：'+n
cache=out/'diagnostic-gray-refs.npz'
if cache.exists():
 data=np.load(cache);refs={k:data[k].astype(np.int16) for k in data.files};assert set(refs)=={k for f,k in fr}
else:
 refs={k:np.asarray(Image.open(shots/(k+'.png')).convert('L').resize((480,270)),dtype=np.int16) for f,k in fr};np.savez(cache,**{k:v.astype(np.uint8) for k,v in refs.items()})
frames=[x[0] for x in fr];targets=sorted({x for i,(f,k) in enumerate(fr) for x in [max(0,f-1),f,min(f+1,(frames[i+1] if i+1<len(fr) else nfr)-1),min(f+2,(frames[i+1] if i+1<len(fr) else nfr)-1),(frames[i+1] if i+1<len(fr) else nfr)-1] if 0<=x<nfr})
print('states',len(fr),'targets',len(targets),flush=True)
ranges=[]
for n in targets:
 if ranges and n==ranges[-1][1]+1:ranges[-1][1]=n
 else:ranges.append([n,n])
def balanced(xs):
 if len(xs)==1:return xs[0]
 k=len(xs)//2;return '('+balanced(xs[:k])+'+'+balanced(xs[k:])+')'
expr=balanced(['between(n,%d,%d)'%(a,z) for a,z in ranges]);reports={}
for mode in args.modes:
 lst=[]
 for (f,k),nxt in zip(fr,frames[1:]+[nfr]):
  lst.append("file '%s'"%(shots/(k+'.png')))
  if mode!='default25':lst.append('option framerate 30')
  lst.append('duration %.6f'%((nxt-f)/30))
 for last in [True,False]:
  lst.append("file '%s'"%(shots/(fr[-1][1]+'.png')))
  if mode!='default25':lst.append('option framerate 30')
  if last:lst.append('duration 1.000000')
 src=out/(mode+'.txt');src.write_text('\n'.join(lst)+'\n');video=out/(mode+'.mp4')
 tb=subprocess.check_output(['ffprobe','-v','error','-f','concat','-safe','0','-i',str(src),'-show_entries','stream=time_base,r_frame_rate','-of','json'],text=True)
 print(mode,'input',tb.strip(),flush=True)
 subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(src),'-fps_mode','cfr','-r','30','-frames:v',str(nfr),'-vf',('scale=480:270,fps=30:start_time=0:round=near' if mode=='fpsfilter30' else 'scale=480:270'),'-c:v','libx264','-preset','ultrafast','-tune','stillimage','-crf','18','-pix_fmt','yuv420p','-g','300','-an',str(video)],check=True)
 cmd=['ffmpeg','-v','error','-i',str(video),'-vf',"select='%s',format=gray"%expr,'-vsync','0','-f','rawvideo','-'];p=subprocess.Popen(cmd,stdout=subprocess.PIPE);records=[]
 for n in targets:
  raw=p.stdout.read(480*270);assert len(raw)==480*270,(mode,n,len(raw));a=np.frombuffer(raw,dtype=np.uint8).reshape(270,480).astype(np.int16);i=bisect.bisect_right(frames,n)-1;k=fr[i][1]
  diff=float(np.abs(a-refs[k]).mean());r={'frame':n,'expected_state_start':frames[i],'key':k,'diff':round(diff,4)}
  if diff>3:
   candidates={fr[j][1]:float(np.abs(a-refs[fr[j][1]]).mean()) for j in range(max(0,i-2),min(len(fr),i+3))};r['closest_key']=min(candidates,key=candidates.get);r['closest_diff']=round(min(candidates.values()),4)
  records.append(r)
 assert not p.stdout.read(1);assert p.wait()==0
 fails=[r for r in records if r['diff']>3];local=[r for r in records if 1818<=r['frame']<=1826]
 report={'mode':mode,'input_probe':json.loads(tb),'states':len(fr),'probes':len(records),'bad_count':len(fails),'bad_probes':fails,'local1820':local,'all_probes':records}
 (out/(mode+'-report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');reports[mode]={'bad_count':len(fails),'local1820':local};print(mode,json.dumps(reports[mode],ensure_ascii=False),flush=True)
(out/'comparison.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n')
