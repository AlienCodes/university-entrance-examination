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


@lru_cache(maxsize=4)
def name_decoder(name, with_context):
    if name == 'halley':
        forms = {'halley':'HH AE L IY', 'haley':'HH EY L IY', 'hawley':'HH AO L IY',
                 'holly':'HH AA L IY', 'allie':'AE L IY', 'pally':'P AE L IY',
                 'tally':'T AE L IY', 'hall':'HH AE L', 'hay':'HH EY'}
        context, rule = {'was':'W AH Z','aware':'AH W EH R'}, '{term} [was] [aware]'
    else:
        forms = {'egg':'EH G', 'ag':'AE G', 'ayg':'EY G', 'eeg':'IY G',
                 'ig':'IH G', 'eye':'AY', 'eggy':'EH G IY', 'eck':'EH K',
                 'vowel':'EH', 'eight':'EY T'}
        context, rule = {'isle':'AY L','of':'AH V','shows':'SH OW Z'}, '[isle] [of] {term} [shows]'
    return grammar_decoder(forms, context if with_context else {}, rule if with_context else '{term}'), forms


def verify_name_in_phrase(audio, expected, first, second):
    from aiden_boundaries import interior_gaps, words
    from aiden_ceylonese import timed_words

    halley = expected[:3] == ['halley','was','aware']
    name, target, index = ('halley','halley',0) if halley else ('eigg','egg',expected.index('eigg'))
    spellings = {'halley','hallie'} if halley else {'egg','eigg','eig'}
    for transcript in (first, second):
        tokens = words(transcript)
        if (len(tokens) != len(expected) or tokens[index] not in spellings
                or tokens[:index] + tokens[index+1:] != expected[:index] + expected[index+1:]):
            raise ValueError(f'The name or its surrounding printed words differ: {transcript!r}')
    timed = timed_words(audio)
    if len(timed) != len(expected):
        raise ValueError(f'Unclear word boundaries around {name}')
    if halley:
        if [w for w,_ in timed[1:3]] != ['was','aware']:
            raise ValueError('Missing context after Halley')
        begin, end = 0, min(len(audio),timed[2][1]+round(.07*RATE))
        left, right = 0, timed[1][1]
    else:
        if [w for w,_ in timed[index-2:index]] != ['isle','of'] or timed[index+1][0] != 'shows':
            raise ValueError('Missing spoken context around Eigg')
        begin, end = max(0,timed[index-2][1]-round(.08*RATE)),len(audio)
        left, right = max(0,timed[index][1]-round(.04*RATE)),min(len(audio),timed[index+1][1]+round(.03*RATE))
    readings=[]
    for low, high, context in ((begin,end,True),(left,right,False)):
        decoder, forms = name_decoder(name,context)
        label, score, start, finish = locate_sound(audio[low:high],decoder,forms)
        if (label != target or score < .25 or finish-start < (.18 if halley else .11)*RATE
                or any(low+start < (a+b)/2 < low+finish for a,b in interior_gaps(audio))):
            raise ValueError(f'Incomplete or unclear {name}: {forms[label]}')
        readings.append(dict(phones=forms[label],confidence=round(score,3),
                             start=(low+start)/RATE,end=(low+finish)/RATE))
    return dict(name=name, context=readings[0], isolated=readings[1])


@lru_cache(maxsize=1)
def tiers_decoder():
    # Cambridge uses the same US recording for tier and tear (from the eye).
    # Compete against tear (rip), a missing plural, and a missing r.
    forms = {'tiers': 'T IH R Z', 'tiers-tense': 'T IY R Z', 'tears-rips': 'T EH R Z',
             'tier': 'T IH R', 'tier-tense': 'T IY R', 'tare': 'T EH R',
             'years': 'Y IH R Z', 'teas': 'T IY Z', 'cheers': 'CH IH R Z'}
    context = {'often': 'AO F AH N', 'oftent': 'AO F T AH N', 'offen': 'AA F AH N', 'in': 'IH N'}
    return grammar_decoder(forms, context, '[often | oftent | offen] [in] {term}'), forms


def verify_often_in_tiers(audio, first, second):
    from aiden_boundaries import interior_gaps, words
    if any(words(s) not in (['often','in','tiers'], ['often','in','tears']) for s in (first, second)):
        raise ValueError('The recording does not contain the complete phrase often in tiers')
    decoder, forms = tiers_decoder()
    label, score, start, end = locate_sound(audio, decoder, forms)
    if (label not in {'tiers', 'tiers-tense'} or score < .4 or not .18*RATE <= end-start <= .9*RATE
            or any(start < (a+b)/2 < end for a,b in interior_gaps(audio))):
        raise ValueError('The vowel, plural ending, or continuity of tiers is unclear: '+forms[label])
    return dict(phones=forms[label], confidence=round(score,3), start=start/RATE, end=end/RATE)


@lru_cache(maxsize=1)
def craftsmen_decoder():
    from itertools import product
    forms = product(('K R AE F T', 'K R AE F', 'K R AE T', 'K R AH F T'),
                    ('S M', 'M', 'S', ''), ('AH N', 'EH N', 'IH N', 'AE N', 'N', 'AH', ''))
    phones = {f'form-{i}': ' '.join(p for p in form if p) for i, form in enumerate(forms)}
    return grammar_decoder(phones, {}, '{term}'), phones


def verify_ancient_craftsmen(audio, first, second):
    from aiden_boundaries import interior_gaps, words
    from aiden_ceylonese import timed_words
    timed = timed_words(audio)
    for read in (words(first), words(second), [w for w,_ in timed]):
        if (read[:2] != ['the', 'ancient'] or len(read) != 3 or
                read[-1] not in {'craftsmen', 'craftsman'}):
            raise ValueError('The ancient craftsmen or its introduction differs')
    offset = max(0, timed[-1][1] - 1700)
    decoder, phones = craftsmen_decoder()
    key, score, begin, end = locate_sound(audio[offset:], decoder, phones)
    # The Oxford US recordings give /ˈkræftsmən/ for both numbers. The
    # stressed /mɛn/ plural is also possible; neither permits a missing n.
    pronounced = phones[key].split()
    if (pronounced[:4] != ['K','R','AE','F'] or pronounced[-4:-2] != ['S','M'] or
            pronounced[-2] not in {'AH','EH','IH'} or pronounced[-1] != 'N' or
            score < .065 or not .38*RATE <= end-begin <= 1.25*RATE):
        raise ValueError('The recording lacks the complete word craftsmen: '+phones[key])
    if any(begin < (a+b)/2 < end for a,b in interior_gaps(audio[offset:])):
        raise ValueError('A silence interrupts the word craftsmen')
    return dict(phones=phones[key],score=round(score,3),
                start=round((offset+begin)/RATE,3),end=round((offset+end)/RATE,3))


_FISH_FORMS = {
    'cod':'K AA D', 'cot':'K AA T', 'cawed':'K AO D', 'cad':'K AE D', 'con':'K AA N',
    'todd':'T AA D', 'tad':'T AE D', 'god':'G AA D', 'got':'G AA T', 'goad':'G OW D',
    'awed':'AO D', 'odd':'AA D', 'caught':'K AO T', 'cut-short':'K AA',
    'dot':'D AA T', 'cud':'K AH D',
}


@lru_cache(maxsize=1)
def fish_decoder():
    return grammar_decoder(_FISH_FORMS, {'sole':'S OW L','soul':'S OW UH L'}, '{term} [sole | soul]')


def verify_groundfish_list(audio, first, second):
    from aiden_boundaries import independent, interior_gaps, words
    from aiden_ceylonese import timed_words
    def complete(h):
        return bool(h and h[0] in {'cod','todd','god'} and
                    ''.join(h[1:]).replace('soul','sole') == 'soleperchandpollock')
    heard = [words(first), words(second)]
    if complete(heard[0]) and not complete(heard[1]):
        # A short AAC excerpt occasionally produces a repeated phrase when
        # decoded in isolation. Keep the whole signal and 40 ms of quiet at each end.
        second = independent(np.pad(audio,(640,640)))
        heard[1] = words(second)
    if not all(complete(h) for h in heard):
        raise ValueError(f'The four printed fish names differ: {first!r} / {second!r}')
    if not any(tokens[:1] == ['cod'] for tokens in heard):
        raise ValueError('Neither full phrase identifies the first fish as cod')
    timing = timed_words(audio)
    end = next((s for word,s in timing if word == 'perch'), len(audio))
    key, score, begin, stop = locate_sound(audio[:min(end,round(.85*RATE))], fish_decoder(), _FISH_FORMS)
    if (key != 'cod' or score < .3 or not .18*RATE <= stop-begin <= .8*RATE or
            any(begin < (a+b)/2 < stop for a,b in interior_gaps(audio))):
        raise ValueError('The first fish name is incomplete or has another initial: '+_FISH_FORMS[key])
    return dict(phones=_FISH_FORMS[key], confidence=round(score,3), start=begin/RATE, end=stop/RATE,
                second_identification=second)


_SOCKEYE = {
    'sockeye':'S AA K AY', 'rounded':'S AO K AY', 'sake-eye':'S EY K AY',
    'saki':'S AA K IY', 'saki-eye':'S AA K IY AY', 'soakeye':'S OW K AY',
    'sock':'S AA K', 'saw-eye':'S AO AY', 'soccer':'S AA K ER', 'sock-uh-eye':'S AA K AH AY',
    'socket':'S AA K IH T', 'kay':'K AY', 'eye':'AY', 'sake':'S EY K',
}
_SALMON_OR = {
    'or':'AO R', 'weak-or':'ER', 'or-ah':'AH R', 'and':'AE N D', 'an':'AH N',
    'ann':'AE N', 'for':'F AO R', 'are':'AA R', 'nor':'N AO R', 'uh':'AH', 'oh':'OW',
}
_SALMON_RED = {
    'red':'R EH D', 'wren':'R EH N', 'ret':'R EH T', 'read':'R IY D', 'ray':'R EY',
    'rest':'R EH S T', 're':'R EH',
}


@lru_cache(maxsize=1)
def sockeye_decoders():
    connector = '(' + ' | '.join(_SALMON_OR) + ')'
    ending = '(' + ' | '.join(_SALMON_RED) + ')'
    return (
        grammar_decoder(_SOCKEYE, {**_SALMON_OR, **_SALMON_RED}, '{term} ['+connector+'] ['+ending+']'),
        grammar_decoder(_SOCKEYE, {}, '{term}'),
        grammar_decoder(_SALMON_OR, {'red':'R EH D'}, '{term} [red]'),
        grammar_decoder(_SALMON_RED, _SALMON_OR, '['+connector+'] {term}'),
    )


def sockeye_release(audio):
    decoder = grammar_decoder({'release':_SOCKEYE['sock-uh-eye']}, {}, '{term}')
    pcm = (np.clip(np.pad(audio,(2400,2400)),-1,1)*32767).astype('<i2').tobytes()
    decoder.set_align_text('release')
    try:
        for align_phones in (False, True):
            if align_phones:
                decoder.set_alignment()
            decoder.start_utt()
            decoder.process_raw(pcm,False,True)
            decoder.end_utt()
    except RuntimeError as exc:
        raise ValueError('Cannot align the release of k in sockeye') from exc
    for word in decoder.get_alignment() or ():
        if word.name == 'release':
            return {phone.name:phone.duration*10 for phone in word}
    raise ValueError('Cannot locate the release of k in sockeye')


def verify_sockeye(audio, first, second):
    from aiden_boundaries import interior_gaps, words
    from aiden_ceylonese import timed_words

    printed, split = ['sockeye','or','red'], ['sock','eye','or','red']
    reads = [words(t) for t in (first, second)]
    if printed not in reads or any(r not in (printed, split) for r in reads):
        raise ValueError(f'The salmon name or the following words differ: {first!r} / {second!r}')
    timed = timed_words(audio)
    if [w for w,_ in timed] not in (printed, split):
        raise ValueError('Unclear word boundaries in sockeye or red')
    or_onset = timed[-2][1]
    context, isolated_name, middle, ending = sockeye_decoders()
    name = locate_sound(audio, context, _SOCKEYE)
    alone = locate_sound(audio[:or_onset], isolated_name, _SOCKEYE)
    # Cambridge US has /ˈsɑːk.aɪ/. Read the same waveform with and without
    # the following words so the vowel of “or” cannot complete the fish name.
    valid = {'sockeye','rounded'}
    release = None
    if alone[0] == 'sock-uh-eye' and name[0] in valid:
        # A short release after /k/ is also measurable in the Cambridge US
        # recording. A sustained third vowel changes the word's rhythm.
        release = sockeye_release(audio[:or_onset])
        if 0 < release['AH'] <= min(70,release['AY']/3):
            valid = valid | {'sock-uh-eye'}
    for key, score, start, stop in (name, alone):
        if (key not in valid or score < .2 or not .25*RATE <= stop-start <= 1.1*RATE
                or any(start < (a+b)/2 < stop for a,b in interior_gaps(audio))):
            raise ValueError('The two syllables of sockeye are incomplete or interrupted')
    offset = name[3]
    link = locate_sound(audio[offset:], middle, _SALMON_OR)
    red = locate_sound(audio[offset:], ending, _SALMON_RED)
    if (link[0] not in {'or','weak-or','or-ah'} or red[0] != 'red' or min(link[1], red[1]) < .2
            or not link[2] < link[3] <= red[2]+round(.04*RATE) < red[3]):
        raise ValueError('The conjunction or the final d in sockeye or red is unclear')
    def reading(observation, forms, start=0):
        key, score, begin, end = observation
        return dict(phones=forms[key], confidence=round(score,3), start=(start+begin)/RATE,
                    end=(start+end)/RATE)
    return dict(name=reading(name,_SOCKEYE), isolated_name=reading(alone,_SOCKEYE),
                isolated_release_ms=release,
                conjunction=reading(link,_SALMON_OR,offset), final_word=reading(red,_SALMON_RED,offset))


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
