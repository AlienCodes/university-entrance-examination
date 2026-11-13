"""冻结六年十八篇的当前导出与可追溯源审候选；不批准、不改正文/时刻。

保留真实 ASR 未逐词对应项。ready 只表示此证据包可交根代理源审，
绝不等于 MP4 或译注已批准，更不把轻声/专名/节奏按比例补时间。
"""
import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import 精听数据 as contract
from 发布汇集 import annotation_semantics, hash_json, validate_annotation_snapshot

B = Path(__file__).resolve().parents[1]
OUT = B / '核验/2010—2015源审候选'


def read(p):
    return json.loads(Path(p).read_text('utf-8'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ref(name, expected=None):
    p = B / name
    actual = sha(p)
    assert expected is None or actual == expected, ('证据SHA变动', name)
    return {'file': name, 'sha256': actual}


def dump(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', 'utf-8')


EXTRA_CASES = {
    ('2010-A', 'categories.'): ('2010-A-categories.json', '独立Whisper目标句只有一次categories；纸源保留一次。主识别在该词附近重复分段，不新增第二次字幕。'),
    ('2010-B2', 'Oh,'): ('2010-B2-Oh.json', '独立Whisper为Oh, I see一次；同一实际短应答被主对齐重复计为额外Oh，保持源稿。'),
    ('2010-B2', 'D.'): ('2010-B2-Doctor.json', '实际为Dr/Doctor Johnson；D.为缩写的ASR碎片，不另增口述字母D。'),
    ('2011-A', 'they'): ('2011-A-they.json', '独立Whisper为when they’re talking to you；额外they是该缩约形式的重复分词，保留源稿they’re。'),
    ('2011-A', 'be?'): ('2011-A-be.json', '独立Whisper目标句只有一次would be；主ASR额外be为重复候选，不再补字幕。'),
    ('2012-A', 'do.'): ('2012-A-do.json', '独立Whisper目标片段为what researchers should do to record behaviour；其后WH产生明显重复幻觉，后缀排除不用。纸源只保留目标片段的一次do。'),
    ('2013-A', 'listening.'): ('2013-A-listening.json', '独立Whisper为activities other than listening and note-taking一次；排除主ASR重复listening片段。'),
    ('2015-B2', 'You'): ('2015-B2-You.json', '两个You都在原文：前句same as you结尾与本句You made开头；额外记录来自跨句匹配归属，不加第三个You，也不删相邻实际话轮。'),
}

# 这些都是语气/同词重复/弱功能词，内容词、否定、数字不得进入此白名单。
# 逐项保留印本与已核完整话轮；缺少单独字秒这一事实保持可见。
INTERNAL_CASES = {
    ('2010-A', 'features of, of language'): '同一介词of的口述重复；保留纸源口语式，模型只锚到其中一次，不为第二次of补秒。',
    ('2010-A', 'This, um, is'): '句内语气um保持纸源；实际语义及前后词锚完整，未声称该语气词有独立字秒。',
    ('2010-B1', 'The first is racial diversity'): 'The为句内弱冠词，first/racial diversity实际锚齐；保留参考字幕，不把缺冠词当内容差异或补造其秒。',
    ('2011-B1', 'today, urmm'): '句内犹豫声urmm；已核完整语义不变，保留印本犹豫标记，未声称独立词时。',
    ('2011-B1', 'and then, urmm'): '引语中犹豫声urmm；全句内容词和前后话轮实际锚齐，不造该声逐字时刻。',
    ('2011-B1', 'For example, umm'): '句内语气umm；保留印本口语标记，独立应声词时未知。',
    ('2012-A', 'and, and when'): '同一连接词and的犹豫重复；按已审口述保留源稿，不按语言习惯改写原句，第二次and无独立ASR锚。',
    ('2012-B1', 'or, or their project'): '同一连接词or重复，保留源稿原始口述；只留已实际返回的词锚，不推测第二个or时刻。',
    ('2012-B1', 'OK. Uh, artists'): '句内轻声Uh；内容词artists/musicians/writers等实际锚齐，保留纸源语气，未虚构Uh字秒。',
    ('2012-B1', 'ideas or or thoughts'): '同一连接词or重复，不改变ideas/thoughts内容；保留源稿，重复or仍无独立字秒。',
    ('2012-B2', 'point is, is they'): '同一系词is口述重复；正文语义与真实前后锚不变，不为重复is分摊时间。',
    ('2013-A', 'and, ah, what'): '讲座开头句内ah犹豫声；保留源稿，内容及句界实际锚齐，不造ah逐字时刻。',
    ('2014-A', 'stressors, er, things'): 'er为句内犹豫声；stressors技术词已由根裁定印本+同源整词锚，绝不重开该词或将er变成内容差异。',
    ('2014-B1', 'humanitarian crisis but um'): 'um为长话轮句内犹豫声；保留已核原句语义及完整真实界，不把省略的ASR语气词伪造为单词时间。',
    ('2014-B2', 'discuss and, and try'): '同一and口述重复；两模型文本可能归一化犹豫，字幕保留纸源重复，不声称两个独立and时刻。',
}


def question_proof(year, sentence):
    n = int(re.match(r'Question\s+(\d+)', sentence['en']).group(1))
    name = f'核验/{year}-考试内容审核.json'
    d = read(B / name)
    hits = [q for q in d['questions'] if q['n'] == n]
    assert len(hits) == 1, (year, n)
    q = hits[0]
    extra_note = None
    if not q['normalized_exact']:
        # 原审计的false如实保留。此唯一例已有明确源专名裁决，不能谎称旧程序exact。
        assert year == 2010 and n == 5 and '保持原PDF' in q['normalization_note']
        normalized = q['asr_text'].replace('Selling Grove', 'Selinsgrove').replace('Main,', 'Maine')
        words = lambda text: re.findall(r"[A-Za-z]+", text.casefold())
        assert words(normalized) == words(q['stem'])
        extra_note = '旧审计normalized_exact=false未改；其明确备注已裁Selinsgrove/Maine近音。仅此题局部按该备注比较后其余全部词相同，未建立全局别名或猜词时。'
    return {'evidence': ref(name), 'question': n, 'source_stem': q['stem'],
            'actual_ASR_text': q['asr_text'], 'source_review_normalized_exact': q['normalized_exact'],
            'normalization_note': q.get('normalization_note'), 'explicit_local_name_comparison': extra_note}


def missing_disposition(ident, year, sentence, missing):
    en = sentence['en']; a = sentence['alignment']
    if a.get('whole_sentence_audio_coverage_verified'):
        e = a['whole_sentence_audio_coverage_verified']
        return {'category': 'verified_whole_utterance_unknown_word_times_retained',
                'decision': e['decision'], 'evidence': ref(e['evidence_ref'], e['evidence_sha256']),
                'whole_sentence_window': [e['start'], e['end']],
                'individual_word_time_asserted': False}
    if a.get('acoustic_filler_boundary'):
        return {'category': 'native_spectral_verified_nonlexical_event',
                'decision': '独立嗯声已实读原采样率频谱，基音及倍频清楚；现有完整1229.31—1229.79应声范围保留，不造Umm词时。',
                'evidence': ref('核验/2010—2015整句声学证据/2013-B2-34-spectral-evidence.json'),
                'whole_sentence_window': [sentence['start'], sentence['end']],
                'individual_word_time_asserted': False}
    if en.startswith('Make sure the word(s)') and [m['text'] for m in missing] == ['s']:
        return {'category': 'printed_optional_plural_marker_not_separate_spoken_letter',
                'decision': 'word(s)为单复数书写形式；模型word/words均在此正式说明，不把括号s当额外念出的字母，不为s单独造秒。',
                'evidence': ref(f'说明语句/{year}.json'), 'individual_word_time_asserted': False}
    if en.startswith('Question '):
        return {'category': 'exam_reviewed_proper_name_ASR_spelling',
                'decision': '试题审核已逐题核同一源音人名/地名并保留原PDF规范拼写；ASR近音分词不改专名。个别专名字母仍无独立逐词映射，未推测时刻。',
                **question_proof(year, sentence), 'individual_word_time_asserted': False}
    hits = [decision for (unit, fragment), decision in INTERNAL_CASES.items()
            if unit == ident and fragment in en]
    assert len(hits) == 1, ('未分类缺词，必须人工裁决', ident, en, missing)
    return {'category': 'reference_retained_internal_disfluency_or_weak_function_word',
            'decision': hits[0],
            'assurance_limit': '既有本年原音正文审查与当前真首尾/内容词支持完整话轮；单个弱音/重复次数未由逐词ASR独立识别，保留该技术限制供根审，不标成字词100%。',
            'evidence': ref(f'核验/正文清理/{year}-双模型.json'),
            'individual_word_time_asserted': False}


def extra_disposition(ident, year, sentence, extra):
    if sentence['en'].startswith('Question '):
        return {'category': 'exam_reviewed_proper_name_ASR_spelling',
                'decision': '额外串为同一已审核专名的ASR近音/拆词，不是额外口述正文。',
                **question_proof(year, sentence)}
    if sentence['en'].startswith('Make sure the word(s)'):
        assert extra == ['words']
        return {'category': 'spoken_plural_variant_of_printed_word_s',
                'decision': 'words对应印本word(s)允许的复数形式，不新增第二个words字幕。',
                'evidence': ref(f'说明语句/{year}.json')}
    if ident == '2012-B2' and extra == ['better']:
        return {'category': 'ASR_duplicate_candidate',
                'decision': '既有完整话轮独立Whisper为a better, more creative brain一次；保留纸源单better，不扩写主模型重复片段。',
                'evidence': ref('核验/2010—2015整句声学证据/2012-B2-14.json')}
    key = (ident, ' '.join(extra))
    assert key in EXTRA_CASES, ('未分类多字，必须人工裁决', ident, extra)
    name, decision = EXTRA_CASES[key]
    return {'category': 'focused_independent_Whisper_reviewed_ASR_segmentation',
            'decision': decision,
            'evidence': ref('核验/2010—2015源审残留多词复核/' + name),
            'model_limitation': '独立Whisper仅作文本旁证；无有效token时刻，未据其推导词秒。'}


def main():
    index_name = '核验/2010-2015-源审依据索引.json'
    layout_name = '核验/2010-2015-语义分屏版式/汇总.json'
    index = read(B / index_name); layout = read(B / layout_name)
    assert layout['unit_count'] == 18 and layout['screen_count'] == 1113 and not layout['final_problems']
    assert index['current_split_semantics_counts']['sentences'] == 95
    assert index['current_split_semantics_counts']['screens'] == 197
    for e in index['shared_evidence']:
        ref(e['file'], e['sha256'])
    units = []; categories = Counter()
    for year in range(2010, 2016):
        mother_name = f'译注草稿/{year}.json'; mother = read(B / mother_name)
        prep_name = f'预处理/{year}/原音准备.json'; prep = read(B / prep_name)
        report_name = f'核验/原文对齐/{year}/对齐报告.json'; report = read(B / report_name)
        for entry in prep['source_entries']:
            actual = Path('/workspace/tem8-input') / entry['file']
            assert actual.is_file() and sha(actual) == entry['sha256'], ('原始音源SHA', actual)
        for m in mother['units']:
            ident = m['id']; final_name = f'精听数据/{ident}.json'; d = read(B / final_name)
            semantic_sha = validate_annotation_snapshot(d, m)
            contract.validate(d, draft=True)
            for s in d['sentences']:
                contract.align_words(s)
            # 只验证已有手定，不把自动候选偷升格为人工方案。
            plans = contract.resolve_manual_splits(d); manual_rows = []
            for plan in m.get('manual_splits', []):
                hits = [(n, s) for n, s in enumerate(d['sentences'], 1) if s['en'] == plan['en']]
                assert len(hits) == 1
                n, s = hits[0]; assert plans[str(n)]['at'] == plan['at'] and plans[str(n)]['zh'] == plan['zh']
                ats = plan['at'] if isinstance(plan['at'], list) else [plan['at']]
                cut_rows = []
                cuts = [0] + [s['en'].index(at) for at in ats] + [len(s['en'])]
                for at in ats:
                    char = s['en'].index(at); w = contract.first_aligned_word(s.get('word_alignment', []), s['en'], char)
                    cut_rows.append({'at': at, 'char': char, 'actual_first_word': s['en'][w['char']:w['char_end']],
                                     'actual_first_word_window': [w['start'], w['end']]})
                # 每屏至少一个真正的内容词注，不能用虚词填充；词条来源为已审语义平表。
                for lo, hi in zip(cuts, cuts[1:]):
                    assert any(lo <= a < z <= hi for w in s['w'] for a, z in w['sp']), (ident, n, '分屏无词注')
                manual_rows.append({'sentence': n, 'en': s['en'], 'at': copy.deepcopy(plan['at']),
                                    'zh': copy.deepcopy(plan['zh']), 'true_cut_word_anchors': cut_rows})
            idx = next(r for r in index['units'] if r['id'] == ident)
            assert idx['mother_sha256'] == sha(B / mother_name)
            for e in idx['year_evidence']:
                ref(e['file'], e['sha256'])
            geo = next(r for r in layout['results'] if r['id'] == ident)
            assert geo['current_mother']['sha256'] == sha(B / mother_name)
            assert geo['current_unit_all_fields_equal_layout_snapshot'] and not geo['final_problems']
            ref(geo['report'], geo['report_sha256'])
            ri = next(r for r in report['units'] if r['id'] == ident)
            assert ri['state'] == 'draft_exported_not_approved' and not ri['missing_boundary_sentences']
            assert d['audio']['sha256'] == prep['canonical']['sha256']
            assert d['audio']['boundary_evidence']['status'] == 'measured_PCM_boundaries_or_complete_file_edge'
            missing_rows = []; extra_rows = []; whole_events = []; nonverbal_events = []; filler_events = []
            for n, s in enumerate(d['sentences'], 1):
                a = s['alignment']; missing = a.get('missing', []); extra = a.get('unmatched_internal_asr', {}).get('asr_text', [])
                if missing:
                    disp = missing_disposition(ident, year, s, missing); categories[disp['category']] += len(missing)
                    missing_rows.append({'sentence': n, 'en': s['en'], 'window': [s['start'], s['end']],
                                         'missing_source_lexemes': missing, 'disposition': disp})
                if extra:
                    extra_rows.append({'sentence': n, 'en': s['en'], 'extra_ASR': a['unmatched_internal_asr'],
                                       'disposition': extra_disposition(ident, year, s, extra)})
                for key, bucket in [('whole_sentence_audio_coverage_verified', whole_events), ('nonverbal_evidence', nonverbal_events)]:
                    if a.get(key):
                        e = a[key]; ref(e['evidence_ref'], e['evidence_sha256'])
                        bucket.append({'sentence': n, 'en': s['en'], 'window': [s['start'], s['end']], 'evidence': e})
                if a.get('acoustic_filler_boundary'):
                    filler_events.append({'sentence': n, 'en': s['en'], 'window': [s['start'], s['end']],
                                          'machine_evidence': a['acoustic_filler_boundary'],
                                          'native_spectral_review': ref('核验/2010—2015整句声学证据/2013-B2-34-spectral-evidence.json')})
                assert a.get('boundary_anchored') or a.get('whole_sentence_audio_coverage_verified') or a.get('nonverbal_evidence') or a.get('acoustic_filler_boundary'), (ident, n, '真句界未解决')
            source_notes = []
            if ident == '2011-B1':
                source_notes.append({'type': 'printed_only_nonspoken_subtitle_omission',
                                     'evidence': ref('核验/正文清理/2011-印本未念应声省略.json'),
                                     'decision': '仅省略前后唯一真锚之间、双ASR与原采样率频谱共同证实未念的那一条印本Mm；另一独立实际鼻音Mm保留。原音不删不改。'})
            if ident == '2013-B2':
                source_notes.append({'type': 'historical_aggregate_flag_stage_order',
                                     'decision': '2013报告coverage.all_sentence_boundaries_resolved=false为声学应声填充前的聚合值；本单元逐项missing_boundary_sentences为空，Umm完整声岛另有原采样率频谱实读。保留原报告，不改冻结核心。'})
            if year == 2014:
                source_notes += [{'type': 'latest_metadata_repairs', 'evidence': ref(n)} for n in [
                    '核验/2014-B1-正式说明人名登记.json', '核验/2014-采访短题名登记.json',
                    '核验/2014-B1-访谈追问UNHCR简称恢复.json']]
            candidate = {
                'id': ident, 'year': year, 'status': 'source_review_candidate_not_approved',
                'recommendation': 'ready',
                'recommendation_scope': '当前源文/译注/真实界/语义手定证据齐备，可提交根源审；未逐词定时的语气、同词重复、专名异拼及节奏明列，须由根采纳例外。不等于MP4或正式发布批准。',
                'mother': {**ref(mother_name), 'unit_semantic_sha256': semantic_sha},
                'final': {**ref(final_name), 'unit_semantic_sha256': hash_json(annotation_semantics(d)),
                          'render_content_sha256': contract.content_sha(d), 'review_status': d.get('review', {}).get('status')},
                'mother_final_semantics_exact': True, 'EN_ZH_W': {'sentence_count': len(d['sentences']),
                    'sha256': hash_json([{'en': s['en'], 'zh': s['zh'], 'w': s['w']} for s in d['sentences']])},
                'audio': {'canonical_source_sha256': prep['canonical']['sha256'], 'raw_source_entries': prep['source_entries'],
                          'raw_source_sha_verified_on_disk': True, 'window': d['audio']['window'],
                          'boundary_status': d['audio']['boundary_evidence']['status'],
                          'boundary_evidence_sha256': hash_json(d['audio']['boundary_evidence']),
                          'raw_audio_unchanged': True},
                'alignment': {'report': ref(report_name), 'state': ri['state'], 'missing_boundary_sentences': [],
                    'raw_missing_word_count': sum(len(r['missing_source_lexemes']) for r in missing_rows),
                    'missing_word_dispositions': missing_rows, 'extra_ASR_dispositions': extra_rows,
                    'whole_utterance_exceptions': whole_events, 'nonverbal_exceptions': nonverbal_events,
                    'acoustic_filler_exceptions': filler_events,
                    'no_unknown_word_times_invented': True,
                    'timing_fingerprint_sha256': hash_json([{'en': s['en'], 'start': s['start'], 'end': s['end'],
                        'word_alignment': s.get('word_alignment', []), 'nonverbal': s.get('nonverbal', False)} for s in d['sentences']])},
                'manual_splits': {'mother_final_exact': True, 'count': len(manual_rows),
                    'screen_count': sum(len(r['zh']) for r in manual_rows), 'all_true_cut_first_word_anchors': True,
                    'chinese_reassembles': True, 'no_highlight_cut': True, 'every_part_has_real_annotation': True,
                    'rows': manual_rows},
                'geometry': {'evidence': ref(layout_name), 'report': ref(geo['report'], geo['report_sha256']),
                    'screens': geo['screens'], 'final_problems': [], 'manual_plans_not_rewritten': True},
                'prior_source_review': {'index': ref(index_name), 'year_evidence': idx['year_evidence'],
                    'shared_evidence': index['shared_evidence'], 'body_audio_corrections_cited': idx['body_audio_corrections_cited']},
                'specific_notes': source_notes, 'retained_input_pending': d.get('待核', []),
                'parent_actions': ['根逐项采纳本包disposition/整声例外后登记当前content_sha256源审；本工具不改draft/待核。',
                                   '正式编码后仍需真实在线画面、换屏时刻及音画审查。'],
            }
            dump(OUT / (ident + '.json'), candidate); units.append(candidate)
    summary = {'status': '18_exported_current_semantics_source_candidates_not_approved',
               'recommendation_meaning': 'ready=证据包齐全可交根源审；不等于无缺失字词时间，不自动批准或清待核。',
               'units': units, 'counts': {'units': len(units), 'ready': len(units), 'hold': 0,
                   'sentences': sum(u['EN_ZH_W']['sentence_count'] for u in units),
                   'manual_sentences': sum(u['manual_splits']['count'] for u in units),
                   'manual_screens': sum(u['manual_splits']['screen_count'] for u in units),
                   'geometry_screens': sum(u['geometry']['screens'] for u in units),
                   'missing_source_lexemes_retained': sum(u['alignment']['raw_missing_word_count'] for u in units),
                   'missing_word_categories': dict(categories),
                   'extra_ASR_disposition_rows': sum(len(u['alignment']['extra_ASR_dispositions']) for u in units),
                   'whole_utterance_exceptions': sum(len(u['alignment']['whole_utterance_exceptions']) for u in units),
                   'nonverbal_exceptions': sum(len(u['alignment']['nonverbal_exceptions']) for u in units),
                   'acoustic_filler_exceptions': sum(len(u['alignment']['acoustic_filler_exceptions']) for u in units)},
               'constraints': ['未改任何母稿EN/ZH/w或原音/词时。', 'unknown保持可见，未为了100%分摊字秒。',
                               '2009/2024源锁单元未触碰，GitHub工作流/renderer未改、未启动。']}
    assert summary['counts']['units'] == 18 and summary['counts']['manual_sentences'] == 95 and summary['counts']['manual_screens'] == 197
    dump(B / '核验/2010—2015源审候选.json', summary)
    # 替换旧11/18历史快照，避免误读为尚未实际导出。
    dump(B / '核验/2010—2015最终导出核查.json', {
        'status': '18_of_18_actual_draft_exports_current_mother_semantics_exact',
        'source_candidates': ref('核验/2010—2015源审候选.json'), 'counts': summary['counts'],
        'units': [{'id': u['id'], 'final': u['final'], 'mother': u['mother'], 'audio': u['audio'],
                   'recommendation': u['recommendation'], 'missing_boundary_sentences': [],
                   'raw_missing_word_count': u['alignment']['raw_missing_word_count'],
                   'candidate': ref('核验/2010—2015源审候选/' + u['id'] + '.json')} for u in units],
        'not_approved': True, 'note': '逐项技术限制、弱音/专名/节奏例外及额外ASR裁决见对应candidate，未通用清待核或自称字词100%。'})
    print(json.dumps(summary['counts'], ensure_ascii=False))


if __name__ == '__main__':
    main()
