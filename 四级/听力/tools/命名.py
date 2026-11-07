"""四级听力成品命名（老师 2026-11-05，B 站分集标题就用文件名）：规则只写这一处（踩坑 108），引擎、发布、核对都调用。
  考试（视频版真题考试）：{年}-{月}-{套}考试.mp4      原文（原文精读）：{年}-{月}-{套}原文.mp4
  月份不补零；只有一套的场次也写 -1。资产名只用 ASCII：cet4-listening-<套>-exam.mp4 / -text.mp4（踩坑 123）。
  顺序：新的在前（年月倒序），同一年月第 1 套在前；同一套“考试”紧跟“原文”。"""
import re

KINDS = {'exam': '考试', 'text': '原文'}


def label(sid, kind):
    return f'{int(sid[:4])}-{int(sid[4:6])}-{int(sid[-1])}{KINDS[kind]}.mp4'


def asset(sid, kind):
    return f'cet4-listening-{sid}-{kind}.mp4'


def order(items):
    """items: [(套, kind)] → 发布顺序"""
    return sorted(items, key=lambda x: (-int(x[0][:6]), int(x[0][-1]), list(KINDS).index(x[1])))


NAME_RE = re.compile(r'(20\d\d)-(1[0-2]|[1-9])-([1-3])(考试|原文)\.mp4')


def problems(labels):
    bad = [f'文件名不合规：{n}' for n in labels if not NAME_RE.fullmatch(n)]
    if len(set(labels)) != len(labels): bad.append('文件名重复')
    return bad


if __name__ == '__main__':
    assert label('202606-1', 'exam') == '2026-6-1考试.mp4' and label('202007-1', 'text') == '2020-7-1原文.mp4'
    assert order([('202512-1', 'exam'), ('202606-2', 'exam'), ('202606-1', 'text'), ('202606-1', 'exam')]) == \
        [('202606-1', 'exam'), ('202606-1', 'text'), ('202606-2', 'exam'), ('202512-1', 'exam')]
    assert problems(['2026-06-1考试.mp4']) and not problems(['2026-6-1考试.mp4'])
    print('✅ 命名自检')
