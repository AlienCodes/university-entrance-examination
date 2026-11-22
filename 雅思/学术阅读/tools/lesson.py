"""Load an edited IELTS lesson. Each gloss is tied to a unique source span."""
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
PID = 'C20T1P1'
LESSON = PROJECT / '篇目' / PID
TEXT = LESSON / '双语精读.tsv'

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

def load():
    meta = json.loads((LESSON / '篇目信息.json').read_text())
    paragraphs = []
    for paragraph in TEXT.read_text().strip().split('\n\n'):
        rows = []
        for line in paragraph.splitlines():
            en, zh, *glosses = line.split('\t')
            if not re.search(r'[一-龥]', zh) or not glosses:
                raise ValueError(line)
            words = []
            occupied = set()
            for entry in glosses:
                phrase, meaning = entry.split('|')
                spans = list(re.finditer(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', en, re.I))
                if not spans:
                    raise ValueError(f'{phrase}: {en}')
                positions = [list(match.span()) for match in spans]
                char_range = {i for begin, end in positions for i in range(begin, end)}
                if occupied.intersection(char_range): raise ValueError(entry)
                occupied.update(char_range)
                words.append(dict(t='phr' if ' ' in phrase else 'core',
                                  h=meta['lemmas'].get(phrase,phrase.lower()),m=meaning,sp=positions))
            rows.append(dict(en=en, zh=zh, w=words))
        paragraphs.append(rows)
    return dict(id=PID,paper='剑桥雅思 20 · Test 1',passage='Passage 1 · The kākāpō',
                fname='剑桥雅思20 Test 1 Passage 1',title='鸮鹦鹉',genre='说明文 · 物种保护',
                words=sum(len(s['en'].split()) for pa in paragraphs for s in pa),paras=paragraphs)
