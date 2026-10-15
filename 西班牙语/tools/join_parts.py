"""合并 Release 里分卷下载的 Qwen3-TTS 模型，校验后解压到 西班牙语/models/qwen3-base/（Windows、macOS、Linux 都能用）。

    python 西班牙语/tools/join_parts.py                       # 在工具包根目录、当前文件夹、“下载”文件夹里找分卷
    python 西班牙语/tools/join_parts.py 分卷所在的文件夹
    python 西班牙语/tools/join_parts.py 文件夹 --delete-parts   # 解压成功后删除分卷（省 4 GB 磁盘）
    python 西班牙语/tools/join_parts.py 文件夹 --verify-only    # 只校验（SHA256 + 压缩包内每个文件的 CRC），不解压

分卷：qwen3-tts-1.7b-base.zip.001、.002 …（每个 < 1.9 GB，合起来约 4.3 GB）。直接把各分卷“串起来”当成一个压缩包读，
不需要先拼出 4 GB 的整包（只需要解压后的约 4.3 GB 空间）。
校验：分卷所在文件夹里有 SHA256SUMS.txt（Release 里一起下载）时，逐个核对每个分卷和合并后整包的 SHA256；
没有也能解压（压缩包里每个文件都有 CRC 校验，坏了会报错），但会提示。
安全：压缩包里的每个文件都必须在 qwen3-base/ 文件夹里（不许 ../ 或绝对路径）；先解压到 qwen3-base.partial/，全部成功再改名。
只用 Python 标准库，安装前也能运行（python3 西班牙语/tools/join_parts.py）。
"""
import argparse
import glob
import hashlib
import io
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ES = HERE.parent
PREFIX = 'qwen3-tts-1.7b-base.zip'
TOP = 'qwen3-base'
NEED = ['model.safetensors', 'config.json', 'speech_tokenizer/config.json', 'speech_tokenizer/model.safetensors']


class Joined(io.RawIOBase):
    """把几个分卷文件当成一个连续的、可随机读取的文件。"""

    def __init__(self, paths):
        self.files = [open(p, 'rb') for p in paths]
        self.sizes = [os.path.getsize(p) for p in paths]
        self.starts = [sum(self.sizes[:i]) for i in range(len(paths))]
        self.size = sum(self.sizes)
        self.pos = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def readinto(self, b):
        n, view = 0, memoryview(b)
        while n < len(view) and self.pos < self.size:
            i = max(k for k, s in enumerate(self.starts) if s <= self.pos)
            f = self.files[i]
            f.seek(self.pos - self.starts[i])
            got = f.readinto(view[n:n + min(len(view) - n, self.starts[i] + self.sizes[i] - self.pos)])
            if not got:
                break
            n += got
            self.pos += got
        return n

    def close(self):
        for f in self.files:
            f.close()
        super().close()


def find_parts(where):
    dirs = [Path(where)] if where else [ES.parent, Path.cwd(), Path.home() / 'Downloads', Path.home() / '下载']
    for d in dirs:
        parts = sorted(Path(p) for p in glob.glob(str(d / f'{PREFIX}.[0-9][0-9][0-9]')))
        if parts:
            return d, parts
    raise SystemExit(f'找不到分卷 {PREFIX}.001 …（找过：{", ".join(map(str, dirs))}）。请把 Release 里的分卷都下载到同一个文件夹，'
                     f'再运行：python 西班牙语/tools/join_parts.py 那个文件夹')


def sha256_file(paths, label):
    h, done, total = hashlib.sha256(), 0, sum(os.path.getsize(p) for p in paths)
    for p in paths:
        with open(p, 'rb') as f:
            for b in iter(lambda: f.read(1 << 24), b''):
                h.update(b)
                done += len(b)
                print(f'\r  计算 SHA256（{label}）：{done * 100 // max(total, 1)}%', end='', flush=True)
    print()
    return h.hexdigest()


def verify_sums(d, parts):
    sums = d / 'SHA256SUMS.txt'
    if not sums.is_file():
        print('  提示：同一文件夹里没有 SHA256SUMS.txt，跳过 SHA256 校验（解压时仍逐个核对 CRC）')
        return
    want = {}
    for line in sums.read_text('utf-8').splitlines():
        m = re.match(r'([0-9a-f]{64})\s+\*?(.+)$', line.strip())
        if m:
            want[m.group(2).strip()] = m.group(1)
    for p in parts:
        if p.name in want and sha256_file([p], p.name) != want[p.name]:
            raise SystemExit(f'{p.name} 的 SHA256 不对：文件没下载完整或损坏，请重新下载这个分卷')
    if PREFIX in want:
        if sha256_file(parts, '合并后') != want[PREFIX]:
            raise SystemExit('合并后的 SHA256 不对：分卷不全或顺序不对，请核对 .001、.002 … 是否都下载了')
        print('  SHA256 全部一致')
    else:
        print('  提示：SHA256SUMS.txt 里没有合并后整包的校验值')


def safe_members(z):
    names = z.namelist()
    for n in names:
        p = Path(n)
        if p.is_absolute() or '..' in p.parts or ':' in n or not (n == TOP + '/' or n.startswith(TOP + '/')):
            raise SystemExit(f'压缩包里有不在 {TOP}/ 里的文件 {n!r}，不解压（不是本工具包发布的分卷？）')
    return [i for i in z.infolist() if not i.is_dir()]


def main():
    ap = argparse.ArgumentParser(description='合并、校验、解压 Qwen3-TTS 模型分卷')
    ap.add_argument('folder', nargs='?', help='分卷所在文件夹（默认自动找）')
    ap.add_argument('--dest', default=str(ES / 'models'), help='解压到哪里（默认 西班牙语/models，得到 西班牙语/models/qwen3-base）')
    ap.add_argument('--verify-only', action='store_true', help='只校验，不解压')
    ap.add_argument('--delete-parts', action='store_true', help='解压成功后删除分卷')
    ap.add_argument('--force', action='store_true', help='已经有 qwen3-base 时也重新解压（旧的改名为 qwen3-base.old）')
    a = ap.parse_args()

    d, parts = find_parts(a.folder)
    nums = [int(p.suffix[1:]) for p in parts]
    if nums != list(range(1, len(parts) + 1)):
        raise SystemExit(f'分卷编号不连续：{[p.name for p in parts]}（缺了哪个就补下载哪个）')
    print(f'找到 {len(parts)} 个分卷（{d}），共 {sum(map(os.path.getsize, parts)) / 2**30:.2f} GB')
    verify_sums(d, parts)
    try:
        unpack(a, parts)
    except (zipfile.BadZipFile, EOFError, zlib_error()) as e:
        shutil.rmtree(Path(a.dest) / (TOP + '.partial'), ignore_errors=True)
        raise SystemExit(f'\n分卷内容损坏或不完整（{e}）：请重新下载分卷（最好连同 SHA256SUMS.txt 一起，能查出是哪一个坏了）')


def zlib_error():
    import zlib
    return zlib.error


def unpack(a, parts):
    src = Joined(parts)
    with zipfile.ZipFile(io.BufferedReader(src, 1 << 20)) as z:
        infos = safe_members(z)
        total = sum(i.file_size for i in infos)
        if a.verify_only:
            for k, i in enumerate(infos, 1):
                with z.open(i) as f:
                    while f.read(1 << 24):
                        pass
                print(f'\r  CRC 校验 {k}/{len(infos)}', end='', flush=True)
            print(f'\n校验通过：{len(infos)} 个文件，解压后 {total / 2**30:.2f} GB')
            return
        dest = Path(a.dest)
        final, part = dest / TOP, dest / (TOP + '.partial')
        if final.exists() and not a.force:
            miss = [x for x in NEED if not (final / x).is_file()]
            if not miss:
                print(f'{final} 已经装好（加 --force 重新解压）')
                return
            raise SystemExit(f'{final} 已存在但不完整（缺 {miss}）：加 --force 重新解压')
        dest.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(dest).free
        if free < total + 2**28:
            raise SystemExit(f'磁盘空间不够：解压要 {total / 2**30:.1f} GB，{dest} 所在磁盘只剩 {free / 2**30:.1f} GB')
        shutil.rmtree(part, ignore_errors=True)
        done = 0
        for i in infos:
            rel = Path(i.filename).relative_to(TOP)
            t = part / rel
            t.parent.mkdir(parents=True, exist_ok=True)
            with z.open(i) as f, open(t, 'wb') as g:          # 读完每个文件时 zipfile 自动核对 CRC，不对就报错
                for b in iter(lambda: f.read(1 << 24), b''):
                    g.write(b)
                    done += len(b)
                    print(f'\r  解压 {done * 100 // max(total, 1)}%', end='', flush=True)
        print()
    src.close()
    miss = [x for x in NEED if not (part / x).is_file()]
    if miss:
        raise SystemExit(f'解压出来的模型不完整，缺 {miss}（分卷不是 Qwen3-TTS 1.7B Base？）')
    if final.exists():
        old = dest / (TOP + '.old')
        shutil.rmtree(old, ignore_errors=True)
        final.rename(old)
        print(f'  原来的 {final} 改名为 {old}（确认新的能用后可以删掉）')
    part.rename(final)
    print(f'已解压到 {final}（{total / 2**30:.2f} GB）。现在可以用 Qwen3 音色：--voice qwen3_M1F5_25')
    if a.delete_parts:
        for p in parts:
            p.unlink()
        print(f'已删除 {len(parts)} 个分卷')
    else:
        print('分卷可以删掉了（或下次加 --delete-parts 自动删）')


if __name__ == '__main__':
    sys.exit(main())
