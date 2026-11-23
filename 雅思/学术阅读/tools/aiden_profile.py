"""Identity of the fixed IELTS narrator chosen from the recorded audition."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / '声音试听'))
from sample import DIRECTION, MODEL, REVISION

SPEAKER = 'Aiden'
PAUSE_POLICY = 'intact-phrase-v1'
PROFILE = dict(speaker=SPEAKER, model=MODEL, model_revision=REVISION, direction=DIRECTION,
               language='English', runtime='qwen-tts==0.1.1', inference='cpu-float32-sdpa',
               audition_sha256='f9173e2c7ff49ea3f8675ea9ab6784cf7d7e989c83b1da2da6bd6d2395ed52cf')
IDENTITY = hashlib.sha256(json.dumps(PROFILE, sort_keys=True).encode()).hexdigest()


def audio_asset(lesson_dir, *, source_revision=None):
    folder=Path(lesson_dir)
    rows=[line.split('\t')[0] for line in (folder/'双语精读.tsv').read_text().splitlines() if line]
    pron=json.loads((folder/'篇目信息.json').read_text()).get('pronunciation',{})
    root=PROJECT.parents[1]
    files=[Path(__file__),PROJECT/'tools/aiden_audio.py',PROJECT/'tools/aiden_boundaries.py',PROJECT/'tools/audio_lesson.py',PROJECT/'声音试听/sample.py',
           root/'六级/tools/make_audio.py',root/'tools/tts/textnorm.py',root/'tools/tts/voices.json',
           root/'tools/tts/pronunciations.json',root/'tools/tts/gaokao_tts.py']
    if any('quercus suber' in row.lower() for row in rows):
        oak=PROJECT/'tools/aiden_cork_oak.py'
        if source_revision is None or subprocess.run(
                ['git','cat-file','-e',source_revision+':'+oak.relative_to(root).as_posix()],
                cwd=root,capture_output=True).returncode==0:
            files.append(oak)
    key=hashlib.sha256(json.dumps([rows,pron,IDENTITY],ensure_ascii=False).encode())
    for file in files:
        data=file.read_bytes() if source_revision is None else subprocess.check_output(
            ['git','show',source_revision+':'+file.relative_to(root).as_posix()],cwd=root)
        key.update(hashlib.sha256(data).digest())
    return f'{folder.name}-aiden-{key.hexdigest()[:16]}.zip'


def confirm(timing):
    if timing.get('narrator') != PROFILE or not timing['certificate'].get('passed'):
        raise ValueError('This recording does not have the approved Aiden voice and audio certificate')
    proof=timing.get('narration_review',{})
    if len(proof)!=len(timing['sentences']) or any(not x.get('recognized') for x in proof.values()):
        raise ValueError('Missing independent Aiden sentence checks')
    count=0
    for sentence in timing['sentences']:
        row=proof.get(f'{timing.get("lesson")}:{sentence["k"]}',{})
        phrases=row.get('phrases',[])
        if (row.get('method')!=PAUSE_POLICY or len(phrases)!=len(sentence['parts']) or not phrases
                or any(not p.get('text') or len(p.get('sha256',''))!=64 for p in phrases)):
            raise ValueError(f'Unconfirmed whole-phrase recordings in sentence {sentence["k"]}')
        count+=len(phrases)
    checks=timing.get('phrase_audio_check',{})
    if (checks.get('policy')!=PAUSE_POLICY or checks.get('passed') is not True
            or checks.get('sha256')!=timing['certificate']['mp3_sha256'] or checks.get('phrases')!=count):
        raise ValueError('The mastered audio has no matching phrase-boundary listening report')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['asset','verify']);p.add_argument('lesson');a=p.parse_args()
    if a.mode=='asset':print(audio_asset(PROJECT/'篇目'/a.lesson))
    else:confirm(json.loads((PROJECT/'audio/timings.json').read_text())['cet4_male'][a.lesson])
