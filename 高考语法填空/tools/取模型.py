"""从老师上传到云盘的大 zip（GPT-SoVITS 整合包 + VoiceTwin 文件夹）里只取合成要用的文件（在 GitHub Actions runner 上跑）。

  python 取模型.py --url-env U --dl /mnt/dl --out /mnt/sovits    下载 → 只解需要的 → 立刻删 zip → 写 out/ref.json
  python 取模型.py --check-out out                                 上传前核对：out/ 里不许有模型、素材

取的东西（按 VoiceTwin 的写法，voicetwin/project.py、data/references.py、synth/select.py）：
  workspace/<声音名>/models.json 的 gptsovits.selected（挑出来的最佳组合：gpt .ckpt + sovits .pth，按文件名在 zip 里找）、
  gptsovits.speed（各语言语速）；references.json 里挑好的参考（每种语言主参考 + 2 条辅助参考，同 aux_references）及其 wav；
  transcripts.csv（以后挑参考、量相似度用）。
zip 里没有 UTF-8 标记的文件名按 GBK 解（Windows 中文系统打的包；同 高考续写/tools/取原卷.py）。
隐私：链接只从环境变量读、不打印；日志只打印个数和大小，不打印素材文字和文件名；模型、素材只在 --out（runner 本地）。
"""
import argparse
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

MODEL_EXT = ('.pth', '.ckpt')


def zname(info):
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode('cp437').decode('gbk')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def parts(name):
    return PurePosixPath(name.replace('\\', '/')).parts


def base(p):
    return PureWindowsPath(str(p)).name if ('\\' in str(p) or ':' in str(p)) else PurePosixPath(str(p)).name


def find_project(names):
    """找 workspace/<声音名>/models.json（有 gptsovits.selected 的那个）。返回 (项目目录前缀 tuple, models.json 成员名)。"""
    cands = [n for n in names if parts(n)[-1] == 'models.json' and 'workspace' in parts(n)]
    if not cands:
        raise SystemExit('zip 里找不到 workspace/<声音名>/models.json')
    return cands


def extract(z, info, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    with z.open(info) as f, open(dst, 'wb') as g:
        shutil.copyfileobj(f, g, 1 << 20)


def take(zpath, out):
    z = zipfile.ZipFile(zpath)
    infos = {zname(i): i for i in z.infolist() if not i.is_dir()}
    names = list(infos)
    print(f'zip 里 {len(names)} 个文件', flush=True)
    chosen = None
    for mj in find_project(names):
        m = json.loads(z.read(infos[mj]).decode('utf-8-sig'))
        g = m.get('gptsovits') or {}
        if g.get('selected'):
            chosen = (mj, m, g)
            break
    if not chosen:
        raise SystemExit('models.json 里没有 gptsovits.selected（还没挑模型？）')
    mj, m, g = chosen
    proj = parts(mj)[:-1]
    sel = g['selected']
    print('最佳组合：', {k: base(v) for k, v in sel.items() if k in ('gpt', 'sovits')}, flush=True)
    res = {'gpt': None, 'sovits': None, 'speed': g.get('speed') or {}, 'refs': {}}
    for key, sub in (('gpt', 'GPT_weights'), ('sovits', 'SoVITS_weights')):
        want = base(sel[key])
        hits = [n for n in names if parts(n)[-1] == want and any(p.startswith(sub) for p in parts(n))]
        hits = hits or [n for n in names if parts(n)[-1] == want]
        if len(hits) != 1:
            raise SystemExit(f'{key} 模型 {want} 在 zip 里找到 {len(hits)} 个')
        extract(z, infos[hits[0]], out / 'weights' / want)
        res[key] = f'weights/{want}'
    pref = '/'.join(proj) + '/'
    for f in ('models.json', 'references.json', 'transcripts.csv', 'profile.json'):
        n = pref + f
        if n in infos:
            extract(z, infos[n], out / 'workspace' / f)
    refs = json.loads((out / 'workspace/references.json').read_text('utf-8-sig'))
    from collections import Counter
    print('references.json 各语言条数：', dict(Counter(r.get('lang') for r in refs)), flush=True)
    for lang in ('zh', 'en'):           # 同 data/references.py：主参考 = 该语言第一条陈述句；辅助 = 同语言另外两条陈述句
        same = [r for r in refs if r['lang'] == lang]
        if not same:
            continue
        main = next((r for r in same if r.get('kind') == 'statement'), same[0])
        aux = [r for r in same if r['id'] != main['id'] and r.get('kind') == 'statement'][:2]
        ent = []
        for r in [main] + aux:
            n = pref + str(r['path']).replace('\\', '/')
            if n not in infos:
                raise SystemExit(f'参考音频不在 zip 里（{lang}）')
            dst = out / 'refs' / f"{lang}_{len(ent)}.wav"
            extract(z, infos[n], dst)
            ent.append({'wav': str(dst.relative_to(out)), 'text': r['text'], 'sec': r.get('duration')})
        res['refs'][lang] = {'main': ent[0], 'aux': ent[1:]}
    (out / 'ref.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), 'utf-8')
    sz = sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    print(f"取出：模型 2 个、参考 {sum(1 + len(v['aux']) for v in res['refs'].values())} 条（{', '.join(res['refs'])}），"
          f"共 {sz / 2**20:.0f} MB；语速 {res['speed']}", flush=True)


class RangeFile:
    """按 HTTP Range 远程读的只读文件对象（zipfile 只读中央目录和要的成员，不下整包）。块缓存 8 MB。"""
    BLOCK = 8 << 20

    def __init__(self, url, session):
        self.url, self.s, self.pos, self.cache = url, session, 0, {}
        r = self.s.get(url, headers={'Range': 'bytes=0-0'}, stream=True, timeout=60)
        if r.status_code != 206 or 'Content-Range' not in r.headers:
            raise OSError(f'不支持 Range（HTTP {r.status_code}）')
        self.size = int(r.headers['Content-Range'].split('/')[-1])
        r.close()
        self.fetched = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def _block(self, k):
        if k not in self.cache:
            a = k * self.BLOCK
            b = min(self.size, a + self.BLOCK) - 1
            for t in range(5):
                try:
                    r = self.s.get(self.url, headers={'Range': f'bytes={a}-{b}'}, timeout=120)
                    if r.status_code == 206 and len(r.content) == b - a + 1:
                        break
                except Exception:   # noqa: BLE001  网络抖动重试
                    pass
            else:
                raise OSError(f'Range 读失败 {a}-{b}')
            if len(self.cache) > 64:
                self.cache.pop(next(iter(self.cache)))
            self.cache[k] = r.content
            self.fetched += len(r.content)
        return self.cache[k]

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        out = bytearray()
        while n > 0:
            k, o = divmod(self.pos, self.BLOCK)
            blk = self._block(k)[o:o + n]
            out += blk
            self.pos += len(blk)
            n -= len(blk)
        return bytes(out)

    def close(self):
        pass


def file_id(url):
    import re
    m = re.search(r'/d/([A-Za-z0-9_-]+)', url) or re.search(r'[?&]id=([A-Za-z0-9_-]+)', url)
    if not m:
        raise SystemExit('认不出云盘文件 ID')
    return m.group(1)


def open_remote(url):
    """先试 Range 远程读（只取需要的几百 MB）；不行返回 None，退回整包下载。"""
    import requests
    s = requests.Session()
    u = f'https://drive.usercontent.google.com/download?id={file_id(url)}&export=download&confirm=t'
    try:
        f = RangeFile(u, s)
    except OSError as e:
        print('Range 远程读不可用：', e, flush=True)
        return None
    print(f'Range 远程读可用，zip {f.size / 2**30:.2f} GB', flush=True)
    return f


def download(url, dl):
    import gdown
    dl.mkdir(parents=True, exist_ok=True)
    p = dl / 'model.zip'
    r = gdown.download(url, str(p), quiet=True, fuzzy=True)   # 处理云盘大文件的确认页
    if not r or not p.exists():
        raise SystemExit('云盘下载失败（链接权限要设成“知道链接的任何人”）')
    print(f'下载完成 {p.stat().st_size / 2**30:.2f} GB', flush=True)
    return p


FORBID_EXT = MODEL_EXT + ('.csv', '.zip', '.npy', '.safetensors', '.bin')


def check_out(out):
    """上传前核对：只许有合成出来的音频、meta、成品与报告；有模型、素材、参考录音就报错（退出码 1）。"""
    bad = []
    for p in Path(out).rglob('*'):
        if p.is_file() and (p.suffix.lower() in FORBID_EXT or p.stat().st_size > 200 * 2**20
                            or p.name in ('ref.json', 'references.json', 'models.json', 'transcripts.csv')
                            or 'refs' in p.parts or 'workspace' in p.parts):
            bad.append(str(p))
    if bad:
        print('隐私核对不通过：out/ 里有不许上传的文件', len(bad), '个', file=sys.stderr)
        for b in bad[:20]:
            print('  ', b, file=sys.stderr)
        return 1
    print('隐私核对通过（out/ 里只有合成结果）')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url-env')
    ap.add_argument('--zip', help='本地已有的 zip（自检用）')
    ap.add_argument('--dl', default='dl')
    ap.add_argument('--out')
    ap.add_argument('--check-out')
    a = ap.parse_args()
    if a.check_out:
        sys.exit(check_out(a.check_out) if Path(a.check_out).exists() else 0)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.zip:
        take(a.zip, out)
        return
    url = os.environ[a.url_env]
    rf = open_remote(url)
    if rf is not None:
        take(rf, out)
        print(f'Range 共读 {rf.fetched / 2**20:.0f} MB', flush=True)
        return
    zp = download(url, Path(a.dl))
    try:
        take(zp, out)
    finally:
        zp.unlink(missing_ok=True)            # runner 磁盘有限：取完立刻删
        print('zip 已删除', flush=True)


if __name__ == '__main__':
    main()
