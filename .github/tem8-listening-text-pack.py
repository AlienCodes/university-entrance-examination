"""专八听力原文精读视频的打包与核对（release-tem8-listening-text.yml 调用；本机可先跑一遍，踩坑 61）。

    python3 .github/tem8-listening-text-pack.py pack            # 按清单核对每个成品的 sha256，打包成 TEM8-listening-text-2025.zip，写 notes.md
    python3 .github/tem8-listening-text-pack.py verify <zip>    # 核对压缩包：文件名、顺序、UTF-8 标记、不压缩、sha256 与清单一致

清单 .github/tem8-listening-text-release.txt：第 1 行标签，之后每行 “<sha256> <文件名>”（成品在 专八/听力/原文/最终视频_水墨/）。
打包一律用 Python zipfile（踩坑 52：Info-ZIP 不给中文文件名打 UTF-8 标记）。
"""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / '.github' / 'tem8-listening-text-release.txt'
SRC = ROOT / '专八' / '听力' / '原文' / '最终视频_水墨'
ZIP = 'TEM8-listening-text-2025.zip'


def manifest():
    lines = [x.strip() for x in LIST.read_text('utf-8').splitlines() if x.strip()]
    tag, items = lines[0], [x.split(' ', 1) for x in lines[1:]]
    if not items:
        sys.exit('停止：清单里没有成品')
    return tag, items


def sha(path_or_fh):
    h = hashlib.sha256()
    fh = open(path_or_fh, 'rb') if isinstance(path_or_fh, Path) else path_or_fh
    for b in iter(lambda: fh.read(1 << 20), b''):
        h.update(b)
    return h.hexdigest()


def pack():
    tag, items = manifest()
    for s, name in items:
        got = sha(SRC / name)
        if got != s:
            sys.exit(f'停止：{name} 的 sha256 {got} ≠ 清单 {s}')
    with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_STORED) as z:
        for _, name in items:
            z.write(SRC / name, name)
    verify(ZIP)
    total = sum((SRC / n).stat().st_size for _, n in items)
    notes = ['2025 年英语专业八级（TEM-8）听力 · 原文逐句精读（书卷水墨）：听力录音的全部原文，一句一屏，英文 + 中文翻译 + 生词短语卡。', '',
             '- 声音就是考试原音（讲座、采访、考试说明、念题），逐句对齐；预览、作答停顿、3 分钟检查等长等待压到约 2 秒，整体响度统一（−16 LUFS）；',
             '- 原文以真题详解扫描件为准，与录音逐词比对；翻译与释义经独立复核（埋雷全部查出）；',
             f'- 3 个视频（4K 3840×2160、30 帧/秒），按考试顺序：', '']
    notes += [f'  {i}. {n}' for i, (_, n) in enumerate(items, 1)]
    notes += ['', f'下载下面的 `{ZIP}`（约 {total / 2**20:.0f} MB），解压即可。', '', 'sha256（mp4）：', '']
    notes += [f'- `{s}` {n}' for s, n in items]
    Path('notes.md').write_text('\n'.join(notes) + '\n', 'utf-8')
    print('打包核对通过', ZIP, Path(ZIP).stat().st_size)


def verify(zp):
    _, items = manifest()
    with zipfile.ZipFile(zp) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if names != [n for _, n in items]:
            sys.exit(f'停止：压缩包里的文件 / 顺序不对：{names}')
        for i, (s, n) in zip(infos, items):
            if not i.flag_bits & 0x800:
                sys.exit(f'停止：{n} 没有 UTF-8 文件名标记')
            if i.compress_type != zipfile.ZIP_STORED:
                sys.exit(f'停止：{n} 被压缩了')
            with z.open(i) as fh:
                got = sha(fh)
            if got != s:
                sys.exit(f'停止：压缩包里 {n} 的 sha256 {got} ≠ 清单 {s}')
    print(f'核对通过：{zp}，{len(items)} 个视频，文件名、顺序、UTF-8 标记、不压缩、sha256 全部一致')


if __name__ == '__main__':
    {'pack': pack, 'verify': lambda: verify(sys.argv[2])}[sys.argv[1]]()
