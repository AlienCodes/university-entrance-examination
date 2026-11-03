"""把解压目录里每个 doc/docx/pdf 转成文本。按文件 sha256 去重（同内容只转一次）。
输出: 文本目录/<sha>.txt，清单 files.tsv（sha、类型、字节、路径、文字字数）。
用法: python3 -I totext.py 文本目录 根目录1 [根目录2 ...]"""
import sys, os, hashlib, zipfile, re, subprocess, shutil, tempfile
from concurrent.futures import ThreadPoolExecutor

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def docx_text(path):
    import xml.etree.ElementTree as ET
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read('word/document.xml'))
    out = []
    for p in root.iter(W + 'p'):
        s = []
        for el in p.iter():
            if el.tag == W + 't' and el.text:
                s.append(el.text)
            elif el.tag == W + 'tab':
                s.append('\t')
            elif el.tag in (W + 'br', W + 'cr'):
                s.append('\n')
        out.append(''.join(s))
    return '\n'.join(out)

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

def main():
    outdir, roots = sys.argv[1], sys.argv[2:]
    os.makedirs(outdir, exist_ok=True)
    files = []
    for r in roots:
        for dp, _, fns in os.walk(r):
            for fn in fns:
                ext = os.path.splitext(fn)[1].lower()
                if ext in ('.doc', '.docx', '.pdf', '.wps', '.rtf'):
                    files.append(os.path.join(dp, fn))
    files.sort()
    with ThreadPoolExecutor(4) as ex:
        shas = list(ex.map(sha, files))
    todo = {}
    for p, h in zip(files, shas):
        todo.setdefault(h, p)
    docs = []
    def conv(item):
        h, p = item
        tp = os.path.join(outdir, h + '.txt')
        if os.path.exists(tp):
            return
        ext = os.path.splitext(p)[1].lower()
        try:
            if ext == '.docx':
                t = docx_text(p)
            elif ext == '.pdf':
                t = subprocess.run(['pdftotext', '-enc', 'UTF-8', p, '-'], capture_output=True, timeout=300).stdout.decode('utf-8', 'replace')
            else:
                docs.append((h, p, ext)); return
        except Exception as e:  # 转换失败也要记下来，不许静默
            t = ''
            print('FAIL', p, e, file=sys.stderr)
        open(tp, 'w').write(t)
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(conv, todo.items()))
    # doc / wps / rtf：LibreOffice 批量转 txt（拷到扁平目录，名字用 sha）
    if docs:
        tmp = tempfile.mkdtemp(dir=outdir)
        for h, p, ext in docs:
            shutil.copy(p, os.path.join(tmp, h + ext))
        names = sorted(os.listdir(tmp))
        for i in range(0, len(names), 40):
            batch = [os.path.join(tmp, n) for n in names[i:i + 40]]
            subprocess.run(['soffice', '--headless', '--convert-to', 'txt:Text (encoded):UTF8', '--outdir', outdir] + batch,
                           capture_output=True, timeout=1800)
        shutil.rmtree(tmp)
        for h, p, ext in docs:
            tp = os.path.join(outdir, h + '.txt')
            if not os.path.exists(tp):
                print('FAIL', p, 'soffice', file=sys.stderr)
                open(tp, 'w').write('')
    with open(os.path.join(outdir, 'files.tsv'), 'w') as f:
        for p, h in zip(files, shas):
            t = open(os.path.join(outdir, h + '.txt'), errors='replace').read()
            f.write(f'{h}\t{os.path.splitext(p)[1].lower()}\t{os.path.getsize(p)}\t{p}\t{len(t.strip())}\n')

if __name__ == '__main__':
    main()
