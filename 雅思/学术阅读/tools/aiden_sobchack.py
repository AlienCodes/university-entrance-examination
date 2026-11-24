"""Verify the film scholars' surname against Kathleen McHugh's two SCMS introductions."""
from functools import lru_cache
import re

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


PHONES = {
    'sobchack': 'S AA B CH AE K', 'sobcheck': 'S AA B CH EH K',
    'extra-vowel': 'S OW B AH CH AE K', 'extra-short-vowel': 'S AA B AH CH AE K',
    'extra-o': 'S AA B OW CH AE K', 'extra-i': 'S AA B IH CH AE K',
    'long-o': 'S OW B CH AE K', 'long-o-check': 'S OW B CH EH K',
    'sopachak': 'S AA P AH CH AE K', 'missed-stop': 'S AA CH AE K',
    'missed-ending': 'S AA B CH AE', 'missed-final-shape': 'S AA B SH AE K',
    'wrong-vowel': 'S AA B CH IY K', 'missing-chack': 'S AA B', 'missing-sob': 'CH AE K',
    'soback': 'S AA B AE K',
}
# These transcriptions occur for the same two-syllable surname in the SCMS interview.
SPELLINGS = {'sobchack', 'sobchak', 'sopchak'}
RENDERINGS = ('Sobchack', 'Sobchak', 'SAHB-chack', 'Sahb-chack', 'Sobchack')


@lru_cache(maxsize=1)
def phone_recognizer():
    context = {'vivian': 'V IH V IY AH N', 'thomas': 'T AA M AH S', 'professor': 'P R AH F EH S ER',
               'and': 'AH N D', 'call': 'K AO L', 'who': 'HH UW', 'has': 'HH AE Z'}
    return grammar_decoder(PHONES, context, '[(vivian | thomas | professor)] {term} [(and | call | who | has)]')


def check_word(sample):
    label, score, start, end = locate_sound(sample, phone_recognizer(), PHONES)
    if label not in {'sobchack', 'sobcheck'} or score < .20:
        raise ValueError(f'Sobchack differs from the two-syllable SCMS examples: {PHONES[label]}')
    if not .27 * RATE <= end - start <= 1.20 * RATE:
        raise ValueError('Cannot locate a complete recording of Sobchack')
    if any(start < (lo + hi) / 2 < end for lo, hi in interior_gaps(sample)):
        raise ValueError('A pause interrupts Sobchack')
    return dict(phones=PHONES[label], score=round(score, 3), start=start / RATE, end=end / RATE)


def verify(audio, text, first, second):
    expected = words(text)
    count = expected.count('sobchack')
    if not count:
        raise ValueError('Missing the stated author')

    def check_context(tokens):
        names = [i for i, word in enumerate(tokens) if word in SPELLINGS]
        # Both recognizers may join film-maker. Retain every actual surrounding word.
        joined = ''.join('sobchack' if word in SPELLINGS else word for word in tokens)
        if len(names) != count or joined != ''.join(expected):
            raise ValueError('The names or their surrounding words differ from the film passage')
        return names

    check_context(words(first))
    # Whisper spells McHugh's two intact examples differently in short excerpts.
    # The time-aligned recognizer and the per-name acoustic check are independent.
    second = re.sub(r'\b(?:sopc check|sopcke)\b', 'Sobchack', second, flags=re.I)
    check_context(words(second))
    timed = timed_words(audio)
    indices = check_context([word for word, _ in timed])
    reports = []
    for i in indices:
        lo = max(0, timed[i][1] - round(.095 * RATE))
        hi = (min(len(audio), timed[i + 1][1] + round(.075 * RATE))
              if i + 1 < len(timed) else len(audio))
        item = check_word(audio[lo:hi])
        item['start'] = round(item['start'] + lo / RATE, 3)
        item['end'] = round(item['end'] + lo / RATE, 3)
        reports.append(item)
    return reports
