"""Check the full Inuktitut term in the Arctic reading against the Acadia spoken example."""
from functools import lru_cache
from itertools import product

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


TERM = 'Qaujimajatuqangit'
RENDERINGS = (TERM, 'Kow-yee-mah-yah-too-kah-ngit', 'Kowyeemahyahtookahngit',
              'Kow-yee-maa-yaw-too-kah-ngit', 'Kowyee-maaya-tooqa-ngit')
HINT = ('Read Qaujimajatuqangit as a single Inuktitut word with all seven syllables, '
        'kow-yee-maa-yaw-too-kah-ngit. Both written j sounds are glides like y in yes. '
        'Make the q deep in the throat, keep ng together as in sing, and finish the final t.')
SYLLABLES = ('K AW','Y IY','M AA','Y AA','T UW','K AA','NG IH T')


def alternatives():
    sounds = {'full': ' '.join(SYLLABLES)}
    for i in range(len(SYLLABLES)):
        sounds[f'missing-{i}'] = ' '.join(SYLLABLES[:i]+SYLLABLES[i+1:])
    for i,options in ((0,['K OW','K AA','K AH']), (1,['JH IY','JH AH','JH IH','IY']),
                      (3,['JH AH','JH AA','CH AH','Y AO']), (5,['CH AH','CH AE','CH AA','SH AH']),
                      (6,['G IH T','NG IY T','NG IH','NG','N IH T'])):
        for k,reading in enumerate(options):
            sounds[f'variant-{i}-{k}'] = ' '.join(SYLLABLES[:i]+(reading,)+SYLLABLES[i+1:])
    for k,(ji,ja,qa) in enumerate(product(('JH IH','JH IY','JH AH'),('JH AH','JH AA'),('CH AE','CH AH','K AA'))):
        sounds[f'affricated-{k}'] = ' '.join((SYLLABLES[0],ji,SYLLABLES[2],ja,SYLLABLES[4],qa,SYLLABLES[6]))
    sounds['missing-middle'] = ' '.join(SYLLABLES[:2]+SYLLABLES[4:])
    sounds['missing-ending'] = ' '.join(SYLLABLES[:-2])
    return sounds


PHONES = alternatives()
# The Acadia speaker has an onset closest to K OW in the English acoustic model.
ACCEPTED = {
    ' '.join(SYLLABLES),
    'K OW Y IY M AA Y AA T UW K AA NG IH T',
    'K AW Y IY M AA Y AO T UW K AA NG IH T',
    'K AW Y IY M AA Y AA T UW K AA NG IY T',
}


@lru_cache(maxsize=1)
def phone_recognizer():
    return grammar_decoder(PHONES,{'inuit':'IH N UW IH T'},'[inuit] {term}')


def check_word(sample):
    label,score,start,stop = locate_sound(sample,phone_recognizer(),PHONES)
    if PHONES[label] not in ACCEPTED or score<.40:
        raise ValueError(f'The seven syllables of {TERM} differ from the pronunciation guide: {PHONES[label]}')
    if not .60*RATE<=stop-start<=3.0*RATE:
        raise ValueError(f'Incomplete interval for {TERM}')
    if any(start<(a+b)/2<stop for a,b in interior_gaps(sample)):
        raise ValueError(f'A pause interrupts {TERM}')
    return dict(phones=PHONES[label],score=round(score,3),start=start/RATE,end=stop/RATE)


def verify(audio,text,first,second):
    expected = words(text)
    if expected.count(TERM.lower())!=1:
        raise ValueError(f'Expected one {TERM}')
    index = expected.index(TERM.lower())
    prefix, suffix = expected[:index], expected[index+1:]

    def locate(heard):
        end = len(heard)-len(suffix)
        # English recognizers sometimes omit the entire foreign term, even in the
        # university recording. The acoustic word test still requires all seven syllables.
        if heard[:index]!=prefix or heard[end:]!=suffix or not 0<=end-index<=9:
            raise ValueError(f'The surrounding English words differ for {TERM}')
        return end

    for hypothesis in (first,second):
        locate(words(hypothesis))
    timed = timed_words(audio)
    end = locate([w for w,t in timed])
    anchored_by_inuit = end==index
    if anchored_by_inuit and (not prefix or prefix[-1]!='inuit'):
        raise ValueError(f'Cannot locate the onset of {TERM}')
    anchor = timed[index-1 if anchored_by_inuit else index][1]
    lo = max(0,anchor-round(.12*RATE))
    hi = min(len(audio),timed[end][1]+round(.04*RATE)) if end<len(timed) else len(audio)
    report = check_word(audio[lo:hi])
    for edge in ('start','end'):
        report[edge] = round(report[edge]+lo/RATE,3)
    if anchored_by_inuit and report['start']<anchor/RATE+.18:
        raise ValueError('The audio attributed to the term overlaps the start of Inuit')
    return report
