"""从原卷 PDF 取出嵌入字体，修复字符映射，供听力视频画面用（字体文件只放本机 fonts_local/，已 .gitignore，绝不提交）。

原卷（专八/真题/2025年 英语专业八级真题.pdf）嵌入的是整套字形（Times New Roman 4728 个、SimSun 28905 个），
但字符映射表（cmap）被裁到只剩原卷用过的字（TNR 97 个、SimSun 147 个）——别的字浏览器找不到，会落到系统字体。
修复：字形顺序本身是有规律的，按规律补全映射，并用 PDF 保留下来的每一条映射逐条核对（一条不符就停）：
  · Times New Roman：可打印 ASCII 是 TrueType 标准 Mac 顺序（GID 3—97，GID 36 = A）；其余只用 PDF 保留的（— ’ 都在），
  · SimSun：ASCII、全角 FF01—FF5E、CJK 统一汉字 4E00—9FA5 三段都按 Unicode 顺序连续排列。
用法：/opt/ttsenv/bin/python 专八/听力/tools/取字体.py
"""
import io, sys
from pathlib import Path
from pypdf import PdfReader
from fontTools.ttLib import TTFont
from fontTools.ttLib.standardGlyphOrder import standardGlyphOrder
from fontTools.agl import toUnicode

HERE = Path(__file__).resolve().parent
PDF = HERE.parents[1] / '真题' / '2025年 英语专业八级真题.pdf'
OUT = HERE.parent / 'fonts_local'
OUT.mkdir(exist_ok=True)


def die(m):
    print('停止：' + m); sys.exit(1)


fonts = {}
for p in PdfReader(str(PDF)).pages:
    for v in p['/Resources'].get('/Font', {}).values():
        v = v.get_object()
        d = v['/DescendantFonts'][0].get_object() if '/DescendantFonts' in v else v
        ff = d['/FontDescriptor'].get_object().get('/FontFile2')
        if ff:
            t = TTFont(io.BytesIO(ff.get_object().get_data()))
            fonts.setdefault(t['name'].getDebugName(4), t)

for name, t in fonts.items():
    go = t.getGlyphOrder()
    old = {k: go.index(g) for k, g in (t.getBestCmap() or {}).items()}
    new = {}
    if name.startswith('Times New Roman'):
        for gid, gn in enumerate(standardGlyphOrder):
            u = toUnicode(gn)
            if len(u) == 1 and 0x20 <= ord(u) <= 0x7E:     # 只推可打印 ASCII（标准顺序的 GID 3—97）；再往后各版本有增删，不推
                new[ord(u)] = gid
    elif name == 'SimSun':
        for lo, hi, base in ((0x20, 0x7E, 0x20 - 3), (0xFF01, 0xFF5E, 0xFF0C - 712), (0x4E00, 0x9FA5, 0x4E13 - 1091)):
            for cp in range(lo, hi + 1):
                new[cp] = cp - base
        new[0x3001], new[0x3002] = 451, 452
    else:
        continue
    bad = [(hex(k), old[k], new.get(k)) for k in old if k in new and new[k] != old[k]]
    if bad:
        die(f'{name}：推出的映射与 PDF 保留的映射不符 {bad[:5]}')
    new.update(old)
    # PDF 只保留了原卷用过的字的轮廓，其余字形是空的（2025-10-25 样板里数字、汉字成了空白）：映射只留有轮廓的字，其余交给后备字体
    gl = t['glyf']
    new = {k: g for k, g in new.items() if k == 0x20 or gl[go[g]].numberOfContours != 0}
    if any(gl[go[g]].numberOfContours == 0 for k, g in new.items() if k != 0x20):
        die(f'{name}：映射里还有空字形')
    for tb in t['cmap'].tables:
        if tb.platformID == 3 or tb.platformID == 0:
            tb.cmap = {k: go[g] for k, g in new.items()}
    fn = OUT / (name.replace(' ', '') + '.ttf')
    t.save(str(fn))
    print(f'{name}：PDF 原有映射 {len(old)} 条逐条一致；有轮廓、可用的字 {len(new)} 个 → {fn.name}')
for name in ('Wingdings', 'Arial'):
    if name in fonts:
        fonts[name].save(str(OUT / (name + '.ttf')))
