"""Measure the possessive before Steelworks in the Falkirk Wheel recording."""
from functools import lru_cache
import re

from aiden_boundaries import RATE, interior_gaps, words
from aiden_pronunciation import grammar_decoder, locate_sound


POSSESSIVE = {'poss':'IH R IH NG Z', 'bare':'IH R IH NG', 'bare-long':'IY R IH NG',
              'devoiced':'IH R IH NG S', 'poss-long':'IY R IH NG Z', 'devoiced-long':'IY R IH NG S',
              'extra-syllable':'IH R IH NG IH Z'}


@lru_cache(maxsize=1)
def recognizer():
    context = {'engin':'EH N JH AH N','butterley':'B AH T ER L IY','at':'AE T','steelworks':'S T IY L W ER K S',
               'in':'IH N','derbyshire':'D AA R B IY SH ER'}
    return grammar_decoder(POSSESSIVE,context,'[at] [butterley] [engin] {term} [steelworks] [in] [derbyshire]')


def verify(audio, first, second):
    for transcript in (first, second):
        spelling = re.sub(r'\bsteel works\b','steelworks',transcript,flags=re.I)
        spelling = re.sub(r'\bbutterleigh\b','butterley',spelling,flags=re.I)
        observed = words(spelling)
        if observed not in (['at','butterley',poss,'steelworks','in','derbyshire'] for poss in ('engineering','engineerings')):
            raise ValueError(f'The words surrounding the name of the steelworks differ: {transcript!r}')
    decoder = recognizer()
    key, score, start, end = locate_sound(audio,decoder,POSSESSIVE)
    context = [s.word for s in decoder.seg() if s.word not in POSSESSIVE and not s.word.startswith('<')]
    if (key not in ('poss','poss-long') or score < .12 or context != ['at','butterley','engin','steelworks','in','derbyshire']):
        raise ValueError(f'The possessive ending in Engineering’s or its context is unclear: {POSSESSIVE[key]}')
    if any(start < (a+b)/2 < end for a,b in interior_gaps(audio)):
        raise ValueError('A pause interrupts the end of Engineering’s')
    return {'ending_phones':POSSESSIVE[key], 'score':round(score,3), 'start':round(start/RATE,3),'end':round(end/RATE,3)}
