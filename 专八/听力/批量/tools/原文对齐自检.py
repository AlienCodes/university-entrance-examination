#!/usr/bin/env python3
"""对齐的真实录音正例与删句/乱序/关键词反例；不生成生产时刻。"""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
spec = importlib.util.spec_from_file_location('tem8_alignment_tested', HERE / '原文对齐.py')
alignment = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = alignment
spec.loader.exec_module(alignment)


def run():
    checks = []
    for year in (2009, 2010, 2011):
        draft = json.loads((BATCH / f'译注草稿/{year}.json').read_text('utf-8'))
        raw = json.loads((BATCH / f'预处理/{year}/识别.json').read_text('utf-8'))
        # 三年讲座前两句均有原文页图，且原始逐词ASR逐字支持。
        positive = copy.deepcopy(draft)
        positive['units'] = [positive['units'][0]]
        body = positive['units'][0]['sentences']
        opening = next(i for i, s in enumerate(body) if s['en'].lower().startswith('good morning'))
        positive['units'][0]['sentences'] = body[opening:opening + 2]
        candidate = alignment.align(positive, raw)
        first = candidate['rows'][0]['word_alignment'][0]['asr_indices'][0]
        last = candidate['rows'][1]['word_alignment'][-1]['asr_indices'][-1]
        audio_excerpt = raw[first:last + 1]
        exact = alignment.align(positive, audio_excerpt)
        assert exact['coverage']['literal_complete'], (year, exact['differences'])
        checks.append({'year': year, 'case': 'real_ASR_two_sentence_positive', 'ok': True,
                       'actual_ASR_window': [audio_excerpt[0][1], audio_excerpt[-1][2]],
                       'ASR_raw_indices': [first, last], 'coverage': exact['coverage']})
        for case in ('delete_sentence', 'reorder_sentences', 'change_keyword'):
            broken = copy.deepcopy(positive)
            sentences = broken['units'][0]['sentences']
            if case == 'delete_sentence':
                sentences.pop()
            elif case == 'reorder_sentences':
                sentences.reverse()
            else:
                sentences[0]['en'] = sentences[0]['en'].replace('morning', 'evening')
            result = alignment.align(broken, audio_excerpt)
            assert not result['coverage']['literal_complete'], (year, case)
            assert result['differences'] or result['uncovered_asr'], (year, case, 'failure invisible')
            checks.append({'year': year, 'case': case, 'ok': True, 'coverage': result['coverage'],
                           'difference_count': len(result['differences'])})
    def fixture(en, heard):
        # 故障注入夹具的合成时刻只在内存存在，不进入任何精听数据/录音核验。
        d = {'units': [{'id': 'TEST', 'sentences': [{'en': en, 'zh': '测试夹具', 'w': []}]}]}
        asr = [[word, i + 1., i + 1.5] for i, word in enumerate(heard)]
        return alignment.align(d, asr)
    for en, heard in [('cannot', ['can']), ('three', ['one', 'and', 'two']), ('5', ['six']),
                       ('life',['lives']),('toward',['towards']),('at',['in']),('no',['number']),('I am',['I','a.m.'])]:
        result = fixture(en, heard)
        assert not result['coverage']['all_source_mapped'], (en, heard)
        assert not result['coverage']['literal_complete']
        checks.append({'case': 'negation_or_number_mismatch', 'source': en, 'ASR': heard, 'ok': True})
    equivalent = fixture('98%', ['ninety', 'eight', 'percent'])
    assert equivalent['coverage']['all_source_mapped']
    assert equivalent['differences'] and not equivalent['coverage']['literal_complete']
    assert equivalent['rows'][0]['boundary_anchored']
    checks.append({'case': 'number_equivalence_reported_not_silently_literal', 'ok': True})
    for en,heard in [('behaviour',['behavior']),('behaviours',['behaviors']),('honoured',['honored']),
                     ('levelling',['leveling']),('disorganised',['disorganized']),('conveyer',['conveyor']),
                     ('school work',['schoolwork']),('dream-like',['dreamlike']),('re-interpreting',['reinterpreting']),
                     ('good will',['goodwill']),('co-workers',['coworkers']),('CV',['C','V']),
                     ('UNHCR',['U.','N.','H.','C.','R.']),('best-sellers',['bestsellers']),('grown-ups',['grownups']),
                     ('9 am',['nine','a.m.']),('No. 3',['number','three'])]:
        result=fixture(en,heard)
        assert result['coverage']['all_source_mapped'],(en,heard,result['differences'])
        assert result['differences'] and not result['coverage']['literal_complete'],(en,heard)
        checks.append({'case':'explicit_spelling_or_compound_reported','source':en,'ASR':heard,'ok':True})
    result = {'ok': True, 'scope': 'word_anchor_alignment_only; no production approval', 'checks': checks}
    alignment.dump(BATCH / '核验/原文对齐/正反例自检.json', result)
    print(json.dumps({'ok': True, 'checks': len(checks)}, ensure_ascii=False))


if __name__ == '__main__':
    run()
