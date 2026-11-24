"""Check surnames in the reading passages against speech and printed context."""
from functools import lru_cache
from itertools import product

from aiden_boundaries import RATE, interior_gaps, words
from aiden_ceylonese import timed_words
from aiden_pronunciation import grammar_decoder, locate_sound


ZAPPATERRA_READINGS = {
    'italian':'D Z AA P AH T EH R AH', 'us':'Z AE P AH T EH R AH', 'zah':'Z AA P AH T EH R AH',
    'ts':'T S AA P AH T EH R AH', 'zah-pah':'Z AA P AA T EH R AH', 'short':'Z AE P T EH R AH',
    'zapatero':'Z AE P AH T EH R OW', 'taro':'Z AA P AH T AA R OW', 'zapata':'Z AH P AA T AH',
    'sapatero':'S AA P AH T EH R OW', 'missing-start':'P AH T EH R AH', 'last-i':'Z AE P AH T EH R IY',
    'zap':'Z AE P', 'zahp':'Z AA P', 'sapat':'S AA P AH T EH R AH', 'zip':'Z IH P AH T EH R AH',
    'zapater':'Z AE P AH T ER', 'spat':'S P AE T', 'zorp':'Z AO P AH T EH R AH','tsapa':'T S AA P AA T EH R AH',
}
ZAPPATERRA_SPELLINGS = {'zappaterra','zapaterra','zapatera','zapatero','zepatera','zappatera','zuppetera'}


@lru_cache(maxsize=1)
def zappaterra_decoder():
    markers = {'mauro':'M AW R OW','doctor':'D AA K T ER','learned':'L ER N D','began':'B IH G AE N'}
    return grammar_decoder(ZAPPATERRA_READINGS,markers,'[mauro | doctor] {term} [learned | began | mauro]')


def zappaterra_words(tokens):
    return ['zappaterra' if w in ZAPPATERRA_SPELLINGS else w for w in tokens]


def verify_zappaterra(audio,expected,first,second):
    timed = timed_words(audio)
    for observed in (words(first),words(second),[w for w,t in timed]):
        if zappaterra_words(observed) != expected:
            raise ValueError('The words surrounding the physician’s name differ from the passage')
    index = expected.index('zappaterra')
    if index == 0 and expected[1:4] == ['learned','about','alternative']:
        start,stop = 0,timed[3][1]+200
    elif index > 0 and expected[index-1:index+3] == ['mauro','zappaterra','began','his']:
        start,stop = max(0,timed[index-1][1]-500),timed[index+2][1]+200
    else:
        raise ValueError('Unrecognised context for Mauro Zappaterra')
    key,p,begin,end = locate_sound(audio[start:stop],zappaterra_decoder(),ZAPPATERRA_READINGS)
    # Two introductions to his Mangu.tv interview have a final unstressed a.
    # English recognizers spell even the interview recording with final -o.
    if (key not in {'italian','us','zah','zah-pah','ts','tsapa'} or p < .22
            or not .32*RATE <= end-begin <= 1.12*RATE
            or any(begin < (a+b)/2 < end for a,b in interior_gaps(audio[start:stop]))):
        raise ValueError('A syllable or the final vowel in Zappaterra differs: '+ZAPPATERRA_READINGS[key])
    return dict(phones=ZAPPATERRA_READINGS[key],confidence=round(p,3),
                start=round((start+begin)/RATE,3),end=round((start+end)/RATE,3))


def forms(*parts):
    return {f'variant-{i}':' '.join(p for p in pronunciation if p)
            for i,pronunciation in enumerate(product(*parts))}


@lru_cache(maxsize=1)
def amagoalik_decoders():
    # The chair introduces John Amagoalik and he then introduces himself
    # in the Canadian House of Commons, NDDN hearing 37, 3 November 2009.
    # Compare the complete name and independently test the final stop against
    # the extra s in the recognizer's “Alex” and endings that lose the k.
    starts = ('AA M AH','AE M AH','AH M AH','EH M AH','AA M AA','AE M AA','AY M AH','IH M AH','AH M','M AH')
    middles = ('G OW AE','G W AH','G UW AH','G OW AH','G W AA','G UW AE','G AO AE','G W EH',
               'HH OW AH','HH OW AE','G UW','G AH','G OW')
    readings = forms(starts,middles,('L IH K','L IY K','L EH K S','L IH K S','L IY','L IH'))
    context = {'says':'S EH Z','john':'JH AA N','mister':'M IH S T ER','im':'AY M'}
    final = {'lick':'L IH K','leek':'L IY K','lex':'L EH K S','licks':'L IH K S','leeks':'L IY K S',
             'lek':'L EH K','lee':'L IY','li':'L IH','lig':'L IH G','leez':'L IY Z','kuh':'L IH K AH'}
    return (readings,grammar_decoder(readings,context,'[says] [john | mister] {term} [im]'),
            final,grammar_decoder(final,{},'{term}'))


def verify_amagoalik(audio, first, second):
    timed = timed_words(audio)
    familiar = {'amagoalik','amagoalick','amagualic','amagualik','amagulik'}
    alternatives = {'imagoalex','imagoalec','amagoalic'}
    spellings = []
    for tokens in (words(first),words(second),[word for word,_ in timed]):
        if tokens[:2] != ['says','john'] or not 1 <= len(tokens[2:]) <= 4:
            raise ValueError('The attribution to John Amagoalik is incomplete')
        joined = ''.join(tokens[2:])
        if joined not in familiar | alternatives:
            raise ValueError('Unrecognised sounds in the surname after John: '+joined)
        spellings.append(joined)
    if not familiar.intersection(spellings):
        raise ValueError('Neither recognizer identified a spelling of the recorded surname')
    readings,decoder,endings,tail_decoder = amagoalik_decoders()
    key,score,start,end = locate_sound(audio,decoder,readings)
    phones = readings[key].split()
    if (phones[:3] not in (['AA','M','AH'],['AE','M','AH'],['AH','M','AH'])
            or phones[3:-3] not in (['G','AO','AE'],['G','OW','AE'],['G','OW','AH'],['G','UW','AH'],['G','W','AH'])
            or phones[-3:] not in (['L','IH','K'],['L','IY','K'])
            or score < .15 or not .44*RATE <= end-start <= 1.16*RATE):
        raise ValueError('A vowel group or the final syllable of Amagoalik differs: '+readings[key])
    if any(start < (a+b)/2 < end for a,b in interior_gaps(audio)):
        raise ValueError('A pause interrupts Amagoalik')
    offset = max(start,end-RATE//2)
    tail_key,tail_score,_,tail_end = locate_sound(audio[offset:],tail_decoder,endings)
    if (endings[tail_key] not in {'L IH K','L IY K'} or tail_score < .30
            or end - offset - tail_end > .10*RATE or len(audio) - (offset+tail_end) > .13*RATE):
        raise ValueError('The speaker must finish Amagoalik on k: '+endings[tail_key])
    return dict(phones=readings[key],confidence=round(score,3),ending=endings[tail_key],
                ending_confidence=round(tail_score,3),start=round(start/RATE,3),end=round(end/RATE,3))


JANZEN = forms(('JH AE N','Y AE N','JH EH N','JH IH N','JH AA N','JH AE','S AE N'),
               ('Z','S','T S',''), ('AH N','IH N','AH','N',''))
HAWLEY = forms(('HH',''),('AO','AA','AE','AH','AY','OW','AA R','AO R'),('L IY','L IH','L','IY'))
DOLAN = {'dolan':'D OW L AH N','dolin':'D OW L IH N','doleen':'D OW L IY N','dylan':'D IH L AH N',
         'dollen':'D AA L AH N','dolen-no-n':'D OW L AH','doe':'D OW','dol':'D OW L'}


@lru_cache(maxsize=1)
def janzen_decoder():
    return grammar_decoder(JANZEN,{'to':'T UW','ta':'T AH'},'[to | ta] {term}')


@lru_cache(maxsize=1)
def hawley_decoder():
    return grammar_decoder(HAWLEY,DOLAN,'{term} [('+' | '.join(DOLAN)+')]')


def verify(audio, expected, first, second):
    janzen = expected == ['according','to','janzen']
    timed = timed_words(audio)
    readings = [words(first),words(second),[token for token,_ in timed]]
    if janzen:
        for read in readings:
            if len(read)!=3 or read[:2]!=['according','to'] or read[-1] not in {'janzen','jansen','janssen','jensin','jensen'}:
                raise ValueError('The introduction or the position of the surname Janzen differs')
        lo = max(0,timed[2][1]-round(.10*RATE))
        decoder = janzen_decoder()
        key,score,begin,end = locate_sound(audio[lo:],decoder,JANZEN)
        phones = JANZEN[key]
        if phones not in {'JH AE N Z AH N','JH AE N Z IH N'} or score < .15 or not .36*RATE <= end-begin <= 1.12*RATE:
            raise ValueError('Unclear initial, voiced z or final n in Janzen: '+phones)
    else:
        if expected != ['angelina','hawley','dolan']:
            raise ValueError('Unrecognised name in the abstract art passage')
        for read in readings:
            if len(read)!=3 or read[0]!='angelina' or read[1] not in {'hawley','holly'} or read[2] not in {'dolan','dolen'}:
                raise ValueError('The two surnames or the first name Angelina differ: '+' '.join(read))
        lo = max(0,timed[1][1]-round(.11*RATE))
        decoder = hawley_decoder()
        key,score,begin,end = locate_sound(audio[lo:],decoder,HAWLEY)
        last = [s for s in decoder.seg() if s.word in DOLAN]
        phones = HAWLEY[key]
        # Aiden uses the merged US vowel in “caught”. Preserve the initial h,
        # the absence of an r, both syllables of Hawley and all of Dolan.
        if (phones not in {'HH AO L IY','HH AA L IY'} or score < .15 or not .22*RATE<=end-begin<=.90*RATE
                or len(last)!=1 or last[0].word not in {'dolan','dolin'} or last[0].end_frame-last[0].start_frame<19):
            raise ValueError('Unclear Hawley-Dolan: '+phones+' / '+' '.join(s.word for s in last))
        phones += ' / '+DOLAN[last[0].word]
        end = min(len(audio)-lo,(last[0].end_frame+1)*160-2400)
    if any(begin < (a+b)/2 < end for a,b in interior_gaps(audio[lo:])):
        raise ValueError('A silence breaks the recorded surname')
    return dict(phones=phones,score=round(score,3),start=round((lo+begin)/RATE,3),end=round((lo+end)/RATE,3))


SHENGGEN = forms(('SH AH NG','SH UH NG','SH ER NG','SH EH NG','SH IH NG','SH IY NG',
                 'SH EH N','SH IH N','S AH NG','SH AE NG'),
                ('G AH N','G EH N','G UH N','G IH N','G AE N','G AH NG','JH EH N',
                 'K AH N','K EH N','K IH N','G',''))
FAN = {'fan':'F AE N','fahn':'F AA N','fun':'F AH N'}


@lru_cache(maxsize=1)
def shenggen_decoder():
    return grammar_decoder(SHENGGEN,FAN,'{term} [fan | fahn | fun]')


def verify_shenggen(audio,first,second):
    for read in (words(first),words(second)):
        if (len(read)!=2 or read[1]!='fan' or read[0] not in
                {'shenggen','shengin','shingen','shengen','shingin','xingen','xingin','xinggen'}):
            raise ValueError('The economist’s given name or surname differs: '+' '.join(read))
    decoder = shenggen_decoder()
    key,score,start,end = locate_sound(audio,decoder,SHENGGEN)
    parts = SHENGGEN[key].split()
    surname = [s for s in decoder.seg() if s.word in FAN]
    # In the Duke interview the second introduction has SH IH NG G AH N.
    # A nasal n at the end of the first syllable or a j in place of g changes the name.
    if (len(parts)!=6 or parts[0]!='SH' or parts[1] not in {'AH','UH','EH','IH','ER'}
            or parts[2]!='NG' or parts[3] not in {'G','K'} or parts[4] not in {'AH','IH','EH','UH'}
            or parts[5]!='N' or score<.09 or not .30*RATE<=end-start<=1.18*RATE
            or len(surname)!=1 or surname[0].word not in {'fan','fahn'} or surname[0].end_frame-surname[0].start_frame<16):
        raise ValueError('Unclear syllable or surname in Shenggen Fan: '+SHENGGEN[key]+' / '+' '.join(s.word for s in surname))
    if any(start < (a+b)/2 < end for a,b in interior_gaps(audio)):
        raise ValueError('A silence interrupts Shenggen')
    return dict(phones=SHENGGEN[key]+' / '+FAN[surname[0].word],score=round(score,3),
                start=round(start/RATE,3),end=round(end/RATE,3))
