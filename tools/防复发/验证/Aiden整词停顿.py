"""Verify the recorded sectors incident, a clean join and a planted within-word mute."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
PROJECT=ROOT/'雅思/学术阅读'
sys.path.insert(0,str(PROJECT/'tools'))
from aiden_boundaries import independent, reference, verify_join, verify_reference
import numpy as np

def rejects(fn,*args):
    try:
        fn(*args)
    except ValueError:
        return
    raise AssertionError('A known broken phrase was accepted')

def main(listen):
    folder=PROJECT/'审校/Aiden词内断音'
    bad=json.loads((folder/'旧版证据.json').read_text())
    wave=folder/'旧版第3句停顿.flac'
    assert hashlib.sha256(wave.read_bytes()).hexdigest()==bad['sha256']
    phrases=bad['observed']
    if listen:
        import soundfile as sf
        raw,sr=sf.read(wave,dtype='float32')
        assert sr==16000
        for phrase,(a,b) in zip(phrases,bad['clip_16khz'],strict=True):
            phrase['second_heard']=independent(raw[a:b])
    rejects(verify_join,*phrases)
    intact=[{'text':written,'second_heard':heard} for written,heard in bad['single_word_previous_sentence']]
    verify_join(*intact)
    sample=np.random.default_rng(235).normal(0,.08,24000).astype('float32')
    ref=reference(sample)
    verify_reference(sample*.81,ref)
    changed=sample.copy();changed[10000:14480]=0
    rejects(verify_reference,changed,ref)
    rejects(verify_reference,sample[:-4480],ref)
    print('旧版 sectors 的真实断点与人为词内静音均被拦截，完整衔接通过。')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--audio',action='store_true')
    main(ap.parse_args().audio)
