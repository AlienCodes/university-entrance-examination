"""四级写作讲义小店上传包：一个 zip，打开就能照顺序上传、粘贴。

    python3 四级作文/讲义/商品图/标题与描述.py     # 先生成 work/简介.txt、work/标题.txt（含简介字数、退款说明检查）
    python3 四级作文/讲义/商品图/打包.py

输出 四级作文/讲义/商品图/四级写作讲义_小店上传包.zip。包内顺序（用户 2026-10-26）：
  0 上传说明.txt
  1 商品图（按顺序上传）/01_主图.jpg … 07_32篇全收录.jpg
  2 主图备选/
  3 商品标题.txt
  4 商品描述.txt          只有可直接粘贴的简介正文
用 Python zipfile（不压缩；非 ASCII 文件名自动打 UTF-8 标记，踩坑 52），打完逐个核对：顺序、UTF-8 标记、内容与源文件一致、CRC。
"""
import importlib.util
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / '四级写作讲义_小店上传包.zip'
spec = importlib.util.spec_from_file_location('btms', HERE / '标题与描述.py')
T = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0], '--自检']           # 只取检查函数，不重新加载渲染程序


def readme(imgs, alts):
    return '\n'.join([
        '四级写作讲义 · B 站小店上传说明',
        '',
        '1. 商品图：打开「1 商品图（按顺序上传）」，按文件名序号 01 → {:02d} 依次上传；01 是主图（列表里显示的那张）。'.format(len(imgs)),
        '   规格：1:1，2000×2000 像素，JPG。',
        '2. 主图备选：「2 主图备选」里是另外 {} 个方向，想换主图就用它替换 01。'.format(len(alts)),
        '3. 商品标题：复制「3 商品标题.txt」里的短版（≤ 30 字）；平台允许长标题时用长版。',
        '4. 商品简介：「4 商品描述.txt」整篇复制粘贴即可（{} 字，平台上限 {} 字）。'.format(T.desc_len(DESC), T.DESC_MAX),
        '   简介已含虚拟商品不退款说明。',
        '',
        '商品本身（3 份 PDF）在 GitHub Release「cet6-writing-handout」。',
        '',
    ])


def main():
    import io
    from contextlib import redirect_stdout
    with redirect_stdout(io.StringIO()):
        try:
            spec.loader.exec_module(T)
        except SystemExit:
            pass
    global DESC
    desc_f, title_f = HERE / 'work' / '简介.txt', HERE / 'work' / '标题.txt'
    DESC = desc_f.read_text('utf-8').rstrip('\n')
    bad = T.desc_problems(DESC)
    imgs = sorted((HERE / '成品').glob('*.jpg'))
    alts = sorted((HERE / '成品' / '备选').glob('*.jpg'))
    names = [p.stem for p in imgs]
    if not imgs or names[0] != '01_主图' or [n[:2] for n in names] != [f'{i:02d}' for i in range(1, len(imgs) + 1)]:
        bad.append(f'商品图序号不连续或缺主图：{names}')
    if bad:
        print('不打包：\n  ' + '\n  '.join(bad))
        return 1
    items = [('0 上传说明.txt', readme(imgs, alts).encode('utf-8'))]
    items += [(f'1 商品图（按顺序上传）/{p.name}', p.read_bytes()) for p in imgs]
    items += [(f'2 主图备选/{p.name}', p.read_bytes()) for p in alts]
    items += [('3 商品标题.txt', title_f.read_bytes()), ('4 商品描述.txt', (DESC + '\n').encode('utf-8'))]
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_STORED) as z:
        for n, b in items:
            z.writestr(n, b)
    # 打完逐个核对
    with zipfile.ZipFile(OUT) as z:
        infos = z.infolist()
        assert [i.filename for i in infos] == [n for n, _ in items], '顺序不对'
        for i, (n, b) in zip(infos, items):
            assert i.flag_bits & 0x800, f'{n} 没有 UTF-8 标记'
            assert i.compress_type == zipfile.ZIP_STORED
            assert z.read(i) == b, f'{n} 内容不一致'
        assert z.testzip() is None
        assert z.read('4 商品描述.txt').decode('utf-8').rstrip('\n') == DESC
    print(f'{OUT.name}：{len(items)} 个文件，{OUT.stat().st_size / 1e6:.1f} MB；顺序、UTF-8 文件名、内容、CRC 核对通过')
    for n, _ in items:
        print('  ' + n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
