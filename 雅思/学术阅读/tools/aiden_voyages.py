"""Check the two disputed spellings in Beyond the blue horizon against the recording."""
from itertools import product

from aiden_boundaries import RATE, independent, interior_gaps, isolated, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound
from aiden_word_review import same_words


TARO = 'their livestock taro seedlings and stone tools'.split()
VOYAGES = 'and people have built canoes to re create those early voyages based on that assumption'.split()


def decoder(term, context):
    # PocketSphinx adapts its cepstral mean across utterances. Each word window
    # must give the same result regardless of which recording was checked first.
    if term == 'taro':
        choices = product(('T', 'D', ''), ('EH', 'AE', 'AA', 'IH', 'ER'), ('R', 'L', ''), ('OW', 'AH', 'AW', ''))
        surrounding = {'seed': 'S IY D L IH NG Z', 'live': 'L AY V S T AA K'}
        rule = '[live] {term} [seed]'
    else:
        choices = product(('R IY', 'R IH', 'R EH', 'R AH', ''), ('K R IY','K R IH','K R','K',''),
                          ('EY T','EY','EH T','EY T IH D',''))
        surrounding = {'to':'T UW', 'ta':'T AH', 'those':'DH OW Z'}
        rule = '[to | ta] {term} [those]'
    forms = {f'p{i}': ' '.join(part for part in sound if part) for i, sound in enumerate(choices) if any(sound)}
    return grammar_decoder(forms, surrounding if context else {}, rule if context else '{term}'), forms


def spelling(tokens, term):
    # The two free readers also alternate between their and they're before livestock.
    if (term == 'taro' and len(tokens) == len(TARO) and tokens[0] in ('their','theyre')
            and tokens[1] == 'livestock' and tokens[2] in ('taro','tarot') and tokens[3:] == TARO[3:]):
        return TARO
    if term == 're-create' and tokens == VOYAGES[:6] + ['recreate'] + VOYAGES[8:]:
        return VOYAGES
    return tokens


def verify(audio, expected, first=None, second=None):
    if expected not in (TARO, VOYAGES):
        raise ValueError('Different printed passage')
    term = 'taro' if expected == TARO else 're-create'
    readings = [first or isolated(audio), second or independent(audio)]
    if not all(same_words(expected, spelling(words(s), term)) for s in readings):
        raise ValueError(f'The surrounding words of {term} differ: {readings}')
    timed = timed_words(audio)
    tokens = [w for w,_ in timed]
    if not same_words(expected, spelling(tokens, term)):
        raise ValueError(f'Could not locate {term} in its printed context')
    if term == 'taro':
        index, following = 2, 3
        # Cambridge gives taro and tarot the same US pronunciation. The two
        # entries in the US acoustic dictionary use EH and AE before this R.
        accepted = {'T EH R OW', 'T AE R OW'}
    else:
        index, following = 6, tokens.index('those')
        accepted = {'R IY K R IY EY T'}
    windows = ((timed[index-1][1]-200, timed[following+1][1]+200, True),
               (timed[index][1]-400, timed[following][1]+160, False))
    checks = []
    for start, end, context in windows:
        start, end = max(0, start), min(len(audio), end)
        recognizer, forms = decoder(term, context)
        word, confidence, begin, finish = locate_sound(audio[start:end], recognizer, forms)
        begin += start
        finish += start
        if (forms[word] not in accepted or confidence < .12 or finish-begin < .18*RATE
                or any(begin < (a+b)/2 < finish for a,b in interior_gaps(audio))):
            raise ValueError(f'Incomplete {term} in its spoken context: {forms[word]}')
        checks.append(dict(phones=forms[word], confidence=round(confidence, 3), samples=[begin,finish]))
    return dict(term=term, readings=readings, measurements=checks)
