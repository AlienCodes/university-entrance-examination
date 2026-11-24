"""Listen to each side of every planned pause, on the isolated take and the distributed audio."""
import base64
from difflib import SequenceMatcher
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tools/tts'))
from textnorm import decade, normalize

from aiden_profile import PAUSE_POLICY as POLICY
RATE = 16000
# The institute spells its initialism I-INCE. Require both I's in the spoken expansion.
NOISE_INITIALS = re.compile(r'\b(?:I|eye)[\s.,-]+(?:I|eye)[\s.,-]+(?:N|en)[\s.,-]+'
                            r'(?:C|see|sea)[\s.,-]+(?:E|ee)\b', re.I)


class JoinError(ValueError):
    pass


class MasteredPhraseError(ValueError):
    def __init__(self, sentence, phrase, start, end, reason):
        self.sentence = sentence
        self.phrase = phrase
        self.includes_previous = isinstance(reason, JoinError)
        super().__init__(f'Sentence {sentence}, phrase {phrase}, {start:.3f}–{end:.3f}s: {reason}')


def spoken_centuries(text):
    # Whisper can print the same century as 1400s or 1,400s.
    return re.sub(r'\b1,?([1-9])00s\b', lambda m: decade(int('1' + m[1] + '00')), text, flags=re.I)


def spoken_spelling(text):
    # These British and American forms have the same spoken word. Preserve
    # grammatical endings, including plural -s, and keep all printed text intact.
    text = spoken_centuries(text)
    # Productive -ize stems actually printed in these papers. Exclude exercise,
    # advise, promise and the other verbs for which this spelling change is invalid.
    spelling = (r'\b(categor|central|character|civil|colon|computer|container|critic|custom|dramat|emphas|'
                r'fertil|financial|general|global|harmon|homogen|incentiv|industrial|institutional|'
                r'interior|ion|jeopard|local|marginal|maxim|mechan|memor|minim|mobil|motor|neutral|'
                r'organ|personal|public|real|recogn|revital|revolution|scrutin|special|standard|'
                r'summar|synchron|systemat|unrecogn|util|victim|visual|vulgar)'
                r'is(e|es|ed|ing|er|ers|ation|ations|ational)\b')
    text = re.sub(spelling, r'\1iz\2', text, flags=re.I)
    text = re.sub(r'\banalys(e|ed|ing)\b', r'analyz\1', text, flags=re.I)
    text = re.sub(r'\bageing\b', 'aging', text, flags=re.I)
    text = re.sub(r'\btravell(?=ed\b|ing\b|ers?\b)', 'travel', text, flags=re.I)
    return re.sub(r'\btonne(s?)\b', r'ton\1', text, flags=re.I)


def words(text):
    text = NOISE_INITIALS.sub('I I N C E', text)
    text = re.sub(r"(?<!\w)O\.?K\.?(?!\w)", "okay", text, flags=re.I)
    text = re.sub(r"\brock\s*['’]n['’]\s*roll\b", 'rock and roll', text, flags=re.I)
    text = re.sub(r'\bman[ -]?made\b', 'man made', text, flags=re.I)
    text = re.sub(r'\bfibre(s?)\b', r'fiber\1', text, flags=re.I)
    # Reuse textnorm's spoken unit and singular/plural rules for both “6.8mm”
    # and “6.8 mm”, the two forms emitted by the independent recognizers.
    text = re.sub(r'(?<=\d)\s+(?=mm\b)', '', text, flags=re.I)
    text = re.sub(r'\bsub[- ]?millimet(?:er|re)(s?)\b', r'submillimeter\1', text, flags=re.I)
    text = spoken_spelling(text)
    text = re.sub(r'\brapa nui\b', 'rapanui', text, flags=re.I)
    text = re.sub(r'\bwindlashed\b', 'wind lashed', text, flags=re.I)
    text = re.sub(r'\bground[ -]fish\b', 'groundfish', text, flags=re.I)
    # In an American reading the tap in Professor Pretty sounds like Priddy.
    text = re.sub(r'\b(professor(?: jules)?) (?:priddy|pritty)\b', r'\1 Pretty', text, flags=re.I)
    text = re.sub(r'\blife[ -]+span(s?)\b', r'lifespan\1', text, flags=re.I)
    text = re.sub(r'\bnorth[ -]+east\b', 'northeast', text, flags=re.I)
    text = re.sub(r'\binter[ -]+modal\b', 'intermodal', text, flags=re.I)
    text = re.sub(r'\bpaint[ -]+brush(es)?\b', r'paintbrush\1', text, flags=re.I)
    # P IH CH B L EH N D in CMUdict. Keep this one word when checking both sides of a pause.
    text = re.sub(r'\bpitch[ -]+blend\b', 'pitchblende', text, flags=re.I)
    text = re.sub(r'\bhally\b','halley',text,flags=re.I)
    text = re.sub(r'\bcounsell(?=ing\b|ed\b|ors?\b)', 'counsel', text, flags=re.I)
    text = re.sub(r'\bwww(?:\.[a-z0-9-]+)+', lambda m:m.group().replace('.', ' dot '), text, flags=re.I)
    # CMUdict gives both surnames M AH0 K F AA1 R L AH0 N. Keep the printed name on screen.
    text = re.sub(r'\bmcfarlane\b', 'macfarlane', text, flags=re.I)
    # The US dictionary transcribes both Dingle and Dingell as D IH NG G AH L.
    # A genuine Tingle has a different initial consonant.
    text = re.sub(r'\bdingell\b','dingle',text,flags=re.I)
    # CMUdict: Berger/Burger B ER G ER, Deane/Dean D IY N, Rasch/Rash R AE SH.
    # Preserve the possessive, the past tense and the speaker's actual title.
    text = re.sub(r"\bthan (?:berger|burger)['’]?s\b", "than Berger's", text, flags=re.I)
    text = re.sub(r'\bdeane?(?= dived? down\b)', 'Deane', text, flags=re.I)
    text = re.sub(r'\b(dr\.?|doctor) phil (?:rasch|rash)\b', 'Doctor Phil Rasch', text, flags=re.I)
    text = re.sub(r'\bu\.?\s*s\.?[ -]+based\b', 'U S based', text, flags=re.I)
    text = re.sub(r'\bgeo[ -]engineering\b', 'geoengineering', text, flags=re.I)
    # Lei Tzu (嫘祖, Léi Zǔ): recognizers also join the two syllables as Leitzu or Leitsu.
    text = re.sub(r'\bLei(?:tzu|tsu)\b', 'Lei Tzu', text, flags=re.I)
    for written, spoken in (('Henry VIII','Henry the eighth'),('Charles II','Charles the second'),
                            ('Amenhotep III','Amenhotep the third'),('Napoleon III','Napoleon the third')):
        text = re.sub(r'\b'+re.escape(written)+r'\b', spoken, text, flags=re.I)
    text = normalize(text.replace('’', "'"))
    # A printed dash separates clauses even when there are no spaces around it.
    text = text.replace('—', ' ').replace('–', ' ')
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    text = text.replace('colour', 'color').replace('centre', 'center').replace('metre', 'meter')
    text = text.replace('organis', 'organiz').replace('customis', 'customiz')
    text = text.replace('civilis', 'civiliz').replace('favour', 'favor').replace('behaviour', 'behavior')
    return re.findall('[a-z0-9]+', text.replace("'", ''))


@lru_cache(maxsize=4096)
def pronunciation(word):
    binary = shutil.which('espeak-ng') or shutil.which('espeak')
    if not binary:
        return ''
    result = subprocess.run([binary, '-q', '--ipa', '-v', 'en-us', '--', word],
                            capture_output=True, text=True, timeout=4)
    return result.stdout.strip() if result.returncode == 0 else ''


def edge_matches(written, heard):
    return written == heard or bool(pronunciation(written) and pronunciation(written) == pronunciation(heard))


def matches(expected, heard):
    if not expected or not heard:
        return False
    if ''.join(expected) == ''.join(heard):
        return True
    if not edge_matches(expected[0], heard[0]) or not edge_matches(expected[-1], heard[-1]):
        return False
    if len(expected) <= 4:
        return len(expected) == len(heard) and all(edge_matches(a,b) for a,b in zip(expected,heard))
    seq = SequenceMatcher(None, expected, heard, autojunk=False)
    matched = sum(block.size for block in seq.get_matching_blocks())
    return (matched >= .8*max(len(expected),len(heard))
            and all(max(b-a,d-c) <= 2 for op,a,b,c,d in seq.get_opcodes() if op != 'equal'))


def isolated(audio, *, padding=2400):
    import numpy as np
    from 听对 import recognizer
    rec = recognizer()
    stream = rec.create_stream()
    stream.accept_waveform(RATE, np.pad(audio,(padding,padding)).astype('float32'))
    rec.decode_stream(stream)
    return stream.result.text


def interior_gaps(audio):
    """Only sustained, near-silent internal regions; stop-consonant closures are usually much shorter."""
    import numpy as np
    hop = RATE // 100
    blocks = audio[:len(audio)//hop*hop].reshape(-1,hop)
    if len(blocks) < 30:
        return []
    db = 10*np.log10(np.mean(blocks.astype('float64')**2,axis=1) + 1e-14)
    quiet = db < min(-48.,float(np.percentile(db,90))-34.)
    edges = np.flatnonzero(np.diff(np.r_[False,quiet,False]))
    return [(int(a*hop),int(b*hop)) for a,b in zip(edges[::2],edges[1::2])
            if b-a >= 15 and a >= 10 and b <= len(db)-10]


def complete_words_at_gap(audio, start, end, expected, first, second):
    # The first low-energy bins can still contain an unvoiced onset. Keep up to
    # 80 ms of the measured quiet interval on each side, with no shared samples.
    # Both halves and a reading of the whole phrase must cover exactly the
    # printed words. The split has to be between two words.
    printed = ''.join(expected)
    if not any(''.join(words(h)) == printed for h in (first, second)):
        return False
    divisions = {(''.join(expected[:i]), ''.join(expected[i:])) for i in range(1,len(expected))}
    for millis in (80, 35):
        context = min(millis * RATE // 1000, (end - start) // 2)
        for listen in (isolated, independent):
            left = ''.join(words(listen(audio[:start + context])))
            right = ''.join(words(listen(audio[end - context:])))
            if (left, right) in divisions:
                return True
    return False


def assess(audio, text, transcript=None, *, recheck=False):
    from aiden_macfarlane import cited_phrase, verify as verify_macfarlane
    from aiden_perkin import cited as has_perkin, verify as verify_perkin, gap_after_attention
    from aiden_diels import cited as has_diels, verify as verify_diels, NAMES as diels_spellings
    expected = words(text)
    transcript = isolated(audio) if transcript is None else transcript
    alternate = None
    historian = None
    if expected == ['quercus', 'suber']:
        from aiden_cork_oak import verify
        alternate = independent(audio)
        pauses = interior_gaps(audio)
        proof = verify(audio, transcript, alternate, pauses)
        return {'text':text, 'heard':transcript, 'second_heard':alternate,
                'botanical_pronunciation':proof,
                'checked_internal_gaps':[[round(a/RATE,3),round(b/RATE,3)] for a,b in pauses]}
    name_evidence = None
    india = None
    star_groups = None
    clock_evidence = None
    inuit_evidence = None
    film_names = None
    psychologist = None
    captain = None
    arctic_advisor = None
    soil_scientist = None
    physicist = None
    geographical = None
    migration_names = None
    ant_tools = None
    falkirk = None
    explorer = None
    turkish_word = None
    chemists = None
    surname = None
    craftsmen = None
    welsh = None
    zappaterra = None
    sevres = None
    fish = None
    opening = None
    ganzfeld = None
    cork_taint = None
    if 'llewyn' in expected:
        from aiden_lynx import verify, pause_after_name
        alternate = independent(audio)
        welsh = verify(audio,expected,transcript,alternate)
    elif 'zappaterra' in expected:
        from aiden_surnames import verify_zappaterra, zappaterra_words
        alternate = independent(audio)
        zappaterra = verify_zappaterra(audio,expected,transcript,alternate)
    elif 'sevres' in expected:
        from aiden_sevres import verify
        alternate = independent(audio)
        sevres = verify(audio,expected,transcript,alternate)
    elif expected == ['cod','sole','perch','and','pollock']:
        from aiden_pronunciation import verify_groundfish_list
        alternate = independent(audio)
        fish = verify_groundfish_list(audio,transcript,alternate)
    elif expected == ['the','ancient','craftsmen']:
        from aiden_pronunciation import verify_ancient_craftsmen
        alternate = independent(audio)
        craftsmen = verify_ancient_craftsmen(audio,transcript,alternate)
    elif expected[:3] == ['the','team','theorizes'] or expected[-2:] == ['norm','referenced']:
        alternate = independent(audio)
        if expected[:3] == ['the','team','theorizes']:
            # The old take is sometimes transcribed correctly only when padded
            # or given the whole sentence. Check the audible opening on its own.
            opening = isolated(audio[:round(2.5*RATE)],padding=0)
            if words(opening)[:3] != expected[:3]:
                raise ValueError(f'The opening the team theorizes is unclear: {opening!r}')
        for text_heard in (transcript,alternate):
            heard = words(text_heard)
            # The baby-language recording lost its initial article and the m in team.
            # The giftedness recording lost the past-participle ending in referenced.
            same_edge = (heard[:3] == expected[:3] if expected[:3] == ['the','team','theorizes']
                         else heard[-2:] == expected[-2:])
            if not same_edge or not matches(expected,heard):
                raise ValueError(f'Unclear printed phrase: {text!r} / {transcript!r} / {alternate!r}')
    elif 'trichloroanisole' in expected:
        from aiden_cork_taint import verify, verify_pause_before_locants
        alternate = independent(audio)
        cork_taint = verify(audio,text,transcript,alternate)
    elif has_perkin(expected):
        alternate = independent(audio)
        chemists = verify_perkin(audio,expected,transcript,alternate)
    elif expected == ['shenggen','fan']:
        from aiden_surnames import verify_shenggen
        alternate = independent(audio)
        surname = verify_shenggen(audio,transcript,alternate)
    elif expected in (['according','to','janzen'], ['angelina','hawley','dolan']):
        from aiden_surnames import verify
        alternate = independent(audio)
        surname = verify(audio,expected,transcript,alternate)
    elif 'ganzfeld' in expected:
        from aiden_ganzfeld import verify
        alternate = independent(audio)
        ganzfeld = verify(audio,expected,transcript,alternate)
    elif 'ceylonese' in expected:
        from aiden_ceylonese import verify
        alternate = independent(audio)
        name_evidence = verify(audio, text, transcript, alternate)
    elif 'decans' in expected:
        from aiden_decans import verify
        alternate = independent(audio)
        star_groups = verify(audio, expected, transcript, alternate)
    elif expected[-3:] == ['notes', 'of', 'ynde']:
        from aiden_india import verify
        alternate = independent(audio)
        india = verify(audio, text, transcript, alternate)
    elif 'fusee' in expected:
        from aiden_fusee import verify
        alternate = independent(audio)
        clock_evidence = verify(audio, text, transcript, alternate)
        alternate = clock_evidence['context_transcript']
    elif 'qaujimajatuqangit' in expected:
        from aiden_inuktitut import verify
        alternate = independent(audio)
        inuit_evidence = verify(audio,text,transcript,alternate)
    elif 'sobchack' in expected:
        from aiden_sobchack import verify
        alternate = independent(audio)
        film_names = verify(audio,text,transcript,alternate)
    elif expected[:1] == ['monbusho'] or expected[-3:] == ['land','mass','aleyska']:
        from aiden_place_names import verify
        alternate = independent(audio)
        geographical = verify(audio,expected,transcript,alternate)
    elif expected == ['brought','na','dene','hunters']:
        from aiden_place_names import verify_na_dene
        alternate = independent(audio)
        geographical = verify_na_dene(audio,transcript,alternate)
    elif 'aleut' in expected:
        from aiden_place_names import verify_migration_names, pause_after_migration_names, pause_before_ancestral_groups
        alternate = independent(audio)
        migration_names = verify_migration_names(audio,expected,transcript,alternate)
    elif has_diels(expected):
        alternate = independent(audio)
        physicist = verify_diels(audio,expected,transcript,alternate)
    elif 'floris' in expected or 'floriss' in expected:
        from aiden_floris import verify
        alternate = independent(audio)
        soil_scientist = verify(audio,expected,transcript,alternate)
    elif expected == ['or','fingers']:
        from aiden_pronunciation import verify_or_fingers
        alternate = independent(audio)
        ant_tools = verify_or_fingers(audio,(transcript,alternate))
    elif 'dreu' in expected:
        from aiden_de_dreu import verify
        alternate = independent(audio)
        psychologist = verify(audio,text,transcript,alternate)
    elif expected == ['dowman','was','determined']:
        from aiden_dowman import verify
        alternate = independent(audio)
        captain = verify(audio,transcript,alternate)
    elif expected[-2:] == ['martin','sommerkorn']:
        from aiden_sommerkorn import verify
        alternate = independent(audio)
        arctic_advisor = verify(audio,transcript,alternate)
    elif expected == ['at','butterley','engineerings','steelworks','in','derbyshire']:
        from aiden_falkirk import verify
        alternate = independent(audio)
        falkirk = verify(audio,transcript,alternate)
    elif expected == ['a','hydraulic','clamp']:
        alternate = independent(audio)
        if any(words(heard) != expected for heard in (transcript, alternate)):
            raise ValueError(f'The final p in hydraulic clamp is unclear: {transcript!r} / {alternate!r}')
    elif expected == ['thor', 'heyerdahl']:
        from aiden_heyerdahl import verify
        alternate = independent(audio)
        explorer = verify(audio,transcript,alternate)
    elif 'shehirlilishtiremediklerimizdensiniz' in expected:
        from aiden_turkish import verify
        alternate = independent(audio)
        turkish_word = verify(audio,text,transcript,alternate)
    elif expected[:3] == ['deane', 'dived', 'down'] or expected[:4] == ['and', 'doctor', 'phil', 'rasch']:
        alternate = independent(audio)
        if any(words(heard) != expected for heard in (transcript, alternate)):
            raise ValueError(f'Unclear past-tense ending or spoken introduction: {transcript!r} / {alternate!r}')
    elif expected[-4:] == ['wind','lashed','infertile','fields'] or expected[-2:] == ['wind','lashed']:
        alternate = independent(audio)
        if any(words(heard) != expected for heard in (transcript, alternate)):
            raise ValueError(f'The Rapanui passage requires the complete adjective wind-lashed: {transcript!r} / {alternate!r}')
    elif expected[:4] == ['from', 'a', 'single', 'thickness']:
        alternate = independent(audio)
        if any(words(heard) != expected for heard in (transcript, alternate)):
            raise ValueError(f'Glass thickness or its units differ: {transcript!r} / {alternate!r}')
    elif cited_phrase(expected):
        alternate = independent(audio)
        historian = verify_macfarlane(audio,expected,transcript,alternate)
    elif NOISE_INITIALS.search(text):
        alternate = independent(audio)
        accepted = all if recheck else any
        if not accepted(NOISE_INITIALS.search(heard) and words(heard) == expected for heard in (transcript, alternate)):
            raise ValueError(f'The five spoken letters I I N C E or their context differ: {transcript!r} / {alternate!r}')
    elif expected[:5] == ['sugars','and','meats','or','oils']:
        # In the printed list of ant baits, one real recording was heard as "chuggers".
        alternate = independent(audio)
        if any(words(heard) != expected for heard in (transcript,alternate)):
            raise ValueError(f'Ant bait names or their context differ: {transcript!r} / {alternate!r}')
    elif recheck:
        alternate = independent(audio)
        if any(words(heard) != expected for heard in (transcript, alternate)):
            raise ValueError(f'Restored recording differs from the printed phrase: {transcript!r} / {alternate!r}')
    elif not matches(expected, words(transcript)):
        alternate = independent(audio)
        # If the two decoders disagree, only the full printed sequence can resolve it.
        if words(alternate) != expected:
            raise ValueError(f'Phrase endpoints or wording differ: {text!r} / {transcript!r} / {alternate!r}')
    sectors = None
    if expected[:4] == ['unlike', 'other', 'export', 'sectors']:
        from aiden_sectors import verify
        sectors = verify(audio, expected)
    gaps = []
    gaps_with_quiet_context = []
    for start,end in interior_gaps(audio):
        left = isolated(audio[:start])
        right = isolated(audio[end:])
        def split_matches(before,after):
            left_words = words(before)
            right_words = words(after)
            if welsh and pause_after_name(audio,start,end,expected,left_words,right_words,welsh):
                return True
            if zappaterra and start/RATE >= zappaterra['end']:
                left_words = zappaterra_words(left_words)
            if migration_names and pause_after_migration_names(expected,left_words,right_words,start,migration_names):
                return True
            if migration_names and pause_before_ancestral_groups(expected,left_words,right_words,end,migration_names):
                return True
            if chemists and gap_after_attention(start,expected,left_words,right_words,chemists):
                return True
            if india and end/RATE < india['start']:
                from aiden_india import TRANSCRIPT_ENDINGS
                for k in (2,1):
                    if ' '.join(right_words[-k:]) in TRANSCRIPT_ENDINGS:
                        right_words = [*right_words[:-k], 'ynde']
                        break
            # A later comma does not change the surname already checked on this
            # waveform. Keep every other word and the far side of the gap intact.
            if geographical and (start+end)/(2*RATE) > geographical['end'] and expected[0] == 'monbusho':
                # This exact waveform has already supplied all three vowels and the final shō.
                # Keep independent recognition of every word following the name.
                tail = next((i for i,token in enumerate(left_words[:4]) if token == expected[1]), None)
                if tail is not None and tail > 0:
                    left_words = ['monbusho', *left_words[tail:]]
                elif 0 < len(left_words) <= 3 and right_words == expected[1:]:
                    left_words = ['monbusho']
            if physicist and expected[0] == 'diels' and start/RATE > physicist['end'] and left_words and left_words[0] in diels_spellings:
                left_words = ['diels', *left_words[1:]]
            if historian and start/RATE > historian['end'] and left_words[:1] == ['mcfarlands']:
                left_words = ['macfarlanes', *left_words[1:]]
            return any(matches(expected[:i],left_words) and matches(expected[i:],right_words)
                       for i in range(1,len(expected)))
        if not split_matches(left,right):
            other_left=independent(audio[:start])
            other_right=independent(audio[end:])
            if not split_matches(other_left,other_right):
                if alternate is None:
                    alternate = independent(audio)
                inuit_gap = None
                if inuit_evidence:
                    from aiden_inuktitut import verify_pause_before_inuit
                    inuit_gap = verify_pause_before_inuit(audio,start,end,expected,left,right,inuit_evidence)
                if inuit_gap:
                    inuit_evidence['separate_words_after_pause'] = inuit_gap
                elif cork_taint and verify_pause_before_locants(audio, start, end, expected, (left, other_left), cork_taint):
                    gaps_with_quiet_context.append([round(start/RATE,3), round(end/RATE,3)])
                elif complete_words_at_gap(audio, start, end, expected, transcript, alternate):
                    gaps_with_quiet_context.append([round(start/RATE,3), round(end/RATE,3)])
                else:
                    raise ValueError(f'Possible break inside a word at {start/RATE:.2f}–{end/RATE:.2f}s: {text!r} / '
                                     f'{left!r} | {right!r}; {other_left!r} | {other_right!r}')
        gaps.append([round(start/RATE,3),round(end/RATE,3)])
    result = {'text':text,'heard':transcript,'checked_internal_gaps':gaps}
    if sectors:
        result['export_sectors_pronunciation'] = sectors
    if gaps_with_quiet_context:
        result['verified_with_quiet_context'] = gaps_with_quiet_context
    if historian is not None:
        result['historian_pronunciation'] = historian
    if alternate is not None:
        result['second_heard']=alternate
    if name_evidence is not None:
        result['ceylonese_pronunciation']=name_evidence
    if star_groups is not None:
        result['decans_pronunciation'] = star_groups
    if india is not None:
        result['ynde_pronunciation'] = india
    if clock_evidence is not None:
        result['fusee_pronunciation']=clock_evidence
    if inuit_evidence is not None:
        result['inuktitut_pronunciation']=inuit_evidence
    if film_names is not None:
        result['film_surnames']=film_names
    if psychologist is not None:
        result['de_dreu_pronunciation']=psychologist
    if captain is not None:
        result['captain_pronunciation']=captain
    if arctic_advisor is not None:
        result['advisor_pronunciation']=arctic_advisor
    if soil_scientist is not None:
        result['floris_pronunciation'] = soil_scientist
    if geographical is not None:
        result['geographic_name'] = geographical
    if migration_names is not None:
        result['migration_names'] = migration_names
    if physicist is not None:
        result['diels_pronunciation'] = physicist
    if ant_tools is not None:
        result['spoken_or_fingers'] = ant_tools
    if falkirk is not None:
        result['engineering_possessive']=falkirk
    if explorer is not None:
        result['heyerdahl_pronunciation']=explorer
    if turkish_word is not None:
        result['turkish_word']=turkish_word
    if chemists is not None:
        result['chemists_surnames']=chemists
    if surname is not None:
        result['surname_pronunciation']=surname
    if craftsmen is not None:
        result['craftsmen_pronunciation']=craftsmen
    if welsh is not None:
        result['welsh_name']=welsh
    if zappaterra is not None:
        result['physician_surname']=zappaterra
    if sevres is not None:
        result['sevres_pronunciation']=sevres
    if fish is not None:
        result['groundfish_list']=fish
    if opening is not None:
        result['unpadded_opening_excerpt']=opening
    if ganzfeld is not None:
        result['ganzfeld_pronunciation']=ganzfeld
    if cork_taint is not None:
        result['cork_taint_pronunciation']=cork_taint
    return result


def reference(audio):
    """10 ms energy in each intact take, retained independently of the compressed media."""
    import numpy as np
    block=RATE//100
    frames=audio[:len(audio)//block*block].reshape(-1,block)
    db=10*np.log10(np.mean(frames.astype('float64')**2,axis=1)+1e-14)
    rel=np.clip(np.rint(db-np.percentile(db,90)),-90,20).astype('int8')
    return {'samples16':len(audio),'energy10ms':base64.b64encode(rel.tobytes()).decode('ascii')}


def verify_reference(audio, original):
    import numpy as np
    if abs(len(audio)-original['samples16'])>RATE*.004:
        raise ValueError('The duration of this phrase differs from its intact recording')
    before=np.frombuffer(base64.b64decode(original['energy10ms']),dtype='int8').astype(int)
    after=np.frombuffer(base64.b64decode(reference(audio)['energy10ms']),dtype='int8').astype(int)
    length=min(len(before),len(after))
    if length<12:raise ValueError('Speech window too short for boundary verification')
    # Allow the fixed encoder latency. Never warp time across a suspected dropout.
    first=before[4:length-4]
    offsets=range(-4,5)
    lag=min(offsets,key=lambda i:np.mean(np.minimum(abs(first-after[4+i:length-4+i]),25)))
    second=after[4+lag:length-4+lag]
    missing=(first>-27)&(second<-47)
    # A 70 ms loss of clearly voiced material is longer than codec pre-echo or one RMS bin.
    if np.convolve(missing.astype(int),np.ones(7,dtype=int),'valid').max(initial=0)>=7:
        raise ValueError('An audible portion of the original phrase is missing from the encoded audio')
    return lag*10


@lru_cache(maxsize=1)
def whisper():
    import sherpa_onnx
    path=ROOT/'tools/tts/models/sherpa-onnx-whisper-base.en'
    return sherpa_onnx.OfflineRecognizer.from_whisper(encoder=str(path/'base.en-encoder.int8.onnx'),
        decoder=str(path/'base.en-decoder.int8.onnx'),tokens=str(path/'base.en-tokens.txt'),num_threads=3)


def independent(audio):
    rec=whisper();stream=rec.create_stream()
    stream.accept_waveform(RATE,audio)
    rec.decode_stream(stream)
    return stream.result.text


def verify_join(left,right):
    left_ref, left_heard = words(left['text']), words(left['second_heard'])
    right_ref, right_heard = words(right['text']), words(right['second_heard'])
    ends=bool(left_heard and edge_matches(left_ref[-1], left_heard[-1]))
    starts=bool(right_heard and edge_matches(right_ref[0], right_heard[0]))
    if left_ref[-1:] == ['groundfish'] and right_ref == ['cod','sole','perch','and','pollock']:
        if ends and right.get('groundfish_list',{}).get('phones') == 'K AA D':
            return
        raise JoinError('The groundfish example needs a complete groundfish and an audible cod')
    if not (ends or starts):
        raise JoinError(f'Both sides of the pause differ: {left["text"]!r} / {left["second_heard"]!r}, '
                         f'{right["text"]!r} / {right["second_heard"]!r}')


def check_media(path, timing):
    import numpy as np
    data = subprocess.check_output(['ffmpeg','-v','error','-xerror','-i',str(path),'-map','0:a:0',
                                   '-ac','1','-ar',str(RATE),'-f','f32le','-'])
    audio = np.frombuffer(data,dtype='<f4')
    results=[]
    for sentence in timing['sentences']:
        number = sentence['k']
        proof = timing['narration_review'][f'{timing["lesson"]}:{number}']
        phrases = proof['phrases']
        spans = sentence['parts']
        if len(phrases) != len(spans) or not phrases:
            raise ValueError(f'Sentence {number}: incomplete phrase timestamps')
        if words(' '.join(p['text'] for p in phrases)) != words(sentence['read']):
            raise ValueError(f'Sentence {number}: the recorded phrases do not reconstruct the source')
        previous=None
        for j,(phrase,(start,end)) in enumerate(zip(phrases,spans),1):
            if not 0 <= start < end <= len(audio)/RATE + .002:
                raise ValueError(f'Sentence {number}, phrase {j}: invalid audio interval')
            try:
                segment=audio[round(start*RATE):round(end*RATE)]
                item = assess(segment,phrase['text'])
                item['source_lag_ms']=verify_reference(segment,phrase['reference'])
                if len(phrases)>1:
                    if 'second_heard' not in item:
                        item['second_heard']=independent(segment)
                    if previous:verify_join(previous,item)
                    previous=item
            except ValueError as error:
                raise MasteredPhraseError(number, j, start, end, error) from error
            results.append(dict(sentence=number,phrase=j,start=start,end=end,**item))
    with Path(path).open('rb') as stream:
        digest = hashlib.file_digest(stream,'sha256').hexdigest()
    return {'policy':POLICY,'sha256':digest,'phrases':len(results),'checks':results,'passed':True}


if __name__ == '__main__':
    from lesson import PID, PROJECT, save
    media, report = map(Path,sys.argv[1:])
    timing = json.loads((PROJECT/'audio/timings.json').read_text())['cet4_male'][PID]
    save(report,check_media(media,timing))
