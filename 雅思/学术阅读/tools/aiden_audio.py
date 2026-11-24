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
from aiden_boundaries import POLICY, assess, independent, words, reference
from aiden_checkpoint import PeriodicSnapshot, rejected_seed
import aiden_cork_oak
import aiden_cork_taint
import aiden_ceylonese
import aiden_inuktitut
import aiden_sobchack
import aiden_de_dreu
import aiden_turkish
import aiden_heyerdahl
import make_audio as cet
import 听对


class UnverifiedTake(ValueError):
    def __init__(self, key, position, reason):
        self.key = key
        self.position = position
        super().__init__(f'{key}: {reason}')


def planned_takes(read,key,settings,variant=0):
    parts=cet.narration_phrases(read,key,settings['clause_pause'])
    return [(part,variant if len(parts)==1 else variant+1000*i) for i,part in enumerate(parts,1)]


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
        names=[f'{name} /{ipa}/' for name,ipa in pron.lexicon.items()
               if name.casefold() not in {'ceylonese', aiden_turkish.ORAL} and re.search(r'\b'+re.escape(name)+r'\b',script,re.I)]
        if names:instruction+=' Pronunciation of names in this sentence: '+', '.join(names)+'.'
        if script.strip(' ,.;:!?').casefold() in {s.casefold() for s in aiden_cork_oak.RENDERINGS}:
            instruction += ' ' + aiden_cork_oak.HINT
        if any(form.casefold() in script.casefold() for form in aiden_cork_taint.RENDERINGS):
            instruction += ' ' + aiden_cork_taint.HINT
        if re.search(r'\bLei Tzu\b',script,re.I):
            instruction += ' Pronounce Lei Tzu (Léi Zǔ) in two connected syllables: lay tsoo, with /ts/ at the start of tsoo.'
        if re.search(r'\b(?:Halley|Hally)\b',script,re.I):
            instruction += ' Read the astronomer’s surname Halley in two connected syllables /ˈhæli/, with an audible initial h.'
        if re.search(r"\bPerkin['’]s\b",script,re.I):
            instruction += ' Read the possessive of Perkin as /ˈpɝkɪnz/: two syllables in total, ending in a single /z/.'
        if any(re.search(r'\b'+re.escape(name)+r'\b',script,re.I) for name in aiden_ceylonese.RENDERINGS):
            instruction += ' ' + aiden_ceylonese.HINT
        if 'I I N C E' in script:
            instruction += ' Read the five initials I, I, N, C, E clearly in one connected group, including both initial I sounds.'
        if words(script)[:5] == ['sugars','and','meats','or','oils']:
            instruction += ' Pronounce the opening word sugars /ˈʃʊɡɚz/, with a soft sh and a voiced final z.'
        if re.search(r'\b(?:fusee|fuzee|fyoo-zee)\b',script,re.I):
            instruction += ' Pronounce the clock term fusee in two connected syllables, fyoo-ZEE /fjuːˈziː/, with a clear final ee vowel.'
        if any(form.casefold() in script.casefold() for form in aiden_inuktitut.RENDERINGS):
            instruction += ' ' + aiden_inuktitut.HINT
        if any(form.casefold() in script.casefold() for form in aiden_sobchack.RENDERINGS):
            instruction += ' Read the family name Sobchack in two syllables: sob-chack. Go directly from b to ch and pronounce the final k.'
        if any(form.casefold() in script.casefold() for form in aiden_de_dreu.RENDERINGS):
            instruction += ' ' + aiden_de_dreu.HINT
        if any(form.casefold() in script.casefold() for form in aiden_turkish.RENDERINGS):
            instruction += ' ' + aiden_turkish.HINT
        if script.strip(' ,.;:!?').casefold() in {form.casefold() for form in aiden_heyerdahl.RENDERINGS}:
            instruction += ' ' + aiden_heyerdahl.HINT
        if "butterley engineering's steelworks" in script.casefold().replace('’', "'"):
            instruction += ' Preserve the possessive z in Engineering’s before the initial s of Steelworks. Read the words together naturally.'
        if words(script) == ['a','hydraulic','clamp']:
            instruction += ' End clamp with a short, clear p release after m, without adding a vowel.'
        if re.search(r'\b(?:Dowman|Dow Man)\b',script,re.I):
            instruction += ' Say Captain Dowman’s name with the vowel in cow, then man. Keep the two syllables joined.'
        if re.search(r'\bDeane? dived down\b',script,re.I):
            instruction += ' In "Deane dived down", articulate the past tense /daɪvd/, linking its final d naturally into "down".'
        if re.search(r"\bapproached the helicopter",script,re.I):
            instruction += ' The first verb is in the past. Finish approached with /tʃt/ before the following word.'
        if 'Villamil' in script or 'vee-yah-MEEL' in script:
            instruction += ' Puerto Villamil ends in a stressed meel with a final l. Link the following words “on Isabela” without adding a vowel to the town name.'
        if 'llewyn' in script.casefold():
            instruction += ' For the Welsh word llewyn, begin with Welsh ll /ɬ/, with voiceless air flowing past the sides of the tongue into the vowel.'
        if words(script)[:2]==['forested','hills']:
            instruction += ' In forested hills, start with a clear f followed by the stressed first syllable of forest. Sound the complete three-syllable adjective before hills.'
        if words(script)[-1:]==['bottlenecks']:
            instruction += ' Finish the plural bottlenecks with the whole final syllable, including the k and s sounds.'
        if 'Sommerkorn' in script or 'Zommerkorn' in script:
            instruction += ' Read Martin Sommerkorn with a voiced z, a short first vowel and the final consonants in korn, as in his own introduction. Use one connected surname.'
        if 'Doctor Phil Rasch' in script:
            instruction += ' Say "And Doctor" as two clearly distinguishable words. The scientist’s surname rhymes with rash.'
        torch.manual_seed(seed)
        cap=min(1800,max(200,len(script.split())*14+120))
        with torch.inference_mode():
            waves,sr=self.model.generate_custom_voice(text=script,speaker=SPEAKER,language='English',
                instruct=instruction,max_new_tokens=cap)
        wave=np.asarray(waves[0],dtype=np.float32)
        if sr!=24000 or wave.ndim!=1 or len(wave)<.15*sr or not np.isfinite(wave).all() or not (np.max(np.abs(wave))>.01):
            raise ValueError('Invalid Aiden waveform')
        return cet.G.trim(wave,pad=.045)

    def recheck_diagnostic(self,file,report,script,seed):
        raw=self.folder/'rejected'/file.name
        recording=raw.read_bytes()
        digest=hashlib.sha256(recording).hexdigest()
        if digest in self.rejected_master_takes:return None
        wave,rate=sf.read(raw,dtype='float32')
        if rate!=24000 or wave.ndim!=1:return None
        transcript,timed=recognize(wave)
        audio=soxr.resample(wave,rate,16000)
        if not timed:
            return None
        # Dedicated acoustic checks require both recognizers to match the
        # English context even when they transcribe a foreign word differently.
        if not {'dreu','heyerdahl','butterley','dowman','sommerkorn',aiden_cork_taint.TERM,aiden_turkish.ORAL}.intersection(words(script)) and (words(transcript)!=words(script) or words(independent(audio))!=words(script)):
            return None
        try:
            assess(audio,script,transcript)
        except ValueError:
            return None
        file.write_bytes(recording)
        data=dict(transcript=transcript,timed=timed,seed=seed,sha256=digest,
                  policy=POLICY,rechecked_from_diagnostic=True)
        report.write_text(json.dumps(data,ensure_ascii=False))
        return wave,data

    def take(self,script,key,variant,pron,position=0):
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
                elif (data.get('policy') == POLICY and words(script) != ['quercus','suber']
                      and not {'ceylonese','fusee','qaujimajatuqangit','sobchack','dreu','heyerdahl','butterley','dowman','sommerkorn',aiden_cork_taint.TERM,aiden_turkish.ORAL}.intersection(words(script))):
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
        failed_seed=rejected_seed(self.folder/'rejected'/report.name,key,script)
        if failed_seed is not None:
            seed=max(seed,failed_seed+997)
            checked=self.recheck_diagnostic(file,report,script,failed_seed)
            if checked is not None:return checked
        spoken=script
        spellings=()
        if words(script)==['quercus','suber']:
            spellings=aiden_cork_oak.RENDERINGS
        elif aiden_cork_taint.TERM in words(script):
            spellings=aiden_cork_taint.RENDERINGS
        elif 'ceylonese' in words(script):
            spellings=aiden_ceylonese.RENDERINGS
        elif 'fusee' in words(script):
            spellings=('fusee','fuzee','fyoo-ZEE','fusee','fyoo-zee')
        elif 'qaujimajatuqangit' in words(script):
            spellings=aiden_inuktitut.RENDERINGS
        elif 'sobchack' in words(script):
            spellings=aiden_sobchack.RENDERINGS
        elif re.search(r'\bDe Dreu\b',script,re.I):
            spellings=aiden_de_dreu.RENDERINGS
        elif words(script)==['deane','dived','down']:
            spellings=('Deane dived down','Dean DIVED down','Deane DIVED down','Dean dived down','Deane dived down')
        elif words(script)[:3]==['approached','the','helicopters']:
            spellings=('approached','APPROACHED','approached','Approached','APPROACHED')
        elif 'Puerto Villamil' in script:
            spellings=('Puerto Villamil','Puerto vee-yah-MEEL','Puerto Villamil','Puerto vee-yah-MEEL','Puerto Villamil')
        elif words(script)[:2]==['forested','hills']:
            spellings=('forested hills','Forested hills','FORESTED hills','Forested hills','forested hills')
        elif words(script) == ['dowman','was','determined']:
            spellings=('Dowman','Dow Man','Dowman','Dow-man','Dowman')
        elif 'sommerkorn' in words(script):
            spellings=('Sommerkorn','Zommerkorn','Sommerkorn','Zommer-korn','Sommerkorn')
        elif words(script) == ['thor', 'heyerdahl']:
            spellings=aiden_heyerdahl.RENDERINGS
        elif aiden_turkish.ORAL in words(script):
            spellings=aiden_turkish.RENDERINGS
        for attempt in range(len(spellings) if spellings else 5):
            if spellings and attempt:
                # Preserve all surrounding printed words, even in a long phrase.
                spoken=re.sub(re.escape(spellings[0]),spellings[attempt],script,flags=re.I)
            elif attempt in (1,3) and re.search(r'\bHalley\b',script,re.I):
                # CMUdict transcribes Halley and Hally identically. Verify the result against the paper.
                spoken=re.sub(r'\bHalley\b','Hally',script,flags=re.I)
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
        raise UnverifiedTake(key,position,issue)

    def save_remaining_takes(self,passage,config,pron,failure):
        first=int(failure.key.rsplit(':',1)[1])
        sentences=(text for paragraph in passage['sents'] for text in paragraph)
        failures=[str(failure)]
        for number,text in enumerate(sentences,1):
            if number<first:
                continue
            key=f'{passage["id"]}:{number}'
            read=pron.read_text(text,key)
            for index,(part,variant) in enumerate(planned_takes(read,key,config)):
                if number==first and index<=failure.position:
                    continue
                try:
                    self.take(part,key,variant,pron,index)
                except UnverifiedTake as error:
                    failures.append(str(error))
            self.snapshots.after_sentence()
        self.snapshots.after_sentence(force=True)
        print('Unverified recordings still required before mastering:',*failures,sep='\n',flush=True)

    def sentence(self,read,key,engine,pron,style,speed,settings):
        variant=round((speed/settings['speed']-1)*1000)
        plan=planned_takes(read,key,settings,variant)
        # Each pause is between whole takes. No word is cut at an ASR timestamp.
        takes=[self.take(part,key,offset,pron,i) for i,(part,offset) in enumerate(plan)]
        self.snapshots.after_sentence()
        chunks=[wave for wave,_ in takes]
        records=[data for _,data in takes]
        basis=POLICY
        self.review[key]=dict(recognized=True,method=basis,groups=len(plan),
            phrases=[dict(text=text,sha256=data['sha256'],reference=reference(soxr.resample(wave,24000,16000)))
                     for (text,_),(wave,data) in zip(plan,takes)],
            transcripts=[r['transcript'] for r in records],seeds=[r['seed'] for r in records])
        print(key,basis,len(chunks),'groups',flush=True)
        return cet.synth_sentence(read,key,engine,pron,style,speed,settings,recorded=chunks)
