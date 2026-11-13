"""仅查2024三个主ASR漏掉的念题题号；两模型证据及真实词锚独立保存。"""
import hashlib,importlib.util,json
from pathlib import Path
import sherpa_onnx

B=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tem8_local_words',B/'tools/补词锚识别.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
prep=json.loads((B/'预处理/2024/原音准备.json').read_text());report=json.loads((B/'核验/原文对齐/2024/对齐报告.json').read_text());jobs=[]
for u in report['units']:
 if not u['missing_boundary_sentences']:continue
 d=json.loads((B/u['output']).read_text())
 for n in u['missing_boundary_sentences']:
  s=d['sentences'][n-1]
  if s['en'].startswith('Question ') and all(x['text']=='Question' or x['text'].isdigit() for x in s['alignment']['missing']):
   t=s['word_alignment'][0]['start'];jobs.append({'unit':u['id'],'en':s['en'],'window':[round(t-3.2,3),round(t+2.,3)]})
model=Path('/workspace/tem8-check-model/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8');names=['encoder.int8.onnx','decoder.int8.onnx','joiner.int8.onnx','tokens.txt']
asr=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(model/names[0]),decoder=str(model/names[1]),joiner=str(model/names[2]),tokens=str(model/names[3]),model_type='nemo_transducer',num_threads=1)
wm=Path('/workspace/tem8-whisper-check/sherpa-onnx-whisper-base.en');wf={k:wm/('base.en-'+v) for k,v in [('encoder','encoder.int8.onnx'),('decoder','decoder.int8.onnx'),('tokens','tokens.txt')]}
second=sherpa_onnx.OfflineRecognizer.from_whisper(**{k:str(v) for k,v in wf.items()},num_threads=1)
rows=[];verified=set()
for job in jobs:
 lo,hi=job['window'];audio=helper.source_clip(prep,Path('/workspace/tem8-input'),lo,hi,verified)
 st=asr.create_stream();st.accept_waveform(16000,audio);asr.decode_stream(st);r=st.result
 wt=second.create_stream();wt.accept_waveform(16000,audio);second.decode_stream(wt)
 rows.append({**job,'primary_text':r.text,'words':helper.words_from_tokens(r.tokens,r.timestamps,lo,hi),'tokens':r.tokens,'timestamps':r.timestamps,'secondary_text':wt.result.text,'status':'evidence_requires_adjudication'})
 out={'year':2024,'canonical_source_sha256':prep['canonical']['sha256'],'model_files':{n:helper.sha(model/n) for n in names},'independent_Whisper_files':{k:helper.sha(v) for k,v in wf.items()},'script_sha256':helper.sha(__file__),'analysis_only':'内存16k单声道，不修改原音/主ASR；只采用实际模型词时刻。','windows':rows}
 helper.save(B/'核验/2024-题号局部双模型.json',out)
 print(job['unit'],job['en'],r.text,'WHISPER',wt.result.text,flush=True)
