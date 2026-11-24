"""Verify the ship captain's two-syllable surname where the rejected take says Delman."""
from functools import lru_cache
from itertools import product
import re

from aiden_boundaries import RATE, interior_gaps, words
from aiden_pronunciation import grammar_decoder, locate_sound


PHONES = {f'sound-{i}':' '.join(part for part in variant if part)
          for i,variant in enumerate(product(('D','T',''),('AW','OW','EH L','AO L','AE L','AE','AH'),
                                             ('M',''),('AH','AE','IH',''),('N','')))}


@lru_cache(maxsize=1)
def recognizer():
    return grammar_decoder(PHONES,{'was':'W AA Z','determined':'D IH T ER M AH N D'},'{term} [was] [determined]')


def verify(audio, first, second):
    for hypothesis in (first, second):
        # Dow and Dao are both D AW in CMUdict. One MP3 is also spelt Dauman
        # by ASR. Every spelling must still pass the D AW acoustic check.
        written = re.sub(r'\b(?:dow|dao|dau)\s*man\b', 'Dowman', hypothesis, flags=re.I)
        if words(written) != ['dowman','was','determined']:
            raise ValueError(f'Unclear captain’s name or its context: {hypothesis!r}')
    decoder = recognizer()
    key, score, start, end = locate_sound(audio,decoder,PHONES)
    context = [s.word for s in decoder.seg() if s.word not in PHONES and not s.word.startswith('<')]
    if PHONES[key] not in ('D AW M AH N','D AW M AE N') or score < .1 or context != ['was','determined']:
        raise ValueError(f'The captain’s surname differs from Dowman: {PHONES[key]}')
    if any(start < (a+b)/2 < end for a,b in interior_gaps(audio)):
        raise ValueError('A pause interrupts the name Dowman')
    return {'phones':PHONES[key],'score':round(score,3),'start':round(start/RATE,3),'end':round(end/RATE,3)}
