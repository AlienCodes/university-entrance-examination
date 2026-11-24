"""Read whole sentences with the auditioned voice and certify the original IELTS pauses."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from collections import deque
from difflib import SequenceMatcher

import numpy as np
import soundfile as sf
import soxr

from aiden_profile import DIRECTION, IDENTITY, SPEAKER
from aiden_boundaries import POLICY, assess, words, reference, salmon_phrase
from aiden_word_review import POLICY as WORD_POLICY
from aiden_checkpoint import PeriodicSnapshot, REVIEW_TAKES, diagnostic_reports, rejected_seed, reviewed_master_failures
import aiden_cork_oak
import aiden_cork_taint
import aiden_ceylonese
import aiden_inuktitut
import aiden_sobchack
import aiden_de_dreu
import aiden_decans
from aiden_place_names import READINGS as PLACE_READINGS
import aiden_india
from aiden_macfarlane import cited_phrase
import aiden_turkish
import aiden_heyerdahl
import make_audio as cet
import 听对


LLEWYN_READINGS = ('llewyn', 'Llewyn', 'llèwin', 'Llehwin', 'slehwin', 'Llewinn', 'llewyn')


def save_raw_take(path, samples):
    """Preserve an original 24 kHz take as lossless PCM for listening or rechecking."""
    if path.suffix != '.flac':
        raise ValueError('Raw Aiden takes must be stored as FLAC')
    sf.write(path, samples, 24000, subtype='PCM_24')


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
        self.rejected_master_takes=reviewed_master_failures()
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
            # A previous complete recording is rechecked first. Fetch the
            # pinned weights only if that check actually calls for a new take.
            folder=restore(Path(os.environ['IELTS_AIDEN_MODEL_PATH']),
                           verify_only=os.getenv('IELTS_AIDEN_FETCH_IF_NEEDED') != 'true')
            self.model=Qwen3TTSModel.from_pretrained(str(folder),dtype=torch.float32,device_map='cpu',attn_implementation='sdpa')
        instruction=DIRECTION
        names=[f'{name} /{ipa}/' for name,ipa in pron.lexicon.items()
               if name.casefold() not in {'ceylonese', aiden_turkish.ORAL} and re.search(r'\b'+re.escape(name)+r'\b',script,re.I)]
        for spellings, guidance in PLACE_READINGS.values():
            if any(re.search(r'\b'+re.escape(form)+r'\b',script,re.I) for form in spellings):
                instruction += ' ' + guidance
        if names:instruction+=' Pronunciation of names in this sentence: '+', '.join(names)+'.'
        if any(name in script.casefold() for name in ('wendrich', 'vendrik', 'ven-drick', 'vendrick')):
            instruction += (' Say the Dutch name Willeke Wendrich in two connected groups: '
                            'VIL-uh-kuh VEN-drick. Keep both unstressed vowels in the first name short, '
                            'and finish the surname with k.')
        if script.strip(' ,.;:!?').casefold() in {s.casefold() for s in aiden_cork_oak.RENDERINGS}:
            instruction += ' ' + aiden_cork_oak.HINT
        if any(form.casefold() in script.casefold() for form in aiden_cork_taint.RENDERINGS):
            instruction += ' ' + aiden_cork_taint.HINT
        if re.search(r'\bLei Tzu\b',script,re.I):
            instruction += ' Pronounce Lei Tzu (Léi Zǔ) in two connected syllables: lay tsoo, with /ts/ at the start of tsoo.'
        if re.search(r'\b(?:Halley|Hally)\b',script,re.I):
            instruction += ' Read the astronomer’s surname Halley in two connected syllables /ˈhæli/, with an audible initial h.'
        if re.search(r'\bPerkin (?:saw|set|spent)\b',script,re.I):
            instruction += ' William Perkin is singular. Finish the name on n, then begin the verb with its own s.'
        if re.search(r"\bPerkin['’]s\b",script,re.I):
            instruction += ' Read the possessive of Perkin as /ˈpɝkɪnz/: two syllables in total, ending in a single /z/.'
        if any(re.search(r'\b'+re.escape(name)+r'\b',script,re.I) for name in aiden_ceylonese.RENDERINGS):
            instruction += ' ' + aiden_ceylonese.HINT
        if 'I I N C E' in script:
            instruction += ' Read the five initials I, I, N, C, E clearly in one connected group, including both initial I sounds.'
        if words(script)[:5] == ['sugars','and','meats','or','oils']:
            instruction += ' Pronounce the opening word sugars /ˈʃʊɡɚz/, with a soft sh and a voiced final z.'
        if re.search(r'\bsock[ -]?eye\b', script, re.I):
            instruction += (' This is a list of Pacific salmon. Sockeye and red are two names for the same fish. '
                            'Say the compound SOCK-eye /ˈsɑk.aɪ/ as one word, with the beat on SOCK. '
                            'Link or red naturally and finish red with its d sound.')
        if re.search(r'^pump through Alaska\b', script, re.I):
            instruction += (' In this quotation the subject is salmon. The fish pump through Alaska. '
                            'Read only the supplied words. Finish the present-tense pump with the lips, '
                            'then let air flow between the teeth for through. Give through the same '
                            'voiceless th after blood.')
        if re.search(r'\b(?:fusee|fuzee|fyoo-zee)\b',script,re.I):
            instruction += ' Pronounce the clock term fusee in two connected syllables, fyoo-ZEE /fjuːˈziː/, with a clear final ee vowel.'
        if any(form.casefold() in script.casefold() for form in aiden_decans.RENDERINGS):
            instruction += ' In the Egyptian star name decans /ˈdɛkənz/, use the short e of deck, an unstressed second syllable and a final z. Keep both syllables together.'
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
        if re.search(r"\bwith (?:modell?ed|model['’]d|mah-duhld) birds\b",script,re.I):
            instruction += (' Here, modeled means shaped into a sculpture. Say the two connected syllables of '
                            'model as in “modelled on”, with a voiced middle d and a brief final d. '
                            'Carry the last consonant straight into birds at the same pace.')
        if 'appreciate the mathematical way' in script.casefold():
            instruction += ' Link “appreciate the mathematical way” naturally, including the unstressed article the.'
        if re.search(r'\bDeane? dived down\b',script,re.I):
            instruction += ' In "Deane dived down", finish the past tense /daɪvd/ with an audible d release. Carry the voice through “down and found” in the same thought.'
        if re.search(r'\bwind[- ]lashed\b',script,re.I):
            instruction += ' In wind-lashed infertile fields, finish lashed with /ʃt/ before the first vowel of infertile.'
        if words(script)[:3] == ['the','team','theorizes']:
            instruction += ' Begin with the article the and the noun team /ðə tiːm/. Close the lips on m before continuing smoothly with theorizes.'
        if re.search(r'\bnorm[- ]',script,re.I):
            instruction += ' In norm-referenced, finish referenced with the final consonants /nst/, including a light t release.'
        if re.search(r"\bapproached the helicopter",script,re.I):
            instruction += ' The first verb is in the past. Finish approached with /tʃt/ before the following word.'
        if 'Villamil' in script or 'vee-yah-MEEL' in script:
            instruction += ' Puerto Villamil ends in a stressed meel with a final l. Link the following words “on Isabela” without adding a vowel to the town name.'
        if any(name.casefold() in script.casefold() for name in LLEWYN_READINGS):
            instruction += ' For the Welsh word llewyn, start with the voiceless lateral fricative /ɬ/. ' \
                           'Keep the tongue in the l position and blow air around its sides into the short e of bed. ' \
                           'Glide directly from that e into the word win, in a single breath. ' \
                           'Read the two syllables as one word in the American English sentence.'
        if words(script)[:2]==['forested','hills']:
            instruction += ' In forested hills, start with a clear f followed by the stressed first syllable of forest. Sound the complete three-syllable adjective before hills.'
        if words(script)[-1:]==['bottlenecks']:
            instruction += ' Finish the plural bottlenecks with the whole final syllable, including the k and s sounds.'
        if 'Sommerkorn' in script or 'Zommerkorn' in script:
            instruction += ' Read Martin Sommerkorn with a voiced z, a short first vowel and the final consonants in korn, as in his own introduction. Use one connected surname.'
        if re.search(r'\b(?:Floris|Floor-iss)\b',script,re.I):
            instruction += ' Read the soil specialist’s surname Floris in two connected syllables, FLOOR-iss. In the possessive, add a short iz before mix.'
        if 'Doctor Phil Rasch' in script:
            instruction += ' Say "And Doctor" as two clearly distinguishable words. The scientist’s surname rhymes with rash.'
        if re.search(r'\b(?:Mac|Mc)farlane\b',script,re.I):
            instruction += ' In Macfarlane, end the surname with an n, as in a short unstressed “lun”. Do not add a d. Sound the z only for a written possessive.'
        if re.search(r'\b(?:auto[ -]?)?ganzfeld\b',script,re.I):
            from aiden_ganzfeld import HINT
            instruction += ' ' + HINT
            if re.search(r'\bauto[ -]?ganzfeld\b', script, re.I):
                instruction += ' Say auto as in automobile and link it to ganzfeld. Complete feld before tests or trials.'
        if re.search(r'\bSh(?:eng|ung)[- ]?(?:gen|gun) Fan\b',script,re.I):
            instruction += ' Shenggen has two syllables. End the first with ng in sing, begin the second with a hard g and end it with n. Then say Fan.'
        if re.search(r'\bJanzen\b',script,re.I):
            instruction += ' Read Janzen in two syllables, JAN-zuhn, with the vowel of jam and a voiced z in the middle.'
        if re.search(r'\bnotes of (?:Ind|Ynde|Eynd)\b', script, re.I):
            instruction += ' ' + aiden_india.HINT
        if re.search(r'\bresearched the chemistry\b', script, re.I):
            instruction += ' Read researched in the past tense: end it with the sound cht, then link naturally to the chemistry.'
        if re.search(r'for girls in', script, re.I) and re.search(r'\b(?:[ÉE]cole|ay-kol)\b', script, re.I):
            instruction += ' Read the French school name École normale supérieure as /e.kɔl nɔʁ.mal sy.pe.ʁjœʁ/. ' \
                           'Then say the English location phrase “for girls in” with a clear /ɪn/ before the town. ' \
                           'The town Sèvres is /sɛvʁ/, or /ˈsɛvrə/ in English. ' \
                           'Finish on the vr sound with at most the light, unrounded final vowel of sofa. The written final s is silent.'
        if re.search(r'\b(?:Pithecanthropus|Pith-ih|pith-uh)\b', script, re.I):
            instruction += ' In Pithecanthropus erectus, say pith-ih-KAN-thruh-puhs ih-REK-tuhs. Both th sounds are as in thin. Read the scientific name in a single connected phrase.'
        torch.manual_seed(seed)
        cap=min(1800,max(200,len(script.split())*14+120))
        with torch.inference_mode():
            waves,sr=self.model.generate_custom_voice(text=script,speaker=SPEAKER,language='English',
                instruct=instruction,max_new_tokens=cap)
        wave=np.asarray(waves[0],dtype=np.float32)
        if sr!=24000 or wave.ndim!=1 or len(wave)<.15*sr or not np.isfinite(wave).all() or not (np.max(np.abs(wave))>.01):
            raise ValueError('Invalid Aiden waveform')
        return cet.G.trim(wave,pad=.045)

    def recheck_diagnostic(self,file,report,script,seed,source_report):
        raw=source_report.with_suffix('.flac')
        recording=raw.read_bytes()
        digest=hashlib.sha256(recording).hexdigest()
        if digest in self.rejected_master_takes:return None
        wave,rate=sf.read(raw,dtype='float32')
        if rate!=24000 or wave.ndim!=1:return None
        transcript,timed=recognize(wave)
        audio=soxr.resample(wave,rate,16000)
        if not timed:
            return None
        try:
            assess(audio,script,transcript,recheck=True)
        except ValueError:
            return None
        file.write_bytes(recording)
        data=dict(transcript=transcript,timed=timed,seed=seed,sha256=digest,
                  policy=POLICY,word_policy=WORD_POLICY,rechecked_from_diagnostic=True)
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
                elif (data.get('policy') == POLICY and data.get('word_policy') == WORD_POLICY
                      and words(script) not in (['quercus','suber'], ['the','ancient','craftsmen'])
                      and not {'llewyn','aleut','zappaterra','sevres','amagoalik','henri','kuhl','clemmons','willeke'}.intersection(words(script))
                      and not salmon_phrase(words(script)) and words(script) != ['cod','sole','perch','and','pollock']
                      and words(script)[:3] != ['the','team','theorizes']
                      and words(script)[-2:] not in (['norm','referenced'], ['says','vandam'], ['percent','longer'])
                      and not cited_phrase(words(script))
                      and not {'perkin','perkins','shenggen','janzen','hawley','ganzfeld','diels','dielss','dene','makete','monbusho','aleyska','ceylonese','fusee','decans','ynde','qaujimajatuqangit','sobchack','dreu','heyerdahl','butterley','dowman','sommerkorn','floris','floriss',aiden_cork_taint.TERM,aiden_turkish.ORAL}.intersection(words(script))):
                    return wave,data
                else:
                    try:
                        assess(soxr.resample(wave,sr,16000),script)
                    except ValueError:
                        previous_seed=data['seed']
                    else:
                        data['policy']=POLICY
                        data['word_policy']=WORD_POLICY
                        report.write_text(json.dumps(data,ensure_ascii=False))
                        return wave,data
        number=int(key.split(':')[1]);seed=24830+number+variant*173
        if previous_seed is not None:
            seed=previous_seed+5*997
        candidates = []
        for candidate in diagnostic_reports(report):
            failed_seed = rejected_seed(candidate, key, script)
            if failed_seed is not None:
                candidates.append((failed_seed, candidate))
                seed = max(seed, failed_seed + 997)
        for failed_seed, candidate in sorted(candidates, reverse=True):
            checked=self.recheck_diagnostic(file,report,script,failed_seed,candidate)
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
        elif 'with modeled birds' in script.casefold():
            # The same narrator gave a clear reading of "modelled on" in C11T1P3.
            # Only the synthesis input varies. Each take is checked against the printed sentence.
            spellings=('modeled', 'modelled', 'MODELLED', "model'd", 'MAH-duhld')
        elif 'decans' in words(script):
            spellings=aiden_decans.RENDERINGS
        elif words(script)[-3:] == ['notes','of','ynde']:
            spellings=aiden_india.RENDERINGS
        elif words(script)[:3] == ['researched','the','chemistry']:
            spellings=('researched', 'RESEARCHED', 'researched', 'RESEARCHED', 'researched')
        elif words(script)[:3] == ['the','team','theorizes']:
            spellings=('The team theorizes','The TEAM theorizes','THE TEAM theorizes','The team theorizes','The TEAM theorizes')
        elif words(script) == ['sockeye','or','red']:
            spellings=('sockeye','sock-eye','SOCK-eye','sock eye','sockeye')
        elif words(script)[:3] == ['pump','through','alaska']:
            spellings=('pump through Alaska','PUMP through Alaska','Pump through Alaska','PUMP through Alaska','pump through Alaska')
        elif 'norm-referenced' in script.casefold():
            spellings=('norm-referenced','norm referenced','norm REH-fuh-renst','norm-referenced','norm REH-frenst')
        elif 'llewyn' in words(script):
            spellings=LLEWYN_READINGS
        elif 'willeke' in words(script):
            spellings=('Willeke Wendrich', 'Villeka Vendrik', 'VIL-uh-kuh VEN-drick', 'Villika Vendrick', 'Villeke Vendrik')
        elif 'autoganzfeld' in words(script):
            spellings=('autoganzfeld', 'auto-ganzfeld', 'auto ganzfeld', 'auto-GANZfeld', 'autoganzfeld')
        elif 'sevres' in words(script):
            spellings=('Ecole Normale Superieure for girls in Sevres',
                       'École Normale Supérieure for girls in Sèvres',
                       'École normale supérieure for girls in Sevra',
                       'École normale supérieure for girls in Sèvra',
                       'École normale supérieure for girls IN Sèvres',
                       'ay-KOL nor-MAL sü-pé-ryœur for girls IN Sevra')
        elif 'pithecanthropus' in words(script):
            spellings=('Pithecanthropus erectus','Pith-ih-KAN-thruh-puhs ih-REK-tuhs',
                       'Pithecanthropus erectus','Pith-uh-KAN-thruh-pus ih-REK-tus','Pithecanthropus erectus')
        elif 'qaujimajatuqangit' in words(script):
            spellings=aiden_inuktitut.RENDERINGS
        elif 'sobchack' in words(script):
            spellings=aiden_sobchack.RENDERINGS
        elif re.search(r'\bDe Dreu\b',script,re.I):
            spellings=aiden_de_dreu.RENDERINGS
        elif words(script)==['shenggen','fan']:
            spellings=('Shenggen Fan','Sheng-gen Fan','Sheng-gun Fan','Shung-gen Fan','Shenggen Fan')
        elif words(script)[:3]==['deane','dived','down']:
            spellings=('Deane dived down','Dean DIVED down','Deane DIVED down','Dean dived down','Deane dived down')
        elif words(script)[:3]==['approached','the','helicopters']:
            spellings=('approached','APPROACHED','approached','Approached','APPROACHED')
        elif place := next((rule for name,rule in PLACE_READINGS.items() if re.search(r'\b'+name+r'\b',script,re.I)), None):
            spellings = place[0]
        elif 'Puerto Villamil' in script:
            spellings=('Puerto Villamil','Puerto vee-yah-MEEL','Puerto Villamil','Puerto vee-yah-MEEL','Puerto Villamil')
        elif words(script)[:2]==['forested','hills']:
            spellings=('forested hills','Forested hills','FORESTED hills','Forested hills','forested hills')
        elif words(script) == ['dowman','was','determined']:
            spellings=('Dowman','Dow Man','Dowman','Dow-man','Dowman')
        elif 'sommerkorn' in words(script):
            spellings=('Sommerkorn','Zommerkorn','Sommerkorn','Zommer-korn','Sommerkorn')
        elif {'floris','floriss'}.intersection(words(script)):
            spellings=('Floris','Floor-iss','Floris','FLOOR-iss','Floris')
        elif words(script) == ['thor', 'heyerdahl']:
            spellings=aiden_heyerdahl.RENDERINGS
        elif cited_phrase(words(script)):
            spellings=('Macfarlane','McFarlane','Macfarlane','McFarlane','Macfarlane')
        elif aiden_turkish.ORAL in words(script):
            spellings=aiden_turkish.RENDERINGS
        attempts = deque(maxlen=REVIEW_TAKES)
        for attempt in range(len(spellings) if spellings else 5):
            if spellings and attempt:
                # Preserve all surrounding printed words, even in a long phrase.
                spoken=re.sub(re.escape(spellings[0]),spellings[attempt],script,flags=re.I)
                if spellings[0] in ('Na-Dene','Na-Denes'):
                    spoken=re.sub(r'\bAleut\b', PLACE_READINGS['Aleut'][0][attempt], spoken, flags=re.I)
            elif attempt in (1,3) and re.search(r'\bHalley\b',script,re.I):
                # CMUdict transcribes Halley and Hally identically. Verify the result against the paper.
                spoken=re.sub(r'\bHalley\b','Hally',script,flags=re.I)
            rendered_text=spoken
            wav=self.render(rendered_text,seed+attempt*997,pron)
            transcript,timed=recognize(wav)
            try:
                assess(soxr.resample(wav,24000,16000),script,transcript)
                with tempfile.TemporaryDirectory(dir=self.folder) as temp:
                    candidate = Path(temp) / file.name
                    save_raw_take(candidate, wav)
                    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
                    if digest in self.rejected_master_takes:
                        raise ValueError(self.rejected_master_takes[digest])
                    candidate.replace(file)
            except ValueError as error:
                issue=str(error)
                attempts.append((wav, rendered_text, seed + attempt * 997, transcript, issue))
                if attempt >= 1:
                    expected=words(script)
                    alignment=SequenceMatcher(None,expected,words(transcript),autojunk=False)
                    missing={w for op,a,b,_,_ in alignment.get_opcodes() if op in ('replace','delete')
                             for w in expected[a:b] if w in {'it','its','the','a','an','at','of','to','not'}}
                    spoken=re.sub(r'\b[a-z]+\b',lambda m:m[0].upper() if m[0] in missing else m[0],script)
                print(f'{key} rereading intact phrase: {issue}',flush=True)
                continue
            data=dict(transcript=transcript,timed=timed,seed=seed+attempt*997,sha256=digest,policy=POLICY,word_policy=WORD_POLICY)
            report.write_text(json.dumps(data,ensure_ascii=False))
            return sf.read(file,dtype='float32')[0],data
        # Preserve distinct attempts for comparison after a pronunciation correction.
        # Only recordings rechecked with the current rules can enter the master.
        (self.folder / 'rejected').mkdir(exist_ok=True)
        for target, take in zip(diagnostic_reports(report), reversed(attempts)):
            wave, rendered, take_seed, heard, reason = take
            candidate = target.with_suffix('.flac')
            save_raw_take(candidate, wave)
            evidence = dict(accepted=False, key=key, printed=script, rendered=rendered,
                            seed=take_seed, transcript=heard, issue=reason,
                            sha256=hashlib.sha256(candidate.read_bytes()).hexdigest())
            target.write_text(json.dumps(evidence, ensure_ascii=False))
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
