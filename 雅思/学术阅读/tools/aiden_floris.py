"""Verify the Dutch soil specialist's surname and its English possessive on the recorded speech."""
from functools import lru_cache
import hashlib
from pathlib import Path

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


# Dutch /ˈfloː.rɪs/. Native reference recordings contain a short, weak second vowel.
FORMS = {
    'floris': 'F L AO R IH S', 'floris-long-o': 'F L OW R IH S',
    'floris-reduced': 'F L AO R AH S', 'floris-long-o-reduced': 'F L OW R AH S',
    'flor': 'F L AO R', 'floors': 'F L AO R Z', 'flores': 'F L AO R EY S',
    'flores-voiced': 'F L AO R EH Z', 'florez': 'F L AO R EY Z',
    'florace': 'F L AO R EH S', 'fleece': 'F L IY S', 'floris-voiced': 'F L AO R IH Z',
}
PERMITTED = {'floris', 'floris-long-o', 'floris-reduced', 'floris-long-o-reduced'}


@lru_cache(maxsize=2)
def decoder(possessive):
    if possessive:
        context = {'iz': 'IH Z', 'uz': 'AH Z', 'mix': 'M IH K S', 'mixed': 'M IH K S T',
                   'miss': 'M IH S', 'to': 'T UW', 'ta': 'T AH'}
        return grammar_decoder(FORMS, context, '{term} [iz | uz] (mix | mixed | miss) [to | ta]')
    return grammar_decoder(FORMS, {'pius': 'P AY AH S', 'peeus': 'P IY AH S'},
                           '[pius | peeus] {term}')


@lru_cache(maxsize=1)
def mastered_reference():
    import soundfile as sf
    path = Path(__file__).with_name('读音对照') / 'Floris-mix-to.flac'
    if hashlib.sha256(path.read_bytes()).hexdigest() != 'deaba4310b9e376b0f6534af9538eb0da4256ae8939a3c2d9f4c39f368c89b3b':
        raise ValueError('The reviewed Floris recording differs from the reference')
    data, rate = sf.read(path, dtype='float32')
    if rate != RATE or data.shape != (24000,):
        raise ValueError('Invalid Floris reference recording')
    return data


def compare_recorded_words(audio, name_onset):
    """Compare the actual Floris’s mix to sequence with the independently mastered, verified take."""
    import numpy as np
    from scipy.signal import correlate
    from aiden_encoded_audio import compare_waveforms
    ref = mastered_reference()
    # The reference begins just before the first consonant. Estimate one codec
    # offset and one gain for the entire excerpt. No stretching or word edits.
    lo = max(0, name_onset - round(.25*RATE))
    hi = min(len(audio), name_onset + len(ref) + round(.10*RATE))
    window = audio[lo:hi]
    if len(window) < len(ref):
        raise ValueError('Truncated Floris recording')
    offset = int(np.argmax(correlate(window, ref, mode='valid', method='fft')))
    clip = window[offset:offset + len(ref)]
    gain = float((clip @ ref) / max(float(clip @ clip), 1.e-12))
    if not .5 < gain < 2.0:
        raise ValueError('The recorded Floris excerpt does not match the reviewed take')
    return dict(start=round((lo+offset)/RATE,4),gain=round(gain,4),
                **compare_waveforms(ref,clip*gain))


def verify(audio, expected, first, second):
    possessive = 'floriss' in expected
    root = 'floriss' if possessive else 'floris'
    i = expected.index(root)
    alternatives = {'floris', 'flores', 'florus'}
    if possessive:
        alternatives |= {s + ending for s in alternatives for ending in ('s','es')}
    def same_words(hypothesis):
        if hypothesis[:i] != expected[:i] or not hypothesis[i:i+1] or hypothesis[i] not in alternatives:
            return False
        if possessive:
            return hypothesis[i+1:i+2] in (['mix'],['mixed']) and hypothesis[i+2:] == expected[i+2:]
        return hypothesis[i+1:] == expected[i+1:]
    for h in (first, second):
        if not same_words(words(h)):
            raise ValueError(f'The wording around Floris differs: {h!r}')
    if possessive and all(words(h)[i+1] != 'mix' for h in (first, second)):
        raise ValueError('Neither reading contains the noun mix after the possessive')
    timed = timed_words(audio)
    if not same_words([w for w, t in timed]):
        raise ValueError('Cannot locate the surname Floris in the printed context')
    lo = max(0, timed[i][1] - round(.11 * RATE))
    # Include the onset and vowel of "to". An isolated t left at the end of the
    # noun can make the acoustic model hear the consonant cluster in "mixed".
    hi = min(len(audio), timed[i+2][1] + round(.14 * RATE)) if possessive and i+2 < len(timed) else len(audio)
    recognizer = decoder(possessive)
    key, score, start, end = locate_sound(audio[lo:hi], recognizer, FORMS)
    if key not in PERMITTED or score < .15 or not .26 * RATE <= end-start <= 1.25 * RATE:
        raise ValueError(f'The two syllables or final s in Floris are unclear: {FORMS[key]}')
    if any(start < (a+b)/2 < end for a, b in interior_gaps(audio[lo:hi])):
        raise ValueError('A silence splits the surname Floris')
    segments = [s.word for s in recognizer.seg()]
    suffix = [word for word in segments if word in ('iz','uz')]
    result = dict(phones=FORMS[key], possessive_syllable=suffix, confidence=round(score,3),
                  start=round((lo+start)/RATE,3), end=round((lo+end)/RATE,3))
    if possessive:
        if len(suffix) != 1:
            raise ValueError('The possessive syllable after Floris is incomplete')
        if 'mix' not in segments:
            if ('mixed' not in segments or not {'to','ta'}.intersection(segments)
                    or [word for word,_ in timed[i+1:i+3]] != ['mix','to']):
                raise ValueError('The noun mix or the following to is unclear')
            result['reviewed_waveform'] = compare_recorded_words(audio,lo+start)
    return result
