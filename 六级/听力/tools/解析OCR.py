"""解析 PDF → 听力部分的文字（解析原文，用来给 transcripts 挑错）。
有文字层的直接 pdftotext；扫描版：每页 100 dpi 粗识别判断是不是听力部分（Part II … Part III 之间），听力页再 300 dpi chi_sim+eng 识别。
用法：python 解析OCR.py 解析.pdf 输出目录      输出：解析原文.txt（按页，"=== 第 N 页" 分隔）、解析OCR.json（用了哪几页、哪种方式）"""
import json, re, subprocess, sys, tempfile
from pathlib import Path

pdf, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True, check=True).stdout


n = int(re.search(r'Pages:\s+(\d+)', sh('pdfinfo', str(pdf))).group(1))
layer = sh('pdftotext', '-layout', str(pdf), '-')
txt = {}
mode = 'text' if len(re.findall(r'[A-Za-z]{3,}', layer)) > 3000 else 'ocr'
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    for p in range(1, n + 1):
        if mode == 'text':
            txt[p] = sh('pdftotext', '-layout', '-f', str(p), '-l', str(p), str(pdf), '-')
        else:
            sh('pdftoppm', '-r', '100', '-gray', '-png', '-f', str(p), '-l', str(p), '-singlefile', str(pdf), str(td / 'lo'))
            txt[p] = sh('tesseract', str(td / 'lo.png'), '-', '-l', 'chi_sim+eng')
    flat = {p: re.sub(r'\s+', '', t) for p, t in txt.items()}
    # 听力部分：从出现 Listening Comprehension / 听力原文 的第一页，到 Part III / Reading Comprehension 出现的那一页（含）
    start = next((p for p in txt if re.search(r'ListeningComprehension|听力原文', flat[p], re.I)), None)
    if start is None: sys.exit('停止：找不到听力部分')
    end = next((p for p in txt if p > start and re.search(r'PartIII|ReadingComprehension', flat[p], re.I)), n)
    pages = list(range(start, end + 1))
    res = {}
    for p in pages:
        if mode == 'text':
            res[p] = txt[p]
        else:
            sh('pdftoppm', '-r', '300', '-gray', '-png', '-f', str(p), '-l', str(p), '-singlefile', str(pdf), str(td / 'hi'))
            res[p] = sh('tesseract', str(td / 'hi.png'), '-', '-l', 'eng+chi_sim', '--psm', '4')
(out / '解析原文.txt').write_text(''.join(f'=== 第 {p} 页\n{t}\n' for p, t in res.items()), 'utf-8')
(out / '解析OCR.json').write_text(json.dumps({'pdf': pdf.name, '方式': mode, '页': pages}, ensure_ascii=False), 'utf-8')
print(pdf.name, mode, '听力页', pages[0], '—', pages[-1])
