"""对剩余轻声/应声/节奏边界实读PCM，输出完整话轮证据与审阅图。
仅确定整句范围，保留实际ASR词锚和unknown；不造字/词时刻，不改源英语。
"""
import json,hashlib,importlib.util,re,subprocess,time
from pathlib import Path
import numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sherpa_onnx
B=Path(__file__).resolve().parents[1];O=B/'核验/2010—2015整句声学证据';O.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('wave_helper',B/'tools/原声窗口边界.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
wmod=Path('/workspace/tem8-whisper-check/sherpa-onnx-whisper-base.en');files={k:wmod/('base.en-'+v) for k,v in [('encoder','encoder.int8.onnx'),('decoder','decoder.int8.onnx'),('tokens','tokens.txt')]};wm=sherpa_onnx.OfflineRecognizer.from_whisper(**{k:str(v) for k,v in files.items()},num_threads=1,enable_token_timestamps=True,enable_segment_timestamps=True);modelmeta={k:{'file':p.name,'sha256':sha(p)} for k,p in files.items()}

def quiet_segments(times,db,lo,hi,threshold):
 idx=np.flatnonzero((times>=lo)&(times<=hi)&(db<threshold));groups=[]
 for i in idx:
  if groups and i==groups[-1][-1]+1:groups[-1].append(i)
  else:groups.append([i])
 return [g for g in groups if len(g)>=2]
def pick(groups,times,db,last=False):
 if not groups:return None
 g=groups[-1] if last else groups[0];return float(times[min(g,key=lambda i:db[i])])
for year in range(2010,2016):
 rp=B/f'核验/原文对齐/{year}/对齐报告.json';report=json.loads(rp.read_text());prep=json.loads((B/f'预处理/{year}/原音准备.json').read_text());ent=prep['source_entries'][0];root=Path('/workspace/tem8-input');src=root/ent['file']
 for info in report['units']:
  if not info['missing_boundary_sentences']:continue
  d=json.loads((B/info['output']).read_text())
  for n in info['missing_boundary_sentences']:
   s=d['sentences'][n-1];prev=d['sentences'][n-2];nxt=d['sentences'][n];pa=prev.get('end');na=nxt.get('start');assert pa is not None and na is not None,(year,n)
   wa=s['word_alignment'];known=[min(x['start'] for x in wa),max(x['end'] for x in wa)] if wa else None
   lo=max(0,pa-.2);hi=min(prep['canonical']['duration'],na+.2);wave=M.pcm(prep,root,lo,hi);db=np.array(wave['frames_dBFS']);ts=lo+np.arange(len(db))*wave['frame_seconds'];th=wave['threshold_dBFS']
   if known:
    left=quiet_segments(ts,db,pa-.1,min(known[0]-.02,na-.04),th);right=quiet_segments(ts,db,max(known[1]-.1,pa+.04),na-.02,th)
    start=pick(left,ts,db);end=pick(right,ts,db,True)
   else:
    # 独立应声：只在相邻真话轮间实际可见的有声岛两边择低谷，不能用任意静音冒充应声。
    ids=np.flatnonzero((ts>=pa-.04)&(ts<=na+.04)&(db>th+6));runs=[]
    for i in ids:
     if runs and i==runs[-1][-1]+1:runs[-1].append(i)
     else:runs.append([i])
    runs=[g for g in runs if len(g)>=2 and pa-.04<ts[g[0]] and ts[g[-1]]<na+.04]
    if runs:
     a,z=min(g[0] for g in runs),max(g[-1] for g in runs)
     start=pick(quiet_segments(ts,db,pa-.1,ts[a]-.01,th),ts,db,True);end=pick(quiet_segments(ts,db,ts[z]+.01,na+.1,th),ts,db)
    else:start=end=None
   valid=start is not None and end is not None and start<end and pa<=start+.15 and end<=na+.15 and (known is None or start<=known[0]+.15 and known[1]<=end+.15)
   key=f'{info["id"]}-{n}';p=O/(key+'.json')
   secondary={}
   if year==2015 and 'da da' in s['en']:
    ep=B/'核验/疑文复识别/2015.json';q=json.loads(ep.read_text());record=next(x for x in q['windows'] if x['query']=='da da DA');secondary={'evidence_ref':str(ep.relative_to(B)),'evidence_sha256':sha(ep),'window':record['window'],'text':record['secondary_text'],'note':'复用root已实际核过的独立Whisper节奏证据，不重复识别，也不冒造其缺失的token时刻。'}
   else:
    context_lo=max(0,(prev.get('start',pa)-.4 if not known else pa-1.2));context_hi=min(prep['canonical']['duration'],nxt.get('end',na)+.5)
    if context_hi-context_lo>35:context_lo=max(0,pa-1.5);context_hi=min(prep['canonical']['duration'],na+4)
    pcm=subprocess.check_output(['ffmpeg','-v','error','-ss',str(context_lo),'-t',str(context_hi-context_lo),'-i',str(src),'-f','f32le','-ac','1','-ar','16000','-']);st=wm.create_stream();st.accept_waveform(16000,np.frombuffer(pcm,dtype='<f4'));t=time.monotonic();wm.decode_stream(st);r=st.result;secondary={'model':'whisper-base.en-int8','model_files':modelmeta,'window':[context_lo,context_hi],'text':r.text,'timestamps':r.timestamps,'elapsed_seconds':round(time.monotonic()-t,3),'note':'独立模型仅文本证据；该decoder未导出cross-attention，不能伪造字词时间。'}
   fig,ax=plt.subplots(figsize=(16,3));ax.plot(ts,db,lw=.8,color='#383874');ax.axhline(th,color='#999999',ls='--',lw=.6)
   ax.axvline(pa,color='#cc7777',label='previous actual ASR end');ax.axvline(na,color='#cc7777',ls='--',label='next actual ASR start')
   if known:
    ax.axvspan(*known,alpha=.1,color='orange',label='known actual word anchors')
   if valid:ax.axvspan(start,end,alpha=.13,color='green',label='whole sentence measured envelope')
   ax.set(xlabel='Original source seconds',ylabel='AC-RMS dBFS',title=key);ax.legend(fontsize=7);fig.tight_layout();png=O/(key+'.png');fig.savefig(png,dpi=120);plt.close(fig)
   proof={'year':year,'unit':info['id'],'en':s['en'],'missing_text':[x['text'] for x in s['alignment']['missing']],'source_refs':d.get('source_refs',[]),'source_file':ent['file'],'source_sha256':ent['sha256'],'canonical_source_sha256':prep['canonical']['sha256'],'adjacent_true_ASR':[pa,na],'known_word_window':known,'measured_sentence_window':[round(start,6),round(end,6)] if valid else None,'actual_PCM':wave,'secondary_model':secondary,'plot':str(png.relative_to(B)),'plot_sha256':sha(png),'method':'原采样率/双声道10ms AC-RMS实读；漏首取可包含整段轻音的前低谷，末节奏取后一真句首前最后低谷；纯应声须见实际有声活动。所有unknown保留，不分摊词时。','status':'measured_whole_sentence_candidate' if valid else 'no_safe_whole_sentence_envelope'};p.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(key,'MEASURED',proof['measured_sentence_window'],'Whisper',secondary.get('text'),flush=True)
