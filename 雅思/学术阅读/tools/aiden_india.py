"""Check the archaic name for India at the end of Mandeville's quotation."""
from functools import lru_cache

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound

# Dictionaries of the Scots Language records the historical spelling Ynde under
# Ind. Merriam-Webster's American noun Ind has single-syllable /ɪnd/ and /aɪnd/.
RENDERINGS = ('Ynde', 'Ind', 'Eynd', 'Ind', 'Eynd')
HINT = ('Read the traveller’s surname Mandeville as MAN-duh-vill, with the short i '
        'of village. At the end of the quotation, read the old name for India in one '
        'syllable, rhyming with kind. End with nd and no vowel after the d.')
PHONES = {
    'short-ind': 'IH N D', 'long-ind': 'AY N D',
    'in-day': 'IH N D EY', 'in-dee': 'IH N D IY', 'ind-uh': 'IH N D AH',
    'ind-eye': 'IH N D AY', 'india': 'IH N D IY AH', 'inn': 'IH N',
    'ine': 'AY N', 'end': 'EH N D', 'and': 'AE N D', 'find': 'F AY N D',
    'hind': 'HH AY N D', 'kind': 'K AY N D', 'wind': 'W AY N D',
}
CONTEXT = {'notes': 'N OW T S', 'of': 'AH V'}
TRANSCRIPT_ENDINGS = {'ind','inde','ynde','ined','eynd','in','end','and','find','in day'}

@lru_cache(maxsize=1)
def decoder():
    return grammar_decoder(PHONES, CONTEXT, '[notes] of {term}')


def verify(audio, text, first, second):
    prefix = words(text)[:-1]
    if prefix[-2:] != ['notes', 'of']:
        raise ValueError('Unrecognised context for the place name Ynde')
    endings = []
    for result in (first, second):
        heard = words(result)
        ending = ' '.join(heard[len(prefix):])
        if heard[:len(prefix)] != prefix or (ending and ending not in TRANSCRIPT_ENDINGS):
            raise ValueError(f'The context or the place name in the quotation differs: {result!r}')
        endings.append(ending)
    if not any(endings):
        raise ValueError('Neither reader heard a place name after Notes of')
    times = timed_words(audio)
    notes = [i for w, i in times if w == 'notes']
    if len(notes) != 1:
        raise ValueError('Cannot locate the end of the quotation')
    offset = max(0, notes[0] - round(.12 * RATE))
    key, score, begin, stop = locate_sound(audio[offset:], decoder(), PHONES)
    begin += offset
    stop += offset
    if (key not in ('short-ind', 'long-ind') or score < .16
            or not .16 * RATE <= stop - begin <= .76 * RATE
            or any(begin < (a + b) / 2 < stop for a,b in interior_gaps(audio))):
        raise ValueError(f'The name Ynde must end with one full syllable: {PHONES[key]}')
    return dict(phones=PHONES[key], confidence=round(score, 3),
                start=round(begin/RATE, 3), end=round(stop/RATE, 3))
