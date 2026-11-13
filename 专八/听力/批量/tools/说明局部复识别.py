"""正式说明疑词的错位上下文双模型局部复识别；不改主ASR或正式原音。

两个模型顺序运行，各num_threads=1。2018通过原音准备canonical_start映射双源。
输出保留实际音源SHA、窗口、局部词元及绝对时刻，只作核对证据，不自动批准。
"""
import argparse,hashlib,json,subprocess,time
from pathlib import Path
import numpy as np
import sherpa_onnx
B=Path(__file__).resolve().parents[1]
OUT=B/'说明语句'/'局部复识别'
CASES=[
 (2010,'a_header',3,4),(2011,'a_header',3,4),(2013,'a_header',3,4),
 (2014,'2014_narrator',2.5,3.5),(2015,'a_title',4,4),(2016,'a_gap',2.5,3.5),
 (2018,'b_pause_fragment',3,4),(2019,'a_blank',3,4),(2019,'b_header',3,4),
 (2021,'a_gap',3,4),(2021,'b1_group_part',4,5),
 (2022,'a_check',3,3),
 (2023,'a_blank_fragment',11,4),(2024,'b2_group_interview',12,4),
]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def locate(year,key):
 d=json.loads((B/f'说明语句/{year}.json').read_text())
 return next(s for u in d['units'] for a in u.values() if isinstance(a,list) for s in a if s['translation_key']==key)
def tokens_words(r,start,duration,kind):
 words=[];cur=None
 for token,timestamp in zip(r.tokens,r.timestamps):
  token=str(token);t=round(start+float(timestamp),3)
  # Sherpa两模型均以词首空格切分；Whisper时间为token时间，非强制对齐。
  if token.startswith(' ') or cur is None:
   if cur and cur[0]:words.append(cur)
   cur=[token.strip(),t,round(min(start+duration,t+.08),3)]
  else:cur[0]+=token;cur[2]=round(min(start+duration,t+.08),3)
 if cur and cur[0]:words.append(cur)
 return words

def pcm_window(prep,start,end,root):
 parts=[];pcm=[]
 for ent in prep['source_entries']:
  a=max(start,ent.get('canonical_start',0));z=min(end,ent.get('canonical_end',prep['canonical']['duration']))
  if z<=a:continue
  path=root/ent['file'];assert path.is_file(),path
  offset=ent.get('canonical_start',0);local=a-offset
  data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(local),'-t',str(z-a),'-i',str(path),'-f','f32le','-ac','1','-ar','16000','-'])
  pcm.append(data);parts.append({'file':ent['file'],'source_sha256':ent['sha256'],'source_window':[round(local,3),round(z-offset,3)],'canonical_window':[round(a,3),round(z,3)]})
 assert pcm,(start,end)
 return np.frombuffer(b''.join(pcm),dtype='<f4'),parts

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--input-root',type=Path,default=Path('/workspace/tem8-input'))
 p.add_argument('--parakeet',type=Path,default=Path('/workspace/tem8-check-model/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8'))
 p.add_argument('--whisper',type=Path,default=Path('/workspace/tem8-whisper-check/sherpa-onnx-whisper-base.en'))
 p.add_argument('--years',type=int,nargs='*');args=p.parse_args()
 cases=[x for x in CASES if not args.years or x[0] in args.years]
 for kind,model in [('parakeet',args.parakeet),('whisper',args.whisper)]:
  if kind=='parakeet':
   files={k:model/(v+'.int8.onnx') for k,v in [('encoder','encoder'),('decoder','decoder'),('joiner','joiner')]};files['tokens']=model/'tokens.txt'
   asr=sherpa_onnx.OfflineRecognizer.from_transducer(**{k:str(v) for k,v in files.items()},model_type='nemo_transducer',num_threads=1)
  else:
   files={k:model/('base.en-'+v) for k,v in [('encoder','encoder.int8.onnx'),('decoder','decoder.int8.onnx'),('tokens','tokens.txt')]}
   asr=sherpa_onnx.OfflineRecognizer.from_whisper(**{k:str(v) for k,v in files.items()},num_threads=1,enable_token_timestamps=True,enable_segment_timestamps=True)
  filemeta={k:{'file':v.name,'sha256':sha(v)} for k,v in files.items()}
  for year,key,pad_before,pad_after in cases:
   source=B/f'预处理/{year}/识别.json';w=json.loads(source.read_text());primary_sha=sha(source)
   prep=json.loads((B/f'预处理/{year}/原音准备.json').read_text());s=locate(year,key);a,z=s['asr_range']
   # Whisper使用错开约2秒的上下文，避免复用相同切块边界导致同样漏词。
   start=max(0,w[a][1]-pad_before-(2 if kind=='whisper' else 0));end=min(prep['canonical']['duration'],w[z-1][2]+pad_after+(1.3 if kind=='whisper' else 0))
   out=OUT/str(year)/(key+'.json');old=json.loads(out.read_text()) if out.exists() else {}
   if old.get('primary_asr_sha256')==primary_sha and any(x['model']==kind for x in old.get('recognitions',[])):continue
   audio,parts=pcm_window(prep,start,end,args.input_root)
   for entry in parts:assert sha(args.input_root/entry['file'])==entry['source_sha256'],entry['file']
   st=asr.create_stream();st.accept_waveform(16000,audio);t=time.monotonic();asr.decode_stream(st);r=st.result
   timestamps_available=len(r.tokens)==len(r.timestamps) and bool(r.timestamps)
   if kind=='parakeet':assert timestamps_available
   row={'model':kind,'model_files':filemeta,'window':[round(start,3),round(end,3)],'source_parts':parts,'text':r.text,
        'tokens':r.tokens,'token_timestamps_relative':r.timestamps,'token_timestamps_available':timestamps_available,
        'words':tokens_words(r,start,end-start,kind) if timestamps_available else [],'elapsed_seconds':round(time.monotonic()-t,3),
        'timestamp_note':None if timestamps_available else '该Whisper模型decoder未导出cross-attention，虽请求token timestamps但实际无值；只作为独立文本证据，不制造词时刻。',
        'status':'machine_evidence_requires_adjudication'}
   if old.get('primary_asr_sha256')!=primary_sha:old={}
   doc={**old,'year':year,'query':key,'primary_asr':str(source.relative_to(B)),'primary_asr_sha256':primary_sha,'primary_asr_range':[a,z],'primary_text':s['asr_text'],
        'recognitions':[x for x in old.get('recognitions',[]) if x['model']!=kind]+[row],
        'script_sha256':sha(__file__),'notes':'仅分析副本重采样为16k单声道。局部词时刻为实际模型token时间，不是按文字长度分配，仍须最后对音。'}
   save(out,doc);print(kind,year,key,[round(start,2),round(end,2)],r.text,flush=True)
  del asr
if __name__=='__main__':main()
