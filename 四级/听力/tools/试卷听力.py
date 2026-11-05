"""取 35 份有听力题的试卷（各次考试第 1、2 套；第 3 套都写明听力与前两套相同）的听力部分文字，存 四级/听力/试卷/<年月-套>.txt。
来源优先级：仓库 四级/真题/ 已校对的 .txt（2021-06 起）> 合集里试卷 PDF 的文字层（pdftotext -layout）。
用法：python3 试卷听力.py 合集解压目录"""
import re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / '四级/听力/试卷'; OUT.mkdir(exist_ok=True)
src = Path(sys.argv[1])
def key(name):
    m = re.search(r'(20\d\d)\s*[年.]\s*(\d{1,2})', name)
    k = re.search(r'第\s*(\d)\s*套', name)
    return f'{m.group(1)}{int(m.group(2)):02d}-{k.group(1) if k else 1}' if m else None
def listening(t):
    i = t.find('Listening Comprehension')
    if i < 0: return None
    j = re.search(r'Part\s*(III|Ⅲ)\b|Reading\s+Comprehension', t[i + 30:])
    part = t[i: i + 30 + j.start()] if j else None
    return part if part and len(re.findall(r'\b[A-D]\s?[.)]', part)) >= 60 else None
got = {}
for f in sorted((ROOT / '四级/真题').rglob('*.txt')):
    k = key(f.name); p = listening(f.read_text('utf-8', 'ignore'))
    if k and p: got[k] = (p, str(f.relative_to(ROOT)))
for f in sorted(src.rglob('*.pdf')):
    if '真题' not in f.name or '解析' in f.name or '详解' in f.name or '一键' in f.name: continue
    k = key(f.name)
    if not k or k in got: continue
    t = subprocess.run(['pdftotext', '-layout', str(f), '-'], capture_output=True, text=True).stdout
    p = listening(t)
    if p: got[k] = (p, '合集/' + str(f.relative_to(src)).split('/', 1)[-1])
for f in sorted(src.rglob('*.docx')):      # PDF 文字层是乱码时（2020-07）用同一份试卷的 Word 版
    k = key(f.name)
    if not k or k in got or '真题' not in f.name: continue
    x = subprocess.run(['unzip', '-p', str(f), 'word/document.xml'], capture_output=True, text=True).stdout
    t = re.sub(r'<[^>]+>', '', re.sub(r'</w:p>', '\n', x))
    p = listening(t)
    if p: got[k] = (p, '合集/' + str(f.relative_to(src)).split('/', 1)[-1])
for k, (p, s) in sorted(got.items()):
    (OUT / f'{k}.txt').write_text(f'# 来源：{s}\n' + p, 'utf-8')
print(len(got), sorted(got))
