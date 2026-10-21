"""学习资料压缩包：用 Python zipfile 打包（不压缩，非 ASCII 文件名自动打 UTF-8 标记：踩坑 52）并逐个核对（踩坑 43）。

    python3 .github/pack-zip.py <压缩包> <dist 目录> <应有文件数> [顺序文件]

顺序文件（可选）：每行一个 dist 下的顶层路径，按行的顺序打包（中考按 B 站 P 号 1—40）；不给就按文件名排序。
"""
import sys
import zipfile
from pathlib import Path

z, dist, n = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
if len(sys.argv) > 4:
    tops = [dist / l for l in Path(sys.argv[4]).read_text('utf-8').splitlines() if l.strip()]
    files = [x for t in tops for x in sorted(t.rglob('*')) if x.is_file()]
else:
    files = sorted(x for x in dist.rglob('*') if x.is_file())
with zipfile.ZipFile(z, 'w', zipfile.ZIP_STORED, allowZip64=True) as zf:
    for x in files:
        zf.write(x, x.relative_to(dist).as_posix())
with zipfile.ZipFile(z) as zf:
    infos = zf.infolist()
    assert len(infos) == len(files) == n, (len(infos), len(files), n)
    for i, x in zip(infos, files):
        assert i.filename == x.relative_to(dist).as_posix() and i.file_size == x.stat().st_size, i.filename
        assert i.flag_bits & 0x800 or i.filename.isascii(), f'{i.filename} 没有 UTF-8 标记'
    assert zf.testzip() is None
print(f'{z.name}：{len(infos)} 个文件，{z.stat().st_size / 2**20:.0f} MB，zipfile 核对通过')
