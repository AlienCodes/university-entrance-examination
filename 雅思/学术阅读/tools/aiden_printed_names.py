"""Verify the syllables of disputed names and terms in their printed context."""
from functools import lru_cache

from aiden_boundaries import RATE, independent, interior_gaps, isolated, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound
from aiden_surnames import forms
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
    'tolo':'T OW L OW Z', 'tonlo':'T AA N L OW Z', 'donlo':'D AA N L OW Z', 'talo':'T AA L OW Z',
    'dullo':'D AH L OW Z', 'donlows':'D OW N L OW Z',
}
GHARIB = {
    'full':'G AH R IY B', 'ae':'G AE R IY B', 'eh':'G EH R IY B', 'short-i':'G AH R IH B',
    'lost-onset':'AH R IY B', 'unvoiced-g':'K AH R IY B', 'lost-b':'G AH R IY',
    'unvoiced-b':'G AH R IY P', 'lost-first-syllable':'R IY B', 'cluster':'G R IY B',
    'lost-ree':'G AH B', 'garban':'G AA R B AH N', 'grab':'G R AE B',
}
EXISTENT = forms(('IH G Z','EH G Z','IH K S','EH K S','G Z'),
                 ('IH S T','IH S','EH S T'), ('AH N T','N T','AH N','IH N','IH NG','AH N S',''))
HAULIERS = forms(('HH',''), ('AO','AA','AE','AH'), ('L IY ER','L Y ER','L IY AH','L IH ER','L ER','L Y','L IY'), ('Z','S',''))
TOELESS = forms(('T','D',''), ('OW','AO','UW','AA'),
                ('L AH S','L IH S','L IH Z','L S','L IH','L AY S','L AH','L IY S','D L AH S',''))
AUTOGANZFELD = forms(('AO T OW','AA T OW','AO T AH','AO T','OW T OW','AE T OW',''),
                     ('G AE N Z','G AA N Z','G AE N S','G AA N S','G AE N T S','G AA N T S','G EY N Z','JH EH N Z','G AE N',''),
                     ('F EH L D','F EH L T','F IY L D','F EH L','F EH D',''))
AUTOGANZFELD = {label: sound for label, sound in AUTOGANZFELD.items() if sound}
CINEMA_PHRASE = ('the','lumiere','brothers','opened','their','cinematographe')
CINEMA_READINGS = forms(('S IH N AH','S IH N IH'), ('M AE T AH','M AE D AH'), ('G R AE F','G R AA F'))
# Compete the English forms heard in the dictionaries against changes to the
# initial syllables, stressed vowel and final consonants, and against related words.
CINEMA = {
    **CINEMA_READINGS,
    'long-i':'S IH N IY M AE T AH G R AE F', 'lost-vowel':'S IH N M AE T AH G R AE F',
    'sine':'S AY N AH M AE T AH G R AE F', 'sen':'S EH N AH M AE T AH G R AE F',
    'sh':'SH IH N AH M AE T AH G R AE F', 'no-s':'IH N AH M AE T AH G R AE F',
    'weak-first':'S AH N AH M AE T AH G R AE F',
    'maht':'S IH N AH M AA T AH G R AE F', 'maht-uk':'S IH N AH M AA T AH G R AA F',
    'mayt':'S IH N AH M EY T AH G R AE F', 'weak-stress':'S IH N AH M AH T AH G R AE F',
    'missing-t':'S IH N AH M AE AH G R AE F', 'short-middle':'S IH N AH M AE T G R AE F',
    'no-middle':'S IH N AH G R AE F', 'weak-final':'S IH N AH M AE T AH G R AH F',
    'no-f':'S IH N AH M AE T AH G R AE', 'no-f-uk':'S IH N AH M AE T AH G R AA',
    'no-g':'S IH N AH M AE T AH R AE F', 'grayf':'S IH N AH M AE T AH G R EY F',
    'grass':'S IH N AH M AE T AH G R AE S', 'cinema':'S IH N AH M AH',
    'short':'S IH N AH M AE T AH', 'grapher':'S IH N AH M AE T AH G R AE F ER',
    'graphy':'S IH N AH M AE T AH G R AE F IY', 'graphic':'S IH N AH M AE T AH G R AE F IH K',
}

CONTEXT = {
    'cinematographe': (CINEMA, {'their':'DH EH R'}, '[their] {term}',
                       set(CINEMA_READINGS), .57),
    'pithecanthropus': (FOSSIL, {'erectus':'IH R EH K T AH S','is':'IH Z'}, '{term} [erectus] [is]',
                        {'full','schwa','stop','schwa-stop','reduced'}, .5),
    'isabela': (ISLAND, {}, '{term}', {'english','unvoiced','long','spanish','spanish-reduced'}, .33),
    'clemmonss': (CLEMMONS, {'sparked':'S P AA R K T','interest':'IH N T R AH S T',
                             'put':'P UH T','unlikely':'AH N L AY K L IY'},
                  '[sparked | put] {term} [interest | unlikely]', {'full','full-alt','schwa'}, .38),
    'dollos': (DOLLO, {'as':'AE Z','if':'IH F','law':'L AO'}, '[as | if] {term} [law]',
               {'dollos','rounded'}, .24),
    'gharib': (GHARIB, {'and':'AE N D','shortand':'AH N','graff':'G R AE F','set':'S EH T'},
               '{term} [and | shortand] [graff] [set]', {'full','ae','eh'}, .25),
    'existent': (EXISTENT, {'the':'DH AH','thee':'DH IY','organisms':'AO R G AH N IH Z AH M Z'},
                 '[the | thee] {term} [organisms]',
                 {key for key,sound in EXISTENT.items() if sound in
                  {'IH G Z IH S T AH N T','EH G Z IH S T AH N T','IH G Z IH S T N T','EH G Z IH S T N T'}}, .30),
    'hauliers': (HAULIERS, {'road':'R OW D','and':'AE N D','weakand':'AH N D'},
                 '[road] {term} [and | weakand]',
                 {key for key, sound in HAULIERS.items() if sound.startswith(('HH AA L','HH AO L'))
                  and sound.endswith(('L IY ER Z','L Y ER Z','L IY AH Z'))}, .28),
    'toeless': (TOELESS, {'from':'F R AH M','ancestors':'AE N S EH S T ER Z'},
                '[from] {term} [ancestors]',
                {key for key,sound in TOELESS.items() if sound in {'T OW L AH S','T OW L IH S'}}, .24),
    'autoganzfeld': (AUTOGANZFELD, {'to':'T UW','weakto':'T AH','of':'AH V','in':'IH N','tests':'T EH S T S','trials':'T R AY AH L Z'},
                     '[to | weakto | of | in] {term} [tests | trials]',
                     {key for key,sound in AUTOGANZFELD.items()
                      if sound.startswith(('AO T OW G','AA T OW G')) and sound.endswith(('F EH L D','F EH L T'))
                      and any(mid in sound for mid in ('G AE N Z F','G AA N Z F','G AE N S F','G AA N S F','G AE N T S F','G AA N T S F'))}, .56),
}


def target(tokens):
    if tuple(tokens) == CINEMA_PHRASE:
        return 'cinematographe'
    if tokens[:2] == ['pithecanthropus','erectus']:
        return 'pithecanthropus'
    if 'isabela' in tokens:
        return 'isabela'
    if tokens[-2:] == ['clemmonss','interest'] or tokens[:5] == ['the','team','put','clemmonss','unlikely']:
        return 'clemmonss'
    if tokens[:2] == ['the','existent']:
        return 'existent'
    if tokens[-4:] == ['road','hauliers','and','railways']:
        return 'hauliers'
    if 'toeless' in tokens and tokens[:3] == ['the','toed','species']:
        return 'toeless'
    if 'autoganzfeld' in tokens:
        return 'autoganzfeld'
    if (tokens[:4] == ['gharib','and','graff','set'] or tokens[-2:] in
            (['gharib','says'], ['says','gharib'], ['gharib','realized'])):
        return 'gharib'
    if any(tokens[i:i+2] == ['dollos','law'] for i in range(len(tokens)-1)):
        return 'dollos'
    return None


def join_compound(parts):
    joined = []
    for word, time in parts:
        if joined and joined[-1][0] in ('auto','otto') and word in ('ganzfeld','gansfeld','gensfeld'):
            prefix, onset = joined[-1]
            joined[-1] = (prefix+word, onset)
        else:
            joined.append((word, time))
    return joined


def compound_words(tokens):
    return [word for word,_ in join_compound((token,0) for token in tokens)]


def recognized_spellings(key):
    if key == 'cinematographe_reading':
        return {'cinematograph':'cinematographe'}
    return MEASURED_NAMES[key]


def confirmed_cinema_ending(item, expected):
    if tuple(expected) != CINEMA_PHRASE:
        return False
    proof = item.get('cinematographe_reading', {})
    readings = proof.get('readings', [])
    return (proof.get('name') == 'cinematographe' and len(readings) == 2
            and all(row['phones'] in CINEMA_READINGS.values() and row['confidence'] >= .16
                    and row['end'] - row['start'] >= .57 for row in readings))


def pause_outside_name(expected, before, after, start, end, result, audio=None):
    key, proof = result
    index = expected.index(proof['name'])
    if proof['name'] == 'autoganzfeld':
        before, after = compound_words(before), compound_words(after)
    joined = before + after
    if not before or not after or len(joined) != len(expected):
        return False
    joined[index] = recognized_spellings(key).get(joined[index], joined[index])
    if not same_words(expected, joined):
        return False
    observations = proof['readings']
    on_right = len(before) <= index
    if on_right and end <= min(round(row['start']*RATE) for row in observations):
        return True
    if not on_right and start >= max(round(row['end']*RATE) for row in observations):
        return True
    if proof['name'] != 'gharib' or audio is None or len(before) not in (index,index+1):
        return False
    # Low-energy bins can include a soft stop onset. Keep its end of the gap,
    # as complete_words_at_gap does, without crossing the middle of the gap.
    margin = min((end-start)//2, round(.08*RATE))
    side, printed = (audio[end-margin:], expected[index:]) if on_right else (audio[:start+margin],expected[:index+1])
    try:
        verify(side,'gharib',printed,isolated(side),independent(side))
    except ValueError:
        return False
    return True


@lru_cache(maxsize=24)
def decoder(name, context, attribution=False):
    forms, neighbours, rule, _, _ = CONTEXT[name]
    if name == 'gharib' and context and attribution:
        neighbours = {'says':'S EH Z','stunned':'S T AH N D','force':'F AO R S','matter':'M AE T ER',
                      'method':'M EH TH AH D','realised':'R IY AH L AY Z D'}
        rule = '[stunned | force | matter | method | says] {term} [says | realised]'
    return grammar_decoder(forms, neighbours if context else {}, rule if context else '{term}')


def verify(audio, name, expected, first, second):
    index = expected.index(name)
    key = name + '_reading'
    spellings = recognized_spellings(key)
    timed = timed_words(audio)
    readings = [words(first), words(second)]
    if name == 'existent' and not any(name in tokens for tokens in readings):
        raise ValueError('Neither independent full-phrase reading identified existent')
    if name == 'autoganzfeld':
        timed = join_compound(timed)
        readings = [compound_words(tokens) for tokens in readings]
    for tokens in (*readings, [w for w,_ in timed]):
        if (len(tokens) != len(expected) or spellings.get(tokens[index],tokens[index]) != name
                or not same_words(expected, tokens[:index] + [name] + tokens[index+1:])):
            raise ValueError(f'The name or its surrounding words differ: {first!r} / {second!r}')
    start = max(0,timed[index][1] - round(.04*RATE))
    stop = timed[index+1][1] if index+1 < len(timed) else len(audio)
    gharib_intro = name == 'gharib' and expected[:4] == ['gharib','and','graff','set']
    if name == 'cinematographe':
        windows = [(max(0,timed[index-1][1]-400),len(audio),True),(max(0,start-400),len(audio),False)]
    elif name == 'pithecanthropus':
        windows = [(0,timed[2][1] + round(.14*RATE),True),(0,stop,False)]
    elif name == 'isabela':
        windows = [(max(0,start-round(.04*RATE)),stop,False),(start,stop+round(.05*RATE),False)]
    elif gharib_intro:
        windows = [(0,timed[3][1]+round(.05*RATE),True),(0,stop+round(.01*RATE),False)]
    elif name in ('autoganzfeld','existent','toeless','hauliers'):
        lead = max(0,timed[index-1][1]-round(.04*RATE)) if index else 0
        tail = timed[index+2][1] if index+2 < len(timed) else len(audio)
        windows = [(lead,tail,True),(max(0,start-round(.02*RATE)),min(len(audio),stop+round(.02*RATE)),False)]
    else:
        lead = max(0,timed[index-1][1]-round(.08*RATE)) if index else 0
        tail = timed[index+2][1] if index+2 < len(timed) else len(audio)
        windows = [(lead,tail,True),(start,stop,False)]
    forms, _, _, permitted, min_seconds = CONTEXT[name]
    gaps = interior_gaps(audio)
    proof = []
    for begin,end,with_context in windows:
        model = decoder(name,with_context,name == 'gharib' and not gharib_intro)
        label, score, left, right = locate_sound(audio[begin:end], model, forms)
        if (label not in permitted or score < .16 or right-left < min_seconds*RATE
                or any(begin+left < (a+b)/2 < begin+right for a,b in gaps)):
            raise ValueError(f'Incomplete or different pronunciation of {name}: {forms[label]}')
        proof.append(dict(phones=forms[label],confidence=round(score,3),start=(begin+left)/RATE,end=(begin+right)/RATE))
    return key, dict(name=name, readings=proof)
