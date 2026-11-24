"""Distinguish the Egyptian star groups (DECK-uhnz) from 'deacons' in the timekeeping paper."""
from functools import lru_cache

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound

# Merriam-Webster, decan, /ˈdɛkən/. The paper uses its plural three times.
PHONES = {
    'decans': 'D EH K AH N Z', 'syllabic-n': 'D EH K N Z',
    'deacons': 'D IY K AH N Z', 'dee-cans': 'D IY K AE N Z',
    'deck-cans': 'D EH K AE N Z', 'dickens': 'D IH K AH N Z',
    'dakens': 'D EY K AH N Z', 'dackins': 'D AE K IH N Z',
    'singular-decan': 'D EH K AH N', 'singular-deacon': 'D IY K AH N',
    'deck': 'D EH K', 'decks': 'D EH K S', 'cans': 'K AE N Z',
}
CONTEXT = {'called': 'K AO L D', 'twelve': 'T W EH L V', 'could': 'K UH D', 'led': 'L EH D'}
RENDERINGS = ('decans', 'Deckens', 'DECK-uhnz', 'deckens', 'DECK-uhnz')


@lru_cache(maxsize=3)
def decoder(left, right):
    rule = '[' + left + '] {term}' + (' [' + right + ']' if right else '')
    return grammar_decoder(PHONES, CONTEXT, rule)


def span(expected, heard):
    start = expected.index('decans')
    end = len(heard) - (len(expected) - start - 1)
    if (heard[:start] != expected[:start] or heard[end:] != expected[start + 1:]
            or not 1 <= end - start <= 2):
        raise ValueError('The words around decans differ from the paper')
    return start, end


def verify(audio, expected, first, second):
    span(expected, words(first))
    span(expected, words(second))
    times = timed_words(audio)
    i, end = span(expected, [w for w, _ in times])
    left, right = expected[i - 1], (expected[i + 1] if i + 1 < len(expected) else '')
    if (left, right) not in {('called', ''), ('twelve', 'could'), ('twelve', 'led')}:
        raise ValueError('Unrecognised word context for the decans in the timekeeping passage')
    lo = max(0, times[i - 1][1] - round(.04 * RATE))
    hi = times[end + 1][1] if end + 1 < len(times) else len(audio)
    key, score, start, stop = locate_sound(audio[lo:hi], decoder(left, right), PHONES)
    start, stop = start + lo, stop + lo
    if (key not in ('decans', 'syllabic-n') or score < .12 or not .21 * RATE <= stop - start <= .85 * RATE
            or any(start < (a + b) / 2 < stop for a, b in interior_gaps(audio))):
        raise ValueError(f'Unclear short e or plural ending in decans: {PHONES[key]}')
    return dict(phones=PHONES[key], confidence=round(score, 3),
                start=round(start / RATE, 3), end=round(stop / RATE, 3))
