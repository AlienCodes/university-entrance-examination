"""Validate the two audible syllables of ganzfeld in the telepathy passage."""
from functools import lru_cache
from itertools import product

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


# The two English recordings by Vealhurl give G AA N Z and G AE N Z.
# Competing long vowels and abbreviated endings come from the rejected takes.
FIRST = ('G AE N T S','G AA N T S','G AE N S','G AA N S','G AE N Z','G AA N Z',
         'G AH N Z','G EH N Z','G IH N Z','JH EH N Z','JH AE N Z','K AE N S',
         'G OW N S','G AY N S','G AO N S','G AE N','G AA N','')
LAST = ('F EH L D','F EH L T','F IY L D','F EH L','F EH D','F AH L','')
FORMS = {f'form-{i}': (a+' '+b).strip() for i,(a,b) in enumerate(product(FIRST,LAST)) if a or b}
SPELLINGS = {'ganzfeld','gansfeld','gensfeld'}
HINT = ('Read ganzfeld in two joined syllables. Begin with a hard g as in garden. '
        'Keep the l and final stop in feld, rhyming with held.')


@lru_cache(maxsize=1)
def recognizer():
    return grammar_decoder(FORMS, {}, '{term}')


def check_sound(sample):
    label, confidence, start, end = locate_sound(sample, recognizer(), FORMS)
    phones = FORMS[label].split()
    if (phones[:3] not in (['G','AE','N'], ['G','AA','N'])
            or phones[3:-4] not in (['Z'], ['S'], ['T','S'])
            or phones[-4:] not in (['F','EH','L','D'], ['F','EH','L','T'])
            or confidence < .13 or not .35*RATE <= end-start <= 1.3*RATE
            or any(start < (a+b)/2 < end for a,b in interior_gaps(sample))):
        raise ValueError('Incomplete or different pronunciation of ganzfeld: '+FORMS[label])
    return dict(phones=FORMS[label], confidence=round(confidence,3), start=start/RATE, end=end/RATE)


def verify(audio, expected, first, second):
    index = expected.index('ganzfeld')
    def check_context(tokens):
        if (len(tokens) != len(expected) or tokens[index] not in SPELLINGS
                or tokens[:index] != expected[:index] or tokens[index+1:] != expected[index+1:]):
            raise ValueError('The context or the position of ganzfeld differs from the paper')
    check_context(words(first))
    check_context(words(second))
    timed = timed_words(audio)
    check_context([word for word,_ in timed])
    lo = max(0,timed[index][1] - round(.08*RATE))
    hi = timed[index+1][1] if index+1 < len(timed) else len(audio)
    proof = check_sound(audio[lo:hi])
    for edge in ('start','end'):
        proof[edge] = round(proof[edge]+lo/RATE,3)
    return proof
