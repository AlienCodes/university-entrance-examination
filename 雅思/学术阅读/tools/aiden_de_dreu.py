"""Check the psychologist's surname against the English interview and the two real Aiden takes."""
from functools import lru_cache
from itertools import product

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


RENDERINGS = ('De Dreu', 'de Drew', 'duh Drew', 'de Drew', 'De Dreu')
HINT = 'Read the psychologist’s surname as two connected syllables, with a weak first syllable and Drew rhyming with true.'
# Include the dropped particle, missing stop or r, and the final vowel of the
# rejected recording in the competition. Unvoiced stops occur in the interview.
PHONES = {
    f'variant-{i}': ' '.join(part for part in (particle, onset, vowel) if part)
    for i, (particle, onset, vowel) in enumerate(product(
        ('D AH', 'D ER', 'T AH', 'D IH', 'D IY', ''),
        ('D R', 'T R', 'R', 'D'), ('UW', 'OW', 'AW', 'AH', 'EY')))
}


@lru_cache(maxsize=1)
def recognizer():
    context = {'carsten': 'K AA R S T AH N', 'to': 'T UW', 'ta': 'T AH',
               'is': 'IH Z', 'at': 'AE T', 'welcome': 'W EH L K AH M'}
    return grammar_decoder(PHONES, context, '[(carsten | to | ta)] {term} [(is | at | welcome)]')


def check_word(sample):
    key, score, start, end = locate_sound(sample, recognizer(), PHONES)
    phones = PHONES[key].split()
    if (len(phones) != 5 or phones[-2:] != ['R', 'UW']
            or not .27 * RATE <= end - start <= 1.2 * RATE or score < .09):
        raise ValueError(f'Unclear particle or final vowel in De Dreu: {PHONES[key]}')
    if any(start < (a + b) / 2 < end for a, b in interior_gaps(sample)):
        raise ValueError('A pause interrupts the surname De Dreu')
    return {'phones': PHONES[key], 'score': round(score, 3), 'start': start / RATE, 'end': end / RATE}


def name_span(tokens):
    for i, word in enumerate(tokens):
        if word in {'dedrew', 'dedreu', 'deidreux'}:
            return i, i + 1
        if word in {'de', 'der', 'duh'} and tokens[i + 1:i + 2] in (['drew'], ['dreu'], ['dru']):
            return i, i + 2
    raise ValueError('The speech recognizer could not locate De Dreu')


def verify(audio, text, first, second):
    expected = words(text)
    start, end = name_span(expected)
    def check_context(tokens):
        left, right = name_span(tokens)
        if tokens[:left] != expected[:start] or tokens[right:] != expected[end:]:
            raise ValueError('The words surrounding De Dreu differ from the printed phrase')
        return left, right

    check_context(words(first))
    check_context(words(second))
    timed = timed_words(audio)
    left, right = check_context([w for w, _ in timed])
    lo = max(0, timed[left][1] - round(.1 * RATE))
    hi = min(len(audio), timed[right][1] + round(.07 * RATE)) if right < len(timed) else len(audio)
    result = check_word(audio[lo:hi])
    for edge in ('start', 'end'):
        result[edge] = round(lo / RATE + result[edge], 3)
    return result
