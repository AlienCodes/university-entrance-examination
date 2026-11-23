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
from textnorm import normalize

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


def words(text):
    text = NOISE_INITIALS.sub('I I N C E', text)
    text = re.sub(r"(?<!\w)O\.?K\.?(?!\w)", "okay", text, flags=re.I)
    text = re.sub(r"\brock\s*['’]n['’]\s*roll\b", 'rock and roll', text, flags=re.I)
    text = re.sub(r'\bman[ -]?made\b', 'man made', text, flags=re.I)
    text = re.sub(r'\bfibre(s?)\b', r'fiber\1', text, flags=re.I)
    text = re.sub(r'\bemphasis(e|es|ed|ing)\b', r'emphasiz\1', text, flags=re.I)
    text = re.sub(r'\bcriticis(e|es|ed|ing)\b', r'criticiz\1', text, flags=re.I)
    text = re.sub(r'\bvulgarisation(s?)\b', r'vulgarization\1', text, flags=re.I)
    # P IH CH B L EH N D in CMUdict. Keep this one word when checking both sides of a pause.
    text = re.sub(r'\bpitch[ -]+blend\b', 'pitchblende', text, flags=re.I)
    text = re.sub(r'\bcounsell(?=ing\b|ed\b|ors?\b)', 'counsel', text, flags=re.I)
    text = re.sub(r'\bwww(?:\.[a-z0-9-]+)+', lambda m:m.group().replace('.', ' dot '), text, flags=re.I)
    # CMUdict gives both surnames M AH0 K F AA1 R L AH0 N. Keep the printed name on screen.
    text = re.sub(r'\bAlan McFarlane\b', 'Alan Macfarlane', text, flags=re.I)
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
    text = text.replace('travell', 'travel').replace('organis', 'organiz').replace('customis', 'customiz')
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


def isolated(audio):
    import numpy as np
    from 听对 import recognizer
    rec = recognizer()
    stream = rec.create_stream()
    stream.accept_waveform(RATE, np.pad(audio,(2400,2400)).astype('float32'))
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


def assess(audio, text, transcript=None):
    expected = words(text)
    transcript = isolated(audio) if transcript is None else transcript
    alternate = None
    if expected == ['quercus', 'suber']:
        from aiden_cork_oak import verify
        alternate = independent(audio)
        pauses = interior_gaps(audio)
        proof = verify(audio, transcript, alternate, pauses)
        return {'text':text, 'heard':transcript, 'second_heard':alternate,
                'botanical_pronunciation':proof,
                'checked_internal_gaps':[[round(a/RATE,3),round(b/RATE,3)] for a,b in pauses]}
    name_evidence = None
    if 'ceylonese' in expected:
        from aiden_ceylonese import verify
        alternate = independent(audio)
        name_evidence = verify(audio, text, transcript, alternate)
    elif NOISE_INITIALS.search(text):
        alternate = independent(audio)
        if not any(NOISE_INITIALS.search(heard) and words(heard) == expected for heard in (transcript, alternate)):
            raise ValueError(f'The five spoken letters I I N C E or their context differ: {transcript!r} / {alternate!r}')
    elif not matches(expected, words(transcript)):
        alternate = independent(audio)
        # If the two decoders disagree, only the full printed sequence can resolve it.
        if words(alternate) != expected:
            raise ValueError(f'Phrase endpoints or wording differ: {text!r} / {transcript!r} / {alternate!r}')
    gaps = []
    for start,end in interior_gaps(audio):
        left = isolated(audio[:start])
        right = isolated(audio[end:])
        def split_matches(before,after):
            return any(matches(expected[:i],words(before)) and matches(expected[i:],words(after))
                       for i in range(1,len(expected)))
        if not split_matches(left,right):
            other_left=independent(audio[:start])
            other_right=independent(audio[end:])
            if not split_matches(other_left,other_right):
                raise ValueError(f'Possible break inside a word at {start/RATE:.2f}–{end/RATE:.2f}s: {text!r} / '
                                 f'{left!r} | {right!r}; {other_left!r} | {other_right!r}')
        gaps.append([round(start/RATE,3),round(end/RATE,3)])
    result = {'text':text,'heard':transcript,'checked_internal_gaps':gaps}
    if alternate is not None:
        result['second_heard']=alternate
    if name_evidence is not None:
        result['ceylonese_pronunciation']=name_evidence
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
