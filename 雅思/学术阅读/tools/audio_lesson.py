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
            text = text.translate(str.maketrans({'[':'',']':'','&':' and ','ş':'sh'}))
            text = text.replace('ME2','Me Two').replace('1910s','nineteen tens')
            text = re.sub(r'(?<=\d)\s*m(?:3|³)\b',' cubic metres',text)
            text = re.sub(r'US\$(\d[\d,]*(?:\.\d+)?)',r'\1 U.S. dollars',text)
            text = re.sub(r'€(\d[\d,]*(?:\.\d+)?)',r'\1 euros',text)
            text = re.sub(r'£(\d+(?:\.\d+)?)m\b',r'\1 million pounds',text)
            text = re.sub(r'°\s*C\b',' degrees Celsius',text).replace('°',' degrees')
            text = text.replace('1/8','one eighth').replace('Nike+','Nike Plus')
            text = text.replace('varieties/breeds','varieties or breeds').replace('(=ethical)','(meaning ethical)')
            text = text.replace('World War II','World War Two')
            for name,number in [('Charles II','Charles the Second'),('Henry VIII','Henry the Eighth'),('Amenhotep III','Amenhotep the Third'),('Napoleon III','Napoleon the Third')]:
                text=text.replace(name,number)
            text = re.sub(r'\bc\.?\s*(?=\d{3,4}\b)', 'circa ',text)
            text = re.sub(r'(\d{4})[–-](\d{2})(?!\d)',lambda m: m[1]+' to '+m[1][:2]+m[2],text)
            text = re.sub(r'(\d)\s*(BC|BCE|AD)\b',r'\1 \2',text)
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
