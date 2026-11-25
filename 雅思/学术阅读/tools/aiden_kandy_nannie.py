"""Measure names in their printed context when the readers use a different spelling."""
from aiden_boundaries import RATE, independent, interior_gaps, isolated, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound
from aiden_surnames import forms


HEPBURN = tuple(('this use of dialogue underscores not only the dizzy quality of the character '
                 'played by katherine hepburn').split())
PHRASES = {
    tuple('the dutch allied themselves with kandy'.split()): ('kandy', 'candy'),
    tuple('is chased by a witch called nannie'.split()): ('nannie', 'nanny'),
    ('says', 'carl', 'cotman'): ('cotman', 'kotman'),
    HEPBURN: ('katherine', 'catherine'),
}
CHECKS = {
    'kandy': (forms(('K', 'G', ''), ('AE', 'AH', 'EH', 'AA'), ('N D', 'N', 'D', ''), ('IY', 'IH', 'EY', '')),
              ('K AE N D IY',), {'with': 'W IH TH', 'widh': 'W IH DH'}, '[with | widh] {term}'),
    'nannie': (forms(('N', 'M', ''), ('AE', 'AH', 'EH', 'EY'), ('N', 'M', ''), ('IY', 'IH', '')),
               ('N AE N IY',), {'called': 'K AO L D', 'cald': 'K AA L D'}, '[called | cald] {term}'),
    'cotman': (forms(('K', 'G', ''), ('AA', 'AO', 'AH', 'OW'), ('T M', 'T', 'M', ''),
                     ('AH N', 'IH N', 'AE N', 'AH M', 'AH', '')),
               ('K AA T M IH N', 'K AA T M AH N'), {'carl': 'K AA R L'}, '[carl] {term}'),
    'katherine': (forms(('K', 'G', ''), ('AE', 'AH', 'EH'), ('TH ER', 'TH R', 'T R', 'R', 'TH', ''),
                        ('IH N', 'AH N', 'IH M', 'IH', '')),
                  ('K AE TH R IH N', 'K AE TH ER IH N'), {'by': 'B AY', 'hepburn': 'HH EH P B ER N'},
                  '[by] {term} [hepburn]'),
}


def verify(audio, expected, first=None, second=None):
    name, spelling = PHRASES[tuple(expected)]
    index = expected.index(name)
    timed = timed_words(audio)
    readings = [first or isolated(audio), second or independent(audio)]
    for tokens in (words(readings[0]), words(readings[1]), [word for word, _ in timed]):
        if len(tokens) == len(expected) and tokens[index] == spelling:
            tokens[index] = name
        if tokens != list(expected):
            raise ValueError(f'The spoken name or its surrounding words differ: {readings}')

    variants, target, markers, rule = CHECKS[name]
    variants = {key: phones for key, phones in variants.items() if phones}
    gaps = interior_gaps(audio)
    checks = []
    # First locate the name in context. In "Katherine Hepburn" the word-level
    # recognizer timestamps the next word before the /n/ has finished. Isolate
    # the first name at its measured phonetic boundary for the second reading.
    for context, start_word in ((True, index - 1), (False, index)):
        start = max(0, timed[start_word][1] - 400)
        stop = len(audio)
        if not context and index + 1 < len(timed):
            begin, stop = checks[0]['samples']
            if abs(begin - timed[index][1]) > .15 * RATE or abs(stop - timed[index + 1][1]) > .15 * RATE:
                raise ValueError(f'Cannot isolate {name} from the following word')
            start = max(0, begin - 240)
        decoder = grammar_decoder(variants, markers if context else {}, rule if context else '{term}')
        label, confidence, begin, end = locate_sound(audio[start:stop], decoder, variants)
        begin += start
        end += start
        if (variants[label] not in target or confidence < .12 or end - begin < .18 * RATE
                or any(begin < (a + b) / 2 < end for a, b in gaps)):
            raise ValueError(f'Incomplete or different pronunciation of {name}: {variants[label]}')
        checks.append(dict(phones=variants[label], confidence=round(confidence, 3), samples=[begin, end]))
    return dict(term=name, readings=readings, measurements=checks)


def confirmed_ending(item, expected):
    target = PHRASES.get(tuple(expected))
    evidence = item.get('contextual_name', {})
    if not target or expected[-1] != target[0] or evidence.get('term') != target[0]:
        return False
    checks = evidence.get('measurements', [])
    return len(checks) == 2 and all(m['phones'] in CHECKS[target[0]][1] for m in checks)
