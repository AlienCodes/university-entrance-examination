"""Pronunciation targets for names in the geography, education and language passages."""
from functools import lru_cache

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound

READINGS = {
    'Monbusho': (
        ('Monbusho','Mohn-boo-shoh','Mombushō','mohn-boo-shoh','Monbushō'),
        'Read the former Japanese ministry Monbushō as one name: mo-n-bu-shō. '
        'Round the opening o, keep the light bu syllable, and lengthen the final shō.'),
    'Aleyska': (
        ('Aleyska','Alyeska','al-ee-ES-kah','Alyeska','al-ee-ES-kuh'),
        'The historical name here is Alyeska. Link al-ee-ES-kah in one word, with the stressed short e of yes.'),
    'Makete': (
        ('Makete','mah-KEH-teh','Ma-ke-te','mah-KEH-teh','Makete'),
        'Read the Tanzanian district of Makete in three connected Swahili syllables: mah-KEH-teh. '
        'Both written e vowels are sounded.'),
    'Na-Dene': (
        ('Na-Dene','Nah-day-nee','Na-Dené','nah-DAY-nee','nah-day-NAY'),
        'Na-Dene is the language-family name. Read the three connected syllables nah-DAY-nee, '
        'with DAY in the middle and the final vowel audible before hunters.'),
}

JAPANESE = {
    'mon':'M OW N B UW SH OW','mon-back':'M AO N B UW SH OW','mom':'M OW M B UW SH OW',
    'mom-back':'M AO M B UW SH OW','mon-u':'M OW N B UH SH OW','mon-u-back':'M AO N B UH SH OW',
    'rounded':'M UW N B UW SH OW','missing-bu-vowel':'M AO N B SH OW','man':'M AE N B UW SH OW',
    'mam':'M AE M B UW SH OW','mah':'M AA N B UW SH OW','mun':'M AH N B UW SH OW',
    'mim':'M IH M B UW SH OW','so':'M AO N B UW S OW','missing-sho':'M AO N B UW',
    'missing-bu':'M AO N SH OW','shu':'M AO N B UW SH UW',
}
JAPANESE_OK = {'mon','mon-back','mom','mom-back','mon-u','mon-u-back','rounded'}
ALASKAN = {
    'al-ee-es-ka':'AE L IY EH S K AH','al-ee-es-ka-light':'AH L IY EH S K AH',
    'al-ih-es-ka':'AE L IH EH S K AH','al-yes-ka':'AE L Y EH S K AH',
    'uh-lee-yess-ka':'AH L IY Y EH S K AH','al-ee-yess-ka':'AE L IY Y EH S K AH',
    'alaska':'AH L AE S K AH','alaska-dark':'AH L AA S K AH','olaska':'AO L AE S K AH',
    'aleeska':'AH L IY S K AH','a-lis-ka':'AH L IH S K AH','without-ka':'AE L IY EH S',
    'without-es':'AE L IY K AH','without-s':'AE L IY EH K AH',
}
ALASKAN_OK = {'al-ee-es-ka','al-ee-es-ka-light','al-ih-es-ka','al-yes-ka','uh-lee-yess-ka','al-ee-yess-ka'}

NA_DENE = {
    'na-day-nee':'N AA D EY N IY', 'na-day-nay':'N AA D EY N EY',
    'na-den-ee':'N AA D EH N IY', 'na-den-ay':'N AA D EH N EY',
    'nah-dee-n':'N AA D IY N', 'nadine':'N AH D IY N', 'naydeen':'N EY D IY N',
    'no-final-vowel':'N AA D EY N', 'not-n':'N AA D EY', 'weak':'N AH D AH N', 'no-first':'D EY N IY',
    'denay':'D EY N EY', 'n-dee':'N D IY', 'none':'N AH',
}


@lru_cache(maxsize=5)
def decoder(context):
    if context == 'hunters':
        return grammar_decoder(NA_DENE, {'brought':'B R AO T', 'hunters':'HH AH N T ER Z'},
                               'brought {term} hunters')
    if context == 'aleut-name':
        return grammar_decoder(ALASKAN, {}, '{term}')
    if context == 'mass':
        return grammar_decoder(ALASKAN, {'mass':'M AE S','land':'L AE N D'}, '[land] [mass] {term}')
    if context == 'as':
        return grammar_decoder(JAPANESE, {'as':'AE Z','uz':'AH Z','part':'P AA R T'}, '{term} [as | uz] [part]')
    return grammar_decoder(JAPANESE, {'also':'AO L S OW','decides':'D IH S AY D Z'}, '{term} [also] [decides]')


def verify_na_dene(audio, first, second):
    for transcript in (first, second):
        heard = words(transcript)
        if not (3 <= len(heard) <= 5 and heard[0] == 'brought' and heard[-1] == 'hunters'):
            raise ValueError('The words around Na-Dene differ from the passage')
    key, confidence, begin, end = locate_sound(audio, decoder('hunters'), NA_DENE)
    if (key not in ('na-day-nee', 'na-day-nay') or confidence < .30
            or end-begin < .30*RATE or any(begin < (a+b)/2 < end for a,b in interior_gaps(audio))):
        raise ValueError(f'Incomplete three-syllable reading of Na-Dene: {NA_DENE[key]}')
    return dict(name='Na-Dene', phones=NA_DENE[key], confidence=round(confidence,3),
                start=round(begin/RATE,3), end=round(end/RATE,3))


def verify(audio, expected, first, second):
    japan = expected[0]=='monbusho'
    index = 0 if japan else len(expected)-1
    def unchanged_context(hypothesis):
        count = len(hypothesis) - len(expected) + 1
        return (1 <= count <= 3 and hypothesis[:index] == expected[:index]
                and hypothesis[index+count:] == expected[index+1:])
    heard = [words(first),words(second)]
    surrounding = expected[:index]+expected[index+1:]
    # A recognizer may omit a non-English name. One must retain the name, both
    # must retain every surrounding word, and the acoustic tests must find it.
    if (not any(unchanged_context(tokens) for tokens in heard)
            or any(tokens != surrounding and not unchanged_context(tokens) for tokens in heard)):
        raise ValueError(f'The words surrounding {expected[index]} differ from the source')
    timed = timed_words(audio)
    if not unchanged_context([w for w,t in timed]):
        raise ValueError(f'Cannot locate {expected[index]} in the recording')
    if japan:
        context = expected[1]
        count = len(timed) - len(expected) + 1
        if context not in ('as','also'):
            raise ValueError('Unrecognised Monbusho context')
        lo, hi = 0, min(len(audio),timed[count+1][1]+round(.30*RATE))
        forms, permitted = JAPANESE, JAPANESE_OK
    else:
        context = 'mass'
        lo, hi = max(0,timed[index-1][1] - round(.0625*RATE)), len(audio)
        forms, permitted = ALASKAN, ALASKAN_OK
    key, confidence, begin, finish = locate_sound(audio[lo:hi], decoder(context), forms)
    begin, finish = lo+begin, lo+finish
    if not japan:
        # The context decoder can supply a missing stressed vowel after "mass",
        # or stop early after "yes". Check the name separately up to its actual end.
        isolated_start = max(0, timed[index][1] - round(.14*RATE))
        isolated_key, isolated_score, start, end = locate_sound(audio[isolated_start:], decoder('aleut-name'), forms)
        if isolated_key not in permitted or isolated_score < .20:
            raise ValueError(f'Incomplete isolated pronunciation of Aleyska: {forms[isolated_key]}')
        if key == 'without-ka' and isolated_start + end - finish >= .12*RATE:
            key, confidence = isolated_key, isolated_score
            begin, finish = isolated_start + start, isolated_start + end
    if (key not in permitted or confidence < .15 or finish-begin < .40*RATE
            or any(begin < (a+b)/2 < finish for a,b in interior_gaps(audio))):
        raise ValueError(f'Incomplete or incorrect pronunciation of {expected[index]}: {forms[key]}')
    return dict(name=expected[index], phones=forms[key], confidence=round(confidence,3),
                start=round(begin/RATE,3), end=round(finish/RATE,3))
