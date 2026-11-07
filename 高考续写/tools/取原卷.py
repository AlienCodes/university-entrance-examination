"""从用户上传的 Release 大压缩包里只取出指定文件（HTTP Range 按需读取，不下载整包）。

用法：python3 高考续写/tools/取原卷.py <包> <输出目录> <包内路径或结尾片段>...
  包：A = releases/download/user-upload/2008-2026.zip，B = releases/download/user-upload-2/default.zip，或直接给 URL
  包内路径：续写题汇总.json 里“原始文件”去掉开头的 A/ 或 B/；也可以只给结尾片段（必须唯一匹配）
中文文件名按 GBK 解码（压缩包没打 UTF-8 标记时）。
"""
import io, sys, zipfile, urllib.request, pathlib

BASE = 'https://github.com/AlienCodes/university-entrance-examination/releases/download/'
PACK = {'A': BASE + 'user-upload/2008-2026.zip', 'B': BASE + 'user-upload-2/default.zip'}


class RF(io.RawIOBase):
    def __init__(s, url):
        r = urllib.request.urlopen(urllib.request.Request(url, headers={'Range': 'bytes=0-0'}))
        s.url, s.size, s.pos = r.geturl(), int(r.headers['Content-Range'].split('/')[1]), 0
        r.read()

    def seekable(s): return True
    def readable(s): return True
    def tell(s): return s.pos

    def seek(s, o, w=0):
        s.pos = o if w == 0 else (s.pos + o if w == 1 else s.size + o)
        return s.pos

    def readinto(s, b):
        if s.pos >= s.size or not len(b):
            return 0
        end = min(s.size, s.pos + len(b)) - 1
        d = urllib.request.urlopen(urllib.request.Request(s.url, headers={'Range': f'bytes={s.pos}-{end}'})).read()
        b[:len(d)] = d
        s.pos += len(d)
        return len(d)


def name(i):
    if i.flag_bits & 0x800:
        return i.filename
    try:
        return i.filename.encode('cp437').decode('gbk')
    except Exception:
        return i.filename


def main():
    pack, out, wants = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3:]
    z = zipfile.ZipFile(io.BufferedReader(RF(PACK.get(pack, pack)), buffer_size=4 << 20))
    infos = [(name(i), i) for i in z.infolist()]
    bad = 0
    for w in wants:
        m = [(n, i) for n, i in infos if n == w or n.endswith('/' + w)]
        if len(m) != 1:
            print(f'✗ {w}：匹配 {len(m)} 个（必须恰好 1 个）', [n for n, _ in m][:5])
            bad += 1
            continue
        n, i = m[0]
        p = out / n.split('/')[-1]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(z.read(i))   # zipfile 自带 CRC 校验，坏了会报错
        print(f'✓ {n} → {p}（{p.stat().st_size} 字节）')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
