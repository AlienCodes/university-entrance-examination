"""采访题组同屏的实际生产门禁双向验证；只读源数据，不运行浏览器或媒体程序。

默认运行标准库测试。可加 --report FILE 保存明确的离线测试报告。
状态与DOM快照都交给考试适配器内的实际门禁，不能只检查源码包含某个字符串。
"""
from __future__ import annotations
import argparse
import copy
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
ADAPTER = ROOT / '专八/听力/批量/tools/考试视频.py'
DATA = ROOT / '专八/听力/批量/数据'


def load_adapter():
    spec = importlib.util.spec_from_file_location('tem8_group_integrity_regression', ADAPTER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for name in ['validate_group_state', 'validate_group_states', 'validate_group_snapshot']:
        assert callable(getattr(module, name, None)), '生产同屏门禁尚未接入：' + name
    return module


def normalize_text(value):
    return ' '.join(value.split())


def source_papers():
    result = [json.loads(p.read_text('utf-8')) for p in sorted(DATA.glob('20*/试卷.json'))
              if p.parent.name != '2025']
    assert sorted(p['year'] for p in result) == list(range(2009, 2020)) + list(range(2021, 2025))
    return result


def state(group, kind='plist', n=None):
    result = {'kind': kind, 'group': group['id'], 'numbers': list(group['questions']),
              'display_page': 1, 'display_pages': 1}
    if kind == 'q':
        result['n'] = n if n is not None else group['questions'][0]
    return result


def snapshot(paper, group):
    lookup = {q['n']: q for q in paper['questions']}
    questions = []
    # 五个独立题块，A/B 固定第一行、C/D 固定第二行；这是批准版式的合成快照，
    # 只能证明生产断言的正反例，不能代替浏览器测量或生产 PNG 审阅。
    for qi, n in enumerate(group['questions']):
        top = 110. + qi * 170.
        options = []
        for oi, text in enumerate(lookup[n]['options']):
            left = 112. + (oi % 2) * 898.
            row_top = top + 6. + (oi // 2) * 74.
            options.append({'label': 'ABCD'[oi], 'text': text, 'font_size': 40.,
                            'scale': 1., 'visible': True, 'clipped': False,
                            'grid': {'label_column': 46., 'column_gap': 6.},
                            'label_rect': {'left': left, 'top': row_top,
                                           'right': left + 40., 'bottom': row_top + 44.},
                            'text_rect': {'left': left + 52., 'top': row_top,
                                          'right': left + 850., 'bottom': row_top + 68.},
                            'rect': {'left': left, 'top': row_top,
                                     'right': left + 850., 'bottom': row_top + 68.}})
        questions.append({'n': n,
                          'rect': {'left': 48., 'top': top,
                                   'right': 1872., 'bottom': top + 156.},
                          'separator': {'width': 2. if qi < 4 else 0.,
                                        'color': 'rgb(0, 0, 0)',
                                        'style': 'solid' if qi < 4 else 'none',
                                        'gap': 28. if qi < 4 else None},
                          'options': options})
    return {'group': group['id'], 'numbers': list(group['questions']), 'page_count': 1,
            'page_label': '', 'questions': questions}


class CompleteInterviewGroup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter_sha256 = hashlib.sha256(ADAPTER.read_bytes()).hexdigest()
        cls.module = load_adapter()
        assert cls.adapter_sha256 == hashlib.sha256(ADAPTER.read_bytes()).hexdigest(), '测试加载期间生产adapter发生改变，结果无效'
        cls.papers = source_papers()
        cls.paper = next(p for p in cls.papers if p['year'] == 2024)
        cls.group = cls.paper['groups'][1]

    def rejected_state(self, value, paper=None, explicit=True):
        with self.assertRaises((AssertionError, ValueError, KeyError, TypeError)):
            self.module.validate_group_state(paper or self.paper, value,
                                             require_explicit=explicit)

    def rejected_screen(self, value, screen_state=None):
        with self.assertRaises((AssertionError, ValueError, KeyError, TypeError)):
            self.module.validate_group_snapshot(self.paper,
                screen_state or state(self.group), value)

    def test_01_all_15_repair_years_every_group_and_every_active_question(self):
        total = 0
        type(self).complete_group_states_checked = 0
        for paper in self.papers:
            for group in paper['groups']:
                with self.subTest(year=paper['year'], group=group['id']):
                    self.assertEqual(len(group['questions']), 5)
                    events = [(0., state(group))]
                    self.module.validate_group_state(paper, events[0][1])
                    self.module.validate_group_snapshot(paper, events[0][1], snapshot(paper, group))
                    type(self).complete_group_states_checked += 1
                    for n in group['questions']:
                        s = state(group, 'q', n)
                        self.module.validate_group_state(paper, s)
                        self.module.validate_group_snapshot(paper, s, snapshot(paper, group))
                        type(self).complete_group_states_checked += 1
                        events.append((float(n), s))
                    self.module.validate_group_states(paper, events)
                    total += 1
        self.assertEqual(total, 30)
        self.assertEqual(type(self).complete_group_states_checked, 180)

    def test_02_original_two_plus_three_screens_are_rejected_individually(self):
        for nums in [self.group['questions'][:2], self.group['questions'][2:]]:
            s = state(self.group); s['numbers'] = nums; s['display_pages'] = 2
            self.rejected_state(s)
            self.rejected_state(s, explicit=False)

    def test_03_single_question_screen_during_answering_is_rejected(self):
        for n in self.group['questions']:
            s = state(self.group, 'q', n); s['numbers'] = [n]
            self.rejected_state(s)

    def test_04_missing_duplicated_reordered_or_cross_group_numbers(self):
        want = self.group['questions']
        for nums in [want[:-1], want + [want[-1]], list(reversed(want)),
                     [self.paper['groups'][0]['questions'][0]] + want[1:]]:
            s = state(self.group); s['numbers'] = nums
            self.rejected_state(s)

    def test_05_partial_source_events_must_not_be_silently_expanded(self):
        for nums in [self.group['questions'][:2], self.group['questions'][2:]]:
            self.rejected_state({'kind': 'plist', 'group': self.group['id'],
                                 'numbers': nums}, explicit=False)

    def test_06_strict_states_need_explicit_complete_numbers(self):
        for kind in ['plist', 'q']:
            s = state(self.group, kind); s.pop('numbers')
            self.rejected_state(s)
        # 原始定稿事件可缺派生numbers；归一化后的生产状态不可以。
        raw = {'kind': 'plist', 'group': self.group['id']}
        self.module.validate_group_state(self.paper, raw, require_explicit=False)

    def test_07_pagination_flag_or_foreign_active_question_rejected(self):
        for key, value in [('display_pages', 2), ('display_page', 2)]:
            s = state(self.group); s[key] = value; self.rejected_state(s)
        s = state(self.group, 'q', self.paper['groups'][0]['questions'][0])
        self.rejected_state(s)

    def test_08_source_group_not_five_or_option_not_four_rejected(self):
        p = copy.deepcopy(self.paper); p['groups'][1]['questions'].pop()
        self.rejected_state(state(self.group), p)
        for options in [[], ['A', 'B', 'C'], ['A', 'B', 'C', ''], ['A'] * 5]:
            p = copy.deepcopy(self.paper)
            next(q for q in p['questions'] if q['n'] == self.group['questions'][0])['options'] = options
            self.rejected_state(state(self.group), p)

    def test_09_whole_timeline_rejects_one_bad_countdown_tick(self):
        good = [(0., state(self.group)), (1., state(self.group, 'q'))]
        self.module.validate_group_states(self.paper, good)
        bad = copy.deepcopy(good); bad[1][1]['numbers'] = [self.group['questions'][0]]
        with self.assertRaises((AssertionError, ValueError, KeyError, TypeError)):
            self.module.validate_group_states(self.paper, bad)

    def test_10_dom_missing_duplicate_or_reordered_question(self):
        for change in ['missing', 'duplicate', 'reverse']:
            snap = snapshot(self.paper, self.group)
            if change == 'missing': snap['questions'].pop()
            elif change == 'duplicate': snap['questions'].append(copy.deepcopy(snap['questions'][-1]))
            else: snap['questions'].reverse()
            self.rejected_screen(snap)

    def test_11_dom_missing_or_mislabelled_option(self):
        snap = snapshot(self.paper, self.group); snap['questions'][0]['options'].pop()
        self.rejected_screen(snap)
        snap = snapshot(self.paper, self.group); snap['questions'][0]['options'][2]['label'] = 'D'
        self.rejected_screen(snap)
        # 二十选项全部存在也必须拒绝未获批准的 inline 连排与错位双栏。
        for oi, axis, delta in [(1, 'top', 12.), (2, 'left', 24.), (1, 'left', -700.)]:
            snap = snapshot(self.paper, self.group)
            rect = snap['questions'][0]['options'][oi]['rect']
            rect[axis] += delta
            rect['bottom' if axis == 'top' else 'right'] += delta
            self.rejected_screen(snap)
        for key, value in [('label_column', 45.), ('column_gap', 4.)]:
            snap = snapshot(self.paper, self.group)
            snap['questions'][0]['options'][0]['grid'][key] = value
            self.rejected_screen(snap)
        snap = snapshot(self.paper, self.group)
        opt = snap['questions'][0]['options'][0]
        opt['text_rect']['left'] = opt['label_rect']['right'] + 5.99
        self.rejected_screen(snap)

    def test_12_dom_rewritten_or_ellipsis_truncated_text(self):
        for text in ['...', 'Climate change…', '', 'WRONG SOURCE OPTION']:
            snap = snapshot(self.paper, self.group)
            snap['questions'][0]['options'][0]['text'] = text
            self.rejected_screen(snap)

    def test_13_dom_hidden_or_cropped_text(self):
        for key, value in [('visible', False), ('clipped', True)]:
            snap = snapshot(self.paper, self.group)
            snap['questions'][2]['options'][3][key] = value
            self.rejected_screen(snap)

    def test_14_dom_too_small_font_is_rejected(self):
        for size in [0., 16., 30., 39.99]:
            snap = snapshot(self.paper, self.group)
            snap['questions'][2]['options'][3]['font_size'] = size
            self.rejected_screen(snap)
        self.module.validate_group_snapshot(self.paper, state(self.group),
                                            snapshot(self.paper, self.group))

    def test_15_dom_page_label_or_cross_group_identity_is_rejected(self):
        for key, value in [('page_count', 2), ('page_label', '(1/2)'),
                           ('page_label', '（2 / 2）'), ('group', 'foreign-group')]:
            snap = snapshot(self.paper, self.group); snap[key] = value
            self.rejected_screen(snap)
        for key, value in [('width', 0.), ('width', 1.), ('width', 3.),
                           ('color', 'rgb(112, 119, 128)'), ('style', 'dashed'),
                           ('gap', 15.99)]:
            snap = snapshot(self.paper, self.group)
            snap['questions'][0]['separator'][key] = value
            self.rejected_screen(snap)
        # 用户批准模板真实文字gap约17.703；仅采访full-group下限为16，
        # 不能为了旧多题页20px检查去缩小已确认的43px字形。
        snap = snapshot(self.paper, self.group)
        for q in snap['questions'][:-1]: q['separator']['gap'] = 16.
        self.module.validate_group_snapshot(self.paper, state(self.group), snap)

    def test_16_non_question_states_are_out_of_scope(self):
        class NoDOMRead:
            def evaluate(self, *args):
                raise AssertionError('填空/答案页不应进入采访DOM门禁')
        for value in [{'kind': 'sheet', 'page': 2}, {'kind': 'ansB', 'numbers': [1, 2, 3]}]:
            self.module.validate_group_state(self.paper, value)
            self.assertIsNone(self.module.group_screen_check(NoDOMRead(), value))

    def test_17_dom_parent_transform_cannot_bypass_minimum_font(self):
        for scale in [.5, .99, 2.]:
            snap = snapshot(self.paper, self.group)
            snap['questions'][0]['options'][0]['scale'] = scale
            self.rejected_screen(snap)


    def test_18_user_confirmed_2025_legacy_identity_stays_frozen(self):
        lines = (ROOT / '.github/tem8-listening-release.txt').read_text('utf-8').splitlines()
        self.assertEqual(lines[2], 'df6e5f3a8995f8e416db36cae8316d8bc232ee64ecfbe9ba7f28359c1ea58ba4')
        self.assertEqual(lines[3:], [lines[1] + '.part00', lines[1] + '.part01'])



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CompleteInterviewGroup)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    adapter_sha256 = hashlib.sha256(ADAPTER.read_bytes()).hexdigest()
    source_unchanged = adapter_sha256 == getattr(CompleteInterviewGroup, 'adapter_sha256', None)
    ok = result.wasSuccessful() and source_unchanged
    if args.report:
        record = {'status': 'PASS' if ok else 'FAIL',
                  'scope': '实际生产纯状态/DOM快照门禁的离线正反例；不宣称已渲染或核过全部成品视频。',
                  'approved_layout': '固定A/B上行、C/D下行的两栏；题间2px纯黑#000000分隔线。',
                  'test_count': result.testsRun,
                  'adapter_sha256': getattr(CompleteInterviewGroup, 'adapter_sha256', None),
                  'adapter_source_unchanged': source_unchanged,
                  'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'synthetic_complete_group_states_checked': getattr(
                      CompleteInterviewGroup, 'complete_group_states_checked', 0),
                  'legacy_2025': {'policy': '用户明确确认保留2025既有视频，不重做；本测试只核旧清单声明身份，正式包还须核媒体原SHA透传。',
                                  'expected_video_sha256': 'df6e5f3a8995f8e416db36cae8316d8bc232ee64ecfbe9ba7f28359c1ea58ba4'}, 'failures': len(result.failures),
                  'errors': len(result.errors),
                  'source_years': list(range(2009, 2020)) + list(range(2021, 2025)),
                  'source_groups': 30, 'production_adapter': str(ADAPTER.relative_to(ROOT))}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    if not source_unchanged:
        print('测试期间生产adapter发生改变，结果无效，须冻结后重跑。', file=sys.stderr)
    sys.exit(not ok)


if __name__ == '__main__':
    main()
