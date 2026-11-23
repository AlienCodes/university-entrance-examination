"""Check the final AAC against each intact take and the actual certified MP3."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from scipy.signal import correlate

from aiden_boundaries import RATE, assess, independent, interior_gaps, isolated, verify_join, verify_reference, words
from aiden_profile import PAUSE_POLICY, confirm
from lesson import PROJECT, PID, save


def pcm(path):
    data=subprocess.check_output(['ffmpeg','-v','error','-xerror','-i',str(path),'-map','0:a:0',
                                  '-ac','1','-ar',str(RATE),'-f','f32le','-'])
    return np.frombuffer(data,dtype='<f4')


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def compare_waveforms(source, encoded):
    """Use one fixed codec delay. Any altered voiced 25 ms window rejects the track."""
    margin=64
    if len(source)!=len(encoded) or len(source)<margin*2+400:
        raise ValueError('Encoded phrase duration differs from its certified MP3')
    def align(offset):
        return encoded[margin+offset:len(encoded)-margin+offset]
    original=source[margin:-margin]
    lag=int(np.argmax(correlate(encoded,original,mode='valid',method='fft')))-margin
    width=RATE//40
    count=len(original)//width*width
    a=original[:count].reshape(-1,width).astype('float64')
    b=align(lag)[:count].reshape(-1,width).astype('float64')
    if count<len(original):
        a=np.vstack((a,original[-width:]))
        b=np.vstack((b,align(lag)[-width:]))
    ap=np.mean(a*a,axis=1)
    bp=np.mean(b*b,axis=1)
    active=np.maximum(ap,bp)>max(1.e-6,float(ap.max())*1.e-4)
    if not np.any(active):
        raise ValueError('No speech was available to compare')
    similarity=(np.mean(a*b,axis=1)/(np.sqrt(ap*bp)+1.e-15))[active]
    level=np.abs(10*np.log10((bp[active]+1.e-15)/(ap[active]+1.e-15)))
    result=dict(lag_samples=lag,worst_window_correlation=round(float(similarity.min()),6),
                average_correlation=round(float(similarity.mean()),6),max_level_difference_db=round(float(level.max()),3))
    if similarity.min()<.93 or similarity.mean()<.985 or level.max()>1.6:
        raise ValueError('The final AAC differs audibly from the certified audio: '+str(result))
    return result


def inspect_phrase(source, encoded, certified, raw, multi):
    # Always compare the actual signals before using a certified spelling.
    comparison=compare_waveforms(source,encoded)
    lag=verify_reference(encoded,raw['reference'])
    try:
        observed=assess(encoded,certified['text'])
    except ValueError as error:
        if not str(error).startswith('Phrase endpoints or wording differ:'):
            raise
        printed=words(certified['text'])
        first=isolated(encoded)
        heard=words(first)
        exact_source=any(words(certified.get(k,''))==printed for k in ('heard','second_heard'))
        if not exact_source or len(heard)!=len(printed) or sum(x!=y for x,y in zip(heard,printed))!=1:
            raise
        # Some decoders change a single spelling after AAC compression (for example Māori marae).
        # Also check that there is no new acoustic gap anywhere in the encoded word.
        gaps=interior_gaps(encoded)
        previous=interior_gaps(source)
        if any(not any(abs(a-x)<=RATE*.02 and abs(b-y)<=RATE*.02 for x,y in previous) for a,b in gaps):
            raise ValueError('The AAC introduced a new pause') from error
        observed=dict(text=certified['text'],heard=first,second_heard=independent(encoded),
                      certified_spelling=certified['text'],checked_internal_gaps=[[a/RATE,b/RATE] for a,b in gaps])
    if multi and 'second_heard' not in observed:
        observed['second_heard']=independent(encoded)
    return dict(**observed,source_lag_ms=lag,mp3_waveform=comparison)


def check(video, timing, certified_mp3):
    confirm(timing)
    certificate=timing['phrase_audio_check']
    if sha(certified_mp3)!=certificate['sha256']:
        raise ValueError('The reference MP3 differs from the published audio certificate')
    source=pcm(certified_mp3)
    encoded=pcm(video)
    evidence=[]
    for row in certificate['checks']:
        n,j=row['sentence'],row['phrase']
        recording=timing['narration_review'][f'{timing["lesson"]}:{n}']['phrases']
        a,b=[round(t*RATE) for t in (row['start'],row['end'])]
        if b>min(len(source),len(encoded)) or row['text']!=recording[j-1]['text']:
            raise ValueError(f'Sentence {n}, phrase {j} differs from the certified source')
        try:
            item=inspect_phrase(source[a:b],encoded[a:b],row,recording[j-1],len(recording)>1)
            if j>1:
                verify_join(evidence[-1],item)
        except ValueError as error:
            raise ValueError(f'Sentence {n}, phrase {j}: {error}') from error
        evidence.append(dict(sentence=n,phrase=j,start=row['start'],end=row['end'],**item))
    if len(evidence)!=certificate['phrases']:
        raise ValueError('Incomplete AAC listening report')
    return dict(policy=PAUSE_POLICY,sha256=sha(video),reference_mp3_sha256=certificate['sha256'],
                phrases=len(evidence),checks=evidence,passed=True)


if __name__=='__main__':
    video,output=map(Path,sys.argv[1:])
    timing=json.loads((PROJECT/'audio/timings.json').read_text())['cet4_male'][PID]
    save(output,check(video,timing,PROJECT/'audio'/timing['file']))
