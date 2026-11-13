from pathlib import Path
import argparse,tempfile
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument("--shots",type=Path,required=True);ap.add_argument("--repro-out",type=Path,required=True);args=ap.parse_args();WORK=Path(tempfile.mkdtemp(prefix="tem8-production-fast-gate-"))
import sys,json,shutil
root=Path(__file__).resolve().parents[5];sys.path.insert(0,str(root/'专八/听力/批量/tools'));import 考试视频 as m
fr=json.loads((HERE/'2019-真实修复run帧表.json').read_text());shots=args.shots.resolve();reportdir=root/'专八/听力/批量/核验/考试图片时间基核验';results=[]
for mode in ['default25','fpsfilter30']:
 out=WORK/mode;out.mkdir(parents=True,exist_ok=True)
 if not (out/'shots').exists():(out/'shots').symlink_to(shots,target_is_directory=True)
 m.configure(root/'专八/听力/批量/数据/2019',out)
 try:
  r=m.fast_frame_check(args.repro_out/(mode+'.mp4'),fr,48007)
  assert mode=='fpsfilter30';results.append({'mode':mode,'status':r['status'],'states':r['states'],'probes':r['probes'],'failures':len(r['failures'])})
 except ValueError as e:
  assert mode=='default25',e;r=json.loads((out/'核验/快片逐状态边界核验.json').read_text());assert r['failures'];results.append({'mode':mode,'correctly_rejected':True,'failures':len(r['failures'])})
 shutil.copy2(out/'核验/快片逐状态边界核验.json',reportdir/(mode+'-真实生产快片关卡.json'))
print(json.dumps(results,ensure_ascii=False,indent=2));(reportdir/'真实生产快片关卡正反例.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
