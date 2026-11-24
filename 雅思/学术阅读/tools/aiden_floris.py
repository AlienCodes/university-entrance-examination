"""Verify the Dutch soil specialist's surname and its English possessive on the recorded speech."""
from functools import lru_cache

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


# Dutch /ˈfloː.rɪs/. Native reference recordings contain a short, weak second vowel.
FORMS = {
    'floris': 'F L AO R IH S', 'floris-long-o': 'F L OW R IH S',
    'floris-reduced': 'F L AO R AH S', 'floris-long-o-reduced': 'F L OW R AH S',
    'flor': 'F L AO R', 'floors': 'F L AO R Z', 'flores': 'F L AO R EY S',
    'flores-voiced': 'F L AO R EH Z', 'florez': 'F L AO R EY Z',
    'florace': 'F L AO R EH S', 'fleece': 'F L IY S', 'floris-voiced': 'F L AO R IH Z',
}
PERMITTED = {'floris', 'floris-long-o', 'floris-reduced', 'floris-long-o-reduced'}


@lru_cache(maxsize=2)
def decoder(possessive):
    if possessive:
        context = {'iz': 'IH Z', 'uz': 'AH Z', 'mix': 'M IH K S', 'mixed': 'M IH K S T',
                   'miss': 'M IH S', 'to': 'T UW', 'ta': 'T AH'}
        return grammar_decoder(FORMS, context, '{term} [iz | uz] (mix | mixed | miss) [to | ta]')
    return grammar_decoder(FORMS, {'pius': 'P AY AH S', 'peeus': 'P IY AH S'},
                           '[pius | peeus] {term}')


def verify(audio, expected, first, second):
    possessive = 'floriss' in expected
    root = 'floriss' if possessive else 'floris'
    i = expected.index(root)
    alternatives = {'floris', 'flores', 'florus'}
    if possessive:
        alternatives |= {s + ending for s in alternatives for ending in ('s','es')}
    def same_words(hypothesis):
        if hypothesis[:i] != expected[:i] or not hypothesis[i:i+1] or hypothesis[i] not in alternatives:
            return False
        if possessive:
            return hypothesis[i+1:i+2] in (['mix'],['mixed']) and hypothesis[i+2:] == expected[i+2:]
        return hypothesis[i+1:] == expected[i+1:]
    for h in (first, second):
        if not same_words(words(h)):
            raise ValueError(f'The wording around Floris differs: {h!r}')
    if possessive and all(words(h)[i+1] != 'mix' for h in (first, second)):
        raise ValueError('Neither reading contains the noun mix after the possessive')
    timed = timed_words(audio)
    if not same_words([w for w, t in timed]):
        raise ValueError('Cannot locate the surname Floris in the printed context')
    lo = max(0, timed[i][1] - round(.11 * RATE))
    # Include the onset and vowel of "to". An isolated t left at the end of the
    # noun can make the acoustic model hear the consonant cluster in "mixed".
    hi = min(len(audio), timed[i+2][1] + round(.14 * RATE)) if possessive and i+2 < len(timed) else len(audio)
    recognizer = decoder(possessive)
    key, score, start, end = locate_sound(audio[lo:hi], recognizer, FORMS)
    if key not in PERMITTED or score < .15 or not .26 * RATE <= end-start <= 1.25 * RATE:
        raise ValueError(f'The two syllables or final s in Floris are unclear: {FORMS[key]}')
    if any(start < (a+b)/2 < end for a, b in interior_gaps(audio[lo:hi])):
        raise ValueError('A silence splits the surname Floris')
    segments = [s.word for s in recognizer.seg()]
    suffix = [word for word in segments if word in ('iz','uz')]
    if possessive and (len(suffix) != 1 or 'mix' not in segments):
        raise ValueError('The possessive syllable or the noun mix is incomplete')
    return dict(phones=FORMS[key], possessive_syllable=suffix, confidence=round(score,3),
                start=round((lo+start)/RATE,3), end=round((lo+end)/RATE,3))
