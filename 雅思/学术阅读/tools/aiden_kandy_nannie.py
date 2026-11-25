"""Measure phrase-final names when the two readers use a different spelling."""
from aiden_boundaries import RATE, independent, interior_gaps, isolated, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound
from aiden_surnames import forms


PHRASES = {
    tuple('the dutch allied themselves with kandy'.split()): ('kandy', 'candy'),
    tuple('is chased by a witch called nannie'.split()): ('nannie', 'nanny'),
    ('says', 'carl', 'cotman'): ('cotman', 'kotman'),
}
CHECKS = {
    'kandy': (forms(('K', 'G', ''), ('AE', 'AH', 'EH', 'AA'), ('N D', 'N', 'D', ''), ('IY', 'IH', 'EY', '')),
              ('K AE N D IY',), {'with': 'W IH TH', 'widh': 'W IH DH'}, '[with | widh] {term}'),
    'nannie': (forms(('N', 'M', ''), ('AE', 'AH', 'EH', 'EY'), ('N', 'M', ''), ('IY', 'IH', '')),
               ('N AE N IY',), {'called': 'K AO L D', 'cald': 'K AA L D'}, '[called | cald] {term}'),
    'cotman': (forms(('K', 'G', ''), ('AA', 'AO', 'AH', 'OW'), ('T M', 'T', 'M', ''),
                     ('AH N', 'IH N', 'AE N', 'AH M', 'AH', '')),
               ('K AA T M IH N', 'K AA T M AH N'), {'carl': 'K AA R L'}, '[carl] {term}'),
}


def verify(audio, expected, first=None, second=None):
    name, spelling = PHRASES[tuple(expected)]
    timed = timed_words(audio)
    readings = [first or isolated(audio), second or independent(audio)]
    for tokens in (words(readings[0]), words(readings[1]), [word for word, _ in timed]):
        if tokens[:-1] != expected[:-1] or tokens[-1:] not in ([name], [spelling]):
            raise ValueError(f'The spoken name or its surrounding words differ: {readings}')

    variants, target, markers, rule = CHECKS[name]
    variants = {key: phones for key, phones in variants.items() if phones}
    gaps = interior_gaps(audio)
    checks = []
    # Each name ends its phrase. First include the preceding word, then measure
    # the word alone with a fresh decoder so adaptation cannot leak between takes.
    for start, context in ((timed[-2][1] - 400, True), (timed[-1][1] - 400, False)):
        start = max(start, 0)
        decoder = grammar_decoder(variants, markers if context else {}, rule if context else '{term}')
        label, confidence, begin, end = locate_sound(audio[start:], decoder, variants)
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
    if not target or evidence.get('term') != target[0]:
        return False
    checks = evidence.get('measurements', [])
    return len(checks) == 2 and all(m['phones'] in CHECKS[target[0]][1] for m in checks)
