"""解压（含嵌套 zip），中文名按 GBK 修正；只解 doc/docx/pdf/zip/rar 等文档，跳过 mp3。
用法: python3 -I unpack.py 源.zip 目标目录"""
import sys, zipfile, os, io

KEEP = ('.doc', '.docx', '.pdf', '.zip', '.wps', '.txt', '.rtf')

def fixname(info):
    n = info.filename
    if not (info.flag_bits & 0x800):
        try:
            n = n.encode('cp437').decode('gbk')
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return n

def unpack(zf, dest, log, prefix=''):
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = fixname(info)
        low = name.lower()
        if not low.endswith(KEEP):
            log.write(f'SKIP\t{prefix}{name}\n')
            continue
        safe = os.path.normpath(name).lstrip('/').replace('..', '_')
        out = os.path.join(dest, safe)
        if low.endswith('.zip'):
            data = zf.read(info)
            sub = out[:-4] + '__zip'
            log.write(f'NEST\t{prefix}{name}\t{len(data)}\n')
            unpack(zipfile.ZipFile(io.BytesIO(data)), sub, log, prefix + name + '!/')
            continue
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with zf.open(info) as s, open(out, 'wb') as d:
            while True:
                b = s.read(1 << 20)
                if not b:
                    break
                d.write(b)
        log.write(f'FILE\t{prefix}{name}\t{info.file_size}\n')

if __name__ == '__main__':
    src, dest = sys.argv[1], sys.argv[2]
    os.makedirs(dest, exist_ok=True)
    with open(dest + '.log', 'w') as log:
        unpack(zipfile.ZipFile(src), dest, log)
