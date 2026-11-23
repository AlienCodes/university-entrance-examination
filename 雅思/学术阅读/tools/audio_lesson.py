"""Read with the chosen IELTS narrator and apply the certified CET mastering pipeline."""
import io
import os
import json
import re
import sys
from lesson import PROJECT, ROOT, LESSON, PID, load, save

sys.path.insert(0, str(ROOT / '六级/tools'))
import make_audio as cet
from gaokao_tts import certificate_problems
from textnorm import ordinal
import soundfile as sf
import 去呼吸


def early_reading_forms(text,pid):
    """Expand the printed abbreviations whose readings depend on the subject of these books."""
    text=text.replace('￡','£').replace('℃','°C')
    text=re.sub(r'(\d)\s+%',r'\1%',text)
    text=re.sub(r'(\d[\d,.]*)\s*km/h\b',r'\1 kilometres per hour',text)
    text=re.sub(r'(\d)\s+ml\b',r'\1 millilitres',text)
    text=re.sub(r'\$\s+(?=\d)','$',text)
    text=re.sub(r'\$US\s*([\d,]+(?:\.\d+)?)\s+(million|billion)\b',r'\1 \2 U.S. dollars',text)
    text=text.replace('ADD/ADHD','A D D or A D H D').replace('(= family)','(meaning family)')
    text=text.replace('el niño / la niña','El Niño and La Niña').replace('105/1000','105 per thousand')
    text=text.replace('February/ March','February or March').replace('mind/body/spirit','mind, body and spirit')
    text=text.replace('house/ hotel','house or hotel').replace('Korn/Ferry/Carre/Orban','Korn Ferry Carre Orban').replace('Korn/Ferry','Korn Ferry')
    text=text.replace('Phase III','Phase Three').replace('Phase II','Phase Two').replace('Phase I','Phase One')
    text=text.replace('George III','George the Third').replace('PM10','P M ten')
    text=text.replace('S.K.I.','S K I').replace('Y.W.C.A.','Y W C A')
    text=text.replace('«','“').replace('»','”')
    text=re.sub(r'\b(\d{1,2})\.(\d{2})(?=\s+[ap]\.m\.)',r'\1 \2',text)
    if pid=='C8T1P2':
        text=re.sub(r'(\d[\d,]*)m\b',r'\1 metres',text)
    if pid=='C4T3P3':
        text=re.sub(r'_{1,}', 'blank', text)
    return text

class Reader(cet.G.Pronouncer):
    def read_text(self, original, key=None):
        if int(PID[1:PID.index('T')]) <= 10:
            original = early_reading_forms(original,PID)
        text = original.replace('ā', 'a').replace('ō','o')
        if PID != 'C20T1P1':
            # Asterisks refer to the printed footnotes and are silent in speech.
            text = text.replace('*','').replace('…', ' — ').replace('...', ' — ')
            text = re.sub(r'\b(\d+)[ \t]+(?:st|nd|rd|th)\b',lambda m:ordinal(int(m[1])),text,flags=re.I)
            text = text.translate(str.maketrans({'[':'',']':'','&':' and ','ş':'sh'}))
            text = text.replace('10⁹','one billion').replace('3Q15','three Q fifteen').replace('ME2','Me Two').replace('1910s','nineteen tens')
            text = re.sub(r'(?<=\d)\s*m(?:3|³)\b',' cubic metres',text)
            text = re.sub(r'US\$(\d[\d,]*(?:\.\d+)?)',r'\1 U.S. dollars',text)
            text = re.sub(r'€(\d[\d,]*(?:\.\d+)?)',r'\1 euros',text)
            text = re.sub(r'£(\d+(?:\.\d+)?)m\b',r'\1 million pounds',text)
            text = re.sub(r'−(?=\d)', 'minus ', text)
            text = re.sub(r'°\s*C\b',' degrees Celsius',text).replace('°',' degrees')
            text = text.replace('1/8','one eighth').replace('Nike+','Nike Plus')
            text = text.replace('varieties/breeds','varieties or breeds').replace('(=ethical)','(meaning ethical)')
            text = text.replace('World War II','World War Two')
            text = re.sub(r'\bH\. (?=naledi\b)', 'Homo ',text)
            for name,number in [('Charles II','Charles the Second'),('Henry VIII','Henry the Eighth'),('Amenhotep III','Amenhotep the Third'),('Napoleon III','Napoleon the Third')]:
                text=text.replace(name,number)
            text = re.sub(r'\bc\.?\s*(?=\d{3,4}\b)', 'circa ',text)
            def full_year_range(match):
                first,suffix=match.groups()
                scale=10**len(suffix)
                end=int(first)//scale*scale+int(suffix)
                if end<int(first):
                    end+=scale
                return f'{first} to {end}'
            text = re.sub(r'\b(1\d{3}|20\d{2})[–-](\d{1,3})(?!\d)',full_year_range,text)
            text = re.sub(r'(\d)\s*(BC|BCE|AD)\b',r'\1 \2',text)
            text = text.replace('CO2','carbon dioxide').replace('CO₂','carbon dioxide')
            for unit,spoken in [('cm','centimetres'),('mm','millimetres'),('km','kilometres'),('kg','kilograms')]:
                text=re.sub(r'(\d)\s*'+unit+r'\b',r'\1 '+spoken,text)
            text=re.sub(r'(?<=\d)[–-](?=\d)', ' to ',text)
        text = text.replace('64 cm','sixty-four centimetres').replace('early 1800s','early eighteen hundreds')
        text = text.replace('mid-1900s','mid-nineteen hundreds').replace('1980–97','nineteen eighty to nineteen ninety-seven')
        text = text.replace('1–4','one to four').replace(' – ', ' — ')
        return super().read_text(text, key)

def affected_sentences(failure):
    samples,sr=sf.read(io.BytesIO(failure.mp3),dtype='float32')
    diagnostics=PROJECT/'样片'/'语音复检'/PID
    diagnostics.mkdir(parents=True,exist_ok=True)
    suspected=[]
    flagged=set()
    for begin,end,level in 去呼吸.breath_check(samples,sr):
        middle=(begin+end)/2
        nearest=min(failure.items,key=lambda row:max(row['start']-middle,middle-row['end'],0))
        flagged.add(f"{PID}:{nearest['k']}")
        name=f"sentence-{nearest['k']}.flac"
        start=max(0,int((nearest['start']-.25)*sr))
        stop=min(len(samples),int((nearest['end']+.25)*sr))
        sf.write(str(diagnostics/name),samples[start:stop],sr)
        suspected.append(dict(file=name,text=nearest['text'],parts=nearest['parts'],
                              start_in_clip=round(begin-start/sr,3),end_in_clip=round(end-start/sr,3),
                              peak_dbfs=level))
    save(diagnostics/'intervals.json',suspected)
    return flagged


def certified_audio(passage,config,engine,reader,dest,*,synthesize=cet.synth_sentence):
    if PID=='C20T1P1':
        return cet.render_with_fallback(passage,config,engine,reader,dest)
    cache={}
    rates={}
    cleaned=set()
    flagged=set()
    breaths=set()
    quiet_clauses=set()

    def synth(read,key,engine,pron,style,speed,settings):
        adjusted=speed*rates.get(key,1.0)
        take=(key,read,adjusted,key in cleaned)
        if take not in cache:
            options={**settings,'debreath_before_level':key in cleaned}
            cache[take]=synthesize(read,key,engine,pron,style,adjusted,options)
        return cache[take]

    def render():
        return cet.G.render_passage(passage,cet.VOICE,config,engine,reader,dest,
                                    sentence_synth=synth,quiet_clauses=quiet_clauses)

    for factor in (1.00,1.00,1.015,.98,1.035,.96):
        cleaned.update(breaths)
        for key in flagged:
            rates[key]=factor
        try:
            result=cet.with_level_fallback(PID,render)
            result['sentence_speed_adjustments']=rates.copy()
            result['pre_level_debreath']=sorted(cleaned)
            if quiet_clauses:
                result['adjusted_clause_endings']=sorted(quiet_clauses)
            return result
        except cet.G.AudioVerificationError as failure:
            breaths=affected_sentences(failure) if failure.report.get('breath_count') else set()
            # Rebalance only the endings that the encoded-audio check flagged.
            # Subsequent takes and the finished video use the original limits.
            endings={(int(k),int(j)) for k,j in re.findall(r'第(\d+)句第(\d+)段末尾（',str(failure))}
            quiet_clauses.update(endings)
            flagged=breaths|{f'{PID}:{k}' for k,j in endings}
            if not flagged or factor==.96:
                raise
            print('按原音色重读未通过换气或段尾响度检查的句子：',sorted(flagged),flush=True)


def main():
    passage = load()
    config = json.loads((cet.G.HERE / 'voices.json').read_text())[cet.VOICE]
    reader = Reader()
    reader.lexicon.update(json.loads((LESSON / '篇目信息.json').read_text())['pronunciation'])
    passage['sents'] = [[s['en'] for s in pa] for pa in passage['paras']]
    path = PROJECT / 'audio'
    if os.getenv('IELTS_NARRATOR') == 'Aiden':
        from aiden_audio import Aiden
        from aiden_profile import PROFILE, confirm
        engine = Aiden()
        timing = certified_audio(passage,config,engine,reader,path / cet.VOICE,synthesize=engine.sentence)
        timing.update(narrator=PROFILE,narration_review=engine.review)
        confirm(timing)
    else:
        timing = certified_audio(passage,config,cet.G.Engine(),reader,path / cet.VOICE)
    problems = certificate_problems(timing,path / timing['file'])
    if problems: raise RuntimeError(problems)
    if [s['text'] for s in timing['sentences']] != [s for pa in passage['sents'] for s in pa]:
        raise RuntimeError('音轨与正文不一致')
    save(path / 'timings.json',{cet.VOICE:{PID:timing}})

if __name__=='__main__': main()
