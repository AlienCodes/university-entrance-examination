"""Read potentially difficult *whole phrases* before starting the lesson master."""
import argparse
import json
import os
from pathlib import Path
import re

from aiden_word_review import dictionary
from lesson import PROJECT


TOKENS = re.compile(r"[^\W\d_]+(?:[-’'][^\W\d_]+)*")
MEASURE = re.compile(r"\b(?:per cent|percent|point|degrees|millimetres?|millimeters?|megahertz|cubic metres?)\b", re.I)
PRINTED_QUANTITY = re.compile(r"(?:[£$€]\s*)?\b\d[\d,.]*(?:\s*(?:%|°\s*[CF]|mm|cm|MHz|km|kg)(?!\w))?", re.I)
BOOK_PLAN = PROJECT / '审校/Aiden/13-6/阶段存档/待制篇目易错词预检.json'


def term_flags(phrase, original, marked, lexicon):
    printed = TOKENS.findall(original)
    names = {word.casefold() for word in printed[1:] if len(word) > 1 and
             (word[:1].isupper() or any(c.isupper() for c in word[1:]))}
    flags = {}
    for word in TOKENS.findall(phrase):
        lower = word.casefold()
        spelling = lower.replace('’', "'")
        if lower in marked and (len(lower) > 3 or word.isupper()):
            flags[word] = 'lexicon'
        elif lower in names:
            flags[word] = 'name or abbreviation'
        elif (lexicon and len(word) >= 4 and spelling not in lexicon
              and spelling.removesuffix("'s") not in lexicon):
            flags[word] = 'outside pronunciation dictionary'
    if re.search(r'\d', original):
        for measure in MEASURE.findall(phrase):
            flags.setdefault(measure, 'spoken measurement')
    return flags


def dictionary_contrast(phrase, heard, overrides):
    """A generation cue for a single disputed name, never a listening exemption."""
    from aiden_boundaries import words

    expected = words(phrase)
    observed = words(heard or '')
    if len(expected) != len(observed):
        return None
    differences = [(a,b) for a,b in zip(expected, observed) if a != b]
    if len(differences) != 1:
        return None
    name, other = differences[0]
    proper_names = {w.casefold() for w in TOKENS.findall(phrase) if w.istitle() or w[1:] != w[1:].lower()}
    if name not in proper_names or name in {w.casefold() for w in overrides}:
        return None
    lexicon = dictionary()
    left, right = lexicon.get(name, set()), lexicon.get(other, set())
    if len(left) == 1 and right and left.isdisjoint(right):
        return f'For {name}, use the American dictionary pronunciation {next(iter(left))} (ARPAbet).'
    return None


def paper_plan(ids):
    from editions import lesson_ids

    if len(set(ids)) != len(ids) or set(ids) - set(lesson_ids(range(13, 5, -1))):
        raise ValueError('Expected unique 13–6 lesson IDs')
    lexicon = dictionary()
    # The lightweight GitHub planning runner can use the saved dictionary scan
    # even before the speech and recognition packages are installed.
    saved = {}
    if not lexicon and BOOK_PLAN.exists():
        for batch in json.loads(BOOK_PLAN.read_bytes())['batches']:
            for lesson in batch:
                saved[lesson['lesson']] = {r['sentence']: r for r in lesson['sentences']}
    pron_file = PROJECT.parents[1] / 'tools/tts/pronunciations.json'
    global_words = set(json.loads(pron_file.read_bytes())['global'])
    lessons = []
    for pid in ids:
        paper = json.loads((PROJECT/'原稿'/(pid+'.json')).read_bytes())
        meta = json.loads((PROJECT/'篇目'/pid/'篇目信息.json').read_bytes())
        marked = {w.casefold() for w in global_words.union(meta.get('pronunciation', {}))}
        returned = {}
        for key, phrase in previously_flagged(pid):
            label = f'意群 {phrase}' if isinstance(phrase, int) else phrase
            returned.setdefault(int(key.rsplit(':', 1)[1]), []).append(label)
        rows = []
        for n, sentence in enumerate((s for para in paper['paragraphs'] for s in para), 1):
            flags = term_flags(sentence, sentence, marked, lexicon)
            old = saved.get(pid, {}).get(n, {})
            if old.get('original') == sentence:
                flags.update({w: kind for w,kind in old['terms'].items() if kind == 'outside pronunciation dictionary'})
            for match in PRINTED_QUANTITY.finditer(sentence):
                flags[match[0].rstrip('.,')] = 'printed number or unit'
            if flags or n in returned:
                rows.append(dict(sentence=n, original=sentence, terms=flags,
                                 returned_phrases=sorted(returned.get(n, []))))
        lessons.append(dict(lesson=pid, printed_test=paper.get('printed_test', paper['test']),
                            title=paper['title'], sentences=rows))
    return dict(batches=[lessons[i:i+20] for i in range(0, len(lessons), 20)])


def previously_flagged(pid, folder=None):
    # These records rank work only. Aiden.take independently verifies the actual
    # source bytes and the full phrase before it admits any recording.
    prior = set()
    paper_review = PROJECT / '审校/Aiden/13-6/复验原声' / (pid + '.退回.json')
    if paper_review.is_file():
        for row in json.loads(paper_review.read_bytes())['takes']:
            prior.add((f"{pid}:{row['sentence']}", row.get('text') or row['phrase']))
    for file in (folder / 'rejected').glob('*.json') if folder else ():
        row = json.loads(file.read_bytes())
        if row.get('accepted') is False and row.get('key') and row.get('printed'):
            prior.add((row['key'], row['printed']))
    return prior


def collect(passage, config, reader, folder):
    from aiden_audio import planned_takes

    pid = passage['id']
    prior = previously_flagged(pid, folder)
    lexicon = dictionary()
    marked = set(word.casefold() for word in reader.lexicon)
    rows = []
    sentences = (text for paragraph in passage['sents'] for text in paragraph)
    for number, original in enumerate(sentences, 1):
        key = f'{pid}:{number}'
        spoken = reader.read_text(original, key)
        for index, (phrase, variant) in enumerate(planned_takes(spoken, key, config)):
            flags = term_flags(phrase, original, marked, lexicon)
            returned = (key, phrase) in prior or (key, index+1) in prior
            rows.append(dict(key=key, position=index, variant=variant, text=phrase,
                             terms=flags, previous_issue=returned))
    return rows


def prepare(engine, passage, config, reader):
    from aiden_audio import UnverifiedTake

    rows = collect(passage, config, reader, engine.folder)
    risks = [row for row in rows if row['previous_issue'] or row['terms']]
    risks.sort(key=lambda row: not row['previous_issue'])
    report = engine.folder.parent / 'native-pronunciation.json'

    def record():
        # Keep a readable checkpoint even when the runner is interrupted.
        temp = report.with_suffix('.tmp')
        temp.write_text(json.dumps(dict(lesson=passage['id'], phrases=rows), ensure_ascii=False),
                        encoding='utf-8')
        temp.replace(report)

    def attempt(row, phase):
        try:
            engine.take(row['text'], row['key'], row['variant'], reader, row['position'],
                        phase=phase, initial_focus=next(iter(row['terms']), None))
        except UnverifiedTake as error:
            row.update(status='needs rereading', issue=str(error))
            record()
            return error
        row['status'] = 'source verified'
        row.pop('issue', None)
        engine.snapshots.after_sentence()
        return None

    record()

    print(f"{passage['id']}: checking {len(risks)} priority phrases before mastering", flush=True)
    pending = [row for row in risks if attempt(row, 'probe') is not None]
    if pending:
        # Give every remaining phrase a turn before spending another synthesis
        # attempt on any one word. Preserve every success on the same runner.
        for row in rows:
            if 'status' not in row and attempt(row, 'probe') is not None:
                pending.append(row)
        engine.snapshots.after_sentence(force=True)
        failures = []
        for row in pending:
            error = attempt(row, 'resume')
            if error is not None:
                failures.append(error)
        if failures:
            record()
            engine.snapshots.after_sentence(force=True)
            print('Unverified recordings still required before mastering:', *failures, sep='\n', flush=True)
            raise failures[0]
    record()

def save_batch_plan(ids, destination):
    plan = paper_plan(ids)
    destination.write_text(json.dumps(plan, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    print(f'Pronunciation preparation for {len(ids)} lessons, in {len(plan["batches"])} groups of at most 20')
    if summary := os.getenv('GITHUB_STEP_SUMMARY'):
        with open(summary, 'a', encoding='utf-8') as stream:
            for batch in plan['batches']:
                print('预检篇目 ' + '、'.join(row['lesson'] for row in batch), file=stream)
                print(file=stream)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('lessons', help='JSON array of printed lesson IDs')
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    save_batch_plan(json.loads(args.lessons), args.destination)
