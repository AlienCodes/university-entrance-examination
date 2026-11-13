"""从老师提供的原始ZIP补入全部真题文档，逐字节保留原卷、答案解析和听力原文。

python 补入原卷解析.py /path/default.zip
"""
import collections
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

D = Path(__file__).resolve().parent.parent
OUT = D / '真题原卷与解析'
EXPECTED = '9270b3f93995cfbddf77793e7d6ba4cd2b6464c2e9ae8100c1dab3acc1dc00a2'


def sha_file(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def original_name(info):
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode('cp437').decode('gbk')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def main(path):
    assert sha_file(path) == EXPECTED, '原始资料ZIP的SHA256不符'
    prior = json.loads((D.parent / '原始材料/清单.json').read_text('utf-8'))
    kinds = {row['文件']: kind for value in prior.values() for kind in ['空白卷', '解析', '原文'] for row in value.get(kind, [])}
    category = {'空白卷': '真题原卷', '解析': '答案与解析', '原文': '补充听力原文'}
    rows, targets, source_documents = [], set(), []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            name = original_name(info)
            if info.is_dir() or Path(name).suffix.lower() not in ('.doc', '.docx', '.pdf'):
                continue
            source_documents.append(name)
            kind = kinds.get(name)
            if kind is None:
                assert '听力试题及答案' in Path(name).name, ('旧清单之外的文档需确认类型', name)
                kind = '解析'
            year = re.search(r'20\d{2}', name)
            assert year and int(year.group()) >= 2019
            dst = OUT / category[kind] / year.group() / Path(name).name
            assert dst not in targets and dst.is_relative_to(OUT)
            targets.add(dst)
            data = archive.read(info)  # zipfile同时验证原ZIP条目的CRC。
            assert len(data) == info.file_size and data
            if dst.suffix.lower() == '.docx':
                import io
                with zipfile.ZipFile(io.BytesIO(data)) as doc:
                    assert 'word/document.xml' in doc.namelist() and doc.testzip() is None
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            assert sha_file(dst) == digest
            rows.append({'category': category[kind], 'year': int(year.group()), 'file': str(dst.relative_to(OUT)), 'source_file': name, 'bytes': len(data), 'sha256': digest})
    assert len(rows) == len(source_documents) and set(kinds).issubset(set(source_documents))
    assert set(p for p in OUT.rglob('*') if p.is_file()) == targets, '目录中存在未列清单的文档'
    rows.sort(key=lambda x: (x['category'], -x['year'], x['file']))
    counts = dict(collections.Counter(row['category'] for row in rows))
    manifest = {'source': '老师提供的gaokao-listening-raw/default.zip', 'source_sha256': EXPECTED, 'year_label': '2019年至今',
                'source_document_count': len(source_documents), 'document_count': len(rows), 'counts': counts,
                'verification': '原始ZIP整体SHA、逐条CRC及提取后文件SHA通过；原文档字节未修改。全部收录原始包中的DOC/DOCX/PDF文档。',
                'scope': '收录范围为老师提供的原始资料清单，不据此声称全国每年每地每场次试卷均齐全。', 'files': rows}
    audit = D / '原卷解析来源核验.json'
    audit.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    text = ['2019年至今高考英语真题原卷、答案解析及补充听力原文', '', '以下文档全部来自所提供的原始资料包，保留原DOC/DOCX/PDF格式及文件字节。', '分套听力PDF按“收录试卷清单.txt”使用；Word原卷与解析按下列清单查找。', '']
    for row in rows:
        text.append(row['file'])
    text += ['', '收录范围以实际清单为准，不表示全国所有地区、所有考试场次全部收录。']
    (D / '原卷解析文件清单.txt').write_text('\n'.join(text) + '\n', 'utf-8')
    print(json.dumps({'已补入': len(rows), '分类': counts, '字节': sum(row['bytes'] for row in rows), '全部原始文档覆盖': True}, ensure_ascii=False))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
