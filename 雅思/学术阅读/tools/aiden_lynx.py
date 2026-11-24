"""Check the Welsh name in the lynx passage against the recorded Welsh ll and final syllable."""
from functools import lru_cache
from itertools import product

import numpy as np

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


@lru_cache(maxsize=1)
def decoder():
    # The English phone model has no /ɬ/. Compare a fricated lateral with a
    # plain l, sibilants, Owen, and readings that lose the last vowel or n.
    starts = ('L','HH L','SH','S','HH','S L','TH L','SH L','L HH','K L','F L','')
    vowels = ('EH','EH W','EY','IH','IY','AW','OW','UW','AO','AH')
    endings = ('W IH N','W EH N','W AH N','IH N','AH N','IY N','IY NG','IH NG','N','')
    forms = {f'variant-{i}':' '.join(part for part in row if part)
             for i,row in enumerate(product(starts,vowels,endings))}
    context = {'a':'AH','called':'K AO L D','mysterious':'M IH S T IH R IY AH S','were':'W ER','in':'IH N'}
    return grammar_decoder(forms,context,'[called] [a | mysterious] {term} [were] [in]'),forms


def inspect_word(audio):
    acoustic, forms = decoder()
    key, score, begin, end = locate_sound(audio,acoustic,forms)
    phones = forms[key].split()
    if (phones[:2] not in (['TH','L'],['HH','L'],['SH','L'],['S','L']) or
            phones[2:] not in (['EH','W','IH','N'],['EH','W','AH','N']) or
            score < .07 or not .30*RATE <= end-begin <= 1.4*RATE):
        raise ValueError(f'The fricated Welsh ll or the two syllables of llewyn are unclear: {forms[key]}')
    frames = np.lib.stride_tricks.sliding_window_view(audio[begin:end],320)[::160]
    rms = np.sqrt(np.mean(frames**2,axis=1))
    opening = frames[:32]
    energy = np.abs(np.fft.rfft(opening*np.hanning(320),axis=1))**2
    high = energy[:,36:].sum(axis=1)/(energy.sum(axis=1)+1e-15)
    periodic = np.array([np.correlate(f,f,'full')[319+35:319+149].max() /
                         max(1e-12,float(np.dot(f,f))) for f in opening])
    friction = (rms[:len(opening)] > rms.max()*.003) & (high > .17) & (periodic < .48)
    if not np.any(friction[:-2] & friction[1:-1] & friction[2:]):
        raise ValueError('The Welsh onset has no sustained unvoiced friction')
    if any(begin < (a+b)/2 < end for a,b in interior_gaps(audio)):
        raise ValueError('A pause interrupts the Welsh name')
    return forms[key], score, begin, end, int(friction.sum())


def verify(audio, expected, first, second):
    position = expected.index('llewyn')
    before, after = expected[:position], expected[position+1:]
    def has_context(heard, prefix):
        end = len(heard)-len(after)
        return (heard[:len(prefix)] == prefix and heard[end:] == after
                and 1 <= end-len(prefix) <= 3)
    reads = [words(first), words(second)]
    if not any(has_context(heard,before) for heard in reads):
        raise ValueError('Neither reading preserves every word around llewyn')
    if any(not has_context(heard,before) and
           not (before[-2:] == ['called','a'] and has_context(heard,before[:-1])) for heard in reads):
        raise ValueError('The words surrounding llewyn differ from the paper')
    timed = timed_words(audio)
    names = [s for s,_ in timed]
    if before[-2:] == ['called','a'] and not after and 'called' in names:
        marker = names.index('called')
        if names[marker+1:marker+2] == ['a']:
            marker += 1
        lo, hi = max(0,timed[marker][1]-1200), len(audio)
    elif before[-1:] == ['mysterious'] and after[:2] == ['were','in'] and 'mysterious' in names and 'were' in names:
        marker = names.index('mysterious')
        following = names.index('were',marker+1)
        lo, hi = max(0,timed[marker][1]-1200), min(len(audio),timed[following][1]+round(.38*RATE))
    else:
        raise ValueError('Cannot locate the Welsh name in its printed phrase')
    phones,score,begin,end,friction = inspect_word(audio[lo:hi])
    return dict(phones=phones,confidence=round(score,3),start=(lo+begin)/RATE,end=(lo+end)/RATE,
                onset_friction_windows=friction)
