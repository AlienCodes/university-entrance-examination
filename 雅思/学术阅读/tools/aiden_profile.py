"""Identity of the fixed IELTS narrator chosen from the recorded audition."""
import ast
import hashlib
import json
from pathlib import Path
import re
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


class RejectedSource(ValueError):
    """A full-track review identified this exact source recording as unsuitable."""


def rejected_sources(pid):
    if not isinstance(pid, str) or not re.fullmatch(r'C\d+T\d+P\d+', pid):
        raise ValueError('Invalid lesson in Aiden source review')
    file = PROJECT / '审校/Aiden/13-6/复验原声' / (pid + '.退回.json')
    if not file.is_file():
        return {}
    review = json.loads(file.read_text(encoding='utf-8'))
    if review['lesson'] != pid or review['narrator'] != IDENTITY:
        raise ValueError('The mastered recording review belongs to a different lesson or voice')
    failures = {}
    for row in review['takes']:
        digest = row['flac_sha256']
        if (not re.fullmatch(r'[0-9a-f]{64}', digest) or not row['issue']
                or not re.fullmatch(r'[0-9a-f]{64}', row['master_mp3_sha256'])):
            raise ValueError('Incomplete evidence for a rejected mastered recording')
        failures[digest] = row['issue']
    return failures


def historical_checkers(profile_source):
    """Read the pronunciation inputs used by the recorded revision, in their original order."""
    function = next(node for node in ast.parse(profile_source).body
                    if isinstance(node, ast.FunctionDef) and node.name == 'audio_asset')
    for stmt in function.body:
        if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'term_checkers' for t in stmt.targets):
            return ast.literal_eval(stmt.value)
        if isinstance(stmt, ast.For) and isinstance(stmt.iter, ast.List):
            return {word: (filename,) for word, filename in ast.literal_eval(stmt.iter)}
    # The first two versions respectively used zero extra files or only the oak checker.
    has_oak_checker = any(isinstance(node, ast.Constant) and node.value == 'tools/aiden_cork_oak.py'
                          for node in ast.walk(function))
    return {'quercus suber': ('aiden_cork_oak.py',)} if has_oak_checker else {}


def audio_asset(lesson_dir, *, source_revision=None):
    folder=Path(lesson_dir)
    rows=[line.split('\t')[0] for line in (folder/'双语精读.tsv').read_text().splitlines() if line]
    pron=json.loads((folder/'篇目信息.json').read_text()).get('pronunciation',{})
    root=PROJECT.parents[1]
    files=[Path(__file__),PROJECT/'tools/aiden_audio.py',PROJECT/'tools/aiden_boundaries.py',PROJECT/'tools/audio_lesson.py',PROJECT/'声音试听/sample.py',
           root/'六级/tools/make_audio.py',root/'tools/tts/textnorm.py',root/'tools/tts/voices.json',
           root/'tools/tts/pronunciations.json',root/'tools/tts/gaokao_tts.py']
    term_checkers = {
        'clemmons': ('aiden_kite_names.py', 'aiden_surnames.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py',
                     '读音对照/Clemmons.flac'),
        'vandam': ('aiden_surnames.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'henri becquerel': ('aiden_place_names.py', 'aiden_surnames.py', 'aiden_pronunciation.py'),
        'quercus suber': ('aiden_cork_oak.py',),
        'the ancient craftsmen': ('aiden_pronunciation.py', 'aiden_ceylonese.py'),
        'llewyn': ('aiden_lynx.py','aiden_ceylonese.py','aiden_pronunciation.py'),
        'cod, sole, perch and pollock': ('aiden_pronunciation.py', 'aiden_ceylonese.py'),
        'ceylonese': ('aiden_ceylonese.py',),
        'decans': ('aiden_decans.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'perkin': ('aiden_perkin.py', 'aiden_surnames.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'shenggen': ('aiden_surnames.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'janzen': ('aiden_surnames.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'zappaterra': ('aiden_surnames.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'amagoalik': ('aiden_surnames.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'sevres': ('aiden_sevres.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'hawley-dolan': ('aiden_surnames.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'ganzfeld': ('aiden_ganzfeld.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'ynde': ('aiden_india.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'export sectors': ('aiden_sectors.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'diels': ('aiden_diels.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'monbusho': ('aiden_place_names.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'aleyska': ('aiden_place_names.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'makete': ('aiden_place_names.py',),
        'na-dene': ('aiden_place_names.py', 'aiden_boundaries.py', 'aiden_pronunciation.py'),
        'floris': ('aiden_floris.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'fusee': ('aiden_fusee.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'qaujimajatuqangit': ('aiden_inuktitut.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'sobochack': ('aiden_sobchack.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
        'macfarlane': ('aiden_macfarlane.py', 'aiden_ceylonese.py', 'aiden_pronunciation.py'),
    }
    if source_revision is not None:
        profile_path = Path(__file__).resolve().relative_to(root).as_posix()
        profile_source = subprocess.check_output(['git', 'show', f'{source_revision}:{profile_path}'], cwd=root)
        term_checkers = historical_checkers(profile_source)
    for term, names in term_checkers.items():
        if not any(term in row.lower() for row in rows):
            continue
        checkers = [PROJECT/'tools'/name for name in names]
        files.extend(checker for checker in checkers if checker not in files)
    key=hashlib.sha256(json.dumps([rows,pron,IDENTITY],ensure_ascii=False).encode())
    for file in files:
        data=file.read_bytes() if source_revision is None else subprocess.check_output(
            ['git','show',source_revision+':'+file.relative_to(root).as_posix()],cwd=root)
        key.update(hashlib.sha256(data).digest())
    return f'{folder.name}-aiden-{key.hexdigest()[:16]}.zip'


def source_take_digests(pid, narration):
    return [phrase['sha256'] for n in range(1, len(narration) + 1)
            for phrase in narration[f'{pid}:{n}']['phrases']]


def verified_subject_terms(pid, receipt):
    failures = rejected_sources(pid)
    if failures:
        takes = receipt.get('source_take_sha256')
        if (not isinstance(takes, list) or not takes or len(takes) != receipt.get('verified_phrases')
                or any(not isinstance(d, str) or not re.fullmatch(r'[0-9a-f]{64}', d) or d in failures for d in takes)):
            return False
    # The three printed plurals in the timekeeping paper have each been read as
    # deacons on a previous track. Require the corrected vowel in the final AAC.
    return pid != 'C8T1P1' or receipt.get('decans_checked_in_mp3_and_aac') == [10, 11, 12]


def confirm(timing):
    if timing.get('narrator') != PROFILE or not timing['certificate'].get('passed'):
        raise ValueError('This recording does not have the approved Aiden voice and audio certificate')
    proof=timing.get('narration_review',{})
    if len(proof)!=len(timing['sentences']) or any(not x.get('recognized') for x in proof.values()):
        raise ValueError('Missing independent Aiden sentence checks')
    failures = rejected_sources(timing.get('lesson'))
    count=0
    for sentence in timing['sentences']:
        row=proof.get(f'{timing.get("lesson")}:{sentence["k"]}',{})
        phrases=row.get('phrases',[])
        if (row.get('method')!=PAUSE_POLICY or len(phrases)!=len(sentence['parts']) or not phrases
                or any(not p.get('text') or len(p.get('sha256',''))!=64 for p in phrases)):
            raise ValueError(f'Unconfirmed whole-phrase recordings in sentence {sentence["k"]}')
        for phrase in phrases:
            if phrase['sha256'] in failures:
                raise RejectedSource(failures[phrase['sha256']])
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
