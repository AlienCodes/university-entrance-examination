"""铁律 20 双向验证：作文字数范围（tools/作文规则.word_range + check）。
有上限（at least 150 / no more than 200）：189 报、190 不报、200 不报、201 报；
只有下限（at least 100）：109 报、110 不报、120 不报、121 报；about 100 同。"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import 作文规则 as r
def bad(limit, n):
    e = {'id': 't', 'prompt': '', 'limit': limit, 'body': [' '.join(['word'] * (n - 1)) + ' end.']}
    lo, hi = r.word_range(limit)
    return any(x.startswith('字数') for x in r.check(e, lo, hi))
cases = [('at least 150 words but no more than 200 words', n, n in (189, 201)) for n in (189, 190, 200, 201)]
cases += [(lim, n, n in (109, 121)) for lim in ('at least 100 words', 'about 100 words') for n in (109, 110, 120, 121)]
wrong = [(l, n) for l, n, want in cases if bad(l, n) != want]
print('作文字数双向验证：', len(cases), '例', '全部正确' if not wrong else f'不符 {wrong}')
sys.exit(1 if wrong else 0)
