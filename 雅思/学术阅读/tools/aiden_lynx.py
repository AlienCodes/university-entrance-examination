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
    # EH + W IH N and EH W + IH N describe the same sound. Duplicate
    # dictionary entries would split its acoustic posterior between homophones.
    unique = dict.fromkeys(' '.join(part for part in row if part)
                           for row in product(starts,vowels,endings))
    forms = {f'variant-{i}':phones for i,phones in enumerate(unique)}
    context = {'a':'AH','called':'K AO L D','mysterious':'M IH S T IH R IY AH S','were':'W ER','in':'IH N'}
    return grammar_decoder(forms,context,'[called] [a | mysterious] {term} [were] [in]'),forms


@lru_cache(maxsize=1)
def onset_contrasts():
    readings = ('TH L EH W IH N','TH L EH W AH N','HH L EH W IH N','HH L EH W AH N',
                'S L EH W IH N','SH L EH W IH N','TH L EY W IH N','L EH W AH N','L OW AH N',
                'OW W EH N','L OW W EH N','L EH W IH N','L EY W IH N','L UW IH N','L IH W IH N',
                'L EH W IH NG','L IY W IH N','TH L EH W IH','S EH W IH N','TH L EH IH N',
                'L EH W EH N','V AE N','W EH N')
    forms = {f'sound-{i}':p for i,p in enumerate(readings)}
    context = {'a':'AH','called':'K AO L D','mysterious':'M IH S T IH R IY AH S','were':'W ER','in':'IH N'}
    return grammar_decoder(forms,context,'[called] [a | mysterious] {term} [were] [in]'),forms


def inspect_word(audio):
    acoustic, forms = decoder()
    key, score, begin, end = locate_sound(audio,acoustic,forms)
    phones = forms[key].split()
    if (phones[:2] not in (['TH','L'],['HH','L'],['SH','L'],['S','L']) or
            phones[2:] not in (['EH','W','IH','N'],['EH','W','AH','N']) or
            not .30*RATE <= end-begin <= 1.4*RATE):
        raise ValueError(f'The fricated Welsh ll or the two syllables of llewyn are unclear: {forms[key]}')
    if score < .07:
        # In running speech the broader search can put little probability on
        # any one word. A focused comparison must return the same phones and
        # the same stretch of audio before the physical onset check below.
        contrast, targets = onset_contrasts()
        alternative, probability, onset, finish = locate_sound(audio,contrast,targets)
        if (targets[alternative] != forms[key] or probability < .18
                or max(abs(onset-begin),abs(finish-end)) > .04*RATE):
            raise ValueError('Two acoustic comparisons do not agree on the complete Welsh name')
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


@lru_cache(maxsize=1)
def and_decoder():
    forms = {'and':'AE N D','weak-and':'AH N D','reduced-and':'AH N','unreleased':'AE N',
             'syllabic':'N','in':'IH N','end':'EH N D','en':'EH N','and-in':'AE N D IH N',
             'ind':'IH N D','on':'AA N','at':'AE T','add':'AE D','uh':'AH'}
    context = {'one':'W AH N','the':'DH AH','same':'S EY M'}
    return grammar_decoder(forms,context,'[one] {term} the [same]'),forms


def verify(audio, expected, first, second):
    position = expected.index('llewyn')
    before, after = expected[:position], expected[position+1:]
    def has_context(heard, prefix):
        end = len(heard)-len(after)
        return (heard[:len(prefix)] == prefix and heard[end:] == after
                and 1 <= end-len(prefix) <= 3)
    reads = [words(first), words(second)]
    timed = timed_words(audio)
    names = [s for s,_ in timed]
    conjunction = None
    if expected[-5:] == ['one','and','the','same','animal']:
        for tokens in reads:
            # Links and lynx are homophones. The printed noun is between
            # “the” and “and the mysterious” in this particular sentence.
            for i in range(1,len(tokens)-3):
                if tokens[i-1:i+4] == ['the','links','and','the','mysterious']:
                    tokens[i] = 'lynx'
        alternate_ending = ['one','in','the','same','animal']
        if (any(t[-5:] == expected[-5:] for t in reads)
                and any(t[-5:] == alternate_ending for t in reads)
                and names[-5:] in (expected[-5:],alternate_ending)):
            start, stop = max(0,timed[-5][1]-600), timed[-1][1]
            acoustic, forms = and_decoder()
            key, score, onset, offset = locate_sound(audio[start:stop],acoustic,forms)
            if key in {'and','weak-and','reduced-and','unreleased'} and score >= .15 and offset-onset >= .035*RATE:
                conjunction = dict(phones=forms[key],start=(start+onset)/RATE,end=(start+offset)/RATE)
                for tokens in reads:
                    if tokens[-5:] == alternate_ending:
                        tokens[-4] = 'and'
    if not any(has_context(heard,before) for heard in reads):
        raise ValueError('Neither reading preserves every word around llewyn')
    if any(not has_context(heard,before) and
           not (before[-2:] == ['called','a'] and has_context(heard,before[:-1])) for heard in reads):
        raise ValueError('The words surrounding llewyn differ from the paper')
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
    result = dict(phones=phones,confidence=round(score,3),start=(lo+begin)/RATE,end=(lo+end)/RATE,
                  onset_friction_windows=friction)
    if conjunction:
        result['one_and_the_same'] = conjunction
    return result


def pause_after_name(audio, start, end, expected, left, right, whole):
    index = expected.index('llewyn')
    if (expected[index-1:index+3] != ['mysterious','llewyn','were','in']
            or right != expected[index+1:] or left[:index] != expected[:index]
            or not 1 <= len(left)-index <= 3 or not 0 <= start/RATE-whole['end'] <= .12):
        return False
    # Verify the complete word again on the left side of the pause. In
    # particular, the final n must already be present before "were" begins.
    left_audio = audio[:(start+end)//2]
    times = timed_words(left_audio)
    marker = next((sample for token,sample in times if token == 'mysterious'), None)
    if marker is None:
        return False
    offset = max(0,marker-1200)
    phones, _, begin, finish, _ = inspect_word(left_audio[offset:])
    return (phones == whole['phones'] and abs((offset+begin)/RATE-whole['start']) <= .04
            and abs((offset+finish)/RATE-whole['end']) <= .04 and offset+finish <= start)
