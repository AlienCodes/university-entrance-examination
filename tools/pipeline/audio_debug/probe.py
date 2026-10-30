import sys,json,numpy as np,soundfile as sf,soxr
sys.path.insert(0,'.')
from qa import Checker
from gaokao_tts import OUT
T=json.load(open(OUT/'timings.json'))['female']
ck=Checker()
for pid,k in [('p13',21),('p17',4),('p17',10)]:
    t=T[pid]['sentences'][k-1]
    a,sr=sf.read(str(OUT/T[pid]['file']),dtype='float32');a16=soxr.resample(a,sr,16000).astype(np.float32)
    print(pid,k,t['parts'])
    for s0,s1 in [(0,0),(-0.15,0.15),(0,-0.08),(0,-0.15)]:
        seg=a16[int((t['start']+s0)*16000):int((t['end']+s1)*16000)]
        print('  ',s0,s1,ck.check(seg)[0])
    for (ps,pe) in t['parts']:
        seg=a16[int(ps*16000):int(pe*16000)]
        print('   part',round(ps,2),round(pe,2),ck.check(seg)[0])
