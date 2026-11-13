"""2009源文印误/漏词的独立Whisper证据；不造词时刻、不自动改源稿。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import numpy as np
import sherpa_onnx

B = Path(__file__).resolve().parents[1]
WINDOWS = [
 ('word_words',45.4,55.4),('have_had',134.4,142.4),('extra_report',272.5,281.),
 ('result_results',285.0,294.0),('list_1_3',368.5,389.),('list_4_5',389.,402.),
 ('would_will',425.,435.),('extra_implications',472.,481.),('extra_you',497.,506.),
 ('the_this',536.,545.),('contradicted',547.,558.),('is_its',878.,889.),
 ('manual_menu',1106.,1119.),('extra_is_a_speech',1119.,1131.),
 ('a_er',1172.,1184.),('an_toast',1193.,1206.),('continues_continued',1218.,1229.),
 ('you_are_welcome',1242.,1255.),('question_7_menu',1275.,1289.),('question_8_mrs',1291.,1305.),
 ('grammarians_article',1167.,1175.)]


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',required=True,type=Path);p.add_argument('--input-root',type=Path,default=Path('/workspace/tem8-input'));args=p.parse_args()
    prep=json.loads((B/'预处理/2009/原音准备.json').read_text());primary=json.loads((B/'预处理/2009/识别.json').read_text());entry=prep['source_entries'][0];src=args.input_root/entry['file'];assert sha(src)==entry['sha256']
    files={k:args.model/('base.en-'+v) for k,v in [('encoder','encoder.int8.onnx'),('decoder','decoder.int8.onnx'),('tokens','tokens.txt')]}
    asr=sherpa_onnx.OfflineRecognizer.from_whisper(**{k:str(v) for k,v in files.items()},num_threads=2,enable_token_timestamps=True,enable_segment_timestamps=True)
    out=B/'核验/2009-原文独立复核.json';rows=json.loads(out.read_text())['windows'] if out.exists() else []
    for key,lo,hi in WINDOWS:
        if any(x['key']==key for x in rows):continue
        pcm=subprocess.check_output(['ffmpeg','-v','error','-ss',str(lo),'-t',str(hi-lo),'-i',str(src),'-f','f32le','-ac','1','-ar','16000','-'])
        stream=asr.create_stream();stream.accept_waveform(16000,np.frombuffer(pcm,dtype='<f4'));start=time.monotonic();asr.decode_stream(stream);r=stream.result
        rows.append({'key':key,'window':[lo,hi],'primary_text':' '.join(w[0] for w in primary if lo<=w[1]<hi),'secondary_text':r.text,'tokens':r.tokens,'timestamps':r.timestamps,'elapsed_seconds':round(time.monotonic()-start,3),'status':'independent_machine_evidence_requires_adjudication'})
        out.write_text(json.dumps({'year':2009,'canonical_sha256':prep['canonical']['sha256'],'source_file':entry['file'],'source_sha256':entry['sha256'],'primary_asr_sha256':sha(B/'预处理/2009/识别.json'),'model':'sherpa-onnx-whisper-base.en-int8','model_files':{k:{'name':v.name,'sha256':sha(v)} for k,v in files.items()},'script_sha256':sha(__file__),'analysis_only':'内存16k单声道，正式原音未改；Whisper未提供的词时刻不补造。','windows':rows},ensure_ascii=False,indent=2)+'\n')
        print(key,lo,hi,r.text,flush=True)


if __name__=='__main__':main()
