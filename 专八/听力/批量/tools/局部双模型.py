#!/usr/bin/env python3
"""显式绝对秒数小窗的Parakeet真词锚与独立Whisper证据；不自动改稿。"""
import argparse,hashlib,importlib.util,json,time
from pathlib import Path
import sherpa_onnx

B=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('tem8_local_audio',B/'tools/补词锚识别.py');H=importlib.util.module_from_spec(sp);sp.loader.exec_module(H)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--jobs',required=True,type=Path);p.add_argument('--out-dir',type=Path,default=B/'核验/独立收尾复核');p.add_argument('--source-root',action='append',type=Path,required=True);p.add_argument('--parakeet',type=Path,required=True);p.add_argument('--whisper',type=Path,required=True);args=p.parse_args()
 jobs=json.loads(args.jobs.read_text())['jobs'];pn=['encoder.int8.onnx','decoder.int8.onnx','joiner.int8.onnx','tokens.txt'];pf=[args.parakeet/x for x in pn]
 first=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(pf[0]),decoder=str(pf[1]),joiner=str(pf[2]),tokens=str(pf[3]),model_type='nemo_transducer',num_threads=1)
 wf={k:args.whisper/('base.en-'+v) for k,v in [('encoder','encoder.int8.onnx'),('decoder','decoder.int8.onnx'),('tokens','tokens.txt')]};second=sherpa_onnx.OfflineRecognizer.from_whisper(**{k:str(v) for k,v in wf.items()},num_threads=1)
 verified=set();pmeta={x.name:H.sha(x) for x in pf};wmeta={k:H.sha(v) for k,v in wf.items()}
 for year in sorted({x['year'] for x in jobs}):
  prep=json.loads((B/f'预处理/{year}/原音准备.json').read_text());primary=json.loads((B/f'预处理/{year}/识别.json').read_text());root=next(r for r in args.source_root if all((r/e['file']).exists() for e in prep['source_entries']));out=args.out_dir/f'{year}.json';rows=json.loads(out.read_text())['windows'] if out.exists() else []
  for job in [x for x in jobs if x['year']==year]:
   if any(x['key']==job['key'] and x['window']==job['window'] for x in rows):continue
   lo,hi=job['window'];assert 0<=lo<hi<=prep['canonical']['duration'] and hi-lo<=30
   audio=H.source_clip(prep,root,lo,hi,verified);t=time.monotonic();s=first.create_stream();s.accept_waveform(16000,audio);first.decode_stream(s);r=s.result;ss=second.create_stream();ss.accept_waveform(16000,audio);second.decode_stream(ss)
   rows.append({**job,'primary_text':' '.join(w[0] for w in primary if lo<=w[1]<hi),'recognitions':[{'model':'parakeet','text':r.text,'tokens':r.tokens,'timestamps':r.timestamps,'words':H.words_from_tokens(r.tokens,r.timestamps,lo,hi)},{'model':'Whisper-base.en','text':ss.result.text}],'elapsed_seconds':round(time.monotonic()-t,3),'status':'independent_evidence_requires_source_adjudication'})
   H.save(out,{'year':year,'canonical_source_sha256':prep['canonical']['sha256'],'source_entries':[{'file':e['file'],'sha256':e['sha256']} for e in prep['source_entries']],'model_files':{'parakeet':pmeta,'Whisper':wmeta},'script_sha256':H.sha(__file__),'jobs_sha256':H.sha(args.jobs),'analysis_only':'只读原音，内存16k单声道分析；新词时刻均来自实际Parakeet词元，不补造Whisper词时。','windows':rows})
   print(year,job['key'],r.text,'WHISPER',ss.result.text,flush=True)


if __name__=='__main__':main()
