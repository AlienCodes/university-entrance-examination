"""六级听力练习视频发布（踩坑 123）：GitHub 会把 Release 资产名里的非 ASCII 字符（中文）去掉（2018年12月…mp4 → 2018.12.1.mp4），
按中文名下载就“no assets match”。所以资产一律用 ASCII 名 cet6-listening-<套>.mp4，中文文件名写进资产 label，
另附 cet6-listening-filenames.txt（UTF-8：资产名、中文文件名、sha256、字节数）。

    python3 .github/cet6-listening-publish.py plan <ids.json> <art 目录> <up 目录>   # 核齐全、sha256、大小，按 ASCII 名放进 up/，写 plan.json
    python3 .github/cet6-listening-publish.py verify <plan.json> <下载目录>           # 按实际资产名核 sha256、个数
    python3 .github/cet6-listening-publish.py --自检                                   # 中文资产名必须报"""
import hashlib, json, re, shutil, sys
from pathlib import Path

LIST = 'cet6-listening-filenames.txt'


def asset_name(sid):
    return f'cet6-listening-{sid}.mp4'


def name_problems(names):
    """资产名必须是 ASCII 的安全字符（GitHub 会改写别的字符），且不重名"""
    bad = [f'资产名不是 ASCII 安全字符（GitHub 会改写）：{n}' for n in names if not re.fullmatch(r'[A-Za-z0-9._-]+', n)]
    if len(set(names)) != len(names): bad.append('资产名重复')
    return bad


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def plan(ids, art, up):
    bad, rows = [], []
    miss = [i for i in ids if not (art / f'cet6listen-{i}' / 'meta.json').exists()]
    if miss: sys.exit(f'还缺 {len(miss)} 套（不发布）：{miss}')
    up.mkdir(parents=True, exist_ok=True)
    for i in ids:
        d = art / f'cet6listen-{i}'
        m = json.loads((d / 'meta.json').read_text('utf-8'))
        f = d / m['mp4']
        if sha(f) != m['mp4_sha256']: bad.append(f'{i} sha256 不符')
        if f.stat().st_size >= 2 * 1024 ** 3: bad.append(f'{i} 超过 2 GB')
        a = asset_name(i)
        shutil.copyfile(f, up / a)
        rows.append({'套': i, 'asset': a, 'label': m['mp4'], 'sha256': m['mp4_sha256'], 'bytes': f.stat().st_size})
    bad += name_problems([r['asset'] for r in rows] + [LIST])
    if len({r['label'] for r in rows}) != len(rows): bad.append('中文文件名重复')
    if bad: sys.exit('停止：' + '；'.join(bad))
    (up / LIST).write_text('资产名\t中文文件名\tsha256\t字节数\n' + ''.join(f"{r['asset']}\t{r['label']}\t{r['sha256']}\t{r['bytes']}\n" for r in rows), 'utf-8')
    (up / 'plan.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), 'utf-8')
    print(f'{len(rows)} 套齐全，资产名全部 ASCII')


def verify(planf, dl):
    rows = json.loads(Path(planf).read_text('utf-8'))
    bad = [f"{r['asset']} sha256 不符" for r in rows if sha(Path(dl) / r['asset']) != r['sha256']]
    if bad: sys.exit('停止：' + '；'.join(bad))
    print(f'下载核对 {len(rows)} 个，sha256 全部一致')


def selftest():
    ok = True
    for name, names, want in [('ASCII 资产名', [asset_name('201812-1'), LIST], False),
                              ('中文资产名（旧写法，按 meta 的 mp4 名上传）', ['2018年12月 六级听力 第1套 视频版真题考试.mp4'], True),
                              ('带空格', ['cet6 listening.mp4'], True), ('重名', ['a.mp4', 'a.mp4'], True)]:
        got = name_problems(names)
        print(('✅' if bool(got) == want else '❌'), name, '→', got or '0 处'); ok &= bool(got) == want
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == '--自检': selftest()
    elif a[0] == 'plan': plan(json.loads(a[1]), Path(a[2]), Path(a[3]))
    elif a[0] == 'verify': verify(a[1], a[2])
