"""仅对解析疑文的小窗口做独立Whisper复识别；不改正式原音或主ASR。

输出是第二模型证据，仍须逐项裁决，不自动批准字幕，不生成成品音频。
"""
import argparse,difflib,hashlib,json,re,subprocess,time
from pathlib import Path
import numpy as np
import sherpa_onnx

B=Path(__file__).resolve().parents[1]
OVERRIDES={(2012,'being observing'):[121,137],
 (2014,'a displaced unstable population'):[1142,1166],
 (2015,'da da DA'):[190,215],(2021,'Emm'):[1315,1336],
 (2022,'stating once again the anthropology'):[138,156],
 (2024,'that is a language translation'):[448,465]}
QUERIES={
 2010:['Has the idea of being different','interesting age gap'],
 2011:['meaning onto itself','or as before as I said','direct methods'],
 2012:['being observing','and, and when we rarely','for that manner','creativity can be saying'],
 2013:['what the world was that about','although sometimes they could be'],
 2014:['I restrict it a term','went inside and met','there seems to be a block in','How do you think U.N.H.C.R.','a displaced unstable population','you willing to come here','pressure perhaps on our government','Why did Angelina see'],
 2015:['da da DA','Why some'],
 2021:['civil rights of the 1960s','memoirs and criticisms','divided into sections','Emm'],
 2022:['stating once again the anthropology'],
 2023:['before, it was fossil metaphor','a year sharp spent','To put it simple','what kind of gap year experience','I see.'],
 2024:['adults and adolescence','that is a language translation','minor novels','examine the Antarctica','I knew that','Also the effects','three times faster']}

def lex(s):return re.findall(r"[a-z]+(?:'[a-z]+)?|\d+",s.lower().replace('’',"'"))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def locate(q,w):
 a=lex(q);target=[lex(x[0]) for x in w];flat=[(t,i) for i,ts in enumerate(target) for t in ts];best=(-1,None,None)
 for i in range(len(flat)):
  if flat[i][0] not in a[:3]:continue
  for n in range(max(1,len(a)-3),len(a)+4):
   score=difflib.SequenceMatcher(None,a,[x[0] for x in flat[i:i+n]],autojunk=False).ratio()
   if score>best[0]:best=(score,flat[i][1],flat[min(len(flat)-1,i+n-1)][1])
 assert best[0]>.4,(q,best)
 return best

def main():
 p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--input-root',type=Path,default=Path('/workspace/tem8-input'));p.add_argument('--threads',type=int,default=2);p.add_argument('--years',type=int,nargs='*');args=p.parse_args()
 files={k:args.model/('base.en-'+v) for k,v in [('encoder','encoder.int8.onnx'),('decoder','decoder.int8.onnx'),('tokens','tokens.txt')]}
 asr=sherpa_onnx.OfflineRecognizer.from_whisper(**{k:str(v) for k,v in files.items()},num_threads=args.threads,enable_token_timestamps=True,enable_segment_timestamps=True)
 for y,queries in QUERIES.items():
  if args.years and y not in args.years:continue
  prep=json.loads((B/'预处理'/str(y)/'原音准备.json').read_text());w=json.loads((B/'预处理'/str(y)/'识别.json').read_text());src=args.input_root/prep['source_entries'][0]['file'];assert src.is_file(),src
  rows=[];out=B/'核验'/'疑文复识别'/f'{y}.json'
  if out.exists():rows=json.loads(out.read_text())['windows']
  for query in queries:
   previous=next((x for x in rows if x['query']==query),None)
   override=OVERRIDES.get((y,query))
   if previous and (not override or previous['window']==override):continue
   if previous:rows.remove(previous)
   if override:start,end=override;score=None
   else:
    score,i,j=locate(query,w);start=max(0,w[i][1]-4);end=min(prep['canonical']['duration'],w[j][2]+6)
   assert 0<end-start<30,(query,start,end)
   pcm=subprocess.check_output(['ffmpeg','-v','error','-ss',str(start),'-t',str(end-start),'-i',str(src),'-f','f32le','-ac','1','-ar','16000','-'])
   a=np.frombuffer(pcm,dtype='<f4');stream=asr.create_stream();stream.accept_waveform(16000,a);t=time.monotonic();asr.decode_stream(stream);r=stream.result
   row={'query':query,'window':[round(start,3),round(end,3)],'locator_similarity':score,'primary_text':' '.join(x[0] for x in w if start<=x[1]<end),'secondary_text':r.text,'tokens':r.tokens,'timestamps':r.timestamps,'elapsed_seconds':round(time.monotonic()-t,3),'status':'independent_machine_evidence_requires_adjudication'};rows.append(row)
   save(out,{'year':y,'source_file':prep['source_entries'][0]['file'],'source_sha256':prep['source_entries'][0]['sha256'],'primary_asr_sha256':sha(B/'预处理'/str(y)/'识别.json'),'model':'sherpa-onnx-whisper-base.en-int8','model_files':{k:{'name':v.name,'sha256':sha(v)} for k,v in files.items()},'script_sha256':sha(__file__),'analysis_only':'分析副本16k单声道；正式原音未修改','windows':rows})
   print(y,query,round(start,2),round(end,2),r.text,flush=True)
if __name__=='__main__':main()
