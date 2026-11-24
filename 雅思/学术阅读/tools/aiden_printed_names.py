"""Listen to the complete spoken names at the specific checkpoints in the reading passages."""
from functools import lru_cache

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound
from aiden_word_review import MEASURED_NAMES, same_words


# Each alternative changes an audible part of a name. Keep the alternatives in
# the decoder even where the two free transcriptions agree on a familiar spelling.
FOSSIL = {
    'full':'P IH TH IH K AE N TH R OW P AH S', 'schwa':'P IH TH AH K AE N TH R OW P AH S',
    'stop':'P IH TH IH K AE N T TH R OW P AH S', 'schwa-stop':'P IH TH AH K AE N T TH R OW P AH S',
    'long':'P IH TH IY K AE N TH R OW P AH S', 'reduced':'P IH TH IH K AE N TH R AH P AH S',
    'lost-th':'P IH TH AH K AE N T R OW P AH S', 'lost-first-th':'P IH T AH K AE N TH R OW P AH S',
    'short':'K AE N TH R OW P AH S', 'lost-ending':'P IH TH IH K AE N TH R OW',
    'anthropus':'AE N TH R OW P AH S', 'lost-s':'P IH TH IH K AE N TH R OW P AH',
    'pie':'P AY TH AH K AE N TH R OW P AH S', 'through':'P IH TH AH K AE N TH R UW P AH S',
}
ISLAND = {
    'english':'IH Z AH B EH L AH', 'unvoiced':'IH S AH B EH L AH', 'long':'IY Z AH B EH L AH',
    'spanish':'IY S AA B EH L AH', 'spanish-reduced':'IY S AH B EH L AH',
    'isabelle':'IH Z AH B EH L', 'bella':'B EH L AH', 'island':'AY L AH N D',
    'isabeela':'IH Z AH B IY L AH', 'izbel':'IH Z B EH L', 'isabel':'IY S AA B EH L',
    'lost-onset':'Z AH B EH L AH', 'lost-b':'IH Z AA L AH',
}
CLEMMONS = {
    'full':'K L EH M AH N Z IH Z', 'full-alt':'K L EH M IH N Z IH Z', 'schwa':'K L EH M AH N Z AH Z',
    'plain':'K L EH M AH N Z', 'alt-plain':'K L EH M IH N Z', 'lost-s':'K L EH M AH N',
    'unvoiced':'K L EH M AH N S', 'short':'K L EH M Z', 'lost-k':'L EH M AH N Z IH Z',
    'extra':'K L EH M AH N S AH N Z',
}
DOLLO = {
    'dollos':'D AA L OW Z', 'rounded':'D AO L OW Z', 'bare':'D AA L OW', 'bare-rounded':'D AO L OW',
    'doblo':'D AA B L OW Z', 'dole':'D OW L Z', 'dollars':'D AA L ER Z', 'dah-loss':'D AA L AO S',
    'dala':'D AA L AH Z', 'dallas':'D AE L AH S', 'dallow':'D AE L OW Z', 'doy':'D OY L OW Z',
}
CONTEXT = {
    'pithecanthropus': (FOSSIL, {'erectus':'IH R EH K T AH S','is':'IH Z'}, '{term} [erectus] [is]',
                        {'full','schwa','stop','schwa-stop','reduced'}, .5),
    'isabela': (ISLAND, {}, '{term}', {'english','unvoiced','long','spanish','spanish-reduced'}, .33),
    'clemmonss': (CLEMMONS, {'sparked':'S P AA R K T','interest':'IH N T R AH S T'},
                  '[sparked] {term} [interest]', {'full','full-alt','schwa'}, .38),
    'dollos': (DOLLO, {'as':'AE Z','if':'IH F','law':'L AO'}, '[as | if] {term} [law]',
               {'dollos','rounded'}, .24),
}


def target(tokens):
    if tokens[:2] == ['pithecanthropus','erectus']:
        return 'pithecanthropus'
    if 'isabela' in tokens:
        return 'isabela'
    if tokens[-2:] == ['clemmonss','interest']:
        return 'clemmonss'
    if any(tokens[i:i+2] == ['dollos','law'] for i in range(len(tokens)-1)):
        return 'dollos'
    return None


def pause_outside_name(expected, before, after, start, end, result):
    key, proof = result
    index = expected.index(proof['name'])
    joined = before + after
    if not before or not after or len(joined) != len(expected):
        return False
    joined[index] = MEASURED_NAMES[key].get(joined[index], joined[index])
    if not same_words(expected, joined):
        return False
    observations = proof['readings']
    if len(before) <= index:
        return end <= min(round(row['start']*RATE) for row in observations)
    return start >= max(round(row['end']*RATE) for row in observations)


@lru_cache(maxsize=8)
def decoder(name, context):
    forms, neighbours, rule, _, _ = CONTEXT[name]
    return grammar_decoder(forms, neighbours if context else {}, rule if context else '{term}')


def verify(audio, name, expected, first, second):
    index = expected.index(name)
    key = name + '_reading'
    spellings = MEASURED_NAMES[key]
    timed = timed_words(audio)
    for tokens in (words(first), words(second), [w for w,_ in timed]):
        if (len(tokens) != len(expected) or spellings.get(tokens[index],tokens[index]) != name
                or not same_words(expected, tokens[:index] + [name] + tokens[index+1:])):
            raise ValueError(f'The name or its surrounding words differ: {first!r} / {second!r}')
    start = max(0,timed[index][1] - round(.04*RATE))
    stop = timed[index+1][1] if index+1 < len(timed) else len(audio)
    if name == 'pithecanthropus':
        windows = [(0,timed[2][1] + round(.14*RATE),True),(0,stop,False)]
    elif name == 'isabela':
        windows = [(max(0,start-round(.04*RATE)),stop,False),(start,stop+round(.05*RATE),False)]
    else:
        lead = max(0,timed[index-1][1]-round(.08*RATE)) if index else 0
        tail = timed[index+2][1] if index+2 < len(timed) else len(audio)
        windows = [(lead,tail,True),(start,stop,False)]
    forms, _, _, permitted, min_seconds = CONTEXT[name]
    gaps = interior_gaps(audio)
    proof = []
    for begin,end,with_context in windows:
        label, score, left, right = locate_sound(audio[begin:end], decoder(name,with_context), forms)
        if (label not in permitted or score < .16 or right-left < min_seconds*RATE
                or any(begin+left < (a+b)/2 < begin+right for a,b in gaps)):
            raise ValueError(f'Incomplete or different pronunciation of {name}: {forms[label]}')
        proof.append(dict(phones=forms[label],confidence=round(score,3),start=(begin+left)/RATE,end=(begin+right)/RATE))
    return key, dict(name=name, readings=proof)
