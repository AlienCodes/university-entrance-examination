"""只把实际已审完整 PNG 集合重绑到已证实仅编码入口变化的当前指纹。

plan 不改审批登记；apply 需要根审阅 plan 的确切 SHA 与审批说明。
绝不迁移 MP4，不制作新图，不改变主工作流。生产仍逐 PNG 比较完整多重集。
"""
import argparse
import copy
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('png_rebind_publisher', HERE / '发布汇集.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
B, ROOT = P.D, P.ROOT
OUT = B / '核验/最终60项PNG重绑'
BASE = '专八/听力/tools/听力视频.py'
EXAM = '专八/听力/批量/tools/考试视频.py'
MAIN = '专八/听力/批量/tools/精听.py'
DATA = '专八/听力/批量/tools/精听数据.py'
HELPER = '专八/听力/批量/tools/图片时钟核验.py'
OLD_MAIN = 'ff515e1be152ea29844970bca368f64b1dbe1939bd8aeacb075157630aeecf26'
OLD_DATA = '072c40ec95a6b532e798218d3be84eed68225608f53c1565f1c6c24895ba0d47'
AAC_MAIN = 'cd766f44cf2075c49331992cb8a2598e48a708d85b2dd873486c494252d03da0'
NEW_MAIN = '02c7fac4ffdadd727c671053c765a9ed0ca2262a36306e8e8874d67b2e2997df'
NEW_DATA = '11b4ef9c00ef2bae834dcb54026d6905202e3e3c57ace801033b25b080d1bb3e'
NEW_HELPER = '824e3ce562b7de13193493e0273f56ba50fb193ddb51f6b857b266851f10c491'
PROOFS = [
    '核验/考试图片时间基核验/默认关闭兼容与15年PNG不变证明.json',
    '核验/考试图片时间基核验/考试精确图片时钟冻结.json',
    '核验/精听图片时钟核验/门禁与最小影响自检结果.json',
    '核验/精听图片时钟核验/精听精确图片时钟冻结.json',
    '核验/AAC编码策略更新/23篇旧PNG核心兼容影响说明.json',
    '核验/最后十七篇在线图审/汇总.json',
]


def payload_part(row):
    return {k: row[k] for k in ('kind', 'id', 'inputs', 'render_sources', 'annotation_source') if k in row}


def diff(a, b):
    return {k: {'old': a.get(k), 'new': b.get(k)} for k in sorted(a.keys() | b.keys()) if a.get(k) != b.get(k)}


def sources():
    """只列根已接纳的 40 份真实候选，绝不自动挑选历史失败版本。"""
    rows = []
    def group(folder, ids, report):
        for ident in ids.split():
            rows.append((ident, B / folder / f'{ident}-candidate.json', B / folder / f'{ident}-{report}.json'))
    rows.append(('2011-A', B/'核验/线上精听审图/43515352262/2011-A/审核候选-旧在线指纹8d7d.json',
                 B/'核验/线上精听审图/43515352262/2011-A/实际审图.json'))
    group('核验/在线精听第二批-sources', '2012-A 2012-B1 2012-B2 2013-A', '实际图审')
    group('核验/在线精听2013_2014图审', '2013-B1 2013-B2 2014-A 2014-B1 2014-B2', '实际看图复核')
    group('核验/在线精听第三批-sources', '2015-B1 2015-B2 2016-A 2017-B2 2018-A 2018-B2', '实际图审')
    group('核验/在线精听2022_2024B2图审', '2022-A 2022-B1 2022-B2 2023-A 2023-B1 2023-B2 2024-B2', '实际看图复核')
    group('核验/最后十七篇在线图审', '2010-A 2010-B1 2010-B2 2011-B1 2011-B2 2015-A 2016-B1 2016-B2 2017-A 2017-B1 2018-B1 2019-A 2019-B1 2019-B2 2021-A 2021-B1 2021-B2', '实际图审')
    assert len(rows) == len({r[0] for r in rows}) == 40
    return rows


def human_pass(report, old):
    assert report['id'] == old['id']
    fp_keys = ['payload_sha256', 'online_payload_sha256', 'payload_sha256_reviewed',
               'reviewed_old_payload_sha256', 'old_payload_sha256_reviewed']
    assert old['payload_sha256'] in [report.get(k) for k in fp_keys], '人工报告未指向该真实候选'
    recommendation = report.get('visual_recommendation', report.get('recommendation', report.get('status')))
    assert recommendation in ['pass', 'pass_visual_old_payload', 'passed_for_reviewed_payload'], '未通过的人工结论'
    assert not report.get('visual_problems'), '人工报告仍有问题'
    assert 'fail' not in str(report.get('status', '')).lower()


def validate_change(old, current, cert, clock, aac_ids):
    assert old['payload_sha256'] == P.hash_json(payload_part(old)), '旧候选自身指纹不符'
    assert old['kind'] == current['kind'] and old['id'] == current['id']
    assert old['inputs'] == current['inputs'], '源文件字节发生未知变化：' + old['id']
    assert old.get('annotation_source') == current.get('annotation_source'), '母稿语义发生未知变化'
    shots = old.get('shots')
    assert shots and all(re.fullmatch('[0-9a-f]{64}', s) for s in shots.values()), '缺少真实完整 PNG SHA'
    changes = diff(old['render_sources'], current['render_sources'])
    if current['kind'] == 'exam':
        expected = {BASE: {'old': cert['base_old_sha256'], 'new': cert['base_new_sha256']},
                    EXAM: {'old': cert['adapter_old_sha256'], 'new': cert['adapter_new_sha256']}}
        assert changes == expected, '考试出现非已证实编码入口依赖变化：' + repr(changes)
        yr = next(r for r in cert['years'] if str(r['year']) == old['id'])
        assert yr['identical'] and yr['old'] == yr['new'], '该年可见输出证据不等价'
        assert len(shots) == len(set(yr['old']['PNG_keys_multiset'])), '旧已审图集合数量与证据不符'
    else:
        allowed = {MAIN: {'old': AAC_MAIN, 'new': NEW_MAIN}, HELPER: {'old': None, 'new': NEW_HELPER}}
        if old['render_sources'][MAIN] == OLD_MAIN:
            assert old['id'] in aac_ids, '该旧 AAC 核心单元无等价证据'
            allowed[MAIN]['old'] = OLD_MAIN
            allowed[DATA] = {'old': OLD_DATA, 'new': NEW_DATA}
        else:
            assert old['render_sources'][DATA] == NEW_DATA
        assert changes == allowed, '精听出现非已证实编码入口依赖变化：' + repr(changes)
        final = P.read(B / '精听数据' / (old['id'] + '.json'))
        body = copy.deepcopy(final); review = body.pop('review')
        assert review['status'] == 'approved' and review['content_sha256'] == P.hash_json(body), '源文审校未批准当前内容'
        assert not final.get('待核')
    return changes


def plan():
    OUT.mkdir(parents=True, exist_ok=True)
    registry = P.read(P.REGISTRY)
    registry_sha = P.sha(P.REGISTRY)
    cert = P.read(B / PROOFS[0]); clock = P.read(B / PROOFS[2]); aac = P.read(B / PROOFS[4])
    assert cert['status'] == 'PASS' and cert['all_other_functions_AST_identical']
    assert clock['status'] == 'pass' and all(t['passed'] for t in clock['tests'])
    assert clock['visual_engine_AST_unchanged'] and clock['compiled_data_file_unchanged'] and clock['audio_check_AST_unchanged']
    assert aac['count'] == 23 and aac['same_visual'] and aac['same_audio']
    assert all(r['source_visual_data_unchanged_since_that_review'] and r['source_audio_data_unchanged_since_that_review'] for r in aac['rows'])
    assert P.sha(ROOT/MAIN) == NEW_MAIN and P.sha(ROOT/DATA) == NEW_DATA and P.sha(ROOT/HELPER) == NEW_HELPER
    assert clock['current_core_sha256'] == NEW_MAIN and clock['checker_sha256'] == NEW_HELPER
    assert P.sha(ROOT/BASE) == cert['base_new_sha256'] and P.sha(ROOT/EXAM) == cert['adapter_new_sha256']
    aac_ids = {r['id'] for r in aac['rows']}
    candidates = []
    for year in P.YEARS:
        key = f'exam:{year}'; old = registry['entries'][key]
        assert old['status'] == 'approved' and old.get('evidence')
        candidates.append((key, old, P.REGISTRY, None))
    for ident in ['2009-A', '2009-B1', '2009-B2', '2024-A', '2024-B1']:
        key = 'intensive:' + ident; old = registry['entries'][key]
        assert old['status'] == 'approved' and old.get('evidence')
        candidates.append((key, old, P.REGISTRY, None))
    for ident, path, report_path in sources():
        old = P.read(path); human_pass(P.read(report_path), old)
        candidates.append(('intensive:' + ident, old, path, report_path))
    expected = {f'exam:{y}' for y in P.YEARS} | {f'intensive:{y}-{part}' for y in P.YEARS for part in ['A','B1','B2']}
    assert {r[0] for r in candidates} == expected and len(candidates) == 60
    evidence_paths = {P.relative(B/p): P.sha(B/p) for p in PROOFS}
    entries, rows = {}, []
    for key, old, path, report_path in candidates:
        current = P.payload(old['kind'], old['id'])
        changes = validate_change(old, current, cert, clock, aac_ids)
        old_ref = {'file': P.relative(path), 'sha256': P.sha(path), 'payload_sha256': old['payload_sha256'],
                   'evidence': old['evidence'], 'shots_multiset_sha256': P.hash_json(sorted(old['shots'].values()))}
        if report_path:
            report = P.read(report_path)
            old_ref['actual_visual_report'] = P.relative(report_path)
            old_ref['actual_visual_report_sha256'] = P.sha(report_path)
            old_ref['run_id'] = report.get('run_id')
            old_ref['head'] = report.get('head', report.get('head_sha'))
            evidence_paths[P.relative(path)] = P.sha(path)
            evidence_paths[P.relative(report_path)] = P.sha(report_path)
        row = {'status': 'pending', 'payload_sha256': P.hash_json(current), **current,
               'evidence': '等待根接纳：保留已实际审过的完整 PNG 字节多重集；仅按冻结的编码时钟等价证据更新指纹。所有 MP4 必须重新编码并全核，生产逐 PNG 核验仍生效。',
               'shots': copy.deepcopy(old['shots']), 'png_rebind_from': old_ref}
        entries[key] = row
        rows.append({'key': key, 'old_payload_sha256': old['payload_sha256'], 'current_payload_sha256': row['payload_sha256'],
                     'PNG_count': len(row['shots']), 'PNG_multiset_preserved': Counter(old['shots'].values()) == Counter(row['shots'].values()),
                     'source_inputs_identical': True, 'annotation_semantics_identical': True,
                     'dependency_changes': changes, 'old_review_evidence': old_ref})
    assert P.sha(P.REGISTRY) == registry_sha, '登记在生成候选期间已变化，请重跑'
    output = {'schema': 1, 'status': 'pending_root_approval', 'scope': '60项仅PNG审批重绑；15考试和45精听MP4全部重新编码，不复用旧视频',
              'registry_before_sha256': registry_sha, 'tool_sha256': P.sha(__file__), 'evidence_files': evidence_paths,
              'entries': entries, 'rows': rows, 'count': len(entries), 'PNG_count': sum(len(r['shots']) for r in entries.values()),
              'all_inputs_identical': True, 'all_PNG_multisets_preserved': True, 'unknown_differences': [],
              'production_gate': '发布汇集.gate(work)在编码前仍比较当前全部PNG的SHA多重集；任何未知新图拒绝。'}
    P.dump(OUT/'60项PNG重绑候选.json', output)
    P.dump(OUT/'摘要.json', {k:v for k,v in output.items() if k != 'entries'})
    print(json.dumps({'status':output['status'],'count':output['count'],'PNG_count':output['PNG_count'],
                      'plan':P.relative(OUT/'60项PNG重绑候选.json'),'sha256':P.sha(OUT/'60项PNG重绑候选.json')},ensure_ascii=False))


def apply(path, approved_sha, note):
    assert len(note.strip()) >= 20, '须记录根已实际审阅本候选与等价证据的结论'
    assert P.sha(path) == approved_sha, '不是根批准的确切候选字节'
    d = P.read(path)
    assert d['status'] == 'pending_root_approval' and d['count'] == len(d['entries']) == 60
    assert d['registry_before_sha256'] == P.sha(P.REGISTRY), '旧登记已变化，请重新生成候选'
    assert d['tool_sha256'] == P.sha(__file__), '候选工具已变化'
    for f, sha in d['evidence_files'].items():
        assert P.sha(ROOT/f) == sha, '旧审核证据已变化：' + f
    registry = P.read(P.REGISTRY)
    for key, entry in d['entries'].items():
        current = P.payload(entry['kind'], entry['id'])
        assert payload_part(entry) == current and entry['payload_sha256'] == P.hash_json(current), '源/依赖已变化'
        assert entry['shots'] and P.hash_json(sorted(entry['shots'].values())) == entry['png_rebind_from']['shots_multiset_sha256']
        assert entry['status'] == 'pending'
        entry = copy.deepcopy(entry); entry['status'] = 'approved'
        entry['evidence'] = note.strip() + '；' + entry['evidence'].replace('等待根接纳：', '')
        entry['png_rebind_plan_sha256'] = approved_sha
        registry['entries'][key] = entry
    P.dump(OUT/'重绑前审核登记.json', P.read(P.REGISTRY))
    tmp = P.REGISTRY.with_suffix('.json.tmp'); P.dump(tmp, registry); tmp.replace(P.REGISTRY)
    P.dump(OUT/'根批准应用记录.json', {'plan_sha256':approved_sha,'approval':note,'count':60,
           'registry_after_sha256':P.sha(P.REGISTRY),'MP4_migrated':False})
    print(json.dumps({'status':'applied_root_approved_PNG_only','count':60,'registry_sha256':P.sha(P.REGISTRY)},ensure_ascii=False))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='command', required=True)
    sub.add_parser('plan')
    a = sub.add_parser('apply'); a.add_argument('--plan',type=Path,required=True); a.add_argument('--approve-plan-sha',required=True); a.add_argument('--approval-note',required=True)
    args = ap.parse_args()
    if args.command == 'plan': plan()
    else: apply(args.plan,args.approve_plan_sha,args.approval_note)
