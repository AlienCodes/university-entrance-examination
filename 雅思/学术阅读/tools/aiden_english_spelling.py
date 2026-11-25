"""Verify spoken words when the readers use a different spelling from the passage."""

SPELLINGS = {
    'clamoured': 'clamored',
    'encyclopaedic': 'encyclopedic',
    'enrolment': 'enrollment',
    'unrivalled': 'unrivaled',
}

# Both readers split or join these exact printed compounds. Keep surrounding
# words and inflections exact, including the final plural in "forests".
COMPOUNDS = {
    tuple('the topics discussed included the co ordinated study of the destruction of forests'.split()): ('co', 'ordinated'),
    tuple('and successfully made the switchover'.split()): ('switch', 'over'),
}


def joined_tokens(timed, pair):
    merged = []
    for word, onset in timed:
        if word == pair[1] and merged and merged[-1][0] == pair[0]:
            merged[-1] = (''.join(pair), merged[-1][1])
        else:
            merged.append((word, onset))
    return merged


def compound_words(tokens, pair):
    return [word for word, _ in joined_tokens(((token, None) for token in tokens), pair)]


def verify_compound(audio, expected, first, second):
    from aiden_boundaries import RATE, independent, interior_gaps, isolated, words
    from aiden_ceylonese import timed_words
    pair = COMPOUNDS[tuple(expected)]
    printed = compound_words(expected, pair)
    joined = ''.join(pair)
    timed = joined_tokens(timed_words(audio), pair)
    if (any(compound_words(words(s), pair) != printed for s in (first, second))
            or [word for word, _ in timed] != printed):
        raise ValueError(f'The full words surrounding {joined} were not confirmed')
    index = printed.index(joined)
    start = timed[index][1]
    end = timed[index+1][1] if index+1 < len(timed) else len(audio)
    if any(start < (a+b)/2 < end-round(.04*RATE) for a,b in interior_gaps(audio)):
        raise ValueError(f'A pause interrupts {joined}')
    # Include "made the" at the end of the switchover sentence. Starting at
    # the weak article alone cuts the previous sound in the original recording.
    before = 2 if index+1 == len(timed) else 1
    left = max(0, timed[max(0, index-before)][1] - round(.05*RATE))
    right = timed[index+2][1] if index+2 < len(timed) else len(audio)
    excerpts = [read(audio[left:right]) for read in (isolated, independent)]
    if any(joined not in compound_words(words(s), pair) for s in excerpts):
        raise ValueError(f'The two focused readings do not confirm {joined}')
    return dict(word=joined, start=start/RATE, end=end/RATE, full_readings=[first,second], focused_readings=excerpts)


def confirmed_compound_edge(item, expected, index):
    from aiden_boundaries import words
    pair = COMPOUNDS.get(tuple(expected))
    evidence = item.get('compound_spelling', {})
    if not pair or evidence.get('word') != ''.join(pair):
        return False
    printed = compound_words(expected, pair)
    readings = evidence.get('full_readings', [])
    return (printed[index] == ''.join(pair) and len(readings) == 2
            and all(compound_words(words(text), pair) == printed for text in readings))


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
