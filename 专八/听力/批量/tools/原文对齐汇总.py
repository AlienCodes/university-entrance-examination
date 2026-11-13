#!/usr/bin/env python3
"""汇总边界故障类别和最小连续补识别窗口；分类是候选，不是人工裁定。"""
import argparse
import json
from pathlib import Path
import re

B = Path(__file__).resolve().parents[1]
FILLER = {'ah', 'oh', 'mm', 'mmm', 'hmm', 'um', 'umm', 'urmm', 'uh', 'er', 'yeah', 'yes', 'no', 'okay', 'ok', 'right', 'well'}


def save(path, d):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, default=B)
    args = p.parse_args()
    base = args.base
    reports = base / '核验/原文对齐'
    units, jobs, boundaries = [], [], []
    for path in sorted(reports.glob('*/对齐报告.json')):
        report = json.loads(path.read_text('utf-8'))
        year = report['year']
        for info in report['units']:
            d = json.loads((base / info['output']).read_text('utf-8'))
            unit = {**info, 'year': year, 'boundary_failure_count': len(info['missing_boundary_sentences']), 'category_counts': {}}
            for n in info['missing_boundary_sentences']:
                s = d['sentences'][n - 1]
                missing = [x['text'] for x in s['alignment']['missing']]
                all_words = re.findall('[a-z]+', s['en'].lower())
                missing_lower = {x.lower() for x in missing}
                relevant = [x for x in report['differences'] if any(z['unit'] == info['id'] and z['sentence'] == n for z in x['source'])]
                candidates = [x for x in relevant if x['kind'] == 'replace' and x['asr_text']]
                if missing_lower <= FILLER or ''.join(all_words) in {'ohisee', 'iseeyes', 'yesisee', 'ohreally', 'yesofcourse'}:
                    category = '2_应声或简短回应未识别'
                elif len(missing) >= 8:
                    category = '4_疑整段未对应_尚未证明缺实际语音'
                elif candidates:
                    category = '1_源文与ASR实词异文_须音证裁定'
                else:
                    category = '3_首尾词缺锚_其余有实际词锚'
                unit['category_counts'][category] = unit['category_counts'].get(category, 0) + 1
                boundaries.append({'year': year, 'unit': info['id'], 'sentence': n, 'category': category,
                                   'source_en': s['en'], 'missing': missing,
                                   'ASR_alternatives': [x['asr_text'] for x in candidates],
                                   'classification_status': 'machine_triage_not_human_decision'})
            units.append(unit)
        for window in report.get('rerecognition_windows', []):
            texts = ' '.join(x['source_text'].lower() for x in window['issues'])
            semantic = bool(re.search(r"\b(?:cannot|can't|not|never|no|isn't|aren't|don't|doesn't)\b", texts))
            # 边界故障优先；长连续缺词和否定词差异也必须识别，不能因在句内而漏掉。
            if window['boundary_sentences'] or window['missing_lexemes'] >= 6 or semantic:
                jobs.append({'year': year, 'source_sha256': report['inputs']['canonical_source_sha256'],
                             'primary_asr_sha256': report['inputs']['asr_sha256'],
                             'reason': 'boundary' if window['boundary_sentences'] else 'negation' if semantic else 'long_missing_run',
                             **window})
    jobs.sort(key=lambda x: (-len(x['boundary_sentences']), -x['missing_lexemes'], x['duration'], x['year']))
    result = {'status': 'machine_triage; all outputs remain draft',
              'years': sorted({u['year'] for u in units}), 'skip': [2022] if not any(u['year'] == 2022 for u in units) else [], 'units': units,
              'unit_count': len(units), 'exported_drafts': sum(u['state'].startswith('draft_exported') for u in units),
              'source_approved_preserved':sum(u['state']=='source_approved_preserved' for u in units),
              'blocked_units': sum(u['state'].startswith('blocked') for u in units),
              'boundary_sentences': boundaries,
              'classification_note': '类别4只表示原文/ASR连续缺口，未据此断言录音真实缺失；类别1也不据机器差异直接改源文。'}
    save(reports / '汇总.json', result)
    save(reports / '补词锚任务.json', {'status': 'candidate_rerecognition_only', 'jobs': jobs,
        'total_windows': len(jobs), 'total_seconds': round(sum(x['duration'] for x in jobs), 3),
        'note': '每窗由真实相邻ASR锚包围并留固定上下文，绝非推测缺词字幕时刻；主识别.json不改。'})
    print(json.dumps({k: result[k] for k in ['unit_count', 'exported_drafts', 'blocked_units']}, ensure_ascii=False))
    print(json.dumps({'windows': len(jobs), 'seconds': round(sum(x['duration'] for x in jobs))}, ensure_ascii=False))


if __name__ == '__main__':
    main()
