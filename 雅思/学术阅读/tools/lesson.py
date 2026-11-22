"""Load an edited IELTS lesson. Each gloss is tied to a unique source span."""
import json
import os
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
PID = os.environ.get('IELTS_LESSON','C20T1P1')
if not re.fullmatch(r'C(?:[1-9]|1[0-9]|20)T[1-4]P[1-3]',PID):
    raise ValueError(f'Invalid IELTS passage ID: {PID}')
LESSON = PROJECT / '篇目' / PID
TEXT = LESSON / '双语精读.tsv'

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

def load():
    meta = json.loads((LESSON / '篇目信息.json').read_text())
    paragraphs = []
    sentence_number = 0
    for paragraph in TEXT.read_text().strip().split('\n\n'):
        rows = []
        for line in paragraph.splitlines():
            sentence_number += 1
            en, zh, *glosses = line.split('\t')
            if not re.search(r'[一-龥]', zh) or not glosses:
                raise ValueError(line)
            words = []
            occupied = set()
            for slot,entry in enumerate(glosses):
                phrase, meaning = entry.split('|')
                spans = list(re.finditer(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', en, re.I))
                if not spans:
                    raise ValueError(f'{phrase}: {en}')
                positions = [list(match.span()) for match in spans]
                char_range = {i for begin, end in positions for i in range(begin, end)}
                if occupied.intersection(char_range): raise ValueError(entry)
                occupied.update(char_range)
                words.append(dict(t='phr' if ' ' in phrase else 'core',
                                  h=meta.get('row_lemmas',{}).get(f'{sentence_number}.{slot}',meta['lemmas'].get(phrase,phrase.lower())),m=meaning,sp=positions))
            rows.append(dict(en=en, zh=zh, w=words))
        paragraphs.append(rows)
    book, test, part = (meta[key] for key in ('book','test','passage'))
    if PID != f'C{book}T{test}P{part}':
        raise ValueError('Lesson metadata points to another book or passage')
    source_path=PROJECT/'原稿'/(PID+'.json')
    source=json.loads(source_path.read_text()) if source_path.is_file() else {}
    printed_test=source.get('printed_test',test)
    return dict(id=PID,paper=f'剑桥雅思 {book} · Test {printed_test}',passage=f"Passage {part} · {meta['title']}",
                fname=f'剑桥雅思{book} Test {printed_test} Passage {part}',title=meta.get('title_zh','鸮鹦鹉'),genre=meta.get('genre','说明文 · 物种保护'),
                words=sum(len(s['en'].split()) for pa in paragraphs for s in pa),paras=paragraphs)
