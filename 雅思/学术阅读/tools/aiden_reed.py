"""Distinguish the two spoken words in the attribution 'Reed adds'."""
from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound
from aiden_surnames import forms


PHRASE = ('reed', 'adds')
CHECKS = (
    (forms(('R', 'L', ''), ('IY', 'IH', 'EH', 'AE'), ('D', 'T', '')),
     'R IY D', {'adds': 'AE D Z'}, '{term} [adds]'),
    (forms(('AE', 'EH', 'AH', 'AA'), ('D', 'T', ''), ('Z', 'S', '')),
     'AE D Z', {'reed': 'R IY D'}, '[reed] {term}'),
)


def verify(audio, first, second):
    timed = timed_words(audio)
    for observed in (words(first), words(second), [word for word, _ in timed]):
        if len(observed) != 2 or observed[0] not in ('reed', 'read', 'reid') or observed[1] not in ('adds', 'ads'):
            raise ValueError(f'The spoken attribution differs from Reed adds: {first!r} / {second!r}')
    onset = timed[1][1]
    gaps = interior_gaps(audio)
    checks = {}
    for index, (alternatives, target, context, rule) in enumerate(CHECKS):
        variants = {key: value for key, value in alternatives.items() if value}
        start = max(0, timed[index][1] - 400)
        end = min(len(audio), onset + 180) if index == 0 else len(audio)
        readings = []
        for left, right, markers, grammar in ((0, len(audio), context, rule), (start, end, {}, '{term}')):
            decoder = grammar_decoder(variants, markers, grammar)
            label, confidence, begin, stop = locate_sound(audio[left:right], decoder, variants)
            begin += left
            stop += left
            if (variants[label] != target or confidence < .12 or stop - begin < .12 * RATE
                    or any(begin < (a + b) / 2 < stop for a, b in gaps)):
                raise ValueError(f'Unclear {PHRASE[index]} in Reed adds: {variants[label]}')
            readings.append(dict(phones=target, confidence=round(confidence, 3), samples=[begin, stop]))
        checks[PHRASE[index]] = readings
    return checks


def confirmed(item):
    if tuple(words(item['text'])) != PHRASE:
        return False
    proof = item.get('reed_attribution', {})
    return all(len(proof.get(word, ())) == 2 and all(r['phones'] == spec[1] for r in proof[word])
               for word, spec in zip(PHRASE, CHECKS))
