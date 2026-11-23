"""Confirm coverage, original-language references, key agreement and distinct writing examples."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from difflib import SequenceMatcher

from study_editor import normalized_quote
from study_pdfs import PROJECT
import illustrated_answers


def result_codes(logic):
    return re.findall(r'(?:故选|所以选|应选|答案(?:应为|是|为)|因此选)\s*[“「‘\']?\s*((?:NOT GIVEN|TRUE|FALSE|YES|NO|[A-K])\b)', logic, re.IGNORECASE | re.ASCII)


def fill_results(question, reasoning):
    if 'Completion' not in question['kind'] or question.get('word_bank'):
        return []
    quoted = re.findall(
        r'(?:答案(?:应该|应为|应|即|就是|为|是|须填入)|故填|应填写|应填入|所以填|因此填|应填)'
        r'\s*[‘\'“「]([a-zA-Z][a-zA-Z -]*)[’\'”」]', reasoning)
    variants = [question['answer'], *question.get('accepted_variants', '').split('/')]
    accepted = {v.strip().casefold() for v in variants if v.strip()}
    return [v for v in quoted if v.strip().casefold() not in accepted]


def audit(folder, ids):
    counts = Counter()
    examples = {}
    warnings = []
    for pid in ids:
        original = PROJECT / '配套讲义' / '题目与证据' / (pid + '.json')
        d = json.loads(original.read_text())
        path = folder / (pid + '.json')
        if not path.exists():
            raise ValueError(f'No teaching notes for {pid}')
        y = json.loads(path.read_text())
        if y['lesson'] != pid or y['input_sha256'] != hashlib.sha256(original.read_bytes()).hexdigest():
            raise ValueError(f'{pid}: notes belong to a different source')
        if set(y['questions']) != {str(q['numbers'][0]) for q in d['questions']}:
            raise ValueError(f'{pid}: missing or unexpected question')
        sentence_count = len(d['sentences'])
        seen_logic = set()
        for q in d['questions']:
            n = q['numbers'][0]
            r = y['questions'][str(n)]
            detailed = illustrated_answers.applies(pid)
            if detailed:
                illustrated_answers.check_reasoning(d, q, r)
            if 'Completion' in q['kind'] and '____' not in q['question']:
                raise ValueError(f'{pid} Q{n}: completion prompt has no visible gap')
            bank = q.get('word_bank', {})
            if q['answer'] in bank and q.get('chosen_text') != bank[q['answer']]:
                raise ValueError(f'{pid} Q{n}: answer label differs from the printed choice')
            if len(re.findall(r'[\u3400-\u9fff]', r['logic'])) < 24 or not r['evidence']:
                raise ValueError(f'{pid} Q{n}: no usable reasoning or evidence')
            if not all(isinstance(x, int) and 1 <= x <= sentence_count for x in r['evidence']):
                raise ValueError(f'{pid} Q{n}: evidence outside passage')
            if not set(q['evidence']) <= set(r['evidence']):
                raise ValueError(f'{pid} Q{n}: an approved source reference was lost')
            if 'logic' in q and not detailed:
                if r['logic'] != q['logic']:
                    raise ValueError(f'{pid} Q{n}: reviewed explanation changed')
            else:
                fragment = normalized_quote(r.get('quote', ''))
                original_parts = [normalized_quote(d['sentences'][i-1]['en']) for i in r['evidence']]
                if len(fragment.split()) < 2 or not any(' '+fragment+' ' in ' '+s+' ' for s in original_parts):
                    raise ValueError(f'{pid} Q{n}: quotation does not come from cited original')
            if r['logic'] in seen_logic:
                raise ValueError(f'{pid} Q{n}: identical explanation for two questions')
            seen_logic.add(r['logic'])
            codes = [c.upper() for c in result_codes(r['logic'])]
            answers = set(q['answer'].upper().split('、'))
            if codes and re.fullmatch(r'(?:TRUE|FALSE|NOT GIVEN|YES|NO|[A-K](?:、[A-K])*)', q['answer']) and not set(codes) <= answers:
                warnings.append({'lesson':pid,'q':n,'answer':q['answer'],'explicit':codes,'reasoning':r['logic']})
            conflicts = fill_results(q, r['logic'])
            if conflicts:
                warnings.append({'lesson':pid,'q':n,'answer':q['answer'],'explicit':conflicts,'reasoning':r['logic']})
            counts['questions'] += len(q['numbers'])
            counts['groups'] += 1
        grammar = y.get('grammar', [])
        if len(grammar) != 3 or len({g['sentence'] for g in grammar}) != 3:
            raise ValueError(f'{pid}: each of the three study spreads needs a different original sentence')
        for g in grammar:
            n = g['sentence']
            if not 1 <= n <= sentence_count:
                raise ValueError(f'{pid}: wrong source sentence for grammar')
            source = normalized_quote(d['sentences'][n-1]['en'])
            if 'grammar' not in d:
                for key in ('subject','verb'):
                    phrase = normalized_quote(g.get(key, ''))
                    if not phrase or ' '+phrase+' ' not in ' '+source+' ':
                        raise ValueError(f'{pid} sentence {n}: {key} not in source')
            text = normalized_quote(g['example'])
            if len(text.split()) < 8 or text in examples:
                raise ValueError(f'{pid} sentence {n}: short or duplicate writing example {examples.get(text)}')
            if SequenceMatcher(None, text, source).ratio()>.89:
                raise ValueError(f'{pid} sentence {n}: writing transfer copies the reading passage')
            if any(not g.get(field,'').strip() for field in ('heading','analysis','task','example_zh','usage','pattern')):
                raise ValueError(f'{pid} sentence {n}: incomplete teaching material')
            examples[text] = pid
            counts['writing'] += 1
        counts['passages'] += 1
    return dict(counts), warnings


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('folder',type=Path)
    ap.add_argument('report',type=Path)
    ap.add_argument('ids',nargs='*')
    args=ap.parse_args()
    ids=args.ids or [f'C{b}T{t}P{p}' for b in range(21,13,-1) for t in range(1,5) for p in range(1,4)]
    counts,warnings=audit(args.folder,ids)
    args.report.write_text(json.dumps({'totals':counts,'explicit_answer_reviews':warnings},ensure_ascii=False,indent=1)+'\n')
    print(counts,'answer references for review:',len(warnings))
