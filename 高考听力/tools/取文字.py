#!/usr/bin/env python3
"""docx → 文字：按 document.xml 的段落顺序取全部 w:t（含表格、文本框），每段一行；表格单元格之间用两个空格。
.doc 先用 soffice --convert-to docx 转。用法：python3 -I 取文字.py <docx 目录> <输出目录>"""
import re, sys, zipfile
from pathlib import Path

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
import xml.etree.ElementTree as ET


def text(docx):
    root = ET.fromstring(zipfile.ZipFile(docx).read('word/document.xml'))
    out, seen = [], set()
    for p in root.iter(W + 'p'):
        if id(p) in seen:
            continue
        for q in p.iter(W + 'p'):       # 文本框里的段落嵌在外层段落里：外层只取自己的字
            seen.add(id(q))
        buf = []
        for el in p.iter():
            if el.tag == W + 't' and el.text:
                buf.append(el.text)
            elif el.tag == W + 'tab':
                buf.append('\t')
            elif el.tag in (W + 'br', W + 'cr'):
                buf.append('\n')
        out.append(''.join(buf))
    return '\n'.join(out)


if __name__ == '__main__':
    src, dst = Path(sys.argv[1]), Path(sys.argv[2]); dst.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.glob('*.docx')):
        (dst / (f.stem + '.txt')).write_text(text(f), 'utf-8')
