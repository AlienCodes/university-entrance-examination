"""截图盲审省 token（用户 2026-10-23：“正在大量消耗 token”）：把审阅副本里的逐屏截图拼成 2×2 拼图，每格左上角标“篇目 屏号”。
审阅员一次打开几张拼图，每人只审二十来张，对话不越堆越长；整图约 1178 张 → 拼图约 300 张，token 少一个数量级。
埋雷照旧（截图盲审准备.py 已把雷埋进副本），先试一批、雷全部查出才放开。

    /opt/ttsenv/bin/python 专八/tools/截图拼图.py <审阅副本目录> <拼图目录>     → 打印每批的拼图清单（JSON）"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
W, H = 960, 540                                  # 每格：1920×1080 截图缩一半；整张拼图 1920×1080
FONT = next((f for f in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
             if Path(f).exists()), None)
font = ImageFont.truetype(FONT, 30) if FONT else ImageFont.load_default()
out = {}
for b in sorted(p for p in src.iterdir() if p.is_dir() and p.name.startswith('b')):
    tiles = [(pid.name, f) for pid in sorted(x for x in b.iterdir() if x.is_dir() and x.name != 'ref') for f in sorted(pid.glob('screen*.jpg'))]
    (dst / b.name).mkdir(parents=True, exist_ok=True)
    sheets = []
    for i in range(0, len(tiles), 4):
        sheet = Image.new('RGB', (2 * W, 2 * H), 'white')
        d = ImageDraw.Draw(sheet)
        for j, (pid, f) in enumerate(tiles[i:i + 4]):
            x, y = (j % 2) * W, (j // 2) * H
            sheet.paste(Image.open(f).convert('RGB').resize((W, H), Image.LANCZOS), (x, y))
            label = f'{pid} {f.stem}'
            d.rectangle([x, y, x + 260, y + 42], fill='#c00000')
            d.text((x + 8, y + 4), label, fill='white', font=font)
            d.rectangle([x, y, x + W - 1, y + H - 1], outline='#444444', width=2)
        name = dst / b.name / f'sheet{i // 4 + 1:03d}.jpg'
        sheet.save(name, quality=90)
        sheets.append(str(name))
    out[b.name] = sheets
    print(b.name, len(tiles), '屏 →', len(sheets), '张拼图', file=sys.stderr)
print(json.dumps(out, ensure_ascii=False))
