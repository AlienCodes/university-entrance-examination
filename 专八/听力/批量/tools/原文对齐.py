#!/usr/bin/env python3
"""把译注原文绑定到实际ASR词锚；只产出待人工审校的精听草稿。

全年度、全单元共同做单调词序匹配，保留所有未匹配词和录音区间。
数字、缩写及收缩形式可解释地规范化；差异仍逐条登记。没有任何按
句长/字数分摊时刻的分支。句首或句尾缺词锚的单元留在隔离目录，
不会生成一份看起来可制作的精听输入。
"""
from __future__ import annotations

import argparse
import bisect
import copy
from dataclasses import dataclass
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import unicodedata

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
TOOL_VERSION = '1.0'
LEX = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:st|nd|rd|th|s)?|[A-Za-zÀ-ÿ]+(?:['’][A-Za-z]+)*|[%&]")
SMALL = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
TENS = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10)))
NUM = SMALL | TENS
SCALE = {'thousand': 1000, 'million': 1000000, 'billion': 1000000000}
NUMBER_WORDS = set(NUM) | set(SCALE) | {'hundred', 'and'}
CONTRACTIONS = {
    "i'm": ['i', 'am'], "you're": ['you', 'are'], "we're": ['we', 'are'], "they're": ['they', 'are'],
    "there's": ['there', 'is'], "here's": ['here', 'is'], "it's": ['it', 'is'],
    "i'll": ['i', 'will'], "you'll": ['you', 'will'], "he'll": ['he', 'will'],
    "she'll": ['she', 'will'], "we'll": ['we', 'will'], "they'll": ['they', 'will'],
    "i've": ['i', 'have'], "you've": ['you', 'have'], "we've": ['we', 'have'], "they've": ['they', 'have'],
    "can't": ['can', 'not'], 'cannot': ['can', 'not'], "won't": ['will', 'not'],
    "don't": ['do', 'not'], "doesn't": ['does', 'not'], "didn't": ['did', 'not'],
    "isn't": ['is', 'not'], "aren't": ['are', 'not'], "wasn't": ['was', 'not'], "weren't": ['were', 'not'],
    "haven't": ['have', 'not'], "hasn't": ['has', 'not'], "hadn't": ['had', 'not'],
    "shouldn't": ['should', 'not'], "wouldn't": ['would', 'not'], "couldn't": ['could', 'not'], "mustn't": ['must', 'not'],
    "let's": ['let', 'us'],
}
SPELLINGS = {'ok': 'okay', 'dr': 'doctor', 'mr': 'mister', '&': 'and', '%': 'percent'}
ABBREVIATIONS = {'us', 'uk', 'un', 'eu', 'mc'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def portable(path, base=BATCH):
    path = Path(path).resolve()
    try:
        return path.relative_to(Path(base).resolve()).as_posix()
    except ValueError:
        return path.name


def simple(text):
    text = unicodedata.normalize('NFKD', text.replace('’', "'").lower())
    return ''.join(c for c in text if not unicodedata.combining(c))


@dataclass
class Lexeme:
    text: str
    char: int
    char_end: int
    group: tuple
    # ASR序号是原识别.json列表的0基下标；同一ASR条目被分词时共享真时刻。
    raw_index: int | None = None
    start: float | None = None
    end: float | None = None


@dataclass
class Atom:
    key: str
    lexemes: tuple[int, ...]
    reason: str = 'literal'


def number_value(words):
    """严格解析一个英语整数；相邻两个独立数不会被相加冒充同一个数。"""
    if not words or words[0] == 'and' or words[-1] == 'and':
        return None
    if len(words) == 1 and words[0] in {'hundred', *SCALE}:
        return 100 if words[0] == 'hundred' else SCALE[words[0]]
    if words[0] in ('nineteen', 'twenty') and len(words) >= 2:
        rest = number_value(words[1:])
        if rest is not None and 10 <= rest < 100:
            return NUM[words[0]] * 100 + rest
    total = current = 0
    previous = None
    last_scale = float('inf')
    for i, word in enumerate(words):
        if word == 'and':
            if previous not in ('hundred', 'scale') or i + 1 == len(words):
                return None
            previous = 'and'
            continue
        if word in NUM or re.fullmatch(r'\d[\d,]*', word):
            value = NUM[word] if word in NUM else int(word.replace(',', ''))
            if previous == 'small':
                return None
            if previous == 'tens' and not 0 < value < 10:
                return None
            if previous == 'hundred' or previous == 'and':
                # 后面的数应是余数；允许one hundred and twenty-five。
                pass
            current += value
            previous = 'tens' if word in TENS else 'small'
        elif word == 'hundred':
            if previous != 'small' or not 0 < current < 10:
                return None
            current *= 100
            previous = 'hundred'
        elif word in SCALE:
            scale = SCALE[word]
            if not current or scale >= last_scale or previous == 'and':
                return None
            total += current * scale
            current = 0
            last_scale = scale
            previous = 'scale'
        else:
            return None
    return total + current


def atoms(lexemes):
    result = []
    i = 0
    while i < len(lexemes):
        item = lexemes[i]
        word = simple(item.text)
        # U.S./U S等只按明列缩写合并，绝不做任意名字的模糊匹配。
        if len(word) == 1:
            for size in (3, 2):
                group = lexemes[i:i + size]
                joined = ''.join(simple(x.text) for x in group)
                if (len(group) == size and all(x.group == item.group and len(simple(x.text)) == 1 for x in group)
                        and joined in ABBREVIATIONS):
                    result.append(Atom(joined, tuple(range(i, i + size)), 'abbreviation'))
                    i += size
                    break
            else:
                size = 0
            if size:
                continue
        if (word in NUMBER_WORDS or re.fullmatch(r'\d[\d,]*', word)) and word != 'and':
            end = i
            while (end < len(lexemes) and end - i < 18 and lexemes[end].group == item.group
                   and (simple(lexemes[end].text) in NUMBER_WORDS or re.fullmatch(r'\d[\d,]*', simple(lexemes[end].text)))):
                end += 1
            for stop in range(end, i, -1):
                n = number_value([simple(x.text) for x in lexemes[i:stop]])
                if n is not None:
                    result.append(Atom('#' + str(n), tuple(range(i, stop)), 'number'))
                    i = stop
                    break
            else:
                raise AssertionError('单个已知数词竟未解析')
            continue
        if re.fullmatch(r'\d[\d,]*(?:\.\d+)?', word):
            result.append(Atom('#' + word.replace(',', ''), (i,), 'number'))
        elif re.fullmatch(r'\d+s', word):
            result.append(Atom('#decade' + word[:-1], (i,), 'number'))
        elif word in CONTRACTIONS:
            result.extend(Atom(x, (i,), 'contraction') for x in CONTRACTIONS[word])
        else:
            result.append(Atom(SPELLINGS.get(word, word), (i,), 'spelling' if word in SPELLINGS else 'literal'))
        i += 1
    return result


def source_lexemes(draft):
    lexemes, sentences = [], []
    for unit in draft['units']:
        for n, sentence in enumerate(unit['sentences'], 1):
            group = (unit['id'], n)
            ids = []
            for match in LEX.finditer(sentence['en']):
                ids.append(len(lexemes))
                lexemes.append(Lexeme(match.group(), match.start(), match.end(), group))
            if not ids:
                raise ValueError(f'{group}没有可对齐英文词')
            sentences.append({'unit': unit['id'], 'n': n, 'sentence': sentence, 'lexemes': ids})
    return lexemes, sentences


def asr_lexemes(raw, duration=None):
    if isinstance(raw, dict):
        raw = raw.get('words', raw.get('word_timestamps'))
    if not isinstance(raw, list) or not raw:
        raise ValueError('ASR必须是非空逐词列表，不能拿整段时刻按长度拆词')
    lexemes = []
    previous = -1.0
    for n, item in enumerate(raw):
        if isinstance(item, dict):
            text, start, end = item.get('word', item.get('text')), item['start'], item['end']
        else:
            text, start, end = item
        start, end = float(start), float(end)
        if not (0 <= start < end and previous <= start and (duration is None or end <= duration + .1)):
            raise ValueError(f'ASR[{n}]时刻无效或不单调：{item}')
        previous = start
        for match in LEX.finditer(text):
            # ASR是全年度连续词序；不能每个单词建立独立group，否则数字无法跨词解析。
            lexemes.append(Lexeme(match.group(), match.start(), match.end(), ('ASR',), n, start, end))
    return raw, lexemes


def describe_asr(ids, lexemes, raw):
    indices = sorted({lexemes[i].raw_index for i in ids})
    if not indices:
        return {'asr_indices': [], 'asr_text': [], 'window': None}
    return {'asr_indices': indices, 'asr_text': [raw[i][0] if not isinstance(raw[i], dict) else raw[i].get('word', raw[i].get('text')) for i in indices],
            'window': [min(lexemes[i].start for i in ids), max(lexemes[i].end for i in ids)]}


def align(draft, raw_asr, duration=None, decisions=None):
    """纯函数：返回逐词映射及完整差异；调用者决定何时写文件。"""
    src, rows = source_lexemes(draft)
    raw, target = asr_lexemes(raw_asr, duration)
    sa, ta = atoms(src), atoms(target)
    sm = difflib.SequenceMatcher(None, [x.key for x in sa], [x.key for x in ta], autojunk=False)
    pairs = {}
    opcodes = sm.get_opcodes()
    for tag, a, b, c, d in opcodes:
        if tag == 'equal':
            pairs.update(zip(range(a, b), range(c, d)))
    occurrences = {}
    for i, atom in enumerate(sa):
        for lex in atom.lexemes:
            occurrences.setdefault(lex, []).append(i)
    mapping = {}
    for lex, positions in occurrences.items():
        # 收缩词少了否定词时不能以只匹配can冒充cannot已经对齐。
        if all(i in pairs for i in positions):
            mapping[lex] = sorted({j for i in positions for j in ta[pairs[i]].lexemes})
    human = []
    for num, decision in enumerate((decisions or {}).get('bindings', []), 1):
        if not decision.get('evidence', '').strip():
            raise ValueError(f'人工裁定{num}缺少可审证据')
        group = (decision['unit'], decision['sentence'])
        row = next((r for r in rows if (r['unit'], r['n']) == group), None)
        if row is None:
            raise ValueError(f'人工裁定{num}引用不存在的句子')
        a, b = decision['char']
        if row['sentence']['en'][a:b] != decision['text']:
            raise ValueError(f'人工裁定{num}原文已变，拒绝沿用')
        ids = [i for i in row['lexemes'] if src[i].char < b and a < src[i].char_end]
        if not ids or any(src[i].char < a or src[i].char_end > b for i in ids):
            raise ValueError(f'人工裁定{num}必须选择完整词，不可把词内字符猜为独立音段')
        indices = decision['asr_indices']
        if not indices or indices != list(range(indices[0], indices[-1] + 1)):
            raise ValueError(f'人工裁定{num}的ASR下标必须连续、有序且非空，禁止跨无关语音拼接词时刻')
        desc = describe_asr([i for i, x in enumerate(target) if x.raw_index in indices], target, raw)
        if desc['asr_indices'] != indices or desc['asr_text'] != decision['asr_text']:
            raise ValueError(f'人工裁定{num}的ASR文字/下标不符，拒绝沿用')
        matched_target = [i for i, x in enumerate(target) if x.raw_index in indices]
        if any(set(v) & set(matched_target) for k, v in mapping.items() if k not in ids):
            raise ValueError(f'人工裁定{num}抢占别句/别词已用锚，必须先查真实重排')
        for i in ids:
            mapping[i] = matched_target
        human.append({'id': num, **copy.deepcopy(decision), 'window': desc['window']})
    # 任何人工映射也不得逆序；同一ASR条目多个字符可共享真实的整词时刻。
    previous = -1
    for i, js in sorted(mapping.items()):
        now = min(js)
        if now < previous:
            raise ValueError(f'{src[i].group}人工/机器映射逆序，拒绝时间重排')
        previous = now
    diff = []
    for tag, a, b, c, d in opcodes:
        if tag == 'equal':
            continue
        si = sorted({i for atom in sa[a:b] for i in atom.lexemes})
        ti = sorted({i for atom in ta[c:d] for i in atom.lexemes})
        diff.append({'kind': tag, 'source': [{'unit': src[i].group[0], 'sentence': src[i].group[1], 'char': [src[i].char, src[i].char_end], 'text': src[i].text} for i in si],
                     **describe_asr(ti, target, raw), 'decision': 'machine_candidate_unreviewed'})
    # 合并相邻、相同ASR绑定的词，以解释数词/缩写/收缩词共享锚，不隐去字面差异。
    seen = set()
    for i, js in sorted(mapping.items()):
        key = tuple(js)
        if key in seen:
            continue
        seen.add(key)
        source_ids = [j for j in sorted(mapping) if tuple(mapping[j]) == key]
        lhs = ' '.join(simple(src[j].text) for j in source_ids)
        rhs = ' '.join(simple(target[j].text) for j in js)
        if lhs != rhs:
            diff.append({'kind': 'normalized_or_reviewed_mapping',
                         'source': [{'unit': src[j].group[0], 'sentence': src[j].group[1], 'char': [src[j].char, src[j].char_end], 'text': src[j].text} for j in source_ids],
                         **describe_asr(js, target, raw), 'canonical': sorted({sa[k].key for j in source_ids for k in occurrences[j]}),
                         'decision': 'human_binding' if any(x['unit'] == src[i].group[0] and x['sentence'] == src[i].group[1] and x['char'][0] <= src[i].char < x['char'][1] for x in human) else 'machine_normalization_requires_review'})
    used = {j for js in mapping.values() for j in js}
    for row in rows:
        ids = row['lexemes']
        matched = [i for i in ids if i in mapping]
        row['missing'] = [i for i in ids if i not in mapping]
        row['boundary_anchored'] = ids[0] in mapping and ids[-1] in mapping
        row['word_alignment'] = [
            {'char': src[i].char, 'char_end': src[i].char_end,
             'start': min(target[j].start for j in mapping[i]), 'end': max(target[j].end for j in mapping[i]),
             'asr_indices': sorted({target[j].raw_index for j in mapping[i]})}
            for i in matched]
        row['anchor_window'] = ([row['word_alignment'][0]['start'], row['word_alignment'][-1]['end']] if matched else None)
        row['internal_asr_unmatched'] = []
        if matched:
            lo = min(mapping[matched[0]])
            hi = max(mapping[matched[-1]])
            row['internal_asr_unmatched'] = [j for j in range(lo, hi + 1) if j not in used]
    uncovered = []
    run = []
    for i in range(len(target) + 1):
        if i < len(target) and i not in used:
            run.append(i)
        elif run:
            uncovered.append({**describe_asr(run, target, raw), 'lexeme_count': len(run), 'classification': 'uncovered_ASR_candidate; inspect_source_and_audio; neither_speech_nor_silence_assumed'})
            run = []
    return {'source': src, 'target': target, 'raw': raw, 'rows': rows, 'mapping': mapping,
            'differences': diff, 'uncovered_asr': uncovered, 'human_decisions': human,
            'coverage': {'source_lexemes': len(src), 'source_mapped': len(mapping),
                         'source_ratio': len(mapping) / len(src), 'asr_lexemes': len(target), 'asr_mapped': len(used),
                         'asr_ratio': len(used) / len(target),
                         'all_source_mapped': len(mapping) == len(src), 'all_asr_mapped': len(used) == len(target),
                         'all_boundaries_anchored': all(r['boundary_anchored'] for r in rows),
                         'literal_complete': len(mapping) == len(src) and len(used) == len(target) and not diff}}


def interface_module():
    spec = importlib.util.spec_from_file_location('tem8_intensive_contract', HERE / '精听数据.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rerecognition_windows(result, duration, context=1.5):
    """用相邻已绑定词包围缺词，再留固定识别上下文；绝非缺词的猜测时刻。"""
    src, target, mapping = result['source'], result['target'], result['mapping']
    keys = sorted(mapping)
    row_by_group = {(r['unit'], r['n']): r for r in result['rows']}
    missing = [i for i in range(len(src)) if i not in mapping]
    runs = []
    for i in missing:
        if runs and i == runs[-1][-1] + 1 and src[i].group == src[runs[-1][-1]].group:
            runs[-1].append(i)
        else:
            runs.append([i])
    windows = []
    for run in runs:
        before = bisect.bisect_left(keys, run[0]) - 1
        after = bisect.bisect_right(keys, run[-1])
        left = keys[before] if before >= 0 else None
        right = keys[after] if after < len(keys) else None
        lo = min(target[j].start for j in mapping[left]) if left is not None else 0.
        hi = max(target[j].end for j in mapping[right]) if right is not None else duration
        if hi <= lo:
            raise ValueError('补识别区间的实际相邻ASR锚逆序')
        unit, sentence = src[run[0]].group
        row = row_by_group[(unit, sentence)]
        def anchor(i):
            if i is None:
                return None
            return {'unit': src[i].group[0], 'sentence': src[i].group[1], 'text': src[i].text,
                    **describe_asr(mapping[i], target, result['raw'])}
        windows.append({'unit': unit, 'window': [round(max(0., lo - context), 6), round(min(duration, hi + context), 6)],
                        'bracketing_only_not_word_timestamps': True,
                        'issues': [{'sentence': sentence, 'source_text': ' '.join(src[i].text for i in run),
                                    'source_chars': [[src[i].char, src[i].char_end] for i in run],
                                    'boundary_missing': not row['boundary_anchored'], 'missing_lexemes': len(run),
                                    'left_anchor': anchor(left), 'right_anchor': anchor(right)}]})
    # 同单元、时间重叠/相距不超过2秒的连续问题只需重识别一次。
    merged = []
    for current in sorted(windows, key=lambda x: (x['unit'], x['window'][0])):
        if (merged and merged[-1]['unit'] == current['unit']
                and current['window'][0] <= merged[-1]['window'][1] + 2):
            merged[-1]['window'][1] = max(merged[-1]['window'][1], current['window'][1])
            merged[-1]['issues'].extend(current['issues'])
        else:
            merged.append(current)
    for w in merged:
        w['missing_lexemes'] = sum(x['missing_lexemes'] for x in w['issues'])
        w['boundary_sentences'] = sorted({x['sentence'] for x in w['issues'] if x['boundary_missing']})
        w['duration'] = round(w['window'][1] - w['window'][0], 6)
    return sorted(merged, key=lambda x: (-len(x['boundary_sentences']), -x['missing_lexemes'], x['duration']))


def run_year(year, args):
    base = Path(args.base).resolve()
    def resolve(template, default):
        value = Path((template or default).format(year=year))
        return value if value.is_absolute() else base / value
    draft_path = resolve(args.draft, '译注草稿/{year}.json')
    asr_path = resolve(args.asr, '预处理/{year}/识别.json')
    prepare_path = resolve(args.prepare, '预处理/{year}/原音准备.json')
    draft = json.loads(draft_path.read_text('utf-8'))
    raw = json.loads(asr_path.read_text('utf-8'))
    prepare = json.loads(prepare_path.read_text('utf-8'))
    assert draft['year'] == year == prepare['year']
    canonical = prepare['canonical']
    assert re.fullmatch('[0-9a-f]{64}', canonical['sha256'])
    meta_path = resolve(args.asr_meta, '预处理/{year}/ASR核验.json')
    meta = None
    if meta_path.exists():
        meta = json.loads(meta_path.read_text('utf-8'))
        if (meta.get('canonical_sha256') != canonical['sha256'] or
                meta.get('outputs', {}).get('识别.json', {}).get('sha256') != sha(asr_path)):
            raise ValueError('ASR核验元数据与canonical SHA或识别.json SHA不符，不得跨音源对齐')
    decisions = {}
    if args.decisions:
        path = Path(args.decisions.format(year=year))
        if not path.is_absolute(): path = base / path
        decisions = json.loads(path.read_text('utf-8'))
        if decisions.get('year') != year or decisions.get('asr_sha256') != sha(asr_path) or decisions.get('source_sha256') != canonical['sha256']:
            raise ValueError('人工裁定文件的年份、ASR哈希或canonical音源哈希不符')
    result = align(draft, raw, canonical['duration'], decisions)
    rerecognition = rerecognition_windows(result, canonical['duration'])
    out = resolve(args.out, '精听数据')
    report_dir = resolve(args.report, '核验/原文对齐') / str(year)
    report_path = report_dir / '对齐报告.json'
    report = {'year': year, 'tool': portable(__file__, base), 'tool_version': TOOL_VERSION,
              'inputs': {'draft': portable(draft_path, base), 'draft_sha256': sha(draft_path),
                         'asr': portable(asr_path, base), 'asr_sha256': sha(asr_path),
                         'prepare': portable(prepare_path, base), 'prepare_sha256': sha(prepare_path),
                         'canonical_source_sha256': canonical['sha256']},
              'method': '全局单调规范词匹配；每个时刻只取实际ASR词条边界。数词/缩写/收缩差异逐条登记；无模糊关键词代换、无比例估时。',
              'machine_result_only': True, 'human_review_status': 'draft',
              'ASR_provenance': ({'file': portable(meta_path, base), 'sha256': sha(meta_path),
                                  'canonical_and_ASR_sha_verified': True, 'status': meta.get('status'),
                                  'word_end_estimate_seconds': meta.get('word_end_estimate_seconds')}
                                 if meta else {'canonical_and_ASR_sha_verified': False, 'pending': '缺ASR核验元数据，须人工证实该识别.json确实来自本canonical WAV'}),
              'coverage': result['coverage'], 'differences': result['differences'],
              'uncovered_asr': result['uncovered_asr'], 'human_decisions': result['human_decisions'],
              'rerecognition_windows': rerecognition, 'units': []}
    contract = interface_module()
    for unit in draft['units']:
        rows = [r for r in result['rows'] if r['unit'] == unit['id']]
        blocked = [r['n'] for r in rows if not r['boundary_anchored']]
        d = {k: copy.deepcopy(v) for k, v in unit.items() if k != 'sentences'}
        d['year'] = year
        d['audio'] = {'file': args.audio_template.format(year=year), 'sha256': canonical['sha256'],
                      'source_sha256': canonical['sha256'], 'source_kind': 'canonical WAV; original sample rate/channels/gain',
                      'window': None}
        if Path(d['audio']['file']).is_absolute():
            raise ValueError('audio-template必须是可移植相对路径；实际输入音源由精听.py --original传入')
        d['sentences'] = []
        unit_missing = 0
        missing_sentences = []
        for row in rows:
            s = copy.deepcopy(row['sentence'])
            s['word_alignment'] = row['word_alignment']
            s['alignment'] = {'boundary_anchored': row['boundary_anchored'], 'source_lexemes': len(row['lexemes']),
                              'mapped_lexemes': len(row['lexemes']) - len(row['missing']),
                              'missing': [{'text': result['source'][i].text, 'char': [result['source'][i].char, result['source'][i].char_end]} for i in row['missing']],
                              'unmatched_internal_asr': describe_asr(row['internal_asr_unmatched'], result['target'], result['raw'])}
            if row['boundary_anchored']:
                s['start'], s['end'] = row['anchor_window']
            else:
                s['start'] = s['end'] = None
            if row['missing']:
                unit_missing += len(row['missing'])
                missing_sentences.append(row['n'])
            d['sentences'].append(s)
        d.setdefault('待核', [])
        d['待核'].append('程序仅绑定ASR候选，不等于源文或音轨已通过人工核验；须复核本年对齐报告的全部差异及未覆盖ASR段。')
        if meta is None:
            d['待核'].append('缺少绑定canonical音源和识别.json哈希的ASR核验元数据；不能声称音源对应已验证。')
        if unit_missing:
            d['待核'].append(f'仍有{unit_missing}个原文词缺少ASR对应；涉及句号{missing_sentences}，严禁按比例补时。')
        d['alignment_report'] = portable(report_path, base)
        d['alignment_tool_version'] = TOOL_VERSION
        if blocked:
            d['待核'].append(f'句首/尾无真实ASR词锚，句号{blocked}；单元未导出到可制作目录。')
            output = report_dir / '未导出单元' / f"{unit['id']}.json"
            stale = out / f"{unit['id']}.json"
            if stale.exists():
                # 不能让上次可制作数据在本次失败后继续冒充当前输入。也不删除别人的审校结果。
                old = json.loads(stale.read_text('utf-8'))
                if old.get('alignment_tool_version') and old.get('review', {}).get('status') == 'draft':
                    stale.unlink()
                else:
                    raise ValueError(f'{stale}已有其他来源/已审校结果，本次失败不能覆盖；请人工处理旧输入')
            state = 'blocked_missing_boundary_anchor'
        else:
            lo = max(0, min(s['start'] for s in d['sentences']) - args.pad)
            hi = min(canonical['duration'], max(s['end'] for s in d['sentences']) + args.pad)
            d['audio']['window'] = [round(lo, 6), round(hi, 6)]
            output = out / f"{unit['id']}.json"
            if output.exists():
                old = json.loads(output.read_text('utf-8'))
                if old.get('review', {}).get('status') == 'approved' and not args.replace_reviewed:
                    raise ValueError(f'{output}已有人审登记，拒绝自动覆盖；明确--replace-reviewed才可重建draft')
            state = 'draft_exported_not_approved'
        d['review'] = {'status': 'draft', 'machine_only': True, 'source': portable(report_path, base)}
        d['review']['content_sha256'] = contract.content_sha(d)
        if not blocked:
            contract.validate(d, draft=True)
        dump(output, d)
        report['units'].append({'id': unit['id'], 'state': state, 'output': portable(output, base),
                                'sentences': len(rows), 'source_lexemes': sum(len(r['lexemes']) for r in rows),
                                'missing_source_lexemes': unit_missing, 'missing_boundary_sentences': blocked,
                                'rerecognition_window_count': sum(w['unit'] == unit['id'] for w in rerecognition),
                                'audio_window': d['audio']['window']})
    dump(report_path, report)
    return report


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('years', type=int, nargs='+')
    p.add_argument('--base', default=str(BATCH))
    p.add_argument('--draft', help='输入模板，支持{year}；相对base')
    p.add_argument('--asr', help='输入模板，支持{year}；只接收真正逐词时刻')
    p.add_argument('--prepare', help='原音准备.json模板')
    p.add_argument('--asr-meta', help='ASR核验.json模板；存在时必须核对音源和识别文件SHA')
    p.add_argument('--decisions', help='可选人工裁定JSON模板，必须绑定ASR/原音哈希和实际词序号')
    p.add_argument('--audio-template', default='预处理/{year}/原音.wav')
    p.add_argument('--out', help='精听数据目录')
    p.add_argument('--report', help='核验报告目录（其下再分年份）')
    p.add_argument('--pad', type=float, default=.12, help='窗口首尾固定留白秒数，不用于估算词时刻')
    p.add_argument('--replace-reviewed', action='store_true', help='显式把已审数据重建为draft；不会沿用approved')
    return p


def main():
    args = parser().parse_args()
    if not 0 <= args.pad <= 1:
        raise ValueError('窗口固定留白限定0—1秒')
    for year in args.years:
        report = run_year(year, args)
        print(json.dumps({'year': year, 'coverage': report['coverage'], 'units': report['units']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
