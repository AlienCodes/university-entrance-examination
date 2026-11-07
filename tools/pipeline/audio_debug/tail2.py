import sys,json,numpy as np,soxr
sys.path.insert(0,'.')
from gaokao_tts import *
from qa import Checker
voices=json.loads((HERE/'voices.json').read_text('utf-8'));vcfg=voices['female']
engine,pron=Engine(),Pronouncer();style=engine.style(vcfg['style']);ck=Checker()
def hiss(a):
    w=int(SR*0.025);n=len(a);m=0
    for i in range(6,0,-1):
        x=a[n-i*w:n-(i-1)*w];rms=20*np.log10(np.sqrt(np.mean(x**2))+1e-9);zcr=np.mean(np.abs(np.diff(np.sign(x))))/2
        if rms>-42: m=max(m,zcr)
    return m
def tryit(ph):
    a=engine.synth(ph,style,vcfg.get('speed',1.0))
    return round(hiss(a),2), ck.check(soxr.resample(a,SR,16000).astype(np.float32))[0]
for ph in ['jˈɛt ðə pɹˈɑbləm,','jˈɛt ðə pɹˈɑblɪm,','jˈɛt ðə pɹˈɑbləm.','jˈɛt ðə pɹˈɑbləm;','jˈɛt ðə pɹˈɑblᵊm,','jˈɛt ðə pɹˈɑbləm —',
           'hˌW dˈu ju mˈin?','hˌW dˈu ju mˈiːn?','hˌW dˈu ju mˈin?”','hˌW dˈu ju mˈinn?','hˌW dˈu ju mˈɪn?','hˌW dˌu ju mˈin?','hˈW dˈu ju mˈin?']:
    print(f'{ph:28s}',tryit(ph))
