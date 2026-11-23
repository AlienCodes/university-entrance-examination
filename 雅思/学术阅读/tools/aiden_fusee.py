"""Check the second syllable of the clock term fusee in the timekeeping passage."""
from functools import lru_cache

import numpy as np

from aiden_boundaries import RATE, independent, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


PHONES = {
    'fusee': 'F Y UW Z IY', 'fuse': 'F Y UW Z', 'fussy': 'F AH S IY',
    'fuzzy': 'F AH Z IY', 'fusees': 'F Y UW Z IY Z', 'unvoiced-s': 'F Y UW S IY',
    'few': 'F Y UW', 'zee': 'Z IY', 'fusing': 'F Y UW Z IH NG', 'fused': 'F Y UW Z D',
    'foozie': 'F UW Z IY', 'fusillade': 'F Y UW S AH L EY D', 'confuse': 'K AH N F Y UW Z',
}


@lru_cache(maxsize=1)
def phone_recognizer():
    return grammar_decoder(PHONES, {'or':'AO R','which':'W IH CH'}, '[or] {term} [which]')


def vowel_after_z(word):
    """Measure a front vowel after the fricative, within the independently located word."""
    from scipy.linalg import solve_toeplitz
    from scipy.signal import lfilter

    window = np.hanning(400)
    frequencies = np.fft.rfftfreq(512, 1/RATE)
    high = (frequencies >= 3600) & (frequencies < 7900)
    middle = (frequencies >= 300) & (frequencies < 3000)
    level = max(1e-6, .10*np.max(np.abs(word)))
    after_z = None
    consecutive = 0
    longest = 0
    for offset in range(0, len(word) - len(window) + 1, 160):
        frame = word[offset:offset + len(window)].astype(float)
        power = np.abs(np.fft.rfft(frame*window, n=512))**2
        if offset >= .08*RATE and power[high].sum() > 2*power[middle].sum() and np.max(np.abs(frame)) >= level:
            after_z = offset
        if after_z is None or not 160 <= offset-after_z <= .35*RATE or np.max(np.abs(frame)) < level:
            consecutive = 0
            continue
        emphasized = lfilter([1., -.97], [1.], frame)*window
        ac = np.correlate(emphasized, emphasized, 'full')[len(frame)-1:]
        if ac[0] <= 1e-12:
            consecutive = 0
            continue
        try:
            roots = np.roots(np.r_[1., solve_toeplitz(ac[:17], -ac[1:18])])
        except np.linalg.LinAlgError:
            consecutive = 0
            continue
        roots = roots[(np.imag(roots)>0) & (np.abs(roots)>0)]
        freq = np.angle(roots)*RATE/(2*np.pi)
        width = -np.log(np.abs(roots))*RATE/np.pi
        formants = sorted(freq[(freq>180) & (freq<4250) & (width>0) & (width<500)])
        front = len(formants)>=2 and formants[0]<580 and 1650<=formants[1]<=3300
        consecutive = consecutive + 1 if front else 0
        longest = max(longest, consecutive)
    return 10*longest


def check_word(sample):
    word,score,start,stop = locate_sound(sample,phone_recognizer(),PHONES)
    if word!='fusee' or score<.40:
        raise ValueError(f'The clock term needs two syllables /fjuːˈziː/, heard {word}')
    if not .25*RATE<=stop-start<=1.25*RATE:
        raise ValueError('The acoustic interval for fusee has an implausible length')
    if any(start<(a+b)/2<stop for a,b in interior_gaps(sample)):
        raise ValueError('A pause interrupts a syllable of fusee')
    vowel_ms = vowel_after_z(sample[start:stop])
    if vowel_ms<70:
        raise ValueError(f'Missing a clear final /iː/ after /z/ in fusee ({vowel_ms} ms)')
    return start, stop, round(score,3), vowel_ms


def term_span(text, heard):
    first = text.index('fusee')
    # Parakeet and Whisper may transcribe the last compound as two complete words.
    def surroundings(tokens):
        return (' '+' '.join(tokens)+' ').replace(' main spring ', ' mainspring ').strip()
    for left in range(len(heard)):
        if surroundings(heard[:left])!=surroundings(text[:first]):
            continue
        for right in range(left+1, min(len(heard),left+3)+1):
            if (''.join(heard[left:right]) in {'fusee','fuzee','fuse','fuze','fusi','fewzee'}
                    and surroundings(heard[right:])==surroundings(text[first+1:])):
                return left,right
    raise ValueError('The spoken words surrounding fusee do not match the printed phrase')


def verify(audio, text, first, second):
    expected = words(text)
    if expected.count('fusee')!=1:
        raise ValueError('Expected one occurrence of fusee')
    term_span(expected, words(first))
    padding_ms = 0
    try:
        term_span(expected,words(second))
    except ValueError:
        # An isolated clip sometimes gets a bracketed noise caption from Whisper.
        # Require the complete printed context from a second decode of identical speech.
        for padding_ms in (100,220):
            zeros = round(padding_ms*RATE/1000)
            second = independent(np.pad(audio,(zeros,zeros)))
            try:
                term_span(expected,words(second))
                break
            except ValueError:
                continue
        else:
            raise ValueError('The second recognizer could not confirm the printed context of fusee')
    timed = timed_words(audio)
    begin, end = term_span(expected,[item for item,_ in timed])
    lo = max(0,timed[begin][1]-round(.10*RATE))
    hi = min(len(audio),timed[end][1]+round(.055*RATE)) if end<len(timed) else len(audio)
    start, stop, score, vowel_ms = check_word(audio[lo:hi])
    return dict(phones='F Y UW Z IY',score=score,start=round((lo+start)/RATE,3),
                end=round((lo+stop)/RATE,3),final_vowel_ms=vowel_ms,
                context_transcript=second,recognizer_padding_ms=padding_ms)
