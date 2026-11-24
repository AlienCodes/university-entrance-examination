"""Check Thor Heyerdahl against the two American Heritage pronunciations and dictionary audio."""
from functools import lru_cache
from itertools import product

from aiden_boundaries import RATE, interior_gaps, words
from aiden_pronunciation import grammar_decoder, locate_sound


RENDERINGS = ('Thor Heyerdahl', 'Thor Hayerdahl', 'Thor Hay-er-dahl', 'Thor Higher-dahl', 'Thor Heyerdahl')
HINT = 'Say the explorer’s name Thor HAY-er-dahl. Use the th in thorn and the ah vowel before the final l in dahl.'
# Compete against the lost consonants and the final vowel in the rejected first take.
PHONES = {
    f'surname-{i}': ' '.join(part for part in sequence if part)
    for i, sequence in enumerate(product(('HH', ''), ('EY', 'AY', 'EH', 'AE'),
                                         ('ER', 'AH R', ''), ('D', 'T', ''), ('AA', 'AO', 'AE'), ('L', '')))
}


@lru_cache(maxsize=1)
def recognizer():
    context = {'thor':'TH AO R', 'door':'D AO R', 'tor':'T AO R', 'for':'F AO R', 'the':'DH AH'}
    return grammar_decoder(PHONES,context,'[(thor | door | tor | for | the)] {term}')


def verify(audio, first, second):
    heard = [words(text) for text in (first, second)]
    if (not all(2 <= len(row) <= 4 and row[0] in {'thor', 'door', 'tor'}
                and row[1].startswith('h') for row in heard) or not any(row[0] == 'thor' for row in heard)):
        raise ValueError(f'The complete name Thor Heyerdahl was not identified: {first!r} / {second!r}')
    decoder = recognizer()
    key, score, start, end = locate_sound(audio, decoder, PHONES)
    first_names = [s for s in decoder.seg() if s.word not in PHONES and not s.word.startswith('<')]
    accepted = {f'HH {vowel} {middle} D AA L' for vowel in ('EY', 'AY') for middle in ('ER', 'AH R')}
    if (len(first_names) != 1 or first_names[0].word != 'thor' or PHONES[key] not in accepted
            or score < .1 or not .32 * RATE < end-start < 1.3 * RATE):
        raise ValueError(f'Thor Heyerdahl differs from the dictionary pronunciations: {[s.word for s in first_names]}, {PHONES[key]}')
    if any(start < (a+b)/2 < end for a,b in interior_gaps(audio)):
        raise ValueError('A pause interrupts the surname Heyerdahl')
    return {'first_name':first_names[0].word, 'phones':PHONES[key], 'score':round(score,3),
            'start':round(start/RATE,3),'end':round(end/RATE,3)}
