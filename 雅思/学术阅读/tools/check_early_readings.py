"""Check what the established narrator will pronounce before starting synthesis."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import audio_lesson
from editions import PRODUCTION_BOOKS, lesson_ids
from lesson import PROJECT, save

# These values have different readings in their printed contexts. Test the actual
# speech normalizer, including the CET rules that it inherits, for every sentence.
CHECKS={
 'C8T1P2': [('365m','three hundred sixty-five metres'),('215m','two hundred fifteen metres'),('5,490m','five thousand four hundred ninety metres')],
 'C2T1P1': [('150m cubic metres','one hundred fifty million cubic metres'),('70m cubic metres','seventy million cubic metres')],
 'C7T2P2': [('£2,343m','two thousand three hundred forty-three million pounds'),('£208','two hundred eight pounds')],
 'C4T3P2': [('1,350°C','one thousand three hundred fifty degrees celsius'),('7.49 a.m.','seven forty-nine a.m.')],
 'C3T4P1': [('PM10','p m ten')],
 'C7T2P3': [('Phase I,','phase one'),('Phase II,','phase two'),('Phase III,','phase three')],
 'C7T3P2': [('Paleo-Indian','paleo-indian')],
 'C7T3P3': [('30% and 50%','thirty percent and fifty percent')],
 'C6T4P2': [('105/1000','one hundred five per thousand')],
 'C10T1P2': [('18km/h','eighteen kilometres per hour')],
 'C9T4P1': [('1.5 grams','one point five grams')],
}

def check(pids):
    reader=audio_lesson.Reader.__new__(audio_lesson.Reader)
    reader.text={}
    checked=[]
    for pid in pids:
        audio_lesson.PID=pid
        paper=json.loads((PROJECT/'原稿'/(pid+'.json')).read_text())
        rows=[s for para in paper['paragraphs'] for s in para]
        for first, second in zip(rows, rows[1:]):
            if re.search(r'\d\.$', first) and re.match(r'\d', second):
                raise ValueError(f'Check the printed page for a split decimal in {pid}: {first[-22:]} / {second[:22]}')
        result=[reader.read_text(s,f'{pid}:{n}') for n,s in enumerate(rows,1)]
        examples=[]
        for needle,expected in CHECKS.get(pid,[]):
            hits=[i for i,en in enumerate(rows) if needle in en]
            if not hits or any(expected not in result[i].lower() for i in hits):
                raise ValueError(f'Unexpected pronunciation in {pid}: {needle!r}; '+str([result[i] for i in hits]))
            examples.append(dict(printed=needle,spoken=expected,reading_units=[i+1 for i in hits]))
        checked.append(dict(lesson=pid,reading_units=len(rows),spoken_sha256=hashlib.sha256('\n'.join(result).encode()).hexdigest(),examples=examples))
    return checked

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('file',type=Path);args=ap.parse_args()
    rows=check(lesson_ids(PRODUCTION_BOOKS['10-1']))
    save(args.file,dict(kind='朗读文本前置核查',passages=len(rows),reading_units=sum(r['reading_units'] for r in rows),
                        unsupported_symbols=0,lessons=rows))
