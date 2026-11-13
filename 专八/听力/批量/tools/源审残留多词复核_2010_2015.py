"""仅复核18份final里少数非专名ASR多词，不重跑全卷、不改任何母稿/final。"""
import json,hashlib,subprocess,time
from pathlib import Path
import sherpa_onnx,numpy as np
B=Path(__file__).resolve().parents[1];O=B/'核验/2010—2015源审残留多词复核';O.mkdir(exist_ok=True);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
C=[(2010,'A','categories',[141,151]),(2010,'B2','Oh',[1325,1333]),(2010,'B2','Doctor',[1375,1384]),(2011,'A','they',[216,225]),(2011,'A','be',[417,426]),(2012,'A','do',[392,402]),(2013,'A','listening',[241,251]),(2015,'B2','You',[1116,1127])]
m=Path('/workspace/tem8-whisper-check/sherpa-onnx-whisper-base.en');ff={k:m/('base.en-'+v) for k,v in [('encoder','encoder.int8.onnx'),('decoder','decoder.int8.onnx'),('tokens','tokens.txt')]};model={k:{'file':p.name,'sha256':sha(p)} for k,p in ff.items()};asr=sherpa_onnx.OfflineRecognizer.from_whisper(**{k:str(v) for k,v in ff.items()},num_threads=1,enable_token_timestamps=True,enable_segment_timestamps=True)
for y,sec,key,(a,z) in C:
 p=O/f'{y}-{sec}-{key}.json'
 if p.exists():continue
 prep=json.loads((B/f'预处理/{y}/原音准备.json').read_text());ent=prep['source_entries'][0];src=Path('/workspace/tem8-input')/ent['file'];assert sha(src)==ent['sha256'];r=json.loads((B/f'核验/原文对齐/{y}/对齐报告.json').read_text());primary=json.loads((B/r['inputs']['asr']).read_text());data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(a),'-t',str(z-a),'-i',str(src),'-f','f32le','-ac','1','-ar','16000','-']);st=asr.create_stream();st.accept_waveform(16000,np.frombuffer(data,dtype='<f4'));t=time.monotonic();asr.decode_stream(st);x=st.result
 d={'year':y,'unit':f'{y}-{sec}','query':key,'window':[a,z],'canonical_source_sha256':prep['canonical']['sha256'],'source_file':ent['file'],'source_sha256':ent['sha256'],'primary_ASR':{'ref':r['inputs']['asr'],'sha256':sha(B/r['inputs']['asr']),'words':[w for w in primary if a<=w[1]<=z]},'independent_Whisper_text':x.text,'model_files':model,'elapsed_seconds':round(time.monotonic()-t,3),'token_timestamps':x.timestamps,'time_note':'独立Whisper只证文本，不为未给出的词时分配数值；原母稿/派生final/原音均未修改。','status':'independent_local_evidence_for_specific_ASR_extra_disposition'};p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(p.name,x.text,flush=True)
