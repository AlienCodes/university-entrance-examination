"""Check the three locants and the chemical name heard in the Cambridge 12 cork passage."""
from functools import lru_cache
import re

import numpy as np

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder


TERM = 'trichloroanisole'
RENDERINGS = (TERM, 'try-kloro-ANN-ih-sole', 'tri-chloro-anisole', 'try-kloro-ANN-uh-sole', TERM)
HINT = ('Read the chemical locants two, four, six separately. In trichloroanisole use '
        'the vowel in Ann after chloro, then an unstressed vowel and sole. Keep the name connected.')

# The Royal Society of Chemistry recording and the rejected Aiden recording both
# contain tri-chloro. They differ at anisole. Keep the competing vowel and
# incomplete endings in the grammar, along with the integer “two hundred forty-six”.
NUMBERS = {'two':'T UW', 'four':'F AO R', 'six':'S IH K S', 'hundred':'HH AH N D R AH D',
           'forty':'F AO R T IY', 'and':'AE N D', 'three':'TH R IY', 'five':'F AY V'}
PARTS = (
    {'try':'T R AY','tri':'T R IH','tra':'T R AH','di':'D AY'},
    {'chloro':'K L AO R OW','cloro':'K L AO R AH','clawruh':'K L AO R','clora':'K L OW R AH',
     'loro':'L AO R OW','co':'K OW'},
    {'anee':'AE N IY','ani':'AE N IH','anu':'AE N AH','unn':'AH N','an':'AE N',
     'enah':'EH N AH','eni':'EH N IH','eena':'IY N AH','ahn':'AA N AH'},
    {'sole':'S OW L','sol':'S AA L','sul':'S AH L','saul':'S AO L','so':'S OW','zon':'Z AH N',
     'coal':'K OW L','kol':'K AA L'},
)
VOCABULARY = {key:value for group in (NUMBERS,*PARTS) for key,value in group.items()}


@lru_cache(maxsize=1)
def recognizer():
    # Optional groups allow incomplete speech to compete on the same signal.
    digits = '[(two | three)] [hundred] [and] [(four | forty | five)] [(six | five)]'
    name = ' '.join('[('+' | '.join(group)+')]' for group in PARTS)
    return grammar_decoder(PARTS[0],VOCABULARY,digits+' '+name)


def check_sound(sample):
    decoder = recognizer()
    padding = 2400
    signal = np.pad(sample,(padding,padding))
    decoder.start_utt()
    decoder.process_raw((np.clip(signal,-1,1)*32767).astype('<i2').tobytes(),False,True)
    decoder.end_utt()
    spans = [(s.word,max(0,s.start_frame*160-padding),min(len(sample),(s.end_frame+1)*160-padding))
             for s in (decoder.seg() or ()) if s.word in VOCABULARY]
    found = [s[0] for s in spans]
    if (len(found)!=7 or found[:4]!=['two','four','six','try']
            or found[4] not in {'chloro','cloro','clawruh','clora'}
            or found[5] not in {'anee','ani','anu'}
            or found[6] not in {'sole','sol','sul','saul'}):
        raise ValueError('Unclear locants, syllable or ending in trichloroanisole: '+' '.join(found))
    if any(spans[3][1] < (a+b)/2 < spans[-1][2] for a,b in interior_gaps(sample)):
        raise ValueError('The recording breaks inside trichloroanisole')
    return [{'phones':VOCABULARY[k],'start':a/RATE,'end':b/RATE} for k,a,b in spans]


def locate(tokens,expected):
    # Separate encodings of the same human reference produced aniso and anacol.
    # Return the spelling as evidence. The final s and l must also be heard.
    term_index = next((i for i,w in enumerate(tokens) if re.fullmatch(r'trichlor[a-z]{1,6}(?:sole?|so|col)',w)),None)
    if term_index is None:
        raise ValueError('The recognizer could not find trichloroanisole')
    for digits in (['two','four','six'],['two','hundred','forty','six']):
        start = term_index-len(digits)
        if start>=0 and tokens[start:term_index]==digits:
            normalized = tokens[:start]+['two','four','six',TERM]+tokens[term_index+1:]
            if normalized==expected:
                return start,term_index+1,tokens[term_index]
    raise ValueError('The context of 2,4,6-trichloroanisole differs from the paper')


def verify(audio,text,first,second):
    expected = words(text)
    heard_names = [locate(words(heard),expected)[2] for heard in (first,second)]
    if not any(re.search(r'sole?$',name) for name in heard_names):
        raise ValueError('Neither independent transcript heard the complete chemical name ending')
    timed = timed_words(audio)
    start,end,_ = locate([word for word,_ in timed],expected)
    lo = max(0,timed[start][1]-round(.11*RATE))
    hi = timed[end][1] if end<len(timed) else len(audio)
    segments = check_sound(audio[lo:hi])
    for part in segments:
        for edge in ('start','end'):
            part[edge] = round(part[edge]+lo/RATE,3)
    return segments
