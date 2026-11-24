"""Reuse a complete Aiden track after validating its current script and decoded audio."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from aiden_profile import IDENTITY, PAUSE_POLICY, audio_asset, confirm
from lesson import LESSON, PID, PROJECT, ROOT
from release_assets import fetch, inventory


def input_signature(passage, reader, config):
    fields = [IDENTITY, PAUSE_POLICY, passage['sents'], reader.lexicon, reader.text, config]
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def eligible_legacy_names():
    # Earlier certified archives lack the runtime input signature. Rebuild their
    # exact artifact names from the authorized recovery runs and today's text.
    settings = json.loads((ROOT / '.github/ielts-aiden-batch.json').read_text())
    names = set()
    for run in settings.get('recover_runs', []):
        if type(run) is not int or run < 1:
            continue
        endpoint = f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{run}"
        info = json.loads(subprocess.check_output(['gh','api',endpoint]))
        revision = info['head_sha']
        if (info['head_branch'] != 'codex/ielts-academic-reading' or
                info['path'] != '.github/workflows/ielts-aiden-production.yml' or
                not re.fullmatch('[a-f0-9]{40}',revision)):
            continue
        if subprocess.run(['git','cat-file','-e',revision+'^{commit}'],cwd=ROOT,capture_output=True).returncode:
            subprocess.run(['git','fetch','--quiet','--no-tags','--depth=1','--filter=blob:none','origin',revision],cwd=ROOT,check=True)
        # Preserve global pronunciation overrides and the exact mastering settings.
        for rel in ('tools/tts/pronunciations.json','六级/tools/读音修正.json','tools/tts/voices.json'):
            old=subprocess.check_output(['git','show',revision+':'+rel],cwd=ROOT)
            if old!=(ROOT/rel).read_bytes():
                break
        else:
            names.add(audio_asset(LESSON,source_revision=revision))
    return names


def read_archive(archive, destination, signature, legacy, passage, reader, config):
    import make_audio as cet
    from gaokao_tts import certificate_problems
    from aiden_boundaries import check_media
    with zipfile.ZipFile(archive) as z:
        records=json.loads(z.read('audio/timings.json'))
        if set(records)!={cet.VOICE} or set(records[cet.VOICE])!={PID}:
            raise ValueError('Different lesson or additional voices')
        timing=records[cet.VOICE][PID]
        confirm(timing)
        if timing.get('spoken_inputs_sha256')!=signature and not (
                not timing.get('spoken_inputs_sha256') and legacy):
            raise ValueError('Different source pronunciation settings')
        source=[(para,text) for para,rows in enumerate(passage['sents'],1) for text in rows]
        if timing.get('lesson')!=PID or [(s['para'],s['text']) for s in timing['sentences']]!=source:
            raise ValueError('Different printed sentences or paragraph sequence')
        for n,entry in enumerate(timing['sentences'],1):
            key=f'{PID}:{n}'
            read=reader.read_text(entry['text'],key)
            groups=cet.narration_phrases(read,key,config['clause_pause'])
            saved=[p['text'] for p in timing['narration_review'][key]['phrases']]
            if n!=entry['k'] or read!=entry['read'] or groups!=saved:
                raise ValueError(f'Current spoken text or phrase boundaries differ in sentence {n}')
        media=Path(timing['file'])
        if (media.parent.as_posix()!=cet.VOICE or media.suffix!='.mp3' or
                not media.name.startswith(PID+'_') or '\\' in media.name):
            raise ValueError('Unexpected track path')
        payload=[media.with_suffix(s) for s in ('.mp3','.loudness.json','.srt','.vtt')]
        for rel in payload:
            target=destination/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open('audio/'+rel.as_posix()) as src,target.open('wb') as out:
                shutil.copyfileobj(src,out)
    errors=certificate_problems(timing,destination/media)
    if errors:
        raise ValueError(str(errors))
    timing['phrase_audio_check']=check_media(destination/media,timing)
    confirm(timing)
    return timing,payload


def recover_master(stage, passage, reader, config, target):
    batch=os.environ.get('IELTS_AIDEN_BATCH')
    if batch not in ('13-6','5-1') or stage!='ielts-academic-aiden-cache-'+batch:
        return None
    try:
        available=inventory(stage)
    except (OSError,subprocess.SubprocessError) as exc:
        print(f'{PID}: unable to read complete-audio inventory ({type(exc).__name__}), using saved takes',flush=True)
        return None
    assets=[a for n,a in available.items()
            if re.fullmatch(re.escape(PID)+r'-aiden-[a-f0-9]{16}\.zip',n) and a.get('digest')]
    if not assets:
        return None
    legacy=None
    signature=input_signature(passage,reader,config)
    for item in sorted(assets,key=lambda a:a['id'],reverse=True):
        try:
            with tempfile.TemporaryDirectory(dir=os.environ['IELTS_WORK']) as temp:
                folder=Path(temp);archive=fetch(item,folder)
                with zipfile.ZipFile(archive) as z:
                    prior=json.loads(z.read('audio/timings.json'))['cet4_male'][PID]
                if not prior.get('spoken_inputs_sha256') and legacy is None:
                    legacy=eligible_legacy_names()
                ready=folder/'checked'
                timing,payload=read_archive(archive,ready,signature,item['name'] in (legacy or ()),passage,reader,config)
                for rel in payload:
                    (target/rel).parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(ready/rel,target/rel)
                timing['spoken_inputs_sha256']=signature
                timing['recovered_master']={'asset':item['name'],'digest':item['digest']}
                print(f"{PID}: reused complete certified audio {item['name']} after checking every phrase",flush=True)
                return timing
        except (ValueError,KeyError,OSError,RuntimeError,subprocess.SubprocessError,zipfile.BadZipFile) as exc:
            print(f"{PID}: prior audio {item['name']} unable to pass current checks: {str(exc)[:260]}",flush=True)
    return None


def stage_recording(stage, destination):
    """Classify available recordings so a picture edit only loads weights if it needs new speech."""
    if not (LESSON / '双语精读.tsv').is_file() or not (LESSON / '篇目信息.json').is_file():
        return 'missing'
    name = audio_asset(LESSON)
    assets = inventory(stage)
    item = assets.get(name)
    if not item or not item.get('digest'):
        previous = any(re.fullmatch(re.escape(PID) + r'-aiden-[a-f0-9]{16}\.zip', n) and a.get('digest')
                       for n, a in assets.items())
        return 'previous' if previous else 'missing'
    archive = fetch(item, destination)
    with zipfile.ZipFile(archive) as saved:
        timing = json.loads(saved.read('audio/timings.json'))['cet4_male'][PID]
        confirm(timing)
    return 'current'


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('stage')
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(stage_recording(args.stage, args.destination))
