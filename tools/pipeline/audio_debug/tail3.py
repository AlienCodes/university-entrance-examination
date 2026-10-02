import sys,json,numpy as np,soxr
sys.path.insert(0,'.')
from gaokao_tts import *
from qa import Checker
voices=json.loads((HERE/'voices.json').read_text('utf-8'));vcfg=voices['female']
engine,pron=Engine(),Pronouncer();style=engine.style(vcfg['style']);ck=Checker()
def fric(a):
    # 末尾高过零率（摩擦音）持续时长，毫秒
    w=int(SR*0.01);n=len(a);d=0
    ref=20*np.log10(np.sqrt(np.mean(a**2))+1e-9)
    for i in range(1,60):
        x=a[n-i*w:n-(i-1)*w];rms=20*np.log10(np.sqrt(np.mean(x**2))+1e-9);z=np.mean(np.abs(np.diff(np.sign(x))))/2
        if rms>ref-30 and z>0.25: d+=10
    return d
for txt in ['For further proof,','For further proofs,','the roof,','For further proof.','a strong proof,','For further evidence,']:
    a=engine.synth(pron.phonemes(txt),style,vcfg.get('speed',1.0))
    print(f'{txt:24s} 摩擦尾 {fric(a)}ms ',ck.check(soxr.resample(a,SR,16000).astype(np.float32))[0])
