"""Repack the released PDFs into one folder per checked Bilibili video title."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unicodedata
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / '配套讲义'
FILES = ('视频逐屏讲义.pdf', '逐题解析.pdf', '长难句与写作句式.pdf')
ARCHIVE = 'Cambridge-IELTS-21-14-Study-PDF.zip'
BOOKS = tuple(range(21, 13, -1))


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_pack(original, dest, manifest):
    old = json.loads((PRODUCT / '讲义打包核验.json').read_text())
    years = json.loads((PRODUCT / '各册出版年.json').read_text())
    if digest(original) != old['zip_sha256'] or old['books'] != list(BOOKS):
        raise ValueError('Source does not match the published student edition')
    rows = old['contents']
    with (ROOT / '审校/第21至11册B站分P标题核对.tsv').open() as f:
        titles = [r['B站发布标题'] for r in csv.DictReader(f, delimiter='\t')]
    ids = [f'C{b}T{t}P{p}' for b in BOOKS for t in range(1,5) for p in range(1,4)]
    if [r['lesson'] for r in rows] != ids or len(titles) < len(ids):
        raise ValueError('Passage inventory differs from the paper')
    target_rows = []
    members = {}
    dest.mkdir(exist_ok=True, parents=True)
    out = dest / ARCHIVE
    with tempfile.TemporaryDirectory(dir=dest) as tmp:
        fresh = Path(tmp) / ARCHIVE
        with zipfile.ZipFile(original) as before, zipfile.ZipFile(fresh, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as after:
            if len(before.namelist()) != 288 or len(set(before.namelist())) != 288:
                raise ValueError('Unexpected original teaching files')
            for index, row in enumerate(rows):
                pid = row['lesson']
                source = json.loads((ROOT / '原稿' / (pid + '.json')).read_text())
                book = source['book']; test = source.get('printed_test',source['test']); passage = source['passage']
                prefix = f'{book}-{test}-{passage} '
                title = titles[index]
                if title != row['folder'] or not title.startswith(prefix):
                    raise ValueError(f'{pid}: wrong video title or printed numbering')
                year = years[str(book)]['year']
                folder = f'{title}（{year}年出版，第{book}册，Test {test}，Passage {passage}）'
                if re.search(r'[<>:"/\\|?*\x00-\x1f]',folder) or len(folder.encode())>240:
                    raise ValueError(folder)
                docs = {f['name']:f for f in row['files']}
                if set(docs)!=set(FILES): raise ValueError(pid+' does not have exactly three different PDFs')
                for name in FILES:
                    pdf = before.read(row['folder'] + '/' + name)
                    hashed = hashlib.sha256(pdf).hexdigest()
                    if hashed != docs[name]['sha256'] or not pdf.startswith(b'%PDF-'):
                        raise ValueError(pid + '/' + name + ' differs from the checked PDF')
                    member = folder + '/' + name
                    info=zipfile.ZipInfo(member,(2026,11,23,0,0,0))
                    info.external_attr=0o100644<<16
                    after.writestr(info,pdf,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
                    members[member] = hashed
                target_rows.append(dict(lesson=pid,video_title=title,publication_year=year,book=book,printed_test=test,
                                        passage=passage,folder=folder,files=[docs[n] for n in FILES]))
        with zipfile.ZipFile(fresh) as check:
            if check.namelist()!=list(members) or len(members)!=288: raise ValueError('Unexpected ZIP contents or order')
            folders=Counter(name.split('/')[0] for name in check.namelist())
            if len(folders)!=96 or set(folders.values())!={3} or len({unicodedata.normalize('NFC',s).casefold() for s in folders})!=96:
                raise ValueError('Folders are not one-to-one with the 96 videos')
            for name, expected in members.items():
                if name.count('/')!=1 or hashlib.sha256(check.read(name)).hexdigest()!=expected:
                    raise ValueError('Pack member failed its final SHA-256 check: '+name)
        fresh.replace(out)
    record=dict(books=list(BOOKS),passages=96,files=len(members),zip_name=out.name,zip_bytes=out.stat().st_size,
                zip_sha256=digest(out),source_zip_sha256=old['zip_sha256'],contents=target_rows)
    manifest.parent.mkdir(exist_ok=True,parents=True)
    manifest.write_text(json.dumps(record,ensure_ascii=False,indent=1)+'\n')
    print(f"{out.name}: {record['passages']} folders, {record['files']} PDFs, {record['zip_bytes']} bytes, {record['zip_sha256']}",flush=True)


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('original',type=Path);cli.add_argument('out',type=Path);cli.add_argument('manifest',type=Path)
    a=cli.parse_args();write_pack(a.original,a.out,a.manifest)
