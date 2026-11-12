"""高考听力成品命名：规则只写这一处（踩坑 108），引擎、发布都调用。
  文件名：{年}年 {卷名} 高考英语真题 视频版考试.mp4（老师要求 7、铁律 6；卷名来自 套.json，同一年两次考试写明场次）
  资产名只用 ASCII：gaokao-listening-<套>.mp4（踩坑 123）。顺序：按年份，每年全国卷在前（铁律 7），再浙江、江苏、上海（春在秋前）。"""
import json, re
from pathlib import Path

SETS = json.loads((Path(__file__).resolve().parents[1] / '套.json').read_text('utf-8'))
NAME_RE = r'^(20\d\d)年 (\S+) 高考英语真题 视频版考试\.mp4$'
KINDS = {'exam': '考试'}


def label(sid, kind='exam'):
    y, paper = SETS[sid]['名'].split(' ', 1)
    return f'{y}年 {paper} 高考英语真题 视频版考试.mp4'


def legacy_label(sid, kind='exam'):
    """已核成品只在发布环节换中文标签和zip内名，不重做视频。"""
    y, paper = SETS[sid]['名'].split(' ', 1)
    return f'{y}年 {paper} 高考英语听力 视频版真题考试.mp4'


def asset(sid, kind='exam'):
    return f'gaokao-listening-{sid}.mp4'


def rank(sid):
    p = SETS[sid]['名']
    return (int(p[:4]), 3 if '上海' in p else 2 if '江苏' in p else 1 if '浙江' in p else 0, p)


def order(items):
    return sorted(items, key=lambda x: rank(x[0]))


def problems(labels):
    bad = [f'文件名不合规：{n}' for n in labels if not re.fullmatch(NAME_RE, n)]
    if len(set(labels)) != len(labels): bad.append('文件名重复')
    return bad


if __name__ == '__main__':
    assert label('2019-shc') == '2019年 上海卷（春考） 高考英语真题 视频版考试.mp4', label('2019-shc')
    o = [x for x, _ in order([(s, 'exam') for s in SETS])]
    assert o.index('2019-xkb1') < o.index('2019-zj6') < o.index('2019-shc') < o.index('2020-xkb1'), o[:8]
    assert not problems([label(s) for s in SETS]) and problems(['2019 上海卷 高考英语听力.mp4'])
    print('✅ 命名自检')
