"""给踩坑检查程序“埋雷”：在数据副本里故意放入每一种踩过的坑，检查程序必须全部查出。

    /opt/ttsenv/bin/python tools/test_check_pitfalls.py

只在内存里改副本，不动任何文件。任何一颗雷没被查出，退出码为 1。
（踩坑 21：检查标准一变就要埋雷测试，防止检查程序自己变松。）
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_pitfalls as C

REAL = C.data()
REAL_LOAD = C.load


def first_with(D, pid):
    return next(p for p in D['passages'] if p['id'] == pid)


def sent(p, k):
    return C.sents(p)[k - 1]


def plant_text(D):
    """返回 [(说明, 篇目, 期望查出的踩坑编号)]"""
    mines = []
    p = first_with(D, 'p25')
    sent(p, 3)['w'] = []
    mines.append(('句子没有标注单词', 'p25', 3))
    p = first_with(D, 'p26')
    sent(p, 2)['en'] = sent(p, 2)['en'].replace('’', "'", 1) if '’' in sent(p, 2)['en'] else sent(p, 2)['en'][:-1] + " world's."
    mines.append(('英文直撇号', 'p26', 7))
    p = first_with(D, 'p28')
    sent(p, 1)['en'] = sent(p, 1)['en'][:-1] + ' by G.'
    mines.append(('在人名缩写处断句', 'p28', 7))
    p = first_with(D, 'p29')
    s = next(x for x in C.sents(p) if '，' in x['zh'])
    s['zh'] = s['zh'].replace('，', ',', 1)
    mines.append(('中文半角逗号', 'p29', 25))
    p = first_with(D, 'p30')
    p['summary'] = p['summary'][:12] + p['summary'][6:]
    mines.append(('概要里重复字串（两处修改叠在一起）', 'p30', 25))
    p = first_with(D, 'p27')                     # matter 事件：高亮落在名词 matters 上，释义却是动词
    s = sent(p, 13)
    i = s['en'].index('matters')
    s['w'].append({'t': 'core', 'h': 'matter', 'm': 'v. 要紧；重要', 'sp': [[i, i + 7]]})
    mines.append(('高亮词词性与释义不符（matters）', 'p27', 24))
    p = first_with(D, 'p31')
    sent(p, 4)['en'] = sent(p, 4)['en'][:-1] + ' 实验.'
    mines.append(('朗读文本残留中文', 'p31', 5))
    sent(p, 6)['en'] = sent(p, 6)['en'][:-1] + ' #1 + more.'
    mines.append(('朗读文本残留符号 # +', 'p31', 5))
    p = first_with(D, 'p32')
    sent(p, 5)['zh'] = sent(p, 5)['zh'] + '。'
    mines.append(('复核通过后又改了文字', 'p32', 14))
    return mines


def main():
    found, missed = [], []
    D = copy.deepcopy(REAL)
    mines = plant_text(D)
    # 每颗雷都必须真的改动了数据（防止埋了个空雷却算作查出）
    changed = {p['id'] for p, q in zip(D['passages'], REAL['passages']) if p != q}
    assert changed == {m[1] for m in mines}, f'有雷没有埋进去：{ {m[1] for m in mines} - changed}'
    C.data = lambda: D
    R = C.Result()
    C.check_text(R, sorted({m[1] for m in mines}))
    for desc, pid, no in mines:
        hit = any(r[0] == no and r[1] == pid and not r[2] for r in R.rows)
        (found if hit else missed).append(f'{desc}（{pid}，踩坑 {no}）')

    # 音频：英文改了没重新生成音频（踩坑 20）；识别出否定词差异（踩坑 23）；音频换了没重跑自检（踩坑 4）
    D = copy.deepcopy(REAL)
    sent(first_with(D, 'p20'), 2)['en'] += ' Indeed.'
    C.data = lambda: D
    qa = json.loads((C.AUDIO / 'qa_report.json').read_text('utf-8'))
    qa['female']['p21']['sentences'][0]['ops'].append(["isn't", 'is'])
    qa['female']['p24']['sentences'][0]['ops'].append(['reawakened', 'reawaken'])
    qa['female']['p22']['mp3_sha256'] = '0' * 64
    qa['female']['p22'].pop('loudness', None)

    def fake_load(path, default):
        return qa if Path(path).name == 'qa_report.json' else REAL_LOAD(path, default)
    C.load = fake_load
    R = C.Result()
    C.check_audio(R, ['p20', 'p21', 'p22', 'p24'])
    for desc, pid, no in [('英文改了却没重新生成音频', 'p20', 20), ('否定词读错（isn’t→is）', 'p21', 23),
                          ('音频换了却没重跑语音识别自检', 'p22', 4), ('词尾 -ed 被吞（reawakened→reawaken）', 'p24', 23)]:
        hit = any(r[0] == no and r[1] == pid and not r[2] for r in R.rows)
        (found if hit else missed).append(f'{desc}（{pid}，踩坑 {no}）')
    C.load = REAL_LOAD
    C.data = lambda: REAL

    print(f'埋雷 {len(found) + len(missed)} 处，查出 {len(found)} 处')
    for x in found:
        print('  ✅', x)
    for x in missed:
        print('  ❌ 没查出：', x)
    sys.exit(1 if missed else 0)


if __name__ == '__main__':
    main()
