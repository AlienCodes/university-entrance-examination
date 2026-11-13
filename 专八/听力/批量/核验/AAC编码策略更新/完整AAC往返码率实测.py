import sys,json,hashlib,subprocess,time
from pathlib import Path
import numpy as np,soundfile as sf
root=Path('/workspace/tem8-project');sys.path.insert(0,str(root/'专八/听力/批量/tools'))
from 精听 import compare_audio
base=Path('/workspace/tem8-aac-2015-analysis');out=base/'roundtrips';out.mkdir(exist_ok=True);work=base/'work'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump():
 (base/'AAC完整往返实测.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
prepared=json.loads((work/'prepared.json').read_text());tm=json.loads((work/'audio/timings.json').read_text())['cet4_male']['2015-A']
original,sr=sf.read(work/'source.wav',dtype='float32',always_2d=True);ref,sr2=sf.read(work/'audio'/tm['file'],dtype='float32',always_2d=True)
assert sr==sr2==44100==tm['sample_rate'] and original.shape[1]==ref.shape[1]==tm['channels']==2
body=np.concatenate([original[round(a*sr):round(b*sr)] for a,b in tm['kept_intervals']],axis=0);offset=round(1.5*sr)
assert np.array_equal(body,ref[offset:offset+len(body)])
report={'id':'2015-A','scope':'同run43517487459精听输入/核心字节、同canonical原音、同prepare后的完整音轨；仅分析副本，未修改源或生产代码，未生成视频。','input_provenance':json.loads((base/'input-provenance.json').read_text()),'thresholds':{'max_abs_gain_db':.05,'min_snr_db':30.,'max_second_level_db':1.},'ffmpeg':subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0],'prepared_sha256':sha(work/'prepared.json'),'timings_sha256':sha(work/'audio/timings.json'),'prepared_audio_sha256':sha(work/'audio'/tm['file']),'prepared_audio_expected_sha256':tm['audio_sha256'],'source_sha256':tm['source_sha256'],'sample_rate':sr,'channels':2,'source_window':tm['window'],'kept_intervals':tm['kept_intervals'],'lead_samples':offset,'body_frames':len(body),'compiled_frames':len(ref),'duration_seconds':len(ref)/sr,'raw_exact_before_encoding':True,'body_pcm_float32_sha256':hashlib.sha256(memoryview(np.ascontiguousarray(body))).hexdigest(),'results':[]}
assert report['prepared_audio_sha256']==report['prepared_audio_expected_sha256'];dump()
for rate in [192,256,320]:
 encoded=out/f'complete-{rate}k.m4a';decoded=out/f'complete-{rate}k.wav';enc=['ffmpeg','-y','-v','error','-i',str(work/'audio'/tm['file']),'-c:a','aac','-b:a',str(rate)+'k',str(encoded)];dec=['ffmpeg','-y','-v','error','-i',str(encoded),'-c:a','pcm_f32le',str(decoded)]
 started=time.monotonic();subprocess.run(enc,check=True);subprocess.run(dec,check=True);got,sr3=sf.read(decoded,dtype='float32',always_2d=True);assert sr3==sr and got.shape[1]==2
 use=got[offset:offset+len(body)];bad,measure=compare_audio(body,use,sr);assert use.shape==body.shape
 e=(body*body).sum();error=use-body;snr=10*np.log10(e/max((error*error).sum(),1e-30))
 info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(encoded)]));stream=next(s for s in info['streams'] if s['codec_type']=='audio');assert int(stream['sample_rate'])==sr and stream['channels']==2
 row={'requested_aac_kbps':rate,'ok':not bad,'problems':bad,'measure':measure,'snr_unrounded_db':float(snr),'snr_margin_above_30_db':float(snr)-30.,'encoded':{'file':encoded.name,'sha256':sha(encoded),'bytes':encoded.stat().st_size,'stream':{k:stream.get(k) for k in ['codec_name','sample_rate','channels','channel_layout','duration','bit_rate','nb_frames']}},'decoded':{'file':decoded.name,'sha256':sha(decoded),'frames':len(got),'sample_rate':sr3,'channels':got.shape[1]},'encode_argv':enc,'decode_argv':dec,'elapsed_seconds':round(time.monotonic()-started,2),'no_resampling_or_gain_filter':True};report['results'].append(row);dump();print(json.dumps({'kbps':rate,'ok':not bad,'measure':measure,'snr_unrounded':float(snr),'problems':bad},ensure_ascii=False),flush=True)
 del got,use,error
passed=[r['requested_aac_kbps'] for r in report['results'] if r['ok']];report['lowest_sufficient_tested_kbps']=min(passed) if passed else None
report['input_and_core_unchanged_after_tests']={p:sha(root/p)==v['current_sha256'] for p,v in report['input_provenance']['production_code'].items()};report['canonical_source_sha256_after']=sha(base/'in/原音.wav');assert report['canonical_source_sha256_after']==report['source_sha256'] and all(report['input_and_core_unchanged_after_tests'].values());dump();print('最低已测充分码率',report['lowest_sufficient_tested_kbps'],flush=True)
