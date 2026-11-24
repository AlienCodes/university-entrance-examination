"""Check the plural in 'unlike other export sectors' against the original split-word recording."""
from functools import lru_cache

from aiden_boundaries import RATE, interior_gaps
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


FORMS = {
    'sectors': 'S EH K T ER Z', 'nonrhotic-sectors': 'S EH K T AH Z',
    'sector': 'S EH K T ER', 'sect': 'S EH K T', 'secs': 'S EH K S',
    'sec': 'S EH K', 'se': 'S EH', 'sects': 'S EH K T S',
    'sers': 'S ER Z', 'tors': 'T ER Z', 'extra-syllable': 'S EH K S T R AH',
}


@lru_cache(maxsize=1)
def decoder():
    context = {'unlike': 'AH N L AY K', 'other': 'AH DH ER',
               'export': 'EH K S P AO R T', 'exports': 'EH K S P AO R T S', 'which': 'W IH CH'}
    return grammar_decoder(FORMS, context, '[unlike] [other] (export | exports) {term} [which]')


def verify(audio, expected):
    sample = audio
    if len(expected) > 4:
        times = timed_words(audio)
        stop = next((t for w, t in times if w == 'make'), None)
        if stop is None:
            raise ValueError('Cannot locate the relative clause after export sectors')
        sample = audio[:stop]
    key, confidence, start, end = locate_sound(sample, decoder(), FORMS)
    if (key not in ('sectors', 'nonrhotic-sectors') or confidence < .50 or end - start < .26 * RATE
            or any(start < (a + b) / 2 < end for a, b in interior_gaps(sample))):
        raise ValueError(f'Incomplete or interrupted plural in export sectors: {FORMS[key]}')
    return dict(phones=FORMS[key], start=round(start / RATE, 3), end=round(end / RATE, 3),
                confidence=round(confidence, 3))
