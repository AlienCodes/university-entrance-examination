"""Use the CET-6 narrator and its certified mastering pipeline."""
import json
import re
import sys
from lesson import PROJECT, ROOT, LESSON, PID, load, save

sys.path.insert(0, str(ROOT / '六级/tools'))
import make_audio as cet
from gaokao_tts import certificate_problems

class Reader(cet.G.Pronouncer):
    def read_text(self, original, key=None):
        text = original.replace('ā', 'a').replace('ō','o')
        if PID != 'C20T1P1':
            # Asterisks refer to the printed footnotes and are silent in speech.
            text = text.replace('*','').replace('…', ' — ').replace('...', ' — ')
            text = text.replace('CO2','carbon dioxide').replace('CO₂','carbon dioxide')
            for unit,spoken in [('cm','centimetres'),('mm','millimetres'),('km','kilometres'),('kg','kilograms')]:
                text=re.sub(r'(\d)\s*'+unit+r'\b',r'\1 '+spoken,text)
            text=re.sub(r'(?<=\d)[–-](?=\d)', ' to ',text)
        text = text.replace('64 cm','sixty-four centimetres').replace('early 1800s','early eighteen hundreds')
        text = text.replace('mid-1900s','mid-nineteen hundreds').replace('1980–97','nineteen eighty to nineteen ninety-seven')
        text = text.replace('1–4','one to four').replace(' – ', ' — ')
        return super().read_text(text, key)

def main():
    passage = load()
    config = json.loads((cet.G.HERE / 'voices.json').read_text())[cet.VOICE]
    reader = Reader()
    reader.lexicon.update(json.loads((LESSON / '篇目信息.json').read_text())['pronunciation'])
    passage['sents'] = [[s['en'] for s in pa] for pa in passage['paras']]
    path = PROJECT / 'audio'
    timing = cet.render_with_fallback(passage,config,cet.G.Engine(),reader,path / cet.VOICE)
    problems = certificate_problems(timing,path / timing['file'])
    if problems: raise RuntimeError(problems)
    if [s['text'] for s in timing['sentences']] != [s for pa in passage['sents'] for s in pa]:
        raise RuntimeError('音轨与正文不一致')
    save(path / 'timings.json',{cet.VOICE:{PID:timing}})

if __name__=='__main__': main()
