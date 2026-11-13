from pathlib import Path
import argparse,tempfile
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument("--passed-work",type=Path,required=True);ap.add_argument("--passed-video",type=Path,required=True);args=ap.parse_args()
import sys,json,shutil,copy
root=Path(__file__).resolve().parents[5];sys.path.insert(0,str(root/'专八/听力/批量/tools'));import 考试视频 as m
fr=json.loads((HERE/'2019-真实修复run帧表.json').read_text());out=args.passed_work.resolve();m.configure(root/'专八/听力/批量/数据/2019',out);shutil.copy2(args.passed_video,out/'fast.mp4');m.require_fast_frame_check(fr,48007);tests=[{'name':'真实完整快片允许进入4K','pass':True}]
def reject(name,fun):
 try:fun()
 except ValueError:tests.append({'name':name,'pass':True})
 else:raise AssertionError(name+'应拒绝')
reject('总帧数改变拒绝',lambda:m.require_fast_frame_check(fr,48008))
bad=copy.deepcopy(fr);bad[19][0]+=1;reject('帧表改变拒绝',lambda:m.require_fast_frame_check(bad,48007))
neg=Path(tempfile.mkdtemp(prefix='tem8-full-gate-negative-'));neg.mkdir(exist_ok=True);(neg/'shots').mkdir(exist_ok=True)
for p in (out/'shots').glob('*.png'):
 dest=neg/'shots'/p.name
 if not dest.exists():dest.symlink_to(p.resolve())
m.configure(root/'专八/听力/批量/数据/2019',neg);record=json.loads((out/'核验/快片逐状态边界核验.json').read_text());rp=neg/'核验/快片逐状态边界核验.json';shutil.copy2(out/'fast.mp4',neg/'fast.mp4')
def save(r):rp.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
save(record);m.require_fast_frame_check(fr,48007)
first=neg/'shots'/(fr[0][1]+'.png');real=first.resolve();first.unlink();shutil.copy2(real,first);first.write_bytes(first.read_bytes()+b'\0');reject('截图真实字节改变拒绝',lambda:m.require_fast_frame_check(fr,48007));first.unlink();first.symlink_to(real)
r=copy.deepcopy(record);r['source_fingerprints']['adapter']='0'*64;save(r);reject('程序旧指纹拒绝',lambda:m.require_fast_frame_check(fr,48007));save(record)
p=neg/'fast.mp4';p.write_bytes(p.read_bytes()+b'\0');reject('快片真实字节改变拒绝',lambda:m.require_fast_frame_check(fr,48007));shutil.copy2(out/'fast.mp4',p)
rp.unlink();reject('没有快片关卡记录拒绝',lambda:m.require_fast_frame_check(fr,48007))
p=root/'专八/听力/批量/核验/考试图片时间基核验/正式编码前快片门禁正反例.json';p.write_text(json.dumps({'status':'PASS','tests':tests},ensure_ascii=False,indent=2)+'\n');print('PASS',len(tests),'full gate tests')
