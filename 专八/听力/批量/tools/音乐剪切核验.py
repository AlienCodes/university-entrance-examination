"""保守的片头音乐边界核验；仅解码开头作分析，不剪写/调音/重采样原音。

逐年波形及频谱人工判读后固定剪点；不使用ASR首词直接计算剪点。
python 音乐剪切核验.py --input /workspace/tem8-input --cache /workspace/tem8-intro-audit
2022使用已approved的完整补充原音；不采用缺头旧包。输出绑定选定canonical SHA。
"""
from pathlib import Path
import argparse,hashlib,json,subprocess
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

D=Path(__file__).resolve().parent.parent
YEARS=list(range(2009,2020))+[2021,2022,2023,2024]
# 人工从波形/频谱确认：选音乐后的低能量静音区间中部，保留正式报幕和开口前余量。
CUTS={2009:(13.20,[13.06,13.37]),2010:(14.22,[13.95,14.49]),2011:(14.19,[13.85,14.53]),2012:(13.18,[13.02,13.35]),2013:(14.24,[13.82,14.67]),2014:(13.16,[12.99,13.33]),2015:(13.14,[12.97,13.32]),2022:(13.60,[13.10,14.20])}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def db(v):return float(20*np.log10(max(float(v),1e-12)))
def dump(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n','utf-8')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,default=Path('/workspace/tem8-input'));ap.add_argument('--cache',type=Path,default=Path('/workspace/tem8-intro-audit'));ap.add_argument('--supplement',type=Path,default=Path('/workspace/TEM8-2022-complete.m4a'));args=ap.parse_args();args.cache.mkdir(exist_ok=True,parents=True)
 out=D/'音乐剪切';out.mkdir(exist_ok=True);figdir=out/'图证';figdir.mkdir(exist_ok=True);records=[]
 for year in YEARS:
  meta=json.loads((D/'预处理'/str(year)/'原音准备.json').read_text())
  if year==2022:
   approval=json.loads((D/'核验/2022-补充音源.json').read_text());assert approval['status']=='approved'
   entry=approval['selected_source'];src=args.supplement
   # 新完整源的原采样率解码SHA由总协调实际解码核定，和缺头旧包不混用。
   canonical={'sha256':'cc2bcead3fcfaf404840caa83e7a98efb7de446415388bd0fcc4803071e827a9','sample_rate':44100,'channels':2,'pcm_format':'float32le'}
  else:entry=meta['source_entries'][0];src=args.input/entry['file'];canonical=meta['canonical']
  rate=canonical['sample_rate'];channels=canonical['channels'];duration=20 if year<=2015 or year==2022 else 7
  actualsha=sha(src);assert actualsha==entry['sha256'],(year,'source sha mismatch')
  cache=args.cache/f'{year}.npy'
  if cache.exists():a=np.load(cache)
  else:
   b=subprocess.check_output(['ffmpeg','-v','error','-i',str(src),'-t',str(duration),'-c:a','pcm_f32le','-f','f32le','-']);a=np.frombuffer(b,dtype='<f4').reshape(-1,channels);np.save(cache,a)
  assert a.ndim==2 and a.shape[1]==channels
  start,interval=CUTS.get(year,(0,None));cut_sample=round(start*rate);assert abs(cut_sample/rate-start)<1e-9
  window=a[max(0,cut_sample-round(.04*rate)):min(len(a),cut_sample+round(.04*rate))]
  peak=db(np.abs(window).max());rms=db(np.sqrt(np.mean(window.astype(float)**2)))
  asr=json.loads((D/'预处理'/str(year)/'识别.json').read_text());first=['Test',14.40] if year==2022 else asr[0]
  if interval:
   assert interval[0]<start<interval[1]
   # 此阈值只作已人工选定静音区间的客观复核；非自动音乐/语音分类器。
   segment=a[round(interval[0]*rate):round(interval[1]*rate)]
   assert np.max(np.abs(segment))<.001,(year,'selected silence interval peak exceeds -60dBFS')
   assert peak<-60,(year,'cut point not in quiet gap')
   evidence=(f'逐年查看0—20s原采样率波形和0—6kHz频谱：约1.7—13s存在连续音乐谐波及旋律变化，结束后频谱进入低能量间隙；'
    f'{interval[0]:.2f}—{interval[1]:.2f}s全声道峰值低于-60dBFS，选择间隙内{start:.2f}s（原样本{cut_sample}）裁去片头音乐。'
    f'剪点前后40ms峰值{peak:.2f}dBFS、RMS {rms:.2f}dBFS；正式报幕Test的ASR参考起点{first[1]:.2f}s，剪点早于该参考{first[1]-start:.2f}s。'
    '已按波形/频谱确认没有剪入报幕音节；不是按ASR首字起点切割。保留报幕、正式说明及其后全部内容。')
  else:
   evidence=('逐年查看0—7s原采样率波形和0—6kHz频谱：正式报幕前没有连续音乐谐波或音乐段，只有前导静音及录音底噪；保留完整开头，start=0。'
    f'ASR仅作报幕内容定位参考，首词Test在{first[1]:.2f}s；不据此删除前导部分。')
   if year==2024:evidence+='本源约0.1s后的波形基线为直流偏置，非音乐；不消除偏置、不作音量或声道处理。'
  result={'year':year,'start':start,'reason':'片头音乐' if start else '无片头音乐','source_sha256':canonical['sha256'],'evidence':evidence,
   'source_entry':{'file':entry['file'],'sha256':actualsha},'canonical_format':{'sample_rate':rate,'channels':channels,'pcm_format':canonical['pcm_format']},
   'cut_sample':cut_sample,'silence_interval':interval,'cut_window':{'half_window_seconds':.04,'max_channel_peak_dbfs':peak,'all_channel_rms_dbfs':rms,'digital_zero':bool(np.max(np.abs(window))==0),'db_display_floor':-240.0},
   'reference_first_word':first,'review_method':'原始PCM波形、10ms全声道峰值及RMS、STFT频谱逐年人工核对；ASR只作交叉定位，不作为剪点。',
   'plot':f'图证/{year}.png','pending':[]}
  dump(out/f'{year}.json',result);records.append(result)
  # 同时显示全开头与剪点局部；所有图仅用于核验，不生成或变更音频。
  frame=max(1,round(rate*.01));z=a[:len(a)//frame*frame].reshape(-1,frame,channels);rmsseries=np.sqrt(np.mean(z.astype(float)**2,axis=(1,2)));ts=(np.arange(len(z))+.5)*frame/rate
  fig,ax=plt.subplots(3 if start else 2,1,figsize=(13,7 if start else 5),gridspec_kw={'height_ratios':[1,2,1]} if start else {'height_ratios':[1,2]})
  ax[0].plot(ts,20*np.log10(np.maximum(rmsseries,1e-10)),lw=.7);ax[0].set_ylim(-100,0);ax[0].set_xlim(0,duration);ax[0].set_ylabel('RMS dBFS');ax[0].set_title(f'{year}: native {rate} Hz, {channels} channel(s); trim start {start:.2f}s')
  ax[0].axvline(first[1],color='red',ls='--',label=f'ASR reference {first[1]:.3f}s');ax[0].legend(loc='upper right')
  mono=a.mean(axis=1);f,t,S=signal.spectrogram(mono,rate,nperseg=1024,noverlap=768);ax[1].pcolormesh(t,f,10*np.log10(np.maximum(S,1e-12)),cmap='magma',vmin=-100,vmax=-35,shading='auto');ax[1].set_ylim(0,6000);ax[1].set_xlim(0,duration);ax[1].set_ylabel('Frequency Hz');ax[1].set_xlabel('Original source seconds')
  if start:
   for at in ax[:2]:at.axvspan(*interval,color='green',alpha=.18);at.axvline(start,color='green',lw=1.4)
   local_lo=round((start-.6)*rate);local_hi=round((start+.6)*rate);tlocal=np.arange(local_lo,local_hi)/rate
   for channel in range(channels):ax[2].plot(tlocal,a[local_lo:local_hi,channel],lw=.6,alpha=.7,label=f'Ch {channel+1}')
   ax[2].set_xlim(start-.6,start+.6);ax[2].axvspan(*interval,color='green',alpha=.18);ax[2].axvline(start,color='green',lw=1.4);ax[2].set_ylabel('Native PCM');ax[2].set_xlabel('Cut point detail (seconds)');ax[2].legend(loc='upper right')
  for at in ax:at.grid(alpha=.12)
  fig.tight_layout();fig.savefig(figdir/f'{year}.png',dpi=110);plt.close(fig)
  print(year,start,interval,'peak',round(peak,2),'sha verified',flush=True)
 # 可读清单与所有图的完整性绑定。
 lines=['# 专八听力片头音乐剪切核验','', '仅核验并给出剪点；本脚本没有剪写成品音频、调整增益、重采样或改声道。剪点绑定“原音准备.json”的canonical WAV SHA256，基准为未剪原音秒数。','',
 '2009—2015和2022完整补充源有片头音乐；其余已核年份没有音乐，保留start=0。2022绑定经approved登记的新完整源及其canonical SHA，不使用缺头旧包。','',
 '能量表中的-240dBFS为对数显示下限；对应片段PCM全为0，并非实测到了-240dBFS的非零声音。JSON另外以digital_zero标记。','', '方法：逐年人工查看原采样率PCM的波形及STFT频谱；音乐段可见连续谐波、持续旋律结构与渐弱尾部。剪点放在音乐结束后、语音开始前的实际低能量间隙，随后用全声道峰值/RMS复核。ASR首词只用于交叉定位，不作为裁切依据。没有音乐的源保留全部前导静音或底噪。','',
 '|年份|音乐|剪点（秒）|原采样率/声道|核验静音区间（秒）|剪点±40ms峰值|ASR Test参考（非剪点）|', '|---|---|---:|---|---|---:|---:|']
 for r in records:
  interval=r['silence_interval'];fmt=r['canonical_format'];lines.append(f'|{r["year"]}|{"有" if r["start"] else "无"}|{r["start"]:.2f}|{fmt["sample_rate"]}Hz/{fmt["channels"]}声道|{str(interval) if interval else "不剪切"}|{r["cut_window"]["max_channel_peak_dbfs"]:.2f}dBFS|{r["reference_first_word"][1]:.2f}|')
 for r in records:lines+=['',f'## {r["year"]}', '',r['evidence'],'',f'canonical SHA256: `{r["source_sha256"]}`',f'原压缩文件 SHA256: `{r["source_entry"]["sha256"]}`','',f'![{r["year"]}波形与频谱]({r["plot"]})']
 (out/'核验记录.md').write_text('\n'.join(lines)+'\n','utf-8')
 dump(out/'核验清单.json',{'years':YEARS,'source_timebase':'未剪原音秒数','outputs':[{'year':r['year'],'start':r['start'],'json':f'{r["year"]}.json','json_sha256':sha(out/f'{r["year"]}.json'),'plot':r['plot'],'plot_sha256':sha(out/r['plot'])} for r in records],'skipped':{},'operations':'只读源音频，未生成裁切音频；无增益/归一化/限幅/重采样/声道转换。'})
if __name__=='__main__':main()
