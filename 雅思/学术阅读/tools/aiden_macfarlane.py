"""Check the historian's final n (or possessive nz) against competing stops."""
from functools import lru_cache
from itertools import product

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


def cited_phrase(expected):
    return expected == ['macfarlane', 'says'] or expected[:2] == ['macfarlanes', 'case']


_HEADS = ('M AH K F AA R L', 'M IH K F AA R L', 'M AE K F AA R L')
_ENDS = ('AH N', 'AH N D', 'AH N T', 'AH N Z', 'AH N D Z', 'AH', 'AE N D', '')
_FORMS = {
    f'name-{i}': (head + ' ' + tail).strip()
    for i, (head, tail) in enumerate(product(_HEADS, _ENDS))
}


@lru_cache(maxsize=2)
def decoder(next_word):
    return grammar_decoder(_FORMS, {'case': 'K EY S', 'says': 'S EH Z'}, '{term} ' + next_word)


def verify(audio, expected, first, second):
    possessive = expected[0] == 'macfarlanes'
    permitted = {'macfarlanes', 'mcfarlands'} if possessive else {'macfarlane', 'mcfarland'}
    for hypothesis in (first, second):
        heard = words(hypothesis)
        if not heard or heard[0] not in permitted or heard[1:] != expected[1:]:
            raise ValueError(f'The wording around Macfarlane differs: {hypothesis!r}')
    sample = audio
    if len(expected) > 2:
        times = timed_words(audio)
        if len(times) < 3 or times[1][0] != 'case' or times[2][0] != 'has':
            raise ValueError('Cannot locate the end of “Macfarlane’s case”')
        sample = audio[:times[2][1]]
    key, score, start, end = locate_sound(sample, decoder(expected[1]), _FORMS)
    phones = _FORMS[key]
    ending = ' AH N Z' if possessive else ' AH N'
    if (not phones.endswith(ending) or score < .12 or not .34 * RATE <= end - start <= 1.05 * RATE
            or any(start < (a + b) / 2 < end for a, b in interior_gaps(sample))):
        raise ValueError(f'Unclear final nasal or possessive in Macfarlane: {phones}')
    return dict(phones=phones, confidence=round(score, 3),
                start=round(start / RATE, 3), end=round(end / RATE, 3))
