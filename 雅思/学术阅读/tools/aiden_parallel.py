"""Recover a single pilot from independently checked recordings while preserving its voice and layout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import zipfile

from aiden_profile import IDENTITY, PAUSE_POLICY, audio_asset, confirm
from lesson import LESSON, PID, PROJECT, save
from material import verify_original
from release_assets import fetch, inventory

STAGE = 'ielts-academic-aiden-cache-' + os.environ.get('IELTS_AIDEN_BATCH', '13-6')
ASSET = audio_asset(LESSON)


def paper():
    verify_original(PROJECT, PID)
    return [s for para in json.loads((PROJECT/'原稿'/(PID+'.json')).read_text())['paragraphs'] for s in para]


def exists():
    inventory.cache_clear()
    item = inventory(STAGE).get(ASSET)
    return bool(item and item.get('digest') and item['size'] > 0)


def plan():
    config = json.loads(Path('.github/ielts-aiden-recovery.json').read_text())
    sentences = paper()
    seed = config.get('measured_run','')
    repo = os.environ['GH_REPO']
    main_run = json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{config["pilot_run"]}']))
    if (config['lesson'] != PID or config['batch'] != os.environ['IELTS_AIDEN_BATCH']
            or main_run['head_branch'] != 'codex/ielts-academic-reading'
            or main_run['path'] != '.github/workflows/ielts-aiden-production.yml'):
        raise ValueError('Recovery must refer to the specified pilot on the production branch')
    done=set()
    prior=config.get('reuse_run')
    successful=[]
    if prior:
        info=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{prior}']))
        if info['path']!='.github/workflows/ielts-aiden-pilot-recovery.yml' or info['head_branch']!=main_run['head_branch']:
            raise ValueError('The previous recordings are from a different workflow')
        jobs=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{prior}/jobs?per_page=100']))
        for job in jobs['jobs']:
            group=re.fullmatch(r'record \(([0-9_]+)\)',job['name'])
            if group and job['conclusion']=='success':
                successful.append('aiden-recorded-'+PID+'-'+group[1])
                done.update(map(int,group[1].split('_')))
    if seed:
        data = json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{seed}/artifacts?per_page=100']))
        prefix = 'aiden-measured-' + PID + '-'
        done = {int(a['name'][len(prefix):]) for a in data['artifacts'] if a['name'].startswith(prefix)
                and a['name'][len(prefix):].isdigit() and a.get('digest') and not a['expired']}
        if done != set(config['measured_sentences']):
            raise ValueError('The measured sentence artifacts do not match this recovery')
    if config.get('source_recording'):
        src=config['source_recording']
        if inventory(STAGE)[src['asset']]['digest']!='sha256:'+src['sha256']:
            raise ValueError('Unverified source recording archive')
    remaining = [] if exists() else [n for n in range(1,len(sentences)+1) if n not in done]
    groups = [[] for _ in range(min(12,len(remaining)))]
    for n in sorted(remaining, key=lambda i:len(sentences[i-1].split()), reverse=True):
        group = min(groups, key=lambda g:sum(len(sentences[i-1].split()) for i in g))
        group.append(n)
    groups = ['_'.join(map(str,sorted(g))) for g in groups]
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:
        print('groups='+json.dumps(groups),file=out)
        print('seed='+str(seed),file=out)
        print('prior='+str(prior or ''),file=out)
        print('verified_groups='+json.dumps(successful),file=out)
    print(f'{len(done)} measured sentences, {len(remaining)} remaining, {len(groups)} workers')


def record(numbers, folder):
    from audio_lesson import Reader, cet
    from aiden_audio import Aiden
    from measure_aiden_sentence import measure
    reader = Reader()
    reader.lexicon.update(json.loads((LESSON/'篇目信息.json').read_text())['pronunciation'])
    engine = Aiden()
    sentences = paper()
    config=json.loads(Path('.github/ielts-aiden-recovery.json').read_text())
    if config.get('source_recording'):
        src=config['source_recording']; remote=inventory(STAGE)[src['asset']]
        if remote['digest']!='sha256:'+src['sha256']:
            raise ValueError('Raw recording archive digest differs')
        voice=json.loads((cet.G.HERE/'voices.json').read_text())[cet.VOICE]
        seeds=set()
        for n in numbers:
            key=f'{PID}:{n}'
            parts=cet.narration_phrases(reader.read_text(sentences[n-1],key),key,voice['clause_pause'])
            if len(parts)==1: seeds.add(24830+n)
        with TemporaryDirectory(dir=folder) as tmp:
            with zipfile.ZipFile(fetch(remote,tmp)) as z:
                for name in z.namelist():
                    if not re.fullmatch(r'aiden-takes/[a-f0-9]{64}\.json',name):continue
                    data=json.loads(z.read(name))
                    if data['seed'] not in seeds:continue
                    wave_name=name[:-5]+'.flac'
                    wave=z.read(wave_name)
                    if hashlib.sha256(wave).hexdigest()!=data['sha256']:
                        raise ValueError('Damaged source take: '+name)
                    (engine.folder/Path(wave_name).name).write_bytes(wave)
                    (engine.folder/Path(name).name).write_bytes(z.read(name))
    for n in numbers:
        if exists():
            print('The original run has delivered a certified audio asset.',flush=True)
            return
        measure(n,folder/f'{PID}-{n}.json',engine,reader,sentences)


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def merge(incoming, work):
    sentences = paper()
    output = work/'aiden-takes'
    output.mkdir(parents=True,exist_ok=True)
    reports = {}
    for f in incoming.rglob(f'{PID}-*.json'):
        match = re.fullmatch(re.escape(PID)+r'-(\d+)\.json',f.name)
        if not match:
            continue
        n = int(match.group(1))
        s = json.loads(f.read_text())
        if (n in reports or not 1<=n<=len(sentences) or s.get('model')!=IDENTITY
                or s.get('text')!=sentences[n-1] or not s.get('passed') or not s['review'].get('recognized')
                or s['review'].get('method')!=PAUSE_POLICY):
            raise ValueError(f'Invalid sentence certificate {f.name}')
        reports[n] = s
    if sorted(reports)!=list(range(1,len(sentences)+1)):
        raise ValueError('Missing sentence recordings: '+str(sorted(set(range(1,len(sentences)+1))-reports.keys())))
    for wave in incoming.rglob('aiden-takes/*.flac'):
        if not re.fullmatch(r'[0-9a-f]{64}\.flac',wave.name):
            raise ValueError('Unrecognised take filename')
        note = wave.with_suffix('.json')
        details = json.loads(note.read_text())
        if not details.get('transcript') or not details.get('timed') or details['sha256']!=digest(wave):
            raise ValueError('Damaged waveform or transcript: '+wave.name)
        for p in (wave,note):
            dest = output/p.name
            if dest.exists():
                if digest(p)!=digest(dest):
                    raise ValueError('Conflicting recording for '+p.name)
            else:
                shutil.copyfile(p,dest)
    save(work/'sentence-evidence.json',[reports[n] for n in sorted(reports)])
    print(f'{len(reports)} verified sentences, {len(list(output.glob("*.flac")))} reusable takes',flush=True)


def publish(work):
    from subprocess import CalledProcessError
    folder = PROJECT/'audio'
    timing = json.loads((folder/'timings.json').read_text())['cet4_male'][PID]
    confirm(timing)
    if [r['text'] for r in timing['sentences']] != paper():
        raise ValueError('Verified audio does not match the complete paper')
    target = work/ASSET
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_STORED) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(PROJECT))
    inventory.cache_clear()
    if ASSET not in inventory(STAGE):
        try:
            subprocess.run(['gh','release','upload',STAGE,str(target)],check=True)
        except CalledProcessError:
            if not exists():raise
    inventory.cache_clear()
    with TemporaryDirectory(dir=work) as tmp:
        remote = fetch(inventory(STAGE)[ASSET],tmp)
        with zipfile.ZipFile(remote) as z:
            accepted = json.loads(z.read('audio/timings.json'))['cet4_male'][PID]
            confirm(accepted)
            if [s['text'] for s in accepted['sentences']]!=paper():
                raise ValueError('Remote recording does not match the paper')
            with z.open('audio/'+accepted['file']) as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=accepted['certificate']['mp3_sha256']:
                    raise ValueError('Remote sound does not match certificate')
    evidence = work/(PID+'-recording-'+IDENTITY[:12]+'-'+PAUSE_POLICY+'.zip')
    with zipfile.ZipFile(evidence,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        z.write(work/'sentence-evidence.json','sentence-evidence.json')
        for p in sorted((work/'aiden-takes').iterdir()):
            z.write(p,'aiden-takes/'+p.name)
    subprocess.run(['gh','release','upload',STAGE,str(evidence),'--clobber'],check=True)
    print(f'Certified complete remote audio {ASSET}; {len(accepted["sentences"])} sentences',flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['plan','have','record','merge','publish'])
    ap.add_argument('--numbers');ap.add_argument('--incoming',type=Path)
    args=ap.parse_args()
    if os.getenv('IELTS_NARRATOR')!='Aiden':
        raise ValueError('Fixed Aiden profile is required')
    if args.mode=='plan':plan()
    elif args.mode=='have':print(str(exists()).lower())
    else:
        work=Path(os.environ['IELTS_WORK']);work.mkdir(parents=True,exist_ok=True)
        if args.mode=='record':record([int(x) for x in args.numbers.split('_')],work)
        elif args.mode=='merge':merge(args.incoming,work)
        else:publish(work)
