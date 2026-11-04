"""六级听力讲义套装 小店上传包（Python zipfile，不压缩，中文名带 UTF-8 标记：踩坑 52；打完逐个核对）。
    python3 标题与描述.py && python3 打包.py   → 六级听力讲义_小店上传包.zip"""
import sys
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / '六级听力讲义_小店上传包.zip'
sys.path.insert(0, str(HERE))
import 标题与描述 as T  # noqa: E402


def main():
    imgs = sorted((HERE / '成品').glob('*.jpg'))
    names = [p.stem for p in imgs]
    desc = (HERE / 'work' / '简介.txt').read_text('utf-8').rstrip('\n')
    bad = T.desc_problems(desc)
    if not imgs or names[0] != '01_商品总图' or [n[:2] for n in names] != [f'{i:02d}' for i in range(1, len(imgs) + 1)]:
        bad.append(f'商品图序号不连续或第 1 张不是商品总图：{names}')
    if desc != T.DESC:
        bad.append('work/简介.txt 与现算的简介不同：先跑 标题与描述.py')
    if bad:
        sys.exit('不打包：\n  ' + '\n  '.join(bad))
    readme = '\n'.join(['六级听力讲义套装 · 小店上传说明', '',
                        f'1. 商品图：打开「1 商品图（按顺序上传）」，按序号 01 → {len(imgs):02d} 依次上传；01 是商品总图（列出套装里所有文件）。规格 1:1，2000×2000，JPG。',
                        f'2. 商品标题：「2 商品标题.txt」短版 ≤ 30 字；平台允许长标题时用长版。',
                        f'3. 商品简介：「3 商品描述.txt」整篇复制粘贴（{T.desc_len(desc)} 字，上限 1000），已含虚拟商品不退款说明。',
                        '商品本身（6 份 PDF）在 GitHub Release「cet6-listening-handout」；历年真题原卷由老师自备。', ''])
    items = [('0 上传说明.txt', readme.encode('utf-8'))] + [(f'1 商品图（按顺序上传）/{p.name}', p.read_bytes()) for p in imgs] + \
            [('2 商品标题.txt', (HERE / 'work' / '标题.txt').read_bytes()), ('3 商品描述.txt', (desc + '\n').encode('utf-8'))]
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_STORED) as z:
        for n, b in items:
            z.writestr(zipfile.ZipInfo(n, (2026, 11, 4, 0, 0, 0)), b)
    with zipfile.ZipFile(OUT) as z:
        info = z.infolist()
        assert [i.filename for i in info] == [n for n, _ in items]
        for i, (n, b) in zip(info, items):
            assert i.flag_bits & 0x800 and i.compress_type == zipfile.ZIP_STORED and i.CRC == zlib.crc32(b) and i.file_size == len(b), n
        assert z.testzip() is None
    print(f'{OUT.name}：{len(items)} 个文件，{OUT.stat().st_size / 1e6:.1f} MB，核对通过')


if __name__ == '__main__':
    main()
