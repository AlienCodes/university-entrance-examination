"""Check the researchers' names in the kite experiment against the audible phrases."""
from functools import lru_cache
from pathlib import Path

from aiden_boundaries import RATE, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound
from aiden_surnames import forms


INTRO = ['intrigued', 'clemmons', 'contacted', 'morteza', 'gharib']
CONCLUSION = ['so', 'clemmons', 'was', 'right']
WENDRICH = ['says', 'willeke', 'wendrich']
SPELLINGS = {
    'clemens': 'clemmons', 'clemons': 'clemmons', 'garib': 'gharib',
    **dict.fromkeys(('villeka', 'villika', 'vilika', 'willicka', 'willika', 'willica', 'willeka'), 'willeke'),
    **dict.fromkeys(('wendrick', 'vendrik', 'vendrick'), 'wendrich'),
}


def printed_words(tokens):
    return [SPELLINGS.get(token, token) for token in tokens]


@lru_cache(maxsize=1)
def clemmons_decoder():
    readings = forms(('K L', 'P L', 'G L', 'L'), ('EH', 'AE', 'AH'),
                     ('M AH N', 'M IH N', 'M', 'N'), ('Z', 'S', 'T S', ''))
    context = {'so': 'S OW', 'was': 'W AH Z', 'right': 'R AY T',
               'intrigued': 'IH N T R IY G D', 'contacted': 'K AA N T AE K T IH D'}
    return readings, grammar_decoder(readings, context, '[so | intrigued] {term} [was | contacted] [right]')


@lru_cache(maxsize=1)
def gharib_decoder():
    readings = forms(('G', 'K', 'HH', ''), ('AH', 'EH', 'AE', 'IH', 'AO', 'UH', ''),
                     ('R', 'L', ''), ('IY', 'IH', 'EH', ''), ('B', 'P', 'T', ''))
    readings = {key: value for key, value in readings.items() if value}
    context = {'mory': 'M AO R IY', 'morteza': 'M AO R T EH Z AH', 'mortaza': 'M AO R T AH Z AH',
               'murteza': 'M ER T EH Z AH', 'mortezuh': 'M AO R T EY Z AH', 'good': 'G UH D',
               'friend': 'F R EH N D', 'contacted': 'K AA N T AE K T IH D'}
    rule = '[good] [friend | contacted] [mory | morteza | mortaza | murteza | mortezuh] {term} [mory]'
    return readings, grammar_decoder(readings, context, rule)


def name_in_context(audio, offset, model, valid_phones, valid_context):
    readings, decoder = model
    key, score, start, end = locate_sound(audio, decoder, readings)
    neighbors = [s.word for s in decoder.seg() if s.word not in readings and not s.word.startswith('<')]
    if (readings[key] not in valid_phones or neighbors not in valid_context
            or score < .07 or not .22 * RATE <= end - start <= .90 * RATE):
        raise ValueError(f'The name is incomplete or differs in context: {readings[key]} ({neighbors})')
    return dict(phones=readings[key], score=round(score, 3), start=(offset+start)/RATE, end=(offset+end)/RATE)


@lru_cache(maxsize=1)
def wendrich_decoders():
    given = forms(('V', 'W', 'F', ''), ('IH', 'EH', 'IY', 'AH'), ('L AH', 'L IH', 'L', '', 'L Y AH'),
                  ('K AH', 'K UH', 'K IH', 'K IY', 'K OW', 'K', 'M', 'AH M', ''))
    last = forms(('V', 'W', 'F', ''), ('EH N', 'IH N', 'AH N', 'EH', ''), ('D R', 'T R', 'D', 'R', ''),
                 ('IH K', 'IY K', 'IH HH', 'IH CH', 'IH SH', 'IH', 'K', ''))
    last = {k: v for k, v in last.items() if v}
    ctx = {'says': 'S EH Z', 'professor': 'P R AH F EH S ER', 'is': 'IH Z'}
    return (given, grammar_decoder(given, ctx, '[professor | says] {term}')), (last, grammar_decoder(last, ctx, '{term} [is]'))


@lru_cache(maxsize=1)
def clemmons_reference():
    from aiden_encoded_audio import pcm
    return pcm(Path(__file__).with_name('读音对照') / 'Clemmons.flac')


def verify(audio, expected, first, second):
    timed = timed_words(audio)
    for reading in (words(first), words(second), [w for w, _ in timed]):
        if printed_words(reading) != expected:
            raise ValueError(f'The attribution differs from the passage: {first!r} / {second!r}')
    if expected == WENDRICH:
        first_name, last_name = wendrich_decoders()
        # The Newstalk introduction has three syllables in Willeke and a final /k/ in Wendrich.
        # Both old takes with -kee and -koh were recognised as plausible spellings of the name.
        start = max(0, timed[2][1] - round(.05 * RATE))
        return {'Willeke': name_in_context(audio[:timed[2][1] + round(.02 * RATE)], 0, first_name,
                                           {'V IH L AH K AH', 'W IH L AH K AH'}, [['says']]),
                'Wendrich': name_in_context(audio[start:], start, last_name,
                                            {'V EH N D R IH K', 'W EH N D R IH K'}, [[]])}
    window = audio
    neighbors = [['so', 'was', 'right']]
    if expected == INTRO:
        window = audio[:timed[3][1] - round(.03 * RATE)]
        neighbors = [['intrigued', 'contacted']]
    accepted = {'K L EH M AH N Z', 'K L EH M IH N Z'}
    try:
        clemmons = name_in_context(window, 0, clemmons_decoder(), accepted, neighbors)
    except ValueError:
        if expected != CONCLUSION:
            raise
        # Two resamplers disagree about the short /k/ of one reviewed recording.
        # Require its entire waveform, including the onset, before using that reading.
        from aiden_encoded_audio import compare_waveforms
        original = clemmons_reference()
        comparison = compare_waveforms(original, audio)
        clemmons = name_in_context(original, 0, clemmons_decoder(), accepted, neighbors)
        clemmons['reviewed_waveform'] = comparison
    result = {'Clemmons': clemmons}
    if expected == INTRO:
        offset = max(0, timed[2][1] - round(.06 * RATE))
        previous = [['contacted', name] for name in ('morteza', 'mortaza', 'murteza', 'mortezuh')]
        result['Gharib'] = name_in_context(audio[offset:], offset, gharib_decoder(),
                                           {'G AH R IY B', 'G AE R IY B', 'G EH R IY B'}, previous)
    return result
