"""Read whole sentences with the auditioned voice and certify the original IELTS pauses."""
import hashlib
import json
import os
from pathlib import Path
import re
from difflib import SequenceMatcher

import numpy as np
import soundfile as sf
import soxr

from aiden_profile import DIRECTION, IDENTITY, SPEAKER
from aiden_boundaries import POLICY, assess, words, reference
from aiden_checkpoint import PeriodicSnapshot
import make_audio as cet
import 听对


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


class Aiden:
    def __init__(self):
        self.model=None
        self.review={}
        self.rejected_master_takes={}
        self.folder=Path(os.environ.get('IELTS_WORK',os.environ.get('RUNNER_TEMP','/tmp')))/'aiden-takes'
        self.folder.mkdir(parents=True,exist_ok=True)
        self.snapshots=PeriodicSnapshot(self.folder)

    def style(self,_):
        return SPEAKER

    def render(self,script,seed,pron):
        import torch
        if self.model is None:
            from aiden_model import restore
            from qwen_tts import Qwen3TTSModel
            torch.set_num_threads(min(4,len(os.sched_getaffinity(0))))
            folder=restore(Path(os.environ['IELTS_AIDEN_MODEL_PATH']),verify_only=True)
            self.model=Qwen3TTSModel.from_pretrained(str(folder),dtype=torch.float32,device_map='cpu',attn_implementation='sdpa')
        instruction=DIRECTION
        names=[f'{name} /{ipa}/' for name,ipa in pron.lexicon.items() if re.search(r'\b'+re.escape(name)+r'\b',script,re.I)]
        if names:instruction+=' Pronunciation of names in this sentence: '+', '.join(names)+'.'
        if words(script) in (['quercus','suber'], ['quirkus','soober']):
            from aiden_cork_oak import HINT
            instruction += ' ' + HINT
        if re.search(r'\bLei Tzu\b',script,re.I):
            instruction += ' Pronounce Lei Tzu (Léi Zǔ) in two connected syllables: lay tsoo, with /ts/ at the start of tsoo.'
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
        previous_seed=None
        if file.is_file() and report.is_file():
            data=json.loads(report.read_text());wave,sr=sf.read(file,dtype='float32')
            if sr==24000 and hashlib.sha256(file.read_bytes()).hexdigest()==data['sha256']:
                if data['sha256'] in self.rejected_master_takes:
                    rejected=self.folder/'rejected'
                    rejected.mkdir(exist_ok=True)
                    failed=rejected/(data['sha256']+'.flac')
                    if not failed.exists():
                        failed.write_bytes(file.read_bytes())
                        evidence=dict(data,accepted=False,key=key,printed=script,stage='mastered-mp3',
                                      issue=self.rejected_master_takes[data['sha256']])
                        failed.with_suffix('.json').write_text(json.dumps(evidence,ensure_ascii=False))
                    previous_seed=data['seed']
                elif data.get('policy') == POLICY and words(script) != ['quercus','suber']:
                    return wave,data
                else:
                    try:
                        assess(soxr.resample(wave,sr,16000),script,data['transcript'])
                    except ValueError:
                        pass
                    else:
                        data['policy']=POLICY
                        report.write_text(json.dumps(data,ensure_ascii=False))
                        return wave,data
        number=int(key.split(':')[1]);seed=24830+number+variant*173
        if previous_seed is not None:
            seed=previous_seed+5*997
        spoken=script
        for attempt in range(5):
            rendered_text=spoken
            wav=self.render(rendered_text,seed+attempt*997,pron)
            transcript,timed=recognize(wav)
            try:
                assess(soxr.resample(wav,24000,16000),script,transcript)
            except ValueError as error:
                issue=str(error)
                if attempt >= 1:
                    expected=words(script)
                    alignment=SequenceMatcher(None,expected,words(transcript),autojunk=False)
                    missing={w for op,a,b,_,_ in alignment.get_opcodes() if op in ('replace','delete')
                             for w in expected[a:b] if w in {'it','its','the','a','an','at','of','to','not'}}
                    spoken=re.sub(r'\b[a-z]+\b',lambda m:m[0].upper() if m[0] in missing else m[0],script)
                if words(script) == ['quercus','suber']:
                    spoken = 'Quirkus Soober'
                print(f'{key} rereading intact phrase: {issue}',flush=True)
                continue
            sf.write(file,wav,24000,subtype='PCM_24')
            data=dict(transcript=transcript,timed=timed,seed=seed+attempt*997,
                      sha256=hashlib.sha256(file.read_bytes()).hexdigest(),policy=POLICY)
            report.write_text(json.dumps(data,ensure_ascii=False))
            return sf.read(file,dtype='float32')[0],data
        # Retain the actual sound for reviewing a name or dropout. Only flat,
        # certified take files are eligible for restoration or mastering.
        rejected=self.folder/'rejected'
        rejected.mkdir(exist_ok=True)
        candidate=rejected/file.name
        sf.write(candidate,wav,24000,subtype='PCM_24')
        evidence=dict(accepted=False, key=key, printed=script, rendered=rendered_text,
                      seed=seed+attempt*997, transcript=transcript, issue=issue,
                      sha256=hashlib.sha256(candidate.read_bytes()).hexdigest())
        (rejected/report.name).write_text(json.dumps(evidence,ensure_ascii=False))
        raise ValueError(f'{key}: {issue}')

    def sentence(self,read,key,engine,pron,style,speed,settings):
        parts=cet.narration_phrases(read,key,settings['clause_pause'])
        variant=round((speed/settings['speed']-1)*1000)
        # Each pause is between whole takes. No word is cut at an ASR timestamp.
        takes=[self.take(part,key,variant if len(parts)==1 else variant+1000*i,pron)
               for i,part in enumerate(parts,1)]
        self.snapshots.after_sentence()
        chunks=[wave for wave,_ in takes]
        records=[data for _,data in takes]
        basis=POLICY
        self.review[key]=dict(recognized=True,method=basis,groups=len(parts),
            phrases=[dict(text=text,sha256=data['sha256'],reference=reference(soxr.resample(wave,24000,16000)))
                     for text,(wave,data) in zip(parts,takes)],
            transcripts=[r['transcript'] for r in records],seeds=[r['seed'] for r in records])
        print(key,basis,len(chunks),'groups',flush=True)
        return cet.synth_sentence(read,key,engine,pron,style,speed,settings,recorded=chunks)
