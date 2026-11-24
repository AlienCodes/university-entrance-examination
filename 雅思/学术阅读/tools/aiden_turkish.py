"""Verify the fourteen Turkish syllables in the language passage with a Turkish character recognizer."""
from functools import lru_cache
from itertools import groupby
import json
from pathlib import Path

import numpy as np

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words


PRINTED = 'şehirliliştiremediklerimizdensiniz'
ORAL = 'shehirlilishtiremediklerimizdensiniz'
SYLLABLES = ('şe', 'hir', 'li', 'liş', 'ti', 're', 'me', 'dik', 'le', 'ri', 'miz', 'den', 'si', 'niz')
RENDERINGS = (ORAL, 'şehirli liştire mediklerimiz densiniz',
              'shehirli lishtire mediklerimiz densiniz', PRINTED,
              'shehheerlee leeshtireh mediklerimeez denseeneez',
              'şehirli-liştire-mediklerimiz-densiniz',
              'sheh-heer-lee-leesh-tee-reh-meh-deek-leh-ree-meez-den-see-neez')
HINT = ('Read the introductory English words in the same voice. The Turkish example that follows is '
        'one continuous word with fourteen evenly linked syllables: '
        'şe-hir-li-liş-ti-re-me-dik-le-ri-miz-den-si-niz. The letter ş is sh and each i is ee. '
        'Link the four groups şehirli, liştire, mediklerimiz, densiniz without silence. '
        'Keep both li syllables, the k in dik, and the z at the end of miz and niz.')
MODEL = Path(__file__).resolve().parents[3] / 'tools/tts/models/ielts-turkish-ctc'


@lru_cache(maxsize=1)
def recognizer():
    import onnxruntime as ort

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 3
    opts.inter_op_num_threads = 1
    session = ort.InferenceSession(str(MODEL / 'model_int8.onnx'), opts, providers=['CPUExecutionProvider'])
    vocab = json.loads((MODEL / 'vocab.json').read_text())
    return session, {int(index): char for char, index in vocab.items()}


def check_word(sample):
    session, characters = recognizer()
    if len(sample) < RATE // 2:
        raise ValueError('Incomplete Turkish recording')
    data = ((sample - sample.mean()) / np.sqrt(sample.var() + 1e-7))[None].astype('float32')
    inputs = {key.name: data if key.type == 'tensor(float)' else np.ones(data.shape, dtype='int64')
              for key in session.get_inputs()}
    logits = session.run(None, inputs)[0][0]
    spans = []
    for symbol, frames in groupby(enumerate(np.argmax(logits, axis=1)), key=lambda row: int(row[1])):
        positions = [i for i, _ in frames]
        char = characters[symbol]
        if char not in {'<s>', '</s>', '<pad>', '|'}:
            # The convolution covers 400 samples; successive logits are 320 samples apart.
            spans.append((char, positions[0] * 320, min(len(sample), positions[-1] * 320 + 400)))
    heard = ''.join(char for char, _, _ in spans)
    if heard != PRINTED:
        raise ValueError(f'Turkish recognizer did not hear the entire printed word: {heard!r}')
    start, end = spans[0][1], spans[-1][2]
    if any(start < (a + b) / 2 < end for a, b in interior_gaps(sample)):
        raise ValueError('A pause interrupts the Turkish word')
    return {'heard': heard, 'syllables': list(SYLLABLES), 'start': start / RATE, 'end': end / RATE}


def verify(audio, text, first, second):
    expected = words(text)
    if expected != ['the', 'turkish', 'word', ORAL]:
        raise ValueError('Unexpected English context for the Turkish word')
    for hypothesis in (first, second):
        if words(hypothesis)[:3] != expected[:3]:
            raise ValueError('The spoken introduction to the Turkish example is incomplete')
    timed = timed_words(audio)
    if len(timed) <= 3 or [w for w, _ in timed[:3]] != expected[:3]:
        raise ValueError('Cannot locate the start of the Turkish word after its English introduction')
    # English timestamps sometimes include the d from "word". Each small crop
    # must still contain all 34 letters in ordinary, unconstrained Turkish recognition.
    errors = []
    for padding in (.08, .0, .14):
        lo = max(0, timed[3][1] - round(padding * RATE))
        try:
            result = check_word(audio[lo:])
        except ValueError as error:
            errors.append(str(error))
            continue
        for edge in ('start', 'end'):
            result[edge] = round(result[edge] + lo / RATE, 3)
        return result
    raise ValueError(' / '.join(dict.fromkeys(errors)))
