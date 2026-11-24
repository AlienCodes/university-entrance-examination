"""Compare the surname with Martin Sommerkorn's spoken self-introduction on APTN."""
from functools import lru_cache
from itertools import product
import re

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


_VARIANTS = product(('Z','S','T',''), ('AA','AO','AH','OW'), ('M',''), ('ER','AH',''),
                    ('K','G',''), ('AO R','AA R','OW R','ER',''), ('N',''))
_PHONES = {f'form-{i}':' '.join(filter(None,parts)) for i,parts in enumerate(_VARIANTS)}
_NAME = re.compile(r'\b(?:sommer|somer|summer|zomer|zomar|zommer)[ -]?[ck]orn\b', re.I)


@lru_cache(maxsize=1)
def recognizer():
    return grammar_decoder(_PHONES,{},'{term}')


def sound(audio):
    key,confidence,a,b = locate_sound(audio,recognizer(),_PHONES)
    phones = _PHONES[key]
    # In his introduction /z/ and both halves of Sommer-korn are audible.
    # An American reading may use a rhotic second syllable in Sommer.
    if (not re.fullmatch(r'Z (?:AA|AO|AH) M (?:ER|AH) K AO R N',phones)
            or confidence < .10 or not .40*RATE <= b-a <= 1.25*RATE):
        raise ValueError(f'Unclear initials, vowel or ending in Sommerkorn: {phones}')
    if any(a < (left+right)/2 < b for left,right in interior_gaps(audio)):
        raise ValueError('A pause interrupts Sommerkorn')
    return {'phones':phones,'start':a/RATE,'end':b/RATE,'confidence':round(confidence,3)}


def verify(audio, first, second):
    for transcript in (first,second):
        normalized = re.sub(r'\bDr\.?(?=\s+Martin\b)','doctor',_NAME.sub('Sommerkorn',transcript),flags=re.I)
        if words(normalized) != ['according','to','doctor','martin','sommerkorn']:
            raise ValueError(f'The introduction to Martin Sommerkorn differs: {transcript!r}')
    times = timed_words(audio)
    if len(times)<5 or times[3][0]!='martin':
        raise ValueError('Cannot locate the name after Martin')
    start = max(0,times[4][1]-round(.07*RATE))
    proof = sound(audio[start:])
    for edge in ('start','end'):
        proof[edge]=round(proof[edge]+start/RATE,3)
    return proof
