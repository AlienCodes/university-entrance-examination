"""对没有文字层的英语文件做 OCR（tesseract eng+chi_sim），结果写回 T/<sha>.txt，并记 T/ocr.tsv。
用法: python3 -I ocr.py T目录"""
import sys, os, subprocess, tempfile, zipfile, glob, re
from concurrent.futures import ThreadPoolExecutor

T = sys.argv[1]
MODE = sys.argv[2] if len(sys.argv) > 2 else '1'
SKIP = re.compile('数学|语文|物理|化学|生物|历史|地理|政治|日语|答题卡')
rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(T, 'files.tsv'))]
todo = {}
for h, ext, size, path, n in rows:
    if SKIP.search(path):
        continue
    if MODE == '1' and int(n) < 200:
        todo.setdefault(h, (ext, path))
    if MODE == '2' and ext == '.pdf' and int(n) >= 200 and ('英语' in path or 'T8' in path):
        t = open(os.path.join(T, h + '.txt'), errors='replace').read()
        if '续写' not in t:
            todo.setdefault(h, (ext, path))

if MODE == '3':  # 文字层拆字乱码（每行一两个字母）的文件：按单字母行比例挑出来
    for h, ext, size, path, n in rows:
        if ext == '.pdf' and not SKIP.search(path) and ('英语' in path or 'T8' in path) and h not in todo:
            ls = [l.strip() for l in open(os.path.join(T, h + '.txt'), errors='replace') if l.strip()]
            if ls and sum(len(l) <= 2 for l in ls) / len(ls) > 0.3:
                todo[h] = (ext, path)

def ocr_img(img):
    r = subprocess.run(['tesseract', img, '-', '-l', 'eng+chi_sim', '--psm', '3'], capture_output=True, timeout=600)
    return r.stdout.decode('utf-8', 'replace')

def pages(h, ext, path, d):
    if ext == '.pdf':
        subprocess.run(['pdftoppm', '-r', '250', '-gray', '-png', path, os.path.join(d, 'p')], check=True, timeout=1800)
        return sorted(glob.glob(os.path.join(d, 'p*.png')))
    z = zipfile.ZipFile(path)
    # 按 document.xml 里出现的顺序取图
    rels = z.read('word/_rels/document.xml.rels').decode()
    rid2 = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="(media/[^"]+)"', rels))
    rid2.update({a: b for b, a in re.findall(r'Target="(media/[^"]+)"[^>]*Id="(rId\d+)"', rels)})
    doc = z.read('word/document.xml').decode()
    out = []
    for i, rid in enumerate(re.findall(r'r:embed="(rId\d+)"', doc)):
        if rid in rid2:
            p = os.path.join(d, f'{i:03d}' + os.path.splitext(rid2[rid])[1])
            open(p, 'wb').write(z.read('word/' + rid2[rid]))
            out.append(p)
    return out

def run(item):
    h, (ext, path) = item
    with tempfile.TemporaryDirectory() as d:
        imgs = pages(h, ext, path, d)
        text = '\n\f\n'.join(ocr_img(p) for p in imgs)
    open(os.path.join(T, h + '.txt'), 'w').write(text)
    return h, path, len(imgs), len(text.strip())

with ThreadPoolExecutor(4) as ex, open(os.path.join(T, f'ocr{MODE}.tsv'), 'w') as log:
    for h, path, np_, n in ex.map(run, todo.items()):
        log.write(f'{h}\t{np_}\t{n}\t{path}\n'); log.flush()
print('done', len(todo))
