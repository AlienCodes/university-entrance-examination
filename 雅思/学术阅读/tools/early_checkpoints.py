"""Reuse individual checked rows after a paper annotation changes."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import re
import subprocess

from release_assets import fetch


# This first production wave did not yet include per-row dependencies in its checkpoints.
LEGACY_REVISION = '1927dd9d71b990a7a83e2fa7173ac17a8b9f488b'
LEGACY_EDITOR = 'paper-context-5.1'


def context(paper, prep, manual, notes, paper_hash, prep_hash, editor):
    result = []
    portable = []
    sentences = [s for paragraph in paper['paragraphs'] for s in paragraph]
    if sentences != [item['en'] for item in prep['rows']]:
        raise ValueError('Checkpoint inputs do not refer to the same reading')
    common = [paper['title'], paper.get('witness'), paper.get('edition_scope')]
    for n, (sentence, preparation) in enumerate(zip(sentences, prep['rows'], strict=True), 1):
        scoped = [item for item in notes if item['sentence'] == n]
        terms = [item for item in paper.get('language_review', []) if item.get('scope_en', sentence) == sentence
                 and item['english'].casefold() in sentence.casefold()]
        fields = [common, sentences[n-2] if n>1 else '', preparation, terms, manual.get(str(n)), scoped]
        data = json.dumps(fields, ensure_ascii=False, sort_keys=True).encode()
        result.append(hashlib.sha256(data).hexdigest())
        # A new sentence earlier in the passage can move the index of an
        # unchanged note. Keep its exact English, gloss, preceding sentence
        # and all other dependencies when matching across that move.
        portable_notes = [{key: value for key, value in note.items() if key != 'sentence'} for note in scoped]
        content = json.dumps([*fields[:-1], portable_notes], ensure_ascii=False, sort_keys=True).encode()
        portable.append(hashlib.sha256(content).hexdigest())
    return {'schema':1,'editor':editor,'paper':paper_hash,'prep':prep_hash,'rows':result,'content_rows':portable}


def legacy_context(project, pid, current, fingerprint, revision=None):
    repo = project.parents[1]
    revision = revision or LEGACY_REVISION
    if current['editor'] != LEGACY_EDITOR or not re.fullmatch(r'[a-f0-9]{40}', revision):
        return None
    available = subprocess.run(['git', 'cat-file', '-e', revision + '^{commit}'], cwd=repo, capture_output=True)
    if available.returncode:
        subprocess.run(['git', 'fetch', '--quiet', '--depth=1', '--no-tags', '--filter=blob:none',
                        'origin', revision], cwd=repo, check=True)
    def get(relative):
        path = (project / relative).relative_to(repo).as_posix()
        return subprocess.check_output(['git', 'show', revision + ':' + path], cwd=repo)
    paper = get('原稿/' + pid + '.json')
    prep = get('备课/' + pid + '.json')
    manual = json.loads(get('审校/早期册语境校订.json')).get(pid, {})
    notes = json.loads(get('审校/逐篇语境重点-10至1.json')).get(pid, [])
    before = context(json.loads(paper), json.loads(prep), manual, notes,
                     hashlib.sha256(paper).hexdigest(), hashlib.sha256(prep).hexdigest(), LEGACY_EDITOR)
    key = fingerprint(pid, before['paper'], before['prep'], len(before['rows']), manual, notes)
    return key, before


def reusable(project, pid, state, assets, folder, sentences, fingerprint, good):
    current = state['context']
    by_sentence = defaultdict(list)
    for n, sentence in enumerate(sentences, 1):
        by_sentence[sentence].append(n)
    result = {'drafted': {}, 'verified': {}}
    files = [asset for name, asset in assets.items() if name.startswith(pid + '-') and name.endswith('-work.json')
             and name != state['key'] + '-work.json']
    snapshots = project / '审校/早期册线上校订版本.json'
    revisions = json.loads(snapshots.read_text()) if snapshots.is_file() else {}
    legacy_sources = {}
    for asset in sorted(files, key=lambda a: a.get('updated_at', ''), reverse=True):
        rowset = json.loads(Path(fetch(asset, folder)).read_bytes())
        if rowset.get('id') != pid or asset['name'] != rowset.get('key', '') + '-work.json':
            continue
        before = rowset.get('context')
        if not before:
            revision = revisions.get(rowset['key'], LEGACY_REVISION)
            if revision not in legacy_sources:
                legacy_sources[revision] = legacy_context(project, pid, current, fingerprint, revision)
            legacy = legacy_sources[revision]
            if not legacy or rowset['key'] != legacy[0]:
                continue
            before = legacy[1]
        if before.get('schema') != current['schema'] or before.get('editor') != current['editor']:
            continue
        previous_content = before.get('content_rows', before['rows'])
        current_content = current.get('content_rows', current['rows'])
        for stage, rows in result.items():
            for item in rowset.get(stage, []):
                old_n = item['n']
                if not 1 <= old_n <= len(before['rows']):
                    continue
                matches = [n for n in by_sentence[item['en']]
                           if before['rows'][old_n-1] == current['rows'][n-1]
                           or previous_content[old_n-1] == current_content[n-1]]
                if len(matches) != 1 or matches[0] in rows:
                    continue
                n = matches[0]
                en = sentences[n-1]
                if (item['en'] != en or ''.join(item['english_parts']) != en or ''.join(item['parts']) != item['zh']
                    or not item['v'] or not good(en, item['english_parts'], item['v'], item['parts'],
                                                  [v[3] for v in item['v']], sentences[n-2] if n > 1 else '')
                    or (stage == 'verified' and 'review_reason' not in item)):
                    continue
                rows[n] = dict(item, n=n) if n != old_n else item
    return result
