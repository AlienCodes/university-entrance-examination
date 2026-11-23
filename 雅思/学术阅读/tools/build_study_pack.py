"""Build a single download with the two reviewed study guides and the original slide PDF per passage."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata
import zipfile

import fitz
from playwright.sync_api import sync_playwright

from study_pdfs import PROJECT, render, rng
import illustrated_answers
from editions import lesson_ids
from illustration_stage import POLICY

READING = '逐题解析.pdf'
WRITING = '长难句与写作句式.pdf'
SLIDES = '视频逐屏讲义.pdf'


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def normalized(value):
    return ''.join(unicodedata.normalize('NFKC', value).split())


def validate_pages(path):
    with fitz.open(path) as pdf:
        if not pdf.page_count:
            raise ValueError(f'Empty PDF: {path}')
        texts = []
        for page in pdf:
            body = page.get_text()
            if len(normalized(body)) < 40 or '\ufffd' in body:
                raise ValueError(f'{path}, page {page.number + 1}: empty page or missing glyph')
            for block in page.get_text('blocks'):
                if block[0] < -1 or block[1] < -1 or block[2] > page.rect.width + 1 or block[3] > page.rect.height + 1:
                    raise ValueError(f'{path}, page {page.number + 1}: text outside of page')
            texts.append(normalized(body))
        return texts


def inspect_guides(folder, lesson, notes, movie=None):
    reading_spreads = validate_pages(folder / READING)
    reading = ''.join(reading_spreads)
    for q in lesson['questions']:
        no = q['numbers'][0]
        if normalized('第' + rng(q) + '题') not in reading or normalized('答案' + q['answer']) not in reading:
            raise ValueError(f"{lesson['lesson']} Q{no}: printed answer or question number missing")
        note=notes['questions'][str(no)]
        details=[note['logic']]
        if movie:
            details.extend([note['focus'],note['locate'],note['check']])
            details.extend(entry['why'] for entry in note['distractors'])
        if any(normalized(line) not in reading for line in details):
            raise ValueError(f"{lesson['lesson']} Q{no}: printed explanation incomplete")
    writing = validate_pages(folder / WRITING)
    if len(writing) != len(notes['grammar']):
        raise ValueError(f"{lesson['lesson']}: incomplete or overflowed grammar spread")
    for content, page in zip(notes['grammar'], writing):
        for field in ('heading', 'analysis', 'task', 'example', 'example_zh', 'usage'):
            if normalized(content[field]) not in page:
                raise ValueError(f"{lesson['lesson']} sentence {content['sentence']}: printed {field} incomplete")
    return len(reading_spreads), len(writing)


def illustrated_inputs(pid, entry, slides):
    audit = PROJECT / '审校' / 'Aiden' / '13-6' / '篇目' / pid / '插图成片核验.json'
    if sha256(audit) != entry['illustrated_receipt_sha256']:
        raise ValueError(pid + ': final video receipt differs from the release index')
    movie = json.loads(audit.read_text())
    slide = json.loads((slides / (pid + '.slides.json')).read_text())
    if (movie['policy'] != POLICY or movie['video_sha256'] != entry['sha256']
            or slide['lesson'] != pid or slide['video_sha256'] != entry['sha256']
            or slide['illustration_sha256'] != movie['illustration_sha256']
            or movie['screens'][1] != dict(page=2, screen='篇目插图', frame=60)
            or [{k:r[k] for k in ('page','screen','frame')} for r in slide['frames']] != movie['screens']):
        raise ValueError(pid + ': pages do not correspond to the published film')
    return slide, movie


def build(notes_dir, slides_dir, zip_path, receipt_path, edition='21-14'):
    illustrated = edition == '13-6'
    books = list(range(13,5,-1) if illustrated else range(21,13,-1))
    ids = lesson_ids(books)
    if illustrated:
        reports = PROJECT / '审校' / 'Aiden' / '13-6'
        index = json.loads((reports / '第13至6册视频成品核验.json').read_text())
        public = json.loads((reports / '第13至6册视频发布核验.json').read_text())
        if (not public['hosted_download_verified'] or public['count']!=len(ids)
                or public['sha256']!=index['sha256'] or public['bytes']!=index['bytes']):
            raise ValueError('The reading handouts must correspond to the published video collection')
        sources = index['lessons']
    else:
        sources = json.loads((PROJECT / '配套讲义' / '逐屏讲义源文件.json').read_text())
    by_id = {s['lesson']: s for s in sources}
    if set(ids) != set(by_id) or len(sources) != 96:
        raise ValueError('Slide manifest does not cover the 96 passages')
    receipts = []
    seen = {}
    paper_numbers = {}
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=zip_path.parent) as tmp:
        work = Path(tmp)
        candidate = work / 'study.zip'
        with sync_playwright() as pw, zipfile.ZipFile(candidate, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
            executable = os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium')
            browser = pw.chromium.launch(executable_path=executable, args=['--no-sandbox', '--disable-dev-shm-usage'])
            try:
                for pid in ids:
                    source = by_id[pid]
                    movie = None
                    slide = slides_dir / (pid + '.pdf')
                    notes = json.loads((notes_dir / (pid + '.json')).read_text())
                    lesson = json.loads((PROJECT / '配套讲义' / '题目与证据' / (pid + '.json')).read_text())
                    if illustrated:
                        if source['filename'] != lesson['display_title']+'.mp4':
                            raise ValueError(pid + ': study folder and published video name differ')
                        source,movie = illustrated_inputs(pid,source,slides_dir)
                        paper_numbers.setdefault(pid.split('P')[0],[]).extend(
                            number for q in lesson['questions'] for number in q['numbers'])
                    if slide.stat().st_size != source['bytes'] or sha256(slide) != source['sha256']:
                        raise ValueError(f'{pid}: slide PDF differs from the verified video companion')
                    with fitz.open(slide) as pdf:
                        if len(pdf) != source['pages']:
                            raise ValueError(f'{pid}: missing original slide')
                    cover_check = render(browser, pid, notes_dir, work, movie, slide if illustrated else None)
                    folder = work / lesson['display_title']
                    reading_pages, writing_pages = inspect_guides(folder, lesson, notes, movie)
                    printed = [(READING, folder / READING, reading_pages), (WRITING, folder / WRITING, writing_pages), (SLIDES, slide, source['pages'])]
                    assets = []
                    for name, path, pages in printed:
                        arcname = f"{lesson['display_title']}/{name}"
                        archive.write(path, arcname)
                        digest = source['sha256'] if name == SLIDES else sha256(path)
                        seen[arcname] = digest
                        assets.append({'name': name, 'pages': pages, 'sha256': digest})
                    receipts.append({'lesson': pid, 'folder': lesson['display_title'], 'numbers': sum(len(q['numbers']) for q in lesson['questions']), 'files': assets})
                    if illustrated:
                        receipts[-1].update(answer_illustration_sha256=movie['illustration_sha256'],
                                            video_sha256=movie['video_sha256'], answer_opening=cover_check)
                    shutil.rmtree(folder)
                    print(f'{len(receipts)}/{len(ids)} {pid}', flush=True)
            finally:
                browser.close()
        if sum(r['numbers'] for r in receipts) != 1280 or len(seen) != 288:
            raise ValueError('Incomplete student pack')
        if illustrated and (len(paper_numbers)!=32 or any(numbers!=list(range(1,41)) for numbers in paper_numbers.values())):
            raise ValueError('The three passages of each printed test must cover questions 1 through 40 in order')
        with zipfile.ZipFile(candidate) as archive:
            if archive.namelist() != list(seen):
                raise ValueError('Archive tree or order differs from verified set')
            for name, expected in seen.items():
                with archive.open(name) as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                        raise ValueError(f'Archived PDF differs: {name}')
        if candidate.stat().st_size >= 2**31:
            raise ValueError('Archive exceeds GitHub release asset limit')
        receipt = {'books': books, 'passages': 96, 'questions': 1280, 'files': 288,
                   'zip_name': zip_path.name, 'zip_bytes': candidate.stat().st_size, 'zip_sha256': sha256(candidate), 'contents': receipts}
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        staged_receipt = receipt_path.with_suffix('.part')
        staged_receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + '\n')
        candidate.replace(zip_path)
        staged_receipt.replace(receipt_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('notes', 'slides', 'zip', 'receipt'):
        parser.add_argument(arg, type=Path)
    parser.add_argument('--edition',choices=('21-14','13-6'),default='21-14')
    args = parser.parse_args()
    build(args.notes, args.slides, args.zip, args.receipt, args.edition)
