import sys,json,numpy as np
sys.path.insert(0,'.')
from gaokao_tts import *
from qa import Checker
import soxr
voices=json.loads((HERE/'voices.json').read_text('utf-8'));vcfg=voices['female']
engine,pron=Engine(),Pronouncer();style=engine.style(vcfg['style'])
ck=Checker()
P={p['id']:p for p in json.load(open(ROOT/'data'/'vocab.json'))['passages']} if 'ROOT' in dir() else None
D=json.load(open('../../data/vocab.json'));P={p['id']:p for p in D['passages']}
def en(pid,k): return [s for pa in P[pid]['paras'] for s in pa][k-1]['en']
def t(pid,k,ov=None):
    key=f'{pid}:{k}'
    old=pron.sentence.get(key)
    if ov is not None: pron.sentence[key]=ov
    a=synth_sentence(pron.read_text(en(pid,k),key),key,engine,pron,style,vcfg.get('speed',1.0),vcfg)[0]
    if old is None: pron.sentence.pop(key,None)
    else: pron.sentence[key]=old
    a16=soxr.resample(a,SR,16000).astype(np.float32)
    outs=[ck.check(a16)[0]]
    pad=np.concatenate([np.zeros(2400,np.float32),a16,np.zeros(2400,np.float32)]);outs.append(ck.check(pad)[0])
    return outs
print(pron.phonemes('Yet the problem,'), '|', pron.phonemes('How do you mean?'),'|',pron.phonemes('for a change,'))
for name,pid,k,ov in [('p03 base','p03',2,None),('p03 prob1','p03',2,{'problem':'pɹˈɑbləm'}),('p03 prob2','p03',2,{'problem':'pɹˈɑblɪm'}),
                      ('p06 base','p06',9,None),('p06 mean1','p06',9,{'mean':'mˈin'}),('p06 mean2','p06',9,{'mean':'mˈiːn'}),
                      ('p30 base','p30',17,None),('p30 a1','p30',17,{'a':'ə'}),('p30 a2','p30',17,{'a':'ʌ'}),('p30 a3','p30',17,{'a':'eɪ'})]:
    print(name,t(pid,k,ov))
