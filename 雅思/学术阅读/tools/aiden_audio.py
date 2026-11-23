"""Read whole sentences with the auditioned voice and certify the original IELTS pauses."""
from difflib import SequenceMatcher
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata

import numpy as np
import soundfile as sf
import soxr

from aiden_profile import DIRECTION, IDENTITY, MODEL, PROFILE, REVISION, SPEAKER
import make_audio as cet
import 听对


def words(text):
    from textnorm import normalize
    text=unicodedata.normalize('NFKD',normalize(text)).encode('ascii','ignore').decode().lower()
    text=text.replace('colour','color').replace('centre','center').replace('metre','meter')
    return re.findall(r'[a-z0-9]+',text.replace("'",''))


def recognize(audio):
    rec=听对.recognizer()
    stream=rec.create_stream()
    stream.accept_waveform(16000,soxr.resample(audio,24000,16000).astype(np.float32))
    rec.decode_stream(stream)
    tokens=[]
    for tok,t in zip(stream.result.tokens,stream.result.timestamps):
        if not tokens or tok.startswith((' ','▁')):
            tokens.append([tok.lstrip(' ▁'),float(t)])
        else:tokens[-1][0]+=tok
    timed=[(w,t) for spelling,t in tokens for w in words(spelling)]
    return stream.result.text,timed


def match_script(script,transcript):
    expected=words(script);heard=words(transcript)
    if not expected:return False
    seq=SequenceMatcher(None,expected,heard,autojunk=False)
    matched=sum(b.size for b in seq.get_matching_blocks())
    edits=[(i2-i1,j2-j1) for tag,i1,i2,j1,j2 in seq.get_opcodes() if tag!='equal']
    # Proper names and spelling variants can look different in ASR; clear extra,
    # missing or repeated strings must be reread. Retain the transcript for review.
    if len(expected)<=4:
        return matched==len(expected) and len(heard)<=len(expected)+1 or (
            len(expected)==len(heard) and SequenceMatcher(None,' '.join(expected),' '.join(heard)).ratio()>=.78)
    return (matched >= .80*len(expected) and matched >= .80*len(heard)
            and not any(max(a,b)>2 for a,b in edits))


def voiced_parts(audio,parts,timed):
    if len(parts)==1:return [audio]
    expected=[w for phrase in parts for w in words(phrase)]
    seq=SequenceMatcher(None,expected,[w for w,t in timed],autojunk=False)
    mapped={b.a+i:b.b+i for b in seq.get_matching_blocks() for i in range(b.size)}
    sr=24000; hop=120
    n=len(audio)//hop
    energy=np.sqrt(np.mean(audio[:n*hop].reshape(n,hop).astype(np.float64)**2,axis=1))
    cuts=[0];index=0
    for phrase in parts[:-1]:
        index+=len(words(phrase))
        if index not in mapped or index-1 not in mapped:return None
        left=timed[mapped[index-1]][1];right=timed[mapped[index]][1]
        lo=max(int((left+.045)*sr/hop),int((right-.40)*sr/hop),int(cuts[-1]/hop)+8)
        hi=min(n,int((right+.035)*sr/hop))
        if hi-lo<6:return None
        window=energy[lo:hi]
        smooth=np.convolve(window,np.ones(6)/6,mode='valid')
        j=int(np.argmin(smooth))
        if smooth[j]>.012:return None
        cuts.append((lo+j+3)*hop)
    cuts.append(len(audio))
    return [cet.G.trim(audio[l:r],pad=.035) for l,r in zip(cuts,cuts[1:])]


class Aiden:
    def __init__(self):
        self.model=None
        self.review={}
        self.folder=Path(os.environ.get('IELTS_WORK',os.environ.get('RUNNER_TEMP','/tmp')))/'aiden-takes'
        self.folder.mkdir(parents=True,exist_ok=True)

    def style(self,_):
        return SPEAKER

    def render(self,script,seed,pron):
        import torch
        if self.model is None:
            from huggingface_hub import snapshot_download
            from qwen_tts import Qwen3TTSModel
            torch.set_num_threads(min(4,len(os.sched_getaffinity(0))))
            folder=snapshot_download(MODEL,revision=REVISION)
            self.model=Qwen3TTSModel.from_pretrained(folder,dtype=torch.float32,device_map='cpu',attn_implementation='sdpa')
        instruction=DIRECTION
        names=[f'{name} /{ipa}/' for name,ipa in pron.lexicon.items() if re.search(r'\b'+re.escape(name)+r'\b',script,re.I)]
        if names:instruction+=' Pronunciation of names in this sentence: '+', '.join(names)+'.'
        torch.manual_seed(seed)
        cap=min(1800,max(200,len(script.split())*14+120))
        with torch.inference_mode():
            waves,sr=self.model.generate_custom_voice(text=script,speaker=SPEAKER,language='English',
                instruct=instruction,max_new_tokens=cap)
        wave=np.asarray(waves[0],dtype=np.float32)
        if sr!=24000 or wave.ndim!=1 or len(wave)<.15*sr or not np.isfinite(wave).all() or not (np.max(np.abs(wave))>.01):
            raise ValueError('Invalid Aiden waveform')
        return cet.G.trim(wave,pad=.045)

    def take(self,script,key,variant,pron):
        fingerprint=json.dumps([IDENTITY,script,key,variant,pron.lexicon],sort_keys=True,ensure_ascii=False)
        name=hashlib.sha256(fingerprint.encode()).hexdigest()
        file=self.folder/(name+'.flac');report=self.folder/(name+'.json')
        if file.is_file() and report.is_file():
            data=json.loads(report.read_text());wave,sr=sf.read(file,dtype='float32')
            if sr==24000 and hashlib.sha256(file.read_bytes()).hexdigest()==data['sha256']:
                return wave,data
        number=int(key.split(':')[1]);seed=24830+number+variant*173
        for attempt in range(2):
            wav=self.render(script,seed+attempt*997,pron)
            transcript,timed=recognize(wav)
            if match_script(script,transcript):
                sf.write(file,wav,24000,subtype='PCM_24')
                data=dict(transcript=transcript,timed=timed,seed=seed+attempt*997,sha256=hashlib.sha256(file.read_bytes()).hexdigest())
                report.write_text(json.dumps(data,ensure_ascii=False))
                return wav,data
        raise ValueError(f'{key} Aiden transcript needs review: {script!r} / {transcript!r}')

    def sentence(self,read,key,engine,pron,style,speed,settings):
        parts=cet.narration_phrases(read,key,settings['clause_pause'])
        script=' '.join(parts)
        variant=round((speed/settings['speed']-1)*1000)
        try:
            audio,evidence=self.take(script,key,variant,pron)
            chunks=voiced_parts(audio,parts,evidence['timed'])
        except ValueError:
            if len(parts)==1:raise
            chunks=None
        if chunks is None:
            takes=[self.take(text,key,variant+1000*(i+1),pron) for i,text in enumerate(parts)]
            chunks=[x[0] for x in takes]
            records=[x[1] for x in takes];basis='semantic groups'
        else:records=[evidence];basis='whole sentence'
        self.review[key]=dict(recognized=True,method=basis,groups=len(chunks),
            transcripts=[r['transcript'] for r in records],seeds=[r['seed'] for r in records])
        print(key,basis,len(chunks),'groups',flush=True)
        return cet.synth_sentence(read,key,engine,pron,style,speed,settings,recorded=chunks)
