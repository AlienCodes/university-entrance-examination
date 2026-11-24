"""Check the silent final s of Sèvres in the account of Marie Curie."""
from functools import lru_cache

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


READINGS = {
    'french':'S EH V R','us':'S EH V R AH','us-r':'S EH V ER','us-ruh':'S EH V ER AH',
    'saver':'S EY V ER','severus':'S EH V ER AH S','severiss':'S EH V ER IH S',
    'severahs':'S EH V R AH S','sev':'S EH V','sair':'S EH R','saverus':'S EY V ER AH S',
    'seevres':'S IY V ER AH','sivers':'S IH V ER Z','severs':'S EH V ER Z',
    'safe':'S EY F','sif':'S IH F',
}


@lru_cache(maxsize=1)
def decoder():
    return grammar_decoder(READINGS,{'in':'IH N'},'[in] {term}')


def verify(audio,expected,first,second):
    timing = timed_words(audio)
    if expected[-4:] != ['for','girls','in','sevres']:
        raise ValueError('Unknown context for Sèvres')
    marks = [sample for word,sample in timing if word == 'in']
    if not marks:
        raise ValueError('Missing preposition before Sèvres')
    offset = max(0,marks[-1]-500)
    key,score,start,end = locate_sound(audio[offset:],decoder(),READINGS)
    # The US dictionary recording has S EH V R AH. The written final s
    # must be silent even when a general recognizer prints “Sèvres”.
    if (key not in {'french','us','us-r','us-ruh'} or score < .20 or not .22*RATE <= end-start <= .92*RATE
            or any(start < (a+b)/2 < end for a,b in interior_gaps(audio[offset:]))):
        raise ValueError('Unclear Sèvres or an extra ending: '+READINGS[key])
    observed = [words(first),words(second)]
    if not all(t[:-1] == expected[:-1] and t[-1:] in
               (['sevres'],['sevre'],['sevra'],['sevrah'],['sever'],['sevruh'],['severa']) for t in observed):
        raise ValueError('The full school name or the sentence around Sèvres requires review')
    return dict(phones=READINGS[key],confidence=round(score,3),start=round((offset+start)/RATE,3),
                end=round((offset+end)/RATE,3))
