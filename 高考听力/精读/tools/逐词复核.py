"""对照真题录音逐词识别、已上传的 Otter 和 SenseVoice 转写，保留差异供原文核对。"""

import argparse
from difflib import SequenceMatcher
import io
import json
from pathlib import Path
import re
import zipfile

LISTENING = Path(__file__).resolve().parents[2]
TOKEN = re.compile(r"[a-z0-9]+(?:['’][a-z]+)?", re.I)
OTTER_HEADER = re.compile(r'^(?:Speaker \d+|Unknown speaker)\s+\d+:\d+(?::\d+)?\s*$', re.I | re.M)


def words(text):
    return [m.group().lower().replace('’', "'") for m in TOKEN.finditer(text)]


def compare(reference, candidate):
    matcher = SequenceMatcher(None, reference, candidate, autojunk=False)
    common = sum(b.size for b in matcher.get_matching_blocks())
    changes = []
    for action, a, b, c, d in matcher.get_opcodes():
        if action == 'equal':
            continue
        changes.append({'动作': action, '逐词识别位置': a + 1,
                        '逐词识别': ' '.join(reference[a:b]), '对照': ' '.join(candidate[c:d]),
                        '前文': ' '.join(reference[max(0, a - 6):a])})
    return {'对上词数': common, '逐词识别词数': len(reference), '对照词数': len(candidate), '差异': changes}


def member_name(info):
    try:
        return info.filename.encode('cp437').decode('gbk')
    except UnicodeError:
        return info.filename


def raw_digest(row):
    return (LISTENING / '识别' / row['识别'] / '原音.sha256').read_text('utf-8').split()[0]


def otter_for(sid, papers, index):
    row = papers[sid]
    for name in dict.fromkeys([row['名'], row['识别']]):
        if candidates := index.get(name, {}).get('otter'):
            return name, candidates[0]['文件']
    for other_id, other in papers.items():
        if other_id == sid or raw_digest(other) != raw_digest(row):
            continue
        for name in dict.fromkeys([other['名'], other['识别']]):
            if candidates := index.get(name, {}).get('otter'):
                return name, candidates[0]['文件']
    raise ValueError(f'{sid} 找不到同一录音的 Otter 转写')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('paper')
    ap.add_argument('archive', type=Path)
    ap.add_argument('out', type=Path)
    args = ap.parse_args()
    papers = json.loads((LISTENING / '套.json').read_text('utf-8'))
    index = json.loads((LISTENING / '原始材料/清单.json').read_text('utf-8'))
    row = papers[args.paper]
    otter_source, path = otter_for(args.paper, papers, index)
    with zipfile.ZipFile(args.archive) as z:
        hits = [m for m in z.infolist() if member_name(m) == path]
        if len(hits) != 1:
            raise ValueError(f'{path} 匹配了 {len(hits)} 个归档文件')
        with zipfile.ZipFile(io.BytesIO(z.read(hits[0]))) as inner:
            names = [n for n in inner.namelist() if n.lower().endswith('_transcript.txt')]
            if len(names) != 1:
                raise ValueError(f'{path} 包含 {len(names)} 份转写')
            otter = inner.read(names[0]).decode('utf-8-sig').split('Transcribed by https://otter.ai', 1)[0]
    parakeet = json.loads((args.out / '识别.json').read_text('utf-8'))
    sensevoice = json.loads((LISTENING / '识别' / row['识别'] / '分块.json').read_text('utf-8'))
    r = words(' '.join(t[0] for t in parakeet))
    if not r:
        raise ValueError(f'{args.paper} 逐词识别为空')
    report = {'套': row['名'], '原音_sha256': raw_digest(row), 'Otter 来源': otter_source,
              '解析材料': [x['文件'] for x in index[row['名']].get('解析', [])],
              'Otter': compare(r, words(OTTER_HEADER.sub('', otter))),
              'SenseVoice': compare(r, words(' '.join(b[3] for b in sensevoice)))}
    (args.out / '转写差异.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    print(args.paper, '逐词识别', len(r), '词，Otter 对上', report['Otter']['对上词数'], '，SenseVoice 对上', report['SenseVoice']['对上词数'])


if __name__ == '__main__':
    main()
