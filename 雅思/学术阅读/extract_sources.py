"""Create review material from Academic Reading sections selected by the page index."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

import fitz

parser = argparse.ArgumentParser()
parser.add_argument('book', type=int)
parser.add_argument('archive', type=Path)
parser.add_argument('index', type=Path)
args = parser.parse_args()
book = args.book
with args.index.open(encoding='utf-8-sig') as stream:
    rows = [row for row in csv.DictReader(stream) if int(row['册']) == book]
assert len(rows) == 12
with zipfile.ZipFile(args.archive) as archive:
    member, = [item for item in archive.infolist()
               if int(re.search(r'\d+', item.filename).group()) == book]
    doc = fitz.open(stream=archive.read(member), filetype='pdf')
output = Path('source-review') / f'C{book:02}'
output.mkdir(parents=True, exist_ok=True)
cache = {}
for i, row in enumerate(rows):
    start = int(row['PDF起始页'])
    # Include source and question pages for editorial reference. Two-up scans
    # can start the following section on the same physical PDF page.
    stop = min(len(doc), start + 5)
    if i % 3 != 2:
        stop = min(stop, int(rows[i + 1]['PDF起始页']))
    passage = output / f"T{row['Test']}P{row['Passage']}"
    passage.mkdir(exist_ok=True)
    pages = []
    for number in range(start, stop + 1):
        if number not in cache:
            page = doc[number - 1]
            pix = page.get_pixmap(dpi=190, colorspace=fitz.csGRAY)
            png = pix.tobytes('png')
            ocr = subprocess.run(['tesseract', 'stdin', 'stdout', '-l', 'eng'],
                                 input=png, stdout=subprocess.PIPE, check=True)
            cache[number] = {'pdf_page': number, 'native_blocks': page.get_text('blocks'),
                             'ocr': ocr.stdout.decode()}
        pages.append(cache[number])
    (passage / 'source-pages.json').write_text(json.dumps(pages, ensure_ascii=False), encoding='utf-8')
