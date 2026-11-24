"""Acoustic comparison of a printed name with documented and truncated pronunciations."""
from functools import lru_cache
from pathlib import Path
import tempfile

import numpy as np

from aiden_boundaries import RATE


def grammar_decoder(phones, context, rule):
    from pocketsphinx import Decoder, get_model_path

    with tempfile.TemporaryDirectory() as tmp:
        dictionary, grammar = Path(tmp)/'target.dict', Path(tmp)/'target.gram'
        entries = {**phones, **context}
        dictionary.write_text(''.join(f'{term} {reading}\n' for term,reading in entries.items()))
        alternatives = '(' + ' | '.join(phones) + ')'
        grammar.write_text('#JSGF V1.0;\ngrammar target;\npublic <term> = '
                           + rule.replace('{term}',alternatives) + ';\n')
        return Decoder(hmm=str(Path(get_model_path())/'en-us/en-us'),dict=str(dictionary),
                       jsgf=str(grammar),samprate=RATE,loglevel='ERROR')


def locate_sound(audio, decoder, phones):
    padding = 2400
    data = (np.clip(np.pad(audio,(padding,padding)),-1,1)*32767).astype('<i2')
    decoder.start_utt()
    decoder.process_raw(data.tobytes(),False,True)
    decoder.end_utt()
    matches = [s for s in (decoder.seg() or ()) if s.word in phones]
    if len(matches)!=1:
        raise ValueError('The recording does not contain one complete, identifiable target word')
    match = matches[0]
    start = max(0,match.start_frame*160-padding)
    stop = min(len(audio),(match.end_frame+1)*160-padding)
    return match.word, match.prob, start, stop


_OR_FORMS = {'or': 'AO R', 'weak-or': 'ER', 'or-ah': 'AH R', 'for': 'F AO R',
             'weak-for': 'F ER', 'fa': 'F AH', 'off': 'AO F', 'uh': 'AH', 'of': 'AH V'}


@lru_cache(maxsize=1)
def finger_choice_decoder():
    return grammar_decoder(_OR_FORMS, {'fingers':'F IH NG G ER Z', 'finger':'F IH NG G ER'},
                           '{term} (fingers | finger)')


def verify_or_fingers(audio, hypotheses):
    from aiden_boundaries import words
    if (not any(words(h) == ['or', 'fingers'] for h in hypotheses)
            or any(words(h) not in (['or','fingers'], ['for','fingers']) for h in hypotheses)):
        raise ValueError('The recorded alternative “or fingers” differs from the paper')
    decoder = finger_choice_decoder()
    key, confidence, start, end = locate_sound(audio, decoder, _OR_FORMS)
    if (key not in ('or', 'weak-or', 'or-ah') or confidence < .45 or end - start < .055 * RATE
            or not any(s.word == 'fingers' for s in decoder.seg())):
        raise ValueError(f'The opening of “or fingers” or the plural ending is unclear: {_OR_FORMS[key]}')
    # A recognizer can restore the expected plural even when the recording
    # stops on the vowel. Measure the actual sibilant in the end of "fingers".
    frame = RATE // 50
    blocks = audio[:len(audio)//frame*frame].reshape(-1,frame)
    power = np.abs(np.fft.rfft(blocks * np.hanning(frame)))**2
    total = power.sum(axis=1)
    audible = total > total.max(initial=0) * 1.6e-4
    last = np.flatnonzero(audible)
    if not last.size:
        raise ValueError('The recording of fingers contains no audible ending')
    window = slice(max(0,last[-1]-8), last[-1]+1)
    high = power[:, 3000*frame//RATE:].sum(axis=1)
    fricative = (audible & (high > .25*total))[window]
    if not np.any(fricative[:-1] & fricative[1:]):
        raise ValueError('The plural sibilant in fingers is cut short')
    return dict(phones=_OR_FORMS[key], confidence=round(confidence,3), start=start/RATE, end=end/RATE,
                final_sibilant_frames_20ms=int(fricative.sum()))
