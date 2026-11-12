"""按原音SHA-256锁定的真实片段重新识别，补查遗漏及具体疑词；不冒充人工耳听。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import sherpa_onnx

HERE=Path(__file__).resolve().parent
C=HERE.parent
ROOT=C.parents[1]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('sid');ap.add_argument('start',type=float);ap.add_argument('end',type=float)
    ap.add_argument('--original',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    source=json.loads((C/'准备/来源清单.json').read_text())['套'][args.sid]['原音_sha256']
    assert sha(args.original)==source
    assert 0<=args.start<args.end
    model=ROOT/'tools/tts/models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8'
    recognizer=sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(model/'encoder.int8.onnx'),decoder=str(model/'decoder.int8.onnx'),
        joiner=str(model/'joiner.int8.onnx'),tokens=str(model/'tokens.txt'),model_type='nemo_transducer',num_threads=2)
    pcm=subprocess.check_output(['ffmpeg','-v','error','-ss',str(args.start),'-t',str(args.end-args.start),
                                 '-i',str(args.original),'-vn','-ac','1','-ar','16000','-f','f32le','-'])
    audio=np.frombuffer(pcm,dtype=np.float32)
    st=recognizer.create_stream();st.accept_waveform(16000,audio);recognizer.decode_stream(st)
    result=st.result;words=[];cur=None
    for tok,t in zip(result.tokens,result.timestamps):
        if tok.startswith(' ') or cur is None:
            if cur:words.append(cur)
            cur=[tok.strip(),round(args.start+t,3),round(args.start+t+.08,3)]
        else:
            cur[0]+=tok;cur[2]=round(args.start+t+.08,3)
    if cur:words.append(cur)
    d={'sid':args.sid,'原音_sha256':source,'窗口':[args.start,args.end],
       '模型':'sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8','encoder_sha256':sha(model/'encoder.int8.onnx'),
       '说明':'真实原音局部重识别；时间为模型相对时刻加片段起点，不是人工猜测。','text':result.text,'words':words}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(d,ensure_ascii=False,indent=1)+'\n')
    print(result.text)
    print('原音局部识别词数',len(words),'→',args.out)


if __name__=='__main__':main()
