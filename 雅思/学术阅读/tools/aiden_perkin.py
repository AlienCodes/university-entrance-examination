"""Distinguish William Perkin from Perkins and verify both chemists' possessives."""
from functools import lru_cache
from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound
from aiden_surnames import forms


PERKIN = forms(('P ER','P AH','B ER'),('K IH N','K AH N','K IH','G IH N'),('','Z','S','Z IH Z','S IH Z','IH Z','T'))
HOFMANN = forms(('HH AA F','HH AO F','HH OW F','HH AH F','AA F','HH AA','HH AA V','HH AE F'),
                ('M AH N','M IH N','M AE N','M AH','M','N'),('Z','S','IH Z','Z IH Z',''))
PERKIN_READS = {'perkin','perkins','perkinss'}
HOFMANN_READS = {'hofmanns','hoffmanns','hofmans','hoffmans','hofmann','hoffman'}


@lru_cache(maxsize=5)
def decoder(following_word):
    if following_word == 'attention':
        return grammar_decoder(HOFMANN,{'caught':'K AO T','cot':'K AA T','attention':'AH T EH N SH AH N'},
                               '[caught | cot] {term} [attention]')
    context = {'set':'S EH T','spent':'S P EH N T','saw':'S AO','saw-us':'S AA','gifts':'G IH F T S',
               'scientific':'S AY AH N T IH F IH K','up':'AH P','the':'DH AH','his':'HH IH Z'}
    following = {'set':'[set] [up]', 'spent':'[spent] [his]', 'saw':'(saw | saw-us) the',
                 'scientific':'[scientific] [gifts]'}[following_word]
    return grammar_decoder(PERKIN,context,'{term} '+following)


def cited(expected):
    return (expected[:3] == ['perkins','scientific','gifts']
            or (expected[:1] == ['perkin'] and expected[1:2] in (['set'],['saw'],['spent'])))


def context(heard,expected):
    result = list(heard)
    if result and result[0] in PERKIN_READS:
        result[0] = expected[0]
    if 'hofmanns' in expected:
        i = expected.index('hofmanns')
        if i < len(result) and result[i] in HOFMANN_READS:
            result[i] = 'hofmanns'
    return result


def verify(audio,expected,first,second):
    stamps = timed_words(audio)
    for tokens in (words(first),words(second),[t for t,_ in stamps]):
        if context(tokens,expected) != expected:
            raise ValueError('The words around Perkin or Hofmann differ: '+' '.join(tokens))
    possessive = expected[0] == 'perkins'
    names = [('Perkin',0,PERKIN)]
    if possessive:
        names.append(('Hofmann',expected.index('hofmanns'),HOFMANN))
    proof = {}
    for name,i,grammar in names:
        lo = max(0,stamps[i][1]-round(.10*RATE))
        hi = min(len(audio),stamps[i+2][1]+round(.12*RATE))
        if expected[i+1:i+3] == ['saw','the'] and i+3 < len(stamps):
            # Include the complete article. Clipping the context during “the” can
            # assign the first s of saw to the surname under one resampler.
            hi = min(len(audio),stamps[i+3][1]+round(.10*RATE))
        key,score,start,end = locate_sound(audio[lo:hi],decoder(expected[i+1]),grammar)
        phones = grammar[key]
        if name=='Perkin':
            accepted = {'P ER K IH N','P ER K AH N'}
            if possessive:
                accepted = {form+' Z' for form in accepted}
        else:
            accepted = {'HH '+v+' F M '+weak+' N Z' for v in ('AO','AA','OW') for weak in ('AH','IH','AE')}
        if (phones not in accepted or score < .11 or not .20*RATE <= end-start <= 1.15*RATE
                or any(start < (a+b)/2 < end for a,b in interior_gaps(audio[lo:hi]))):
            raise ValueError('Unclear surname or possessive for '+name+': '+phones)
        proof[name] = dict(phones=phones,confidence=round(score,3),start=round((lo+start)/RATE,3),end=round((lo+end)/RATE,3))
    return proof


def gap_after_attention(start, expected, left, right, proof):
    if 'Hofmann' not in proof or start/RATE <= proof['Hofmann']['end'] or 'attention' not in expected:
        return False
    next_word = expected.index('attention')+1
    return context(left,expected)==expected[:next_word] and right==expected[next_word:]
