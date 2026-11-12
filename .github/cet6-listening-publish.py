"""六级听力练习视频发布（踩坑 123）：GitHub 会把 Release 资产名里的非 ASCII 字符（中文）去掉（2018年12月…mp4 → 2018.12.1.mp4），
按中文名下载就“no assets match”。所以资产一律用 ASCII 名 cet6-listening-<套>.mp4，中文文件名写进资产 label，
另附 cet6-listening-filenames.txt（UTF-8：资产名、中文文件名、sha256、字节数）。

    python3 .github/cet6-listening-publish.py plan <ids.json> <art 目录> <up 目录>   # 核齐全、sha256、大小，按 ASCII 名放进 up/，写 plan.json
    python3 .github/cet6-listening-publish.py verify <plan.json> <下载目录>           # 按实际资产名核 sha256、个数
    python3 .github/cet6-listening-publish.py --自检                                   # 中文资产名必须报"""
import hashlib, json, os, re, shutil, sys, zipfile
from pathlib import Path

LIST = 'cet6-listening-filenames.txt'
ZIPS = ('cet6-listening-practice-1.zip', 'cet6-listening-practice-2.zip')   # 中文文件名的包（老师：下载解压就是中文名），各 15 套
ZDATE = (2026, 11, 4, 0, 0, 0)                                              # 固定时间戳：同样内容打出来逐字节相同（不重传）


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
        if (up / a).exists(): (up / a).unlink()
        os.link(f, up / a)                          # 硬链接，不占双倍磁盘
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


def halves(rows):
    k = (len(rows) + 1) // 2
    return [rows[:k], rows[k:]]


def pack(planf, out):
    """按中文文件名打两个包：不压缩（ZIP_STORED）、非 ASCII 名 Python 自动打 UTF-8 标记（0x800）、固定时间戳；各 < 2 GB"""
    rows = json.loads(Path(planf).read_text('utf-8')); up = Path(planf).parent
    for z, part in zip(ZIPS, halves(rows)):
        with zipfile.ZipFile(Path(out) / z, 'w', zipfile.ZIP_STORED, allowZip64=True) as zf:
            for r in part:
                zi = zipfile.ZipInfo(r['label'], date_time=ZDATE); zi.compress_type = zipfile.ZIP_STORED; zi.external_attr = 0o644 << 16
                with open(up / r['asset'], 'rb') as src, zf.open(zi, 'w', force_zip64=True) as dst: shutil.copyfileobj(src, dst, 1 << 20)
        n = (Path(out) / z).stat().st_size
        if n >= 2 * 1024 ** 3: sys.exit(f'停止：{z} {n} 字节 ≥ 2 GB')
        print(z, len(part), '套', round(n / 1e9, 3), 'GB')


def zip_problems(zpath, part):
    """下载回来的包逐个核：文件名 = 中文名（顺序一致）、UTF-8 标记、不压缩、CRC、每个视频 sha256 = meta"""
    bad = []
    with zipfile.ZipFile(zpath) as zf:
        il = zf.infolist()
        if [i.filename for i in il] != [r['label'] for r in part]: bad.append(f'{Path(zpath).name} 文件名 / 顺序不符：{[i.filename for i in il][:2]}')
        for i, r in zip(il, part):
            if not i.flag_bits & 0x800: bad.append(f'{i.filename} 没有 UTF-8 标记')
            if i.compress_type != zipfile.ZIP_STORED: bad.append(f'{i.filename} 压缩了')
            h = hashlib.sha256()
            with zf.open(i) as f:                     # 读到底时 zipfile 自己核 CRC，不符抛 BadZipFile
                for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
            if h.hexdigest() != r['sha256']: bad.append(f'{i.filename} sha256 ≠ meta')
    return bad


def checkzip(planf, zpath):
    rows = json.loads(Path(planf).read_text('utf-8'))
    part = halves(rows)[ZIPS.index(Path(zpath).name)]
    try: bad = zip_problems(zpath, part)
    except zipfile.BadZipFile as e: bad = [f'CRC / 包损坏：{e}']
    if bad: sys.exit('停止：' + '；'.join(bad))
    print(f'✅ {Path(zpath).name}：{len(part)} 个中文文件名、UTF-8 标记、不压缩、CRC、sha256 全部一致')


def todo(planf, relf):
    """已在 Release 里、digest（GitHub 服务器上算的 sha256）对上的资产不再上传（老师：不删、不重传）；打印要上传的“资产名<TAB>标签”"""
    rows = json.loads(Path(planf).read_text('utf-8'))
    have = {a['name']: a for a in json.loads(Path(relf).read_text('utf-8'))['assets']}
    for r in rows:
        x = have.get(r['asset'])
        if not x or x.get('digest') != 'sha256:' + r['sha256'] or x.get('label') != r['label']:
            print(r['asset'] + '\t' + r['label'])


def notes(planf, out):
    """Release 说明：中文名 ↔ 资产名对照表"""
    rows = json.loads(Path(planf).read_text('utf-8'))
    Path(out).write_text('2018-12 至 2026-06 共 30 套六级听力「视频版真题考试」，4K，原音（不调响度、不压缩、不限幅；2026-06 第 1 套插了作答停顿）。\n\n'
                         '**要中文文件名请下载两个包**（解压后就是中文文件名；不压缩，解压很快）：' + '；'.join(f"{z}：{p[0]['label'][:-len(' 视频版真题考试.mp4')]} — {p[-1]['label'][:-len(' 视频版真题考试.mp4')]}，{len(p)} 套" for z, p in zip(ZIPS, halves(rows))) + '。\n\n'
                         'GitHub 不允许资产名里有中文：单个视频的资产名用英文，中文文件名是每个资产的标签，对照表如下（也见 cet6-listening-filenames.txt）。\n\n'
                         '| 资产名 | 中文文件名 | 大小 |\n|---|---|---|\n' +
                         ''.join(f"| {r['asset']} | {r['label']} | {r['bytes'] / 1e6:.0f} MB |\n" for r in rows), 'utf-8')


def verify_digest(planf, relf):
    """按资产名 + digest 核：每个资产都在、digest = 渲染时 meta 的 sha256、大小、标签一致；资产总数 = 30 + 清单"""
    rows = json.loads(Path(planf).read_text('utf-8'))
    have = {a['name']: a for a in json.loads(Path(relf).read_text('utf-8'))['assets']}
    bad = []
    for r in rows:
        x = have.get(r['asset'])
        if not x: bad.append(f"缺 {r['asset']}"); continue
        if x.get('digest') != 'sha256:' + r['sha256']: bad.append(f"{r['asset']} digest {x.get('digest')} ≠ meta")
        if x['size'] != r['bytes']: bad.append(f"{r['asset']} 大小不符")
        if x.get('label') != r['label']: bad.append(f"{r['asset']} 标签不符")
    extra = set(have) - {r['asset'] for r in rows} - {LIST, *ZIPS}
    if extra: bad.append(f'多出资产 {sorted(extra)}')
    if bad: sys.exit('停止：' + '；'.join(bad))
    print(f'digest 核对 {len(rows)}/{len(rows)} 一致，资产 {len(have)} 个')


class NoUtf8(zipfile.ZipInfo):
    """自检用：旧工具（Info-ZIP zip -0）的写法——中文名按 GBK 写、不打 UTF-8 标记（踩坑 52）"""
    def _encodeFilenameFlags(self):
        return self.filename.encode('gbk'), self.flag_bits & ~0x800


def selftest():
    ok = True
    for name, names, want in [('ASCII 资产名', [asset_name('201812-1'), LIST], False),
                              ('中文资产名（旧写法，按 meta 的 mp4 名上传）', ['2018年12月 六级听力 第1套 视频版真题考试.mp4'], True),
                              ('带空格', ['cet6 listening.mp4'], True), ('重名', ['a.mp4', 'a.mp4'], True)]:
        got = name_problems(names)
        print(('✅' if bool(got) == want else '❌'), name, '→', got or '0 处'); ok &= bool(got) == want
    import tempfile                                   # digest 核对：正常 0；digest 不对、名字被 GitHub 改写（旧中文名上传）都报
    rows = [{'套': '201812-1', 'asset': asset_name('201812-1'), 'label': '2018年12月 六级听力 第1套 视频版真题考试.mp4', 'sha256': 'a' * 64, 'bytes': 5}]
    good = {'assets': [{'name': rows[0]['asset'], 'digest': 'sha256:' + 'a' * 64, 'size': 5, 'label': rows[0]['label']}, {'name': LIST, 'size': 1}]}
    with tempfile.TemporaryDirectory() as d:
        pf = Path(d) / 'p.json'; pf.write_text(json.dumps(rows, ensure_ascii=False), 'utf-8')
        for name, rel, want in [('digest 正常', good, False),
                                ('digest 不对', {'assets': [dict(good['assets'][0], digest='sha256:' + 'b' * 64), good['assets'][1]]}, True),
                                ('名字被 GitHub 改写（2018.12.1.mp4）', {'assets': [dict(good['assets'][0], name='2018.12.1.mp4'), good['assets'][1]]}, True)]:
            rf = Path(d) / 'r.json'; rf.write_text(json.dumps(rel, ensure_ascii=False), 'utf-8')
            try: verify_digest(pf, rf); got = False
            except SystemExit as e: got = bool(e.code) and e.code != 0
            print(('✅' if got == want else '❌'), name, '→', '报出' if got else '0 处'); ok &= got == want
        # 包：正常 0；ASCII 名进包、没有 UTF-8 标记（cp437 写法）、压缩了、内容不对，都报
        up = Path(d); (up / rows[0]['asset']).write_bytes(b'hello'); rows[0]['sha256'] = hashlib.sha256(b'hello').hexdigest()
        pf.write_text(json.dumps(rows, ensure_ascii=False), 'utf-8')
        def mk(z, name, data=b'hello', comp=zipfile.ZIP_STORED, utf8=True):
            with zipfile.ZipFile(z, 'w') as zf:
                zi = (zipfile.ZipInfo if utf8 else NoUtf8)(name, date_time=ZDATE); zi.compress_type = comp
                zf.writestr(zi, data)
        for name, kw, want in [('包 正常', {}, False), ('包 文件名是资产名', {'name': rows[0]['asset']}, True),
                               ('包 没有 UTF-8 标记', {'utf8': False}, True), ('包 压缩了', {'comp': zipfile.ZIP_DEFLATED}, True),
                               ('包 内容不对', {'data': b'hellp'}, True)]:
            z = up / 'x.zip'; mk(z, kw.pop('name', rows[0]['label']), **kw)
            try: got = bool(zip_problems(z, rows))
            except Exception: got = True
            print(('✅' if got == want else '❌'), name, '→', '报出' if got else '0 处'); ok &= got == want
        pack(pf, d); a1 = (up / ZIPS[0]).read_bytes(); pack(pf, d)
        same = (up / ZIPS[0]).read_bytes() == a1 and not zip_problems(up / ZIPS[0], halves(rows)[0])
        print(('✅' if same else '❌'), '包 两次打出来逐字节相同、自己核 0 处'); ok &= same
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == '--自检': selftest()
    elif a[0] == 'plan': plan(json.loads(a[1]), Path(a[2]), Path(a[3]))
    elif a[0] == 'verify': verify(a[1], a[2])
    elif a[0] == 'todo': todo(a[1], a[2])
    elif a[0] == 'notes': notes(a[1], a[2])
    elif a[0] == 'verify-digest': verify_digest(a[1], a[2])
    elif a[0] == 'pack': pack(a[1], a[2])
    elif a[0] == 'checkzip': checkzip(a[1], a[2])
