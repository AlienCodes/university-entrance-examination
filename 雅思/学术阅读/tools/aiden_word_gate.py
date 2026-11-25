"""Audit the 13–6 illustrated films, reusing their verified tracks and checking disputed excerpts."""
import argparse
from functools import lru_cache
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

from aiden_boundaries import RATE, independent, isolated, verify_reference, words
from aiden_encoded_audio import pcm
import aiden_word_review
from aiden_word_review import (POLICY, check_known_span, hear_differences, known_span,
                               measured_words, report_words, same_words)
from aiden_profile import IDENTITY, verified_subject_terms
from illustration_stage import CACHE, checked
from lesson import PROJECT, ROOT, save
from release_assets import fetch, inventory

REPORTS = PROJECT/'审校/Aiden/13-6/逐词核音'


def read(path):
    return json.loads(path.read_bytes())


@lru_cache(maxsize=1)
def rules_digest():
    from aiden_boundaries import spoken_centuries, spoken_spelling
    digest = hashlib.sha256(Path(aiden_word_review.__file__).read_bytes())
    for function in (spoken_centuries, spoken_spelling, words, scan):
        digest.update(inspect.getsource(function).encode())
    return digest.hexdigest()


def identity(pid, core, film):
    return dict(lesson=pid, policy=POLICY, rules_sha256=rules_digest(), source_mp3_sha256=core['audio_sha256'],
                core_sha256=core['video_sha256'], video_sha256=film['video_sha256'],
                original_aac_packets=film['audio']['original_aac_packets'],
                illustrated_intro_frames=film['plate_frames'])


def scan(pid, core, film, voice, load_audio):
    if (core['lesson'] != pid or film['core_sha256'] != core['video_sha256'] or film['plate_frames'] != 30
            or not film['audio']['original_aac_packets'] or voice['mp3_check']['sha256'] != core['audio_sha256']
            or voice['mp4_check']['sha256'] != core['video_sha256']):
        raise ValueError(f'{pid} caption, source and encoded audio do not refer to the same film')
    review = report_words(pid, voice)
    pending = review.pop('to_listen')
    report = dict(**identity(pid, core, film), **review, clips=[], passed=True)
    if not pending:
        return report
    audio = load_audio()
    checks = {(r['sentence'],r['phrase']):r for r in voice['mp4_check']['checks']}
    for row in pending:
        n, j = row['sentence'], row['phrase']
        evidence = checks[n, j]
        raw = voice['sentences'][f'{pid}:{n}']['phrases'][j-1]
        # The intro inserts exactly one second before the previously checked audio.
        begin = round((row['start']+1)*RATE)
        end = round((row['end']+1)*RATE)
        sample = audio[begin:end]
        row['source_lag_ms'] = verify_reference(sample, raw['reference'])
        row['final_start_sample'], row['final_end_sample'] = begin, end
        row['decoded_sha256'] = hashlib.sha256(sample.astype('<f4').tobytes()).hexdigest()
        first, second = isolated(sample), independent(sample)
        row.update(heard=first, second_heard=second)
        target = words(row['text'])
        complete = any(same_words(target, measured_words(words(t), evidence)) for t in (first, second))
        if not complete:
            observations = []
            proof = hear_differences(sample, row['text'], second, observations)
            row['focused_listening'] = observations
            complete = bool(proof)
        if span := known_span(target):
            try:
                row['word_detail'] = check_known_span(sample, span)
            except ValueError as exc:
                row['word_detail_issue'] = str(exc)
                complete = False
        row['passed'] = complete
        if not complete:
            report['passed'] = False
        report['clips'].append(row)
    return report


def require(pid, core, film, voice):
    path = REPORTS/(pid+'.json')
    if not path.is_file():
        raise ValueError(f'{pid} lacks a word-by-word audit')
    return validate_report(pid,core,film,voice,read(path))


def validate_report(pid, core, film, voice, review):
    if (any(review.get(k) != v for k, v in identity(pid, core, film).items()) or review.get('passed') is not True
            or any(r.get('passed') is not True for r in review['clips'])):
        raise ValueError(f'{pid} has unresolved words or a different version of the video')
    original = report_words(pid, voice)
    def anchors(rows):
        return [(x['sentence'],x['phrase'],x['source_take_sha256'],x['text'],x['start'],x['end']) for x in rows]
    if (any(review[k] != original[k] for k in ('phrases','spoken_words'))
            or anchors(review['clips']) != anchors(original['to_listen'])):
        raise ValueError(f'{pid} has an incomplete word-by-word audit')
    return review['spoken_words']


def range_reader():
    src = ROOT/'高考语法填空/tools/取模型.py'
    spec = importlib.util.spec_from_file_location('ielts_remote_zip', src)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RangeFile.BLOCK = 256*1024
    return module.RangeFile


def reread_reason(clip):
    from aiden_review_windows import retake_reason

    if clip.get('word_detail_issue'):
        return clip['word_detail_issue']
    if reason := retake_reason(clip):
        return reason
    # Only request an automatic retake for a specific grammatical difference
    # heard by both decoders between the same two printed neighbours.
    for item in clip.get('focused_listening', []):
        start, stop = item['printed_words']
        left, right = item['checked_words']
        if not left < start < stop < right or stop != start+1:
            continue
        goal = item['expected_window'].split()
        slot = start-left
        printed = goal[slot]
        alternatives = []
        if printed in {'a','an','the','of','to','in','not','no','and','or','on','at','for','by'}:
            alternatives.append([])
        if printed.endswith('ed'):
            alternatives.extend([[printed[:-1]], [printed[:-2]]])
        if printed.endswith('s'):
            alternatives.append([printed[:-1]])
        for alternative in alternatives:
            altered = goal[:slot] + alternative + goal[slot+1:]
            if all(same_words(altered, words(item[k])) for k in ('heard','second_heard')):
                return f"Both local readings heard {' '.join(altered)!r} for {item['expected_window']!r}"
    return None


def save_retake_requests(report):
    path = REPORTS.parent/'复验原声'/(report['lesson']+'.退回.json')
    batch = read(path) if path.is_file() else dict(lesson=report['lesson'], narrator=IDENTITY, takes=[])
    known = {take['flac_sha256'] for take in batch['takes']}
    manual = []
    for clip in report['clips']:
        digest = clip['source_take_sha256']
        if clip['passed'] or digest in known:
            continue
        issue = reread_reason(clip)
        uncertain = not issue and bool(clip.get('window_review'))
        previous = [t for t in batch['takes'] if (t['sentence'],t['phrase'],t.get('text')) ==
                    (clip['sentence'],clip['phrase'],clip['text'])]
        same = [t for t in previous if t.get('issue') == issue] if issue else [
            t for t in previous if t.get('kind') == 'unclear-after-listening']
        if (uncertain and same) or (issue and len(same) >= 2):
            manual.append(dict(sentence=clip['sentence'], phrase=clip['phrase'], text=clip['text'],
                               video_sha256=report['video_sha256'], source_sha256=digest,
                               previous_sources=[t['flac_sha256'] for t in same],
                               start_sample=clip['final_start_sample'], end_sample=clip['final_end_sample'],
                               rate=RATE, heard=[clip['heard'],clip['second_heard']], issue=issue or 'inconclusive'))
            continue
        if uncertain:
            issue = 'The final-film recording could not be confirmed by two blind readers in context. Try one clearer whole take.'
        if issue:
            batch['takes'].append(dict(sentence=clip['sentence'], phrase=clip['phrase'], flac_sha256=digest,
                                       master_mp3_sha256=report['source_mp3_sha256'], text=clip['text'],
                                       kind='unclear-after-listening' if uncertain else 'specific-difference', issue=issue))
            known.add(digest)
    if manual:
        batch['needs_listening'] = manual
        print(f"{report['lesson']}: {len(manual)} excerpts need a pronunciation decision before another take",flush=True)
    else:
        batch.pop('needs_listening',None)
    if known and (not path.is_file() or read(path) != batch):
        save(path,batch)


def finish_checks(pid, core, film, voice, prior, load_audio):
    from aiden_review_windows import needs_review, recheck
    reusable = all(prior.get(k) == v for k,v in identity(pid,core,film).items())
    report = prior if reusable else scan(pid,core,film,voice,load_audio)
    for clip in report['clips']:
        if needs_review(clip):
            sample = load_audio()[clip['final_start_sample']:clip['final_end_sample']]
            raw = voice['sentences'][f"{pid}:{clip['sentence']}"]['phrases'][clip['phrase']-1]
            recheck(clip,sample,raw)
    report['passed'] = all(clip['passed'] for clip in report['clips'])
    if report['passed']:
        validate_report(pid,core,film,voice,report)
    save(REPORTS/(pid+'.json'),report)
    save_retake_requests(report)
    unresolved = sum(not r['passed'] for r in report['clips'])
    print(f"{pid}: {report['spoken_words']} words, {unresolved} excerpts to review",flush=True)
    return report['passed']


def audit_output(pid, folder, assets):
    from illustration_stage import digest
    core_file, film_file = (folder/(pid+suffix) for suffix in ('-receipt.json','-illustrated.json'))
    for path in (core_file, film_file):
        if assets[path.name]['digest'] != 'sha256:'+digest(path):
            raise ValueError(f'{pid} local and published receipts differ')
    core, film = read(core_file), read(film_file)
    asset = checked(pid,core,film,assets)
    if not verified_subject_terms(pid,core):
        raise ValueError(f'{pid} contains a returned recording')
    video = folder/asset['name']
    if video.stat().st_size != asset['size'] or digest(video) != film['video_sha256']:
        raise ValueError(f'{pid} audit needs the exact published MP4')
    archive = folder/f"{pid}-{core['material_sha256'][:16]}.zip"
    if assets[archive.name]['digest'] != 'sha256:'+digest(archive):
        raise ValueError(f'{pid} archived narration differs from the published source')
    with zipfile.ZipFile(archive) as z:
        proof = json.loads(z.read('verification.json'))
        if not proof['ok'] or proof['receipt'] != core:
            raise ValueError(f'{pid} source and final film refer to different recordings')
        voice = json.loads(z.read('source/narration.json'))
    path = REPORTS/(pid+'.json')
    prior = read(path) if path.exists() else {}
    @lru_cache(maxsize=1)
    def final_audio():
        return pcm(video)
    return finish_checks(pid,core,film,voice,prior,final_audio)


def audit_lesson(pid, session, remote_zip):
    from aiden_batch import cached
    from aiden_review_windows import needs_review
    assets = inventory(CACHE)
    if not all(pid+suffix in assets for suffix in ('-receipt.json','-illustrated.json')):
        return False
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        core = read(fetch(assets[pid+'-receipt.json'],folder))
        film = read(fetch(assets[pid+'-illustrated.json'],folder))
        if film['core_sha256'] != core['video_sha256'] or not verified_subject_terms(pid,core):
            return False
        path = REPORTS/(pid+'.json')
        prior = read(path) if path.is_file() else {}
        reusable = all(prior.get(k) == v for k,v in identity(pid,core,film).items())
        if reusable and (prior['passed'] or not any(needs_review(c) for c in prior['clips'])):
            if not prior['passed']:
                save_retake_requests(prior)
            return prior['passed']
        if not cached(pid,'13-6'):
            return False
        video = checked(pid,core,film,assets)
        archive = assets[f"{pid}-{core['material_sha256'][:16]}.zip"]
        with zipfile.ZipFile(remote_zip(archive['browser_download_url'], session)) as z:
            signed = json.loads(z.read('verification.json'))
            if not signed['ok'] or signed['receipt'] != core:
                raise ValueError(f'{pid} master changed while auditing the reading')
            voice = json.loads(z.read('source/narration.json'))
        @lru_cache(maxsize=1)
        def final_audio():
            return pcm(fetch(video,folder))
        return finish_checks(pid,core,film,voice,prior,final_audio)


def audit_existing(require_all, selected_books=None):
    import requests
    from aiden_batch import BATCHES
    from editions import lesson_ids

    reader = range_reader()
    ids = lesson_ids(selected_books or BATCHES['13-6'])
    outstanding = []
    with requests.Session() as session:
        for pid in ids:
            try:
                if audit_lesson(pid,session,reader):
                    continue
            except (ValueError, KeyError, OSError, subprocess.CalledProcessError, requests.RequestException) as exc:
                inventory.cache_clear()
                print(f'{pid}: could not verify ({type(exc).__name__})',flush=True)
            outstanding.append(pid)
    print(f'{len(outstanding)} of {len(ids)} still require verified readings',flush=True)
    if require_all and outstanding:
        raise SystemExit('Outstanding word checks: '+', '.join(outstanding))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-all',action='store_true')
    parser.add_argument('--books', nargs='+', type=int, choices=range(6,14))
    parser.add_argument('--final-dir',type=Path)
    parser.add_argument('--lesson')
    args = parser.parse_args()
    if args.final_dir or args.lesson:
        from editions import lesson_ids
        if not args.final_dir or args.lesson not in lesson_ids(range(13,5,-1)) or args.books or args.require_all:
            parser.error('A single finished film requires its 13–6 lesson ID and final directory')
        raise SystemExit(0 if audit_output(args.lesson,args.final_dir,inventory(CACHE)) else 1)
    if args.require_all and args.books:
        parser.error('A release check must cover all 96 films')
    audit_existing(args.require_all, args.books)
