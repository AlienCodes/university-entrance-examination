"""六级听力原始材料整理（GitHub Actions 上跑，本会话不能建 Release）。
老师上传 user-upload-3/default.zip（1.8 GB）→ 核对 sha256 → 取出 30 个原音 mp3、30 份 otter transcripts、
内层 zip 里 30 套对应的 真题 / 解析 PDF → 统一命名 cet6-<年月>-<套>{.mp3,-otter.zip,-paper.pdf,-jiexi.pdf}
→ 与仓库 六级/听力/原始材料/SHA256SUMS 逐个比对（本机整理时算的，多一个、少一个、不一样都停）。
用法：python3 cet6-listening-materials.py default.zip 输出目录
中文文件名：带 UTF-8 标记的直接用，不带的按 GBK 解（踩坑 43、52，一律 Python zipfile）。"""
import hashlib, re, sys, zipfile
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
SRC_SHA = '4dbb1aa98110549fd34cd3ba440fa4ed5c713d5095621dfe3ca0625fa3e54769'
h = hashlib.sha256()
with open(src, 'rb') as f:
    for b in iter(lambda: f.read(1 << 22), b''): h.update(b)
if h.hexdigest() != SRC_SHA: sys.exit(f'停止：default.zip sha256 {h.hexdigest()} ≠ {SRC_SHA}')


def name(i):
    return i.filename if i.flag_bits & 0x800 else i.filename.encode('cp437').decode('gbk')


def key(n):
    y, mo, k = re.search(r'(\d{4})年(\d{1,2})月.*?第(\d)套', n).groups()
    return f'{y}{int(mo):02d}-{k}'


z = zipfile.ZipFile(src)
sets, inner = set(), None
for i in z.infolist():
    n = name(i)
    if n.endswith('.mp3') or n.endswith('_otter_ai.zip'):
        k = key(n.rsplit('/', 1)[-1]); sets.add(k)
        dst = out / (f'cet6-{k}.mp3' if n.endswith('.mp3') else f'cet6-{k}-otter.zip')
        if dst.exists(): sys.exit(f'停止：重名 {dst.name}')
        dst.write_bytes(z.read(i))
    elif n.endswith('真题及答案解析.zip'):
        inner = i
z2 = zipfile.ZipFile(z.open(inner))
for i in z2.infolist():
    n = name(i)
    m = re.match(r'(\d{4})年(\d{2})月', n)
    base = n.rsplit('/', 1)[-1]
    if not m or not base.lower().endswith('.pdf'): continue
    ks = [int(x) for x in re.findall(r'第(\d)', base)] or ([1] if '全1套' in base else [])
    kind = 'jiexi' if re.search('解析|详解', base) else 'paper'
    for k in ks:
        s = f'{m.group(1)}{m.group(2)}-{k}'
        if s in sets:
            dst = out / f'cet6-{s}-{kind}.pdf'
            if dst.exists(): sys.exit(f'停止：重名 {dst.name}')
            dst.write_bytes(z2.read(i))
want = dict(l.split()[::-1] for l in (Path(__file__).parents[1] / '六级/听力/原始材料/SHA256SUMS').read_text().splitlines() if l.strip())
got = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir()}
bad = sorted(set(want) ^ set(got)) + [n for n in want if n in got and want[n] != got[n]]
if len(sets) != 30 or bad: sys.exit(f'停止：{len(sets)} 套；不一致 {bad}')
print(f'30 套，{len(got)} 个文件，sha256 与仓库清单逐个相同')
