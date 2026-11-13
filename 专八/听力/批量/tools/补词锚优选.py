#!/usr/bin/env python3
"""局部ASR只在增加真实原文词锚且不丢失已有词锚时接纳；仍然只是草稿。"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
B = HERE.parent
spec = importlib.util.spec_from_file_location('tem8_anchor_selection', HERE / '原文对齐.py')
A = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = A
spec.loader.exec_module(A)


def text_sha(draft):
    obj = [(u['id'], [s['en'] for s in u['sentences']]) for u in draft['units']]
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('years', type=int, nargs='+')
    args = parser.parse_args()
    for year in args.years:
        out = B / f'核验/补词锚/{year}'
        if not (out / '窗口.json').exists():
            continue
        draft = json.loads((B / f'译注草稿/{year}.json').read_text('utf-8'))
        prep = json.loads((B / f'预处理/{year}/原音准备.json').read_text('utf-8'))
        primary_path = B / f'预处理/{year}/识别.json'
        original_sha = A.sha(primary_path)
        current = json.loads(primary_path.read_text('utf-8'))
        evidence = json.loads((out / '窗口.json').read_text('utf-8'))
        assert evidence['primary_asr_sha256'] == original_sha
        assert evidence['canonical_source_sha256'] == prep['canonical']['sha256']
        def compare(raw):
            effective, _ = A.augment_sentence_asr(draft, raw, B, prep)
            return A.align(draft, effective, prep['canonical']['duration'])
        result = compare(current)
        initial = result['coverage']
        decisions = []
        # 原窗互不重叠；按时间顺序接纳，每次都重查全局单调映射。
        for record in sorted(evidence['windows'], key=lambda r: r['window'][0]):
            lo, hi = record['window']
            proposal = [w for w in current if not lo <= w[1] < hi] + record['words']
            proposal.sort(key=lambda w: (w[1], w[2]))
            updated = compare(proposal)
            old_keys, new_keys = set(result['mapping']), set(updated['mapping'])
            added, lost = sorted(new_keys - old_keys), sorted(old_keys - new_keys)
            moved = []
            for i in sorted(old_keys & new_keys):
                a = min(result['target'][j].start for j in result['mapping'][i])
                z = min(updated['target'][j].start for j in updated['mapping'][i])
                if not lo - .2 <= a <= hi + .2 and abs(a - z) > 2:
                    moved.append({'source': result['source'][i].text, 'before': a, 'after': z})
            accepted = bool(added) and not lost and not moved
            def describe(ids, r):
                return [{'unit': r['source'][i].group[0], 'sentence': r['source'][i].group[1],
                         'text': r['source'][i].text, 'char': [r['source'][i].char, r['source'][i].char_end]} for i in ids]
            decisions.append({'window_key': record['key'], 'window': record['window'], 'unit': record['unit'],
                              'machine_selection': 'accepted_extra_anchors_no_losses' if accepted else 'retained_primary',
                              'added': describe(added, updated), 'lost': describe(lost, result), 'outside_window_moved': moved,
                              'note': '程序保守选择，不代表人工审校或英文异文裁决。'})
            if accepted:
                current, result = proposal, updated
        assert A.sha(primary_path) == original_sha
        A.dump(out / '优选识别.json', current)
        A.dump(out / '优选记录.json', {'year': year, 'source_text_sha256': text_sha(draft),
            'source_draft_sha256': A.sha(B / f'译注草稿/{year}.json'), 'baseline_coverage': initial,
            'selected_coverage': result['coverage'], 'decisions': decisions,
            'rule': '新增原文词锚；不丢任何旧原文词锚；原窗外无超过2秒的锚点漂移；不批准字幕内容。'})
        A.dump(out / '优选ASR核验.json', {'year': year, 'canonical_sha256': prep['canonical']['sha256'],
            'source_unchanged': True, 'music_trim_applied': False, 'primary_asr_sha256': original_sha,
            'source_text_sha256': text_sha(draft), 'word_end_estimate_seconds': .08,
            'selection_evidence': f'核验/补词锚/{year}/优选记录.json', 'selection_sha256': A.sha(out / '优选记录.json'),
            'window_evidence_sha256': A.sha(out / '窗口.json'), 'script_sha256': A.sha(__file__),
            'status': '机器优选逐词ASR候选；未审，不修改主ASR或正式原音。',
            'outputs': {'识别.json': {'sha256': A.sha(out / '优选识别.json')}}})
        print(json.dumps({'year': year, 'accepted': sum(d['machine_selection'].startswith('accepted') for d in decisions),
                          'windows': len(decisions), 'mapped_before': initial['source_mapped'],
                          'mapped_after': result['coverage']['source_mapped'],
                          'boundaries_before': sum(not r['boundary_anchored'] for r in compare(json.loads(primary_path.read_text()))['rows']),
                          'boundaries_after': sum(not r['boundary_anchored'] for r in result['rows'])}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
