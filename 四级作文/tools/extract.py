"""四级作文范文 → 句子（供翻译、标注、讲义、音频、视频使用；照 考研作文/tools/extract.py）。

    python3 四级作文/tools/extract.py

输入 四级/作文/2026.json … 2021.json（范文定稿，6 轮复核，见 四级/作文/复核记录.md），输出 四级作文/作文/sents.json：
[{id, src, year, month, set, paper, passage, pdf, words, prompt_img, lead, sents: [[段1句1, …], …], first?}]
编号 c01 = 2026 年 6 月第 1 套 …（从新到旧；同一次考试第 1 套在前）。
切句用考研阅读的 split（保护缩写），逐段校验句子拼回去与原段落完全一致。
lead = 第一句开口时刻：片头 1.5 秒 + 原题屏 PROMPT 秒（都静音）；音频、视频都从这里取。
"""
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parent
ROOT = C.parent
PROMPT = 2.0           # 原题屏停留秒数（同考研作文，用户 2026-10-22 定）
_spec = importlib.util.spec_from_file_location('ky_split', ROOT / '考研' / 'tools' / 'split_sents.py')
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
split = _m.split


def count(sents):
    """片头“全文 N 词”：与 build_vocab 的复算规则相同（tools/text_rules.word_count 的口径：空白、破折号、省略号切分）。"""
    return len([w for w in re.split(r'[\s—–…]+', ' '.join(s for para in sents for s in para)) if re.search(r'[A-Za-z0-9]', w)])


def essays():
    es = []
    for p in (C.parent / '四级' / '作文').glob('20??.json'):
        es += json.loads(p.read_text('utf-8'))
    def key(e):
        y, m, s = re.match(r'c(\d{4})-(\d\d)-(\d)', e['id']).groups()
        return (-int(y), -int(m), int(s))
    return sorted(es, key=key)


def main():
    out = []
    for n, e in enumerate(essays(), 1):
        pid = f'c{n:02d}'
        y, m, s = re.match(r'c(\d{4})-(\d\d)-(\d)', e['id']).groups()
        sents = []
        for para in e['body']:
            ss = split(para)
            assert ' '.join(ss) == para, (pid, para[:80])
            sents.append(ss)
        rec = {'id': pid, 'src': e['id'], 'year': int(y), 'month': int(m), 'set': int(s),
               'paper': f"{e['paper']} 写作", 'passage': 'Part I', 'pdf': e['paper'],
               'words': count(sents), 'prompt_img': f'{pid}.png', 'lead': round(1.5 + PROMPT, 3), 'sents': sents}
        if e.get('first'):
            rec['first'] = e['first']
        out.append(rec)
    (C / '作文').mkdir(exist_ok=True)
    (C / '作文' / 'sents.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')
    print(f'{len(out)} 篇，{sum(len(s) for r in out for s in r["sents"])} 句')


if __name__ == '__main__':
    main()
