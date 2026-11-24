"""Check the English reading of Diels against the recorded pronunciation of the family name."""
from functools import lru_cache

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound

FORMS = {
    'name':'D IY L Z', 'possessive':'D IY L Z IH Z', 'weak-possessive':'D IY L Z AH Z',
    'deels-unvoiced':'D IY L S', 'dill-s':'D IH L S', 'dills':'D IH L Z',
    'dales':'D EY L Z', 'dales-s':'D EY L S', 'dials':'D AY AH L Z',
    'deeds':'D IY D Z', 'deles':'D EH L Z', 'deal':'D IY L', 'dee':'D IY',
    'dies':'D AY Z', 'dozens':'D AH Z AH N Z',
}
NAMES = {'diels', 'deals', 'dieels', 'dieles'}
POSSESSIVES = {(s+'s',) for s in NAMES} | {(s,'his') for s in NAMES}


def cited(expected):
    return expected[:3] == ['diels','also','hopes'] or expected[:5] == ['bernstein','says','that','dielss','system']


@lru_cache(maxsize=2)
def decoder(possessive):
    if possessive:
        return grammar_decoder(FORMS, {'that':'DH AE T','system':'S IH S T AH M','is':'IH Z'},
                               '[that] {term} [system] [is]')
    return grammar_decoder(FORMS, {'also':'AO L S OW','hopes':'HH OW P S'}, '{term} [also] [hopes]')


def verify(audio, expected, first, second):
    possessive = 'dielss' in expected
    index = expected.index('dielss' if possessive else 'diels')
    def locate(hypothesis):
        count = len(hypothesis) - len(expected) + 1
        if count < 1 or hypothesis[:index] != expected[:index] or hypothesis[index+count:] != expected[index+1:]:
            raise ValueError('The English words surrounding Diels differ from the paper')
        middle = tuple(hypothesis[index:index+count])
        if (possessive and middle not in POSSESSIVES) or (not possessive and not (count == 1 and middle[0] in NAMES)):
            raise ValueError('The family name Diels differs in the independent readings')
        return count
    for heard in (first, second):
        locate(words(heard))
    timed = timed_words(audio)
    count = locate([w for w,t in timed])
    # The possessive uses the start of the next word, system, to retain its final /iz/.
    lo = max(0,timed[index][1] - round(.17 * RATE))
    anchor = index+count+1
    hi = min(len(audio),timed[anchor][1] + round(.19 * RATE))
    key, confidence, first_sample, last_sample = locate_sound(audio[lo:hi], decoder(possessive), FORMS)
    allowed = {'possessive','weak-possessive'} if possessive else {'name'}
    start, end = lo+first_sample, lo+last_sample
    if (key not in allowed or confidence < .32 or end-start < (.32 if possessive else .19)*RATE
            or any(start < (a+b)/2 < end for a,b in interior_gaps(audio))):
        raise ValueError(f'Unclear Diels vowel, ending or possessive: {FORMS[key]}')
    return dict(phones=FORMS[key], confidence=round(confidence,3),
                start=round(start/RATE,3), end=round(end/RATE,3))
