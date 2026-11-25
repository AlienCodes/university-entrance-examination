"""Recheck disputed words in the decoded final film, retaining both blind readings."""
from difflib import SequenceMatcher
import hashlib
import re

from aiden_boundaries import RATE, independent, isolated, verify_reference, words
from aiden_ceylonese import timed_words
from aiden_word_review import check_known_span, dictionary, known_span, same_words


VERSION = 'two-reader-context-v1'


def needs_review(clip):
    return not clip['passed'] and clip.get('window_review', {}).get('version') != VERSION


def contains_words(tokens, phrase):
    return any(same_words(phrase, tokens[i:i+len(phrase)]) for i in range(len(tokens)-len(phrase)+1))


def word_windows(audio, clip, timed):
    text = clip['text']
    printed = words(text)
    heard = [word for word, _ in timed]
    changes = SequenceMatcher(None, printed, heard, autojunk=False).get_opcodes()
    results = []
    for index, (kind, a, b, c, d) in enumerate(changes):
        if kind == 'equal' or same_words(printed[a:b], heard[c:d]):
            continue
        left = a - changes[index-1][1] if index and changes[index-1][0] == 'equal' else 0
        right = changes[index+1][2] - b if index+1 < len(changes) and changes[index+1][0] == 'equal' else 0
        result = dict(printed=printed[a:b], heard=heard[c:d], confirmed=False, windows=[])
        results.append(result)
        if (a and not left) or (b < len(printed) and not right) or not (left or right):
            continue
        used = set()
        consistent = set()
        nearby = printed[a-min(1,left):a] + heard[c:d] + printed[b:b+min(1,right)]
        if nearby and all(contains_words(words(clip[k]), nearby) for k in ('heard', 'second_heard')):
            consistent.add((0, len(audio)))
        for before, after in ((2, 2), (2, 1), (1, 2), (1, 1)):
            l, r = min(before, left), min(after, right)
            low = max(0, timed[c-l][1] - round(.035*RATE)) if c-l else 0
            high = timed[d+r][1] if d+r < len(timed) else len(audio)
            if (low, high) in used or high <= low:
                continue
            used.add((low, high))
            goal = printed[a-l:b+r]
            snippet = audio[low:high]
            first, second = isolated(snippet), independent(snippet)
            observations = [words(first), words(second)]
            result['windows'].append(dict(samples=[low, high], expected=goal, first=first, second=second))
            if all(same_words(goal, observation) for observation in observations):
                result['confirmed'] = True
                break
            if nearby and all(contains_words(observation, nearby) for observation in observations):
                consistent.add((low, high))
        # Only send a common printed word for rereading when two differently bounded
        # excerpts give the same specific discrepancy with both independent readers.
        if (not result['confirmed'] and len(consistent) >= 2 and b == a+1
                and d-c <= 1 and printed[a] in dictionary()
                and all(word in dictionary() for word in heard[c:d])
                and re.search(r'\b' + re.escape(printed[a]) + r'\b', text)):
            result['reread'] = True
    return results


def recheck(clip, audio, raw):
    digest = hashlib.sha256(audio.astype('<f4').tobytes()).hexdigest()
    if digest != clip['decoded_sha256'] or raw['sha256'] != clip['source_take_sha256']:
        raise ValueError('The disputed excerpt differs from the signed final-film samples')
    lag = verify_reference(audio, raw['reference'])
    from aiden_voyages import TARO, VOYAGES, verify
    expected = words(clip['text'])
    if expected in (TARO, VOYAGES):
        try:
            measured = verify(audio, expected)
        except ValueError as error:
            clip['window_review'] = dict(version=VERSION, source_lag_ms=lag, pronunciation_issue=str(error))
            clip['passed'] = False
        else:
            clip['window_review'] = dict(version=VERSION, source_lag_ms=lag, pronunciation=measured)
            clip['passed'] = True
        return
    timed = timed_words(audio)
    changes = word_windows(audio, clip, timed)
    passed = bool(changes) and all(change['confirmed'] for change in changes)
    if not changes:
        # A recognizer giving the expected result with different outer padding
        # alone cannot overrule a disputed word.
        passed = same_words(words(clip['text']), [w for w,_ in timed]) and same_words(
            words(clip['text']), words(independent(audio)))
    span = known_span(words(clip['text']))
    if span:
        try:
            detail = check_known_span(audio, span)
        except ValueError as error:
            clip['word_detail_issue'] = str(error)
            passed = False
        else:
            clip['word_detail'] = detail
            clip.pop('word_detail_issue', None)
    clip['window_review'] = dict(version=VERSION, source_lag_ms=lag, differences=changes)
    clip['passed'] = passed


def retake_reason(clip):
    if issue := clip.get('window_review', {}).get('pronunciation_issue'):
        return issue
    for result in clip.get('window_review', {}).get('differences', []):
        if result.get('reread'):
            observed = ' '.join(result['heard']) or '(omitted)'
            return (f"Two independent readers in two windows of the final AAC heard {observed!r} "
                    f"for printed {' '.join(result['printed'])!r}; reread this complete phrase.")
    return None
