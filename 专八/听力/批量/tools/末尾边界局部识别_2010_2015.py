"""仅识别最终导出剩余边界缺词的已锚定小窗，不重开源文裁决。
窗口只定位复识别上下文；词时刻来自Parakeet实际token，不能拿窗口边缘冒充词时。
"""
import json,hashlib,time,subprocess
from pathlib import Path
import sherpa_onnx,numpy as np
B=Path(__file__).resolve().parents[1];O=B/'核验/2010—2015剩余边界复识别';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=Path('/workspace/tem8-check-model/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8');ff={k:m/(k+'.int8.onnx') for k in ['encoder','decoder','joiner']};ff['tokens']=m/'tokens.txt';model={k:{'file':v.name,'sha256':sha(v)} for k,v in ff.items()};asr=sherpa_onnx.OfflineRecognizer.from_transducer(**{k:str(v) for k,v in ff.items()},model_type='nemo_transducer',num_threads=1)
for y in range(2010,2016):
 rp=B/f'核验/原文对齐/{y}/对齐报告.json';report=json.loads(rp.read_text());prep=json.loads((B/f'预处理/{y}/原音准备.json').read_text());ent=prep['source_entries'][0];src=Path('/workspace/tem8-input')/ent['file'];assert sha(src)==ent['sha256']
 for rec in report['rerecognition_windows']:
  cases=[x for x in rec['issues'] if x['boundary_missing']]
  if not cases:continue
  a,z=rec['window'];assert 0<z-a<50
  key=rec['unit']+'-'+','.join(str(x['sentence']) for x in cases);p=O/(key+'.json');p.parent.mkdir(parents=True,exist_ok=True)
  if p.exists() and json.loads(p.read_text()).get('window')==[a,z]:continue
  raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(a),'-t',str(z-a),'-i',str(src),'-f','f32le','-ac','1','-ar','16000','-']);audio=np.frombuffer(raw,dtype='<f4');st=asr.create_stream();st.accept_waveform(16000,audio);t=time.monotonic();asr.decode_stream(st);r=st.result;w=[];cur=None
  for token,ts in zip(r.tokens,r.timestamps):
   ti=round(a+float(ts),3)
   if token.startswith(' ') or cur is None:
    if cur and cur[0]:w.append(cur)
    cur=[token.strip(),ti,round(min(z,ti+.08),3)]
   else:cur[0]+=token;cur[2]=round(min(z,ti+.08),3)
  if cur and cur[0]:w.append(cur)
  d={'year':y,'unit':rec['unit'],'issues':cases,'source_file':ent['file'],'source_sha256':ent['sha256'],'canonical_source_sha256':prep['canonical']['sha256'],'alignment_report':str(rp.relative_to(B)),'alignment_report_sha256':sha(rp),'window':[a,z],'bracketing_only_not_word_timestamps':True,'text':r.text,'tokens':r.tokens,'token_timestamps_relative':r.timestamps,'words':w,'word_end_estimate_seconds':.08,'model_files':model,'elapsed_seconds':round(time.monotonic()-t,3),'status':'仅实际局部识别证据；未修改母稿EN/ZH/w，不声称approved'};p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(key,[a,z],r.text,flush=True)
