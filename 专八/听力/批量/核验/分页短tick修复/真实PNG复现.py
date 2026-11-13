import json,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
import argparse,hashlib
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--shots',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();shots=args.shots.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
source=json.loads((HERE/'真实2017PNG片段清单.json').read_text());fr=[]
for r in source['rows']:
 assert hashlib.sha256((shots/r['file']).read_bytes()).hexdigest()==r['sha256'],'必须使用真实已审PNG，不可另画替代'
 fr.append([r['frame'],Path(r['file']).stem])
for label,rows in [('old',fr),('new',[r for r in fr if r[0]!=2061])]:
 entries=[]
 for (f,k),nxt in zip(rows,[r[0] for r in rows[1:]]+[2121]):entries.append(f"file '{shots/(k+'.png')}'\nduration {(nxt-f)/30:.6f}")
 entries += [f"file '{shots/(rows[-1][1]+'.png')}'\nduration 1.000000",f"file '{shots/(rows[-1][1]+'.png')}'"]
 lst=out/(label+'.txt');lst.write_text('\n'.join(entries)+'\n');v=out/(label+'.mp4')
 subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(lst),'-fps_mode','cfr','-r','30','-frames:v','2121','-vf','scale=480:270','-c:v','libx264','-preset','medium','-tune','stillimage','-crf','18','-pix_fmt','yuv420p','-g','300',str(v)],check=True)
 folder=out/label;folder.mkdir(exist_ok=True)
 subprocess.run(['ffmpeg','-y','-v','error','-i',str(v),'-vf',r'select=between(n\,2059\,2064)','-vsync','0',str(folder/'%03d.png')],check=True)
 # unmodified base verify's precise seek for the reported failing old state
 subprocess.run(['ffmpeg','-y','-v','error','-ss',f'{(2061+1.5)/30:.4f}','-i',str(v),'-frames:v','1',str(folder/'base-seek.png')],check=True)
 refs={k:np.asarray(Image.open(shots/(k+'.png')).convert('L').resize((480,270)),dtype=float) for k in ['e61d034b17e3','b9ecd67ae584','1a4290d76d85']}
 results=[]
 for i,p in enumerate(sorted(folder.glob('[0-9]*.png'))):
  a=np.asarray(Image.open(p).convert('L'),dtype=float);results.append({'frame':2059+i,'diff':{k:round(float(np.abs(a-b).mean()),4) for k,b in refs.items()}})
 a=np.asarray(Image.open(folder/'base-seek.png').convert('L'),dtype=float)
 report={'frames':results,'original_probe_seconds':(2061+1.5)/30,'original_probe_diff':{k:round(float(np.abs(a-b).mean()),4) for k,b in refs.items()}}
 (folder/'结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(label,json.dumps(report,ensure_ascii=False),flush=True)

old=json.loads((out/'old/结果.json').read_text());new=json.loads((out/'new/结果.json').read_text());assert old['original_probe_diff']['b9ecd67ae584']>3
# 新状态第18项为真实下一页2062，按完全不改的底座取样规则验证。
p=out/'new/new-state-probe.png';subprocess.run(['ffmpeg','-y','-v','error','-ss',f'{(2062+1.5)/30:.4f}','-i',str(out/'new.mp4'),'-frames:v','1',str(p)],check=True)
a=np.asarray(Image.open(p).convert('L'),dtype=float);refs={k:np.asarray(Image.open(shots/(k+'.png')).convert('L').resize((480,270)),dtype=float) for k in ['b9ecd67ae584','1a4290d76d85']};diff={k:float(np.abs(a-v).mean()) for k,v in refs.items()};assert diff['1a4290d76d85']<3 and diff['b9ecd67ae584']>3
report={'status':'PASS','old_probe_rejected_at_unchanged_threshold_3':old['original_probe_diff']['b9ecd67ae584'],'new_retained_state_probe_passed_at_same_threshold_3':diff['1a4290d76d85'],'intentional_wrong_page_negative_rejected':diff['b9ecd67ae584'],'old':old,'new':new,'encoder':'与底座相同concat时长与30fps/libx264 medium，真实4K PNG缩为480诊断片，不是正式成品','quantization':'PNG输入默认25fps转30fps：旧版本实解2063翻页（计划2062），抑制冗余tick后实解2061翻页（计划仍2062），如实限于既有CFR量化±1帧；未改底座/编码器/阈值，未声称受影响5年MP4逐字相同。'}
(HERE/'2017-真实PNG双向编码复现.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('PASS old/new/wrong-page:',report['old_probe_rejected_at_unchanged_threshold_3'],report['new_retained_state_probe_passed_at_same_threshold_3'],report['intentional_wrong_page_negative_rejected'])
