"""Check the silent final s of Sèvres in the account of Marie Curie."""
from functools import lru_cache
import hashlib
import io
from pathlib import Path
import zipfile

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


READINGS = {
    'french':'S EH V R','us':'S EH V R AH','us-r':'S EH V ER','us-ruh':'S EH V ER AH',
    'saver':'S EY V ER','severus':'S EH V ER AH S','severiss':'S EH V ER IH S',
    'severahs':'S EH V R AH S','sev':'S EH V','sair':'S EH R','saverus':'S EY V ER AH S',
    'seevres':'S IY V ER AH','sivers':'S IH V ER Z','severs':'S EH V ER Z',
    'safe':'S EY F','sif':'S IH F',
    'sev-roo':'S EH V R UW','sever-oo':'S EH V ER UW',
    'severe':'S AH V IH R','severe-long':'S IH V IY R','severe-clear':'S EH V IY R',
    'severed':'S EH V ER D','severer':'S EH V ER ER',
}
TOWN_SPELLINGS = {'sevres','sevre','sevra','sevrah','sever','sevruh','severa'}


@lru_cache(maxsize=1)
def decoder():
    return grammar_decoder(READINGS,{'in':'IH N'},'[in] {term}')


@lru_cache(maxsize=1)
def reviewed_school_recordings():
    import soundfile as sf
    import soxr
    tools = Path(__file__).resolve().parent
    with zipfile.ZipFile(tools.parent / '审校/Aiden/13-6/复验原声/C9T4P1.zip') as archive:
        source = archive.read('aiden-takes/0b5227d33191e4e574833667e090d428347ab9ad012ce69b66028d1edc5552bd.flac')
    mastered = (tools / '读音对照/Sevres-mastered.flac').read_bytes()
    if (hashlib.sha256(source).hexdigest() != '1fd5e395f8f379bca198f75c9feb511d33c6e80a23a9a6d77f4aea25464e8bfb'
            or hashlib.sha256(mastered).hexdigest() != '1ab252bb45fde1e581aac891fd2e7fd5e023bbfd4fc89f2dc5acbd811977a3a0'):
        raise ValueError('The reviewed school and location recordings have changed')
    raw, rate = sf.read(io.BytesIO(source), dtype='float32')
    mixed, mixed_rate = sf.read(io.BytesIO(mastered), dtype='float32')
    if rate != 24000 or mixed_rate != RATE:
        raise ValueError('Unexpected sample rate for the reviewed French names')
    return (('source', soxr.resample(raw, rate, RATE)), ('mastered', mixed))


def match_reviewed_school(audio):
    from aiden_encoded_audio import compare_waveforms
    for stage, ref in reviewed_school_recordings():
        if abs(len(ref) - len(audio)) > round(.004 * RATE):
            continue
        size = min(len(ref), len(audio))
        original, recorded = ref[:size], audio[:size]
        gain = float(original @ recorded) / max(float(recorded @ recorded), 1.e-12)
        if not .5 < gain < 2.0:
            continue
        try:
            comparison = compare_waveforms(original, recorded * gain)
        except ValueError:
            continue
        return dict(stage=stage, gain=round(gain, 4), **comparison)
    raise ValueError('The recording differs from the independently reviewed school and location')


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
    def literal(reading):
        return bool(reading and reading[:-1] == expected[:-1] and reading[-1] in TOWN_SPELLINGS)
    result = dict(phones=READINGS[key],confidence=round(score,3),start=round((offset+start)/RATE,3),
                  end=round((offset+end)/RATE,3))
    if not all(literal(t) for t in observed):
        # English Whisper wrote “Echol Normale Superyear” on the same material
        # that a French recognizer identified as École Normale Supérieure.
        # Keep every English word, including the preposition, and require the
        # actual reviewed recording across the full phrase in 25 ms windows.
        if not any(literal(t) for t in observed):
            from aiden_boundaries import isolated
            observed.append(words(isolated(audio)))
        prefix = expected[:expected.index('ecole')] if 'ecole' in expected else []
        if not prefix or not any(literal(t) for t in observed) or not all(t[:len(prefix)] == prefix and
                t[-4:-1] == ['for','girls','in'] and t[-1] in TOWN_SPELLINGS | {'severe'} for t in observed):
            raise ValueError('The full school name or the sentence around Sèvres requires review')
        result['reviewed_recording'] = match_reviewed_school(audio)
    return result
