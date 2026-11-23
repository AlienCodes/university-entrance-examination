"""Acoustic comparison of a printed name with documented and truncated pronunciations."""
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
