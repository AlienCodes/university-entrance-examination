"""Verify whole words in order in the original Aiden reading and its encoded audio."""
from difflib import SequenceMatcher
from functools import lru_cache
from itertools import product
from pathlib import Path
import re

POLICY = 'ordered-spoken-words-v1'


# These are spelling changes in the printed books which preserve the pronunciation.
# In particular, keep tense, number, comparatives, negatives and spoken numbers intact.
SPELLINGS = {
    'labour':'labor', 'labours':'labors', 'labourers':'laborers',
    'odour':'odor', 'odours':'odors', 'rigours':'rigors', 'valour':'valor',
    'neighbour':'neighbor', 'neighbours':'neighbors', 'harbour':'harbor', 'harbours':'harbors',
    'storey':'story', 'storeys':'stories', 'judgement':'judgment', 'judgements':'judgments',
    'programme':'program', 'programmes':'programs', 'theatre':'theater', 'theatres':'theaters',
    'defence':'defense', 'defences':'defenses', 'practised':'practiced', 'practising':'practicing',
    'channelled':'channeled', 'fuelled':'fueled', 'signalled':'signaled',
    'modelled':'modeled', 'modelling':'modeling', 'millilitres':'milliliters', 'grey':'gray',
    'archaeologists':'archeologists', 'archaeologist':'archeologist',
    'artefacts':'artifacts', 'sceptical':'skeptical', 'skilful':'skillful',
    'unravelling':'unraveling', 'odourless':'odorless', 'meagre':'meager',
    'leukaemia':'leukemia', 'archipelagoes':'archipelagos', 'palaeontologist':'paleontologist',
    'litre':'liter', 'litres':'liters', 'flavour':'flavor', 'faecal':'fecal',
    'paediatrics':'pediatrics', 'manoeuvre':'maneuver', 'cocoanuts':'coconuts',
}

# Both spellings occur in the two recognizers' readings of these printed compounds.
# List the exact split so an arbitrary new word boundary cannot be accepted.
COMPOUND_SPELLINGS = {
    ('counter', 'productive'), ('counter', 'intuitively'), ('north', 'western'),
    ('south', 'western'), ('semi', 'circular'), ('re', 'tooling'), ('cork', 'strippers'),
    ('counter', 'intuitive'), ('re', 'enactment'), ('bar', 'code'), ('bar', 'codes'),
    ('best', 'selling'), ('brain', 'stem'), ('bow', 'strings'), ('code', 'names'),
    ('data', 'bank'), ('film', 'maker'), ('fire', 'fighting'), ('glass', 'house'),
    ('glass', 'makers'), ('hard', 'wired'), ('main', 'spring'), ('micro', 'technology'),
    ('night', 'dress'), ('rain', 'forests'), ('sound', 'track'), ('steam', 'ships'),
    ('sub', 'continent'), ('super', 'colony'), ('super', 'hot'), ('super', 'viruses'),
    ('thunder', 'clouds'), ('time', 'keeping'), ('train', 'spotters'), ('train', 'spotting'),
    ('watch', 'towers'), ('wind', 'blown'), ('co', 'operate'), ('co', 'ordinate'),
    ('corn', 'flakes'), ('on', 'line'), ('anti', 'fungal'), ('anti', 'social'),
    ('re', 'routing'), ('re', 'directed'), ('blue', 'stocking'), ('for', 'ever'), ('steel', 'works'),
}


@lru_cache(maxsize=1)
def dictionary():
    try:
        from pocketsphinx import get_model_path
    except ModuleNotFoundError:
        return {}
    entries = {}
    data = Path(get_model_path()) / 'en-us/cmudict-en-us.dict'
    for line in data.read_text(encoding='utf-8').splitlines():
        token, _, phones = line.partition(' ')
        word = re.sub(r'\(\d+\)$', '', token)
        entries.setdefault(word, set()).add(phones)
    return entries


@lru_cache(maxsize=8192)
def sounds(tokens):
    lexicon = dictionary()
    choices = [lexicon.get(token) for token in tokens]
    if any(not readings for readings in choices):
        return frozenset()
    return frozenset(' '.join(parts) for parts in product(*choices))


def same_words(expected, observed):
    if not expected or not observed:
        return False
    expected = tuple(SPELLINGS.get(t, t) for t in expected)
    observed = tuple(SPELLINGS.get(t, t) for t in observed)
    if expected == observed:
        return True

    @lru_cache(maxsize=None)
    def covers(i, j):
        if i == len(expected) or j == len(observed):
            return i == len(expected) and j == len(observed)
        left, right = expected[i], observed[j]
        prise_away = ({left, right} == {'prise', 'prize'}
                      and expected[i+1:i+2] == observed[j+1:j+2] == ('away',))
        # US "loch" and "lock" are both L AA K in CMUdict. The printed
        # Scottish phrase has the plural /s/ on both readings.
        sea_lochs = ({left, right} == {'lochs', 'locks'} and i > 0 and j > 0
                     and expected[i-1] == observed[j-1] == 'sea')
        if left == right or prise_away or sea_lochs or (sounds((left,)) and sounds((left,)) == sounds((right,))):
            if covers(i + 1, j + 1):
                return True
        # A compound may have been printed as one word and decoded as two (or vice versa).
        # Equal letters alone would also accept "nowhere" as "now here".
        for size in range(2, 5):
            for a, b in ((size, 1), (1, size)):
                x, y = expected[i:i+a], observed[j:j+b]
                if (len(x) == a and len(y) == b and ''.join(x) == ''.join(y)
                        and (x in COMPOUND_SPELLINGS or y in COMPOUND_SPELLINGS
                             or (sounds(x) and sounds(x) == sounds(y))) and covers(i+a, j+b)):
                    return True
        return False

    return covers(0, 0)


def hear_differences(audio, text, secondary, observations=None):
    """Listen to a differing word with real neighbouring words on both sides."""
    from aiden_boundaries import RATE, independent, isolated, words
    from aiden_ceylonese import timed_words

    expected = words(text)
    times = timed_words(audio)
    heard = [t for t, _ in times]
    if same_words(expected, heard):
        # Timing comes from the primary recognizer. Require an independent whole reading as well.
        if same_words(expected, words(secondary)):
            return {'timed_and_independent': True}
        return None
    ops = SequenceMatcher(None, expected, heard, autojunk=False).get_opcodes()
    evidence = []
    for index, (operation, a, b, c, d) in enumerate(ops):
        if operation == 'equal' or same_words(expected[a:b], heard[c:d]):
            continue
        left = min(3, a - ops[index-1][1]) if index and ops[index-1][0] == 'equal' else 0
        right = min(3, ops[index+1][2] - b) if index+1 < len(ops) and ops[index+1][0] == 'equal' else 0
        if not left and not right:
            return None
        goal = expected[a-left:b+right]
        begin = max(0, times[c-left][1] - round(.045*RATE)) if c-left < len(times) else len(audio)
        stop = min(len(audio), times[d+right][1]) if d+right < len(times) else len(audio)
        if stop <= begin:
            return None
        window = audio[begin:stop]
        first, second = isolated(window), independent(window)
        item = {'printed_words': [a, b], 'checked_words': [a-left, b+right], 'expected_window':' '.join(goal),
                'start_sample': begin, 'end_sample': stop, 'heard': first, 'second_heard': second}
        if observations is not None:
            observations.append(item)
        if not all(same_words(goal, words(h)) for h in (first, second)):
            return None
        evidence.append(item)
    return {'windows': evidence} if evidence else None


# These spellings occur in speech-recognition output from the verified name checkers.
# Apply a spelling only when that checker has measured the sounds on this very phrase.
MEASURED_NAMES = {
    'pithecanthropus_reading': dict.fromkeys(
        ('pithocanthropus','pithacanthropus','pythacanthropus','pythakantropus','pithakentropus',
         'pithicanthropus','pythocanthropus','pythaganthropus'), 'pithecanthropus'),
    'isabela_reading': {'isabella':'isabela'},
    'clemmonss_reading': dict.fromkeys(('clemens','clemenss','clemons','clemonss','clemmons'), 'clemmonss'),
    'dollos_reading': dict.fromkeys(('dalos','dallos','dollows','dallows'), 'dollos'),
    'gharib_reading': {'garib':'gharib'},
    'existent_reading': {'existing':'existent'},
    'toeless_reading': dict.fromkeys(('tolless','tollis','toless','toalous','tolus'), 'toeless'),
    'autoganzfeld_reading': {prefix+suffix:'autoganzfeld' for prefix in ('otto','auto','otto ','auto ')
                             for suffix in ('ganzfeld','gansfeld','gensfeld')},
    'halley_pronunciation': {'hallie':'halley'},
    'eigg_pronunciation': {'egg':'eigg', 'eig':'eigg'},
    'ganzfeld_pronunciation': {'gansfeld':'ganzfeld', 'gensfeld':'ganzfeld'},
    'stepwell_tiers': {'tears':'tiers'},
    'surname_pronunciation': {'koole':'kuhl', 'holly':'hawley', 'jansen':'janzen', 'amagoalick':'amagoalik'},
    'floris_pronunciation': {'florus':'floris', 'floress':'floriss'},
    'diels_pronunciation': {'deals':'diels'},
    'advisor_pronunciation': {'zommercorn':'sommerkorn'},
    'film_surnames': {'sobchak':'sobchack'},
    'ceylonese_pronunciation': {'silanese':'ceylonese'},
    'fusee_pronunciation': {'fuse':'fusee'},
    'captain_pronunciation': {'dao man':'dowman'},
    'geographic_name': {'mon boo show':'monbusho', 'na dani':'na dene'},
    'migration_names': {'eliut':'aleut', 'nadenese':'na denes', 'nade ni':'na dene'},
    'heyerdahl_pronunciation': {'door hired all':'thor heyerdahl'},
    'inuktitut_pronunciation': {'koyi maya tok nit':'qaujimajatuqangit'},
    'kite_researchers': {'clemens':'clemmons','clemons':'clemmons','garib':'gharib'},
}


def measured_words(tokens, evidence):
    ynde = evidence.get('ynde_pronunciation', {})
    if (ynde.get('phones') in {'IH N D', 'AY N D'} and ynde.get('confidence', 0) >= .16
            and tokens[-3:] in (['notes', 'of', 'ind'], ['notes', 'of', 'inde'])):
        tokens = tokens[:-1] + ['ynde']
    # The free recognizers write this two-word name as “Quircus Subar” even when
    # the phonetic check detects both K W ER K AH S and S UW B ER on the same audio.
    oak = evidence.get('botanical_pronunciation', {})
    if (evidence.get('text', '').strip(' ,.;:').casefold() == 'quercus suber'
            and oak.get('heard') == ['quercus', 'suber'] and len(tokens) == 2
            and tokens[0] in {'quercus', 'quircus', 'quirkus', 'quirkous'}
            and tokens[1] in {'suber', 'subar', 'subaru'}):
        return ['quercus', 'suber']
    value = ' ' + ' '.join(tokens) + ' '
    for key, spellings in MEASURED_NAMES.items():
        if evidence.get(key):
            for heard, written in spellings.items():
                value = value.replace(' '+heard+' ', ' '+written+' ')
    return value.split()


def known_span(tokens):
    speech = ' ' + ' '.join(SPELLINGS.get(w, w) for w in tokens) + ' '
    for span in ('with modeled birds', 'appreciate the mathematical way'):
        if ' ' + span + ' ' in speech:
            return span
    return None


def check_known_span(audio, span):
    """Read the affected words from audio between their two spoken neighbours."""
    from aiden_boundaries import RATE, independent, isolated, words
    from aiden_ceylonese import timed_words
    from aiden_pronunciation import grammar_decoder, locate_sound

    target = span.split()
    timed = timed_words(audio)
    tokens = [w for w, _ in timed]
    pairs = [(a,b) for a,w in enumerate(tokens) if w == target[0]
             for b in range(a+1,min(len(tokens), a+len(target)+2)) if tokens[b] == target[-1]]
    if len(pairs) != 1:
        raise ValueError(f'Could not locate both spoken neighbours of {span!r}')
    left, right = pairs[0]
    begin = max(0, timed[left][1]-round(.045*RATE))
    end = min(len(audio),timed[right+1][1]) if right+1 < len(timed) else len(audio)
    segment = audio[begin:end]
    first, second = isolated(segment), independent(segment)
    # Word timestamps can include the preceding "to" or the start of "arranged".
    # Accept neighbouring printed words, while requiring the entire target in both readings.
    def contains_target(reading):
        heard = words(reading)
        return any(same_words(target, heard[i:i+len(target)]) for i in range(len(heard)-len(target)+1))

    if not all(contains_target(t) for t in (first, second)):
        raise ValueError(f'Incomplete {span!r} in the recording: {first!r} / {second!r}')
    if span == 'with modeled birds':
        forms = {'complete':'M AA D AH L D','bare':'M AA D AH L','plural':'M AA D AH L Z'}
        context = {'with':'W IH DH','birds':'B ER D Z','arranged':'ER EY N JH D'}
        grammar = '[with] {term} [birds] [arranged]'
    else:
        forms = {'complete':'DH AH M AE TH AH M AE T IH K AH L',
                 'weak':'DH IH M AE TH AH M AE T IH K AH L',
                 'reduced':'AH M AE TH AH M AE T IH K AH L',
                 'bare':'M AE TH AH M AE T IH K AH L','bare-short':'M AE TH M AE T IH K AH L'}
        context = {'to':'T UW','appreciate':'AH P R IY SH IY EY T','way':'W EY','of':'AH V'}
        grammar = '[to] [appreciate] {term} [way] [of]'
    decoder = grammar_decoder(forms, context, grammar)
    form, score, _, _ = locate_sound(segment, decoder, forms)
    if form not in {'complete','weak','reduced'}:
        raise ValueError(f'The final consonant or unstressed article in {span!r} is unclear: {form}')
    return dict(span=span, start_sample=begin, end_sample=end, heard=first, second_heard=second,
                pronunciation=forms[form], score=round(score,4))


def report_words(lesson, narration):
    """Reuse full word readings only across matching MP3 and AAC waveforms."""
    from aiden_boundaries import words
    mp3, aac = narration['mp3_check'], narration['mp4_check']
    if (not mp3['passed'] or not aac['passed'] or aac['reference_mp3_sha256'] != mp3['sha256']
            or aac['phrases'] != mp3['phrases'] or len(aac['checks']) != aac['phrases']):
        raise ValueError('Inconsistent MP3 and AAC listening evidence')
    originals = [((n, j), phrase) for n in range(1, len(narration['sentences'])+1)
                 for j, phrase in enumerate(narration['sentences'][f'{lesson}:{n}']['phrases'], 1)]
    pending = []
    total = 0
    for (address, raw), source, encoded in zip(originals, mp3['checks'], aac['checks'], strict=True):
        wave = encoded['mp3_waveform']
        if (any((r['sentence'], r['phrase']) != address or r['text'] != raw['text'] for r in (source, encoded))
                or (source['start'], source['end']) != (encoded['start'], encoded['end'])
                or wave['worst_window_correlation'] < .93 or wave['average_correlation'] < .985
                or wave['max_level_difference_db'] > 1.6):
            raise ValueError(f'{lesson} {address} has inconsistent text, timing or AAC evidence')
        text = raw['text']
        if lesson == 'C6T4P1' and address == (10, 1):
            # The paper prints “a few $1,000 honoraria”. Older narration
            # metadata expanded the attributive amount with a plural dollar.
            text = text.replace('one thousand dollars honoraria', 'one thousand dollar honoraria')
        expected = words(text)
        if not expected:
            raise ValueError(f'{lesson} {address} has an empty spoken phrase')
        total += len(expected)
        span = known_span(expected)
        intact = not span or all(row.get('word_detail',{}).get('span') == span for row in (source, encoded))
        if not intact or not any(same_words(expected, measured_words(words(row[key]), row))
                                 for row in (source, encoded) for key in ('heard', 'second_heard') if row.get(key)):
            pending.append({'sentence':address[0], 'phrase':address[1], 'text':text,
                            'source_take_sha256':raw['sha256'], 'start':encoded['start'], 'end':encoded['end']})
    return {'phrases':len(originals), 'spoken_words':total, 'to_listen':pending}
