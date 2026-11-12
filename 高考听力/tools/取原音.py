#!/usr/bin/env python3
"""从老师 Release gaokao-listening-raw 的 default.zip 取一套的原音（GitHub Actions 与本机同一条路）。
  python3 -I 取原音.py <套号> <输出.mp3> [default.zip]
zip 不在就用 gh api 按资产号下载（gh release download 走 GraphQL 被拦）；zip 里文件名是 GBK（按 cp437 → gbk 解码）；
按 识别/<套>/原音.sha256 找那一段录音，写出后再核 sha256，对不上就停。"""
import hashlib, json, subprocess, sys, zipfile
from pathlib import Path

P = Path(__file__).resolve().parents[1]
ASSET, ZSHA = 732507489, '9270b3f93995cfbddf77793e7d6ba4cd2b6464c2e9ae8100c1dab3acc1dc00a2'
sid, out = sys.argv[1], Path(sys.argv[2])
zp = Path(sys.argv[3]) if len(sys.argv) > 3 else Path('/tmp/gaokao-default.zip')
S = json.loads((P / '套.json').read_text('utf-8'))[sid]
want, name = (P / '识别' / S['识别'] / '原音.sha256').read_text('utf-8').split(None, 1)
name = name.strip()


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


if not zp.exists():
    with open(zp, 'wb') as f:
        subprocess.run(['gh', 'api', '-H', 'Accept: application/octet-stream',
                        f'repos/aliencodes/university-entrance-examination/releases/assets/{ASSET}'], stdout=f, check=True)
    if sha(zp) != ZSHA: sys.exit(f'停止：default.zip sha256 不对')
with zipfile.ZipFile(zp) as z:
    def dec(i):
        try: return i.filename.encode('cp437').decode('gbk')
        except (UnicodeEncodeError, UnicodeDecodeError): return i.filename
    hit = [i for i in z.infolist() if dec(i) == name]
    if len(hit) != 1: sys.exit(f'停止：zip 里 {name} 找到 {len(hit)} 个')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(z.read(hit[0]))
if sha(out) != want: sys.exit(f'停止：{out} sha256 ≠ 识别/{S["识别"]}/原音.sha256')
print(sid, '原音', name, '→', out, 'sha256 已核')
