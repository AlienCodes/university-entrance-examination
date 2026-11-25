"""Check the American transcriptions of four British spellings in the printed passages."""

SPELLINGS = {
    'clamoured': 'clamored',
    'encyclopaedic': 'encyclopedic',
    'enrolment': 'enrollment',
    'unrivalled': 'unrivaled',
}


def normalized(tokens):
    return [SPELLINGS.get(token, token) for token in tokens]


def verify(audio, expected, first, second):
    from aiden_boundaries import RATE, independent, interior_gaps, isolated, words
    from aiden_ceylonese import timed_words

    printed = normalized(expected)
    timed = timed_words(audio)
    for observed in (words(first), words(second), [word for word, _ in timed]):
        if normalized(observed) != printed:
            raise ValueError('The two full readings or the timed words differ beyond the spelling')
    checks = []
    gaps = interior_gaps(audio)
    for index, term in enumerate(expected):
        if term not in SPELLINGS:
            continue
        start = timed[index][1]
        end = timed[index+1][1] if index+1 < len(timed) else len(audio)
        if any(start < (a+b)/2 < end-round(.04*RATE) for a,b in gaps):
            raise ValueError(f'A possible interruption within {term} needs another reading')
        # Repeat the recognition on the word with its immediate neighbours,
        # independently of the context available in the whole sentence.
        left = max(0, timed[max(0,index-1)][1]-round(.05*RATE)) if index > 1 else 0
        right = timed[index+2][1] if index+2 < len(timed) else len(audio)
        excerpt = audio[left:right]
        readings = (isolated(excerpt), independent(excerpt))
        if any(SPELLINGS[term] not in normalized(words(reading)) for reading in readings):
            raise ValueError(f'The focused readings did not both identify {term}')
        checks.append(dict(printed=term, transcribed=SPELLINGS[term], start=start/RATE,
                           end=end/RATE, focused_readings=readings))
    if not checks:
        raise ValueError('No reviewed spelling occurs in the printed phrase')
    return checks
