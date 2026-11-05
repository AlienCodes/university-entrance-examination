"""从老师上传的 Release（草稿 435624091 / 标签 upload-1）的 default.zip 里取出原始文件，按 ASCII 名存放并核 sha256。
用法：python3 取材料.py 输出目录 <id 或 原名正则> ...
  id（如 t202512-1、s202303-1）：取 原始材料/音频清单.json 里那段录音，存为 cet4-<id>.mp3，核 SHA256SUMS；
  re:<正则>：取原名匹配的所有文件（试卷 / 解析 PDF 等），原样存（文件名保留中文），并打印 sha256。
只用标准库 + gh（GH_TOKEN）。default.zip 下载一次缓存在 $CET4_ZIP（默认 /tmp/cet4-default.zip）。"""
import hashlib, json, os, re, subprocess, sys, zipfile
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
REPO = 'aliencodes/university-entrance-examination'
ZIP = Path(os.environ.get('CET4_ZIP', '/tmp/cet4-default.zip'))
INNER = '四级听力视频/解析 听力原文对照.zip'

def gh(*a):
    return subprocess.run(['gh', 'api', *a], capture_output=True, check=True).stdout
def fetch():
    if ZIP.exists() and ZIP.stat().st_size > 2_000_000_000: return
    rel = None
    for path in (f'repos/{REPO}/releases/435624091', f'repos/{REPO}/releases/tags/upload-1'):
        try: rel = json.loads(gh(path)); break
        except subprocess.CalledProcessError: pass
    if rel is None:   # 老师重新建了 Release：找带 default.zip 的最新一个
        rel = next(r for r in json.loads(gh(f'repos/{REPO}/releases?per_page=30'))
                   if any(a['name'] == 'default.zip' for a in r['assets']))
    a = next(a for a in rel['assets'] if a['name'] == 'default.zip')
    with open(ZIP, 'wb') as f:
        subprocess.run(['gh', 'api', '-H', 'Accept: application/octet-stream', f'repos/{REPO}/releases/assets/{a["id"]}'],
                       stdout=f, check=True)
    assert ZIP.stat().st_size == a['size'], (ZIP.stat().st_size, a['size'])
def nm(i):
    n = i.filename
    if not i.flag_bits & 0x800:
        try: n = n.encode('cp437').decode('gbk')
        except Exception: pass
    return n
def members(need_inner):
    z = zipfile.ZipFile(ZIP)
    outer = {nm(i): (z, i) for i in z.infolist()}
    if not need_inner: return outer, {}
    inner_path = ZIP.with_suffix('.inner.zip')
    if not inner_path.exists():
        with z.open(outer[INNER][1]) as s, open(inner_path, 'wb') as d:
            while b := s.read(1 << 22): d.write(b)
    zi = zipfile.ZipFile(inner_path)
    inner = {'【' + nm(i).split('【', 1)[1] if '【' in nm(i) else nm(i): (zi, i) for i in zi.infolist()}
    return outer, inner
def copy(src, dst):
    z, i = src; h = hashlib.sha256()
    with z.open(i) as s, open(dst, 'wb') as d:
        while b := s.read(1 << 22): h.update(b); d.write(b)
    return h.hexdigest()

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
lst = {x['id']: x for x in json.loads((HERE / '原始材料/音频清单.json').read_text('utf-8'))}
fetch()
outer, inner = members(any(a.startswith('re:') or not lst[a]['原名'].startswith('四级听力视频/') for a in sys.argv[2:]))
allm = {**outer, **inner}
sums = dict(l.split()[::-1] for l in (HERE / '原始材料/SHA256SUMS').read_text().split('\n') if l)
bad = []
for arg in sys.argv[2:]:
    if arg.startswith('re:'):
        hit = [k for k in allm if re.search(arg[3:], k) and not k.endswith('/')]
        if not hit: bad.append(f'没有文件匹配 {arg}')
        for k in hit:
            h = copy(allm[k], out / k.split('/')[-1]); print(h, k)
        continue
    x = lst[arg]; asset = x['asset']
    h = copy(allm[x['原名']], out / asset)
    if h != sums[asset]: bad.append(f'{asset} sha256 不对')
    print(h, asset)
if bad: sys.exit('停止：' + '；'.join(bad))
