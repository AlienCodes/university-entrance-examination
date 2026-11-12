"""高考听力视频发布（Release gaokao-listening；由 cet4-listening-publish.py 复制）。照六级 cet6-listening-publish.py（踩坑 123、铁律 26）：
资产名只用 ASCII（四级/听力/tools/命名.py 的 asset），中文文件名（命名.label）写进资产标签 + cet4-listening-filenames.txt；
要中文文件名的下 zip：Python zipfile 不压缩、UTF-8 标记、固定时间戳，包里一个文件夹“四级听力”，按 命名.order（新的在前、同套考试紧跟原文），
按体积分包（每包 ≤ 1.9 GB，Release 单个附件 < 2 GB）。发布出问题只改发布这一步，不重做视频（铁律 26）。

    python3 .github/cet4-listening-publish.py plan <必须齐的种类,逗号> <ids.json> <art 目录> <up 目录>
    python3 .github/cet4-listening-publish.py todo|notes|pack|checkzip|verify-digest …
    python3 .github/cet4-listening-publish.py --自检
artifact：cet4listen-<套>（考试）/ cet4text-<套>（原文），里面 meta.json {套, kind, mp4, mp4_sha256, mp4_bytes, 原音_sha256}。"""
import hashlib, json, os, shutil, sys, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '高考听力/tools'))
import 命名

LIST = 'gaokao-listening-filenames.txt'
ZDATE = (2026, 11, 5, 0, 0, 0)
FOLDER = '高考听力/'
MAXZ = 1900 * 2 ** 20
ART = {'exam': 'gklisten-'}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def plan(kinds, ids, art, up):
    bad, rows = [], []
    have = {(i, k) for k in ART for i in ids if (art / f'{ART[k]}{i}' / 'meta.json').exists()}
    miss = [(i, k) for k in kinds for i in ids if (i, k) not in have]
    if miss: sys.exit(f'还缺 {len(miss)} 个（不发布）：{miss[:10]}')
    up.mkdir(parents=True, exist_ok=True)
    for i, k in 命名.order(sorted(have)):
        d = art / f'{ART[k]}{i}'
        m = json.loads((d / 'meta.json').read_text('utf-8'))
        f = d / m['mp4']
        if m.get('kind', 'exam') != k or m['套'] != i: bad.append(f'{i} {k} meta 不符')
        if m['mp4'] not in (命名.label(i, k), 命名.legacy_label(i, k)):
            bad.append(f'{i} {k} 文件名不属于本套当前或已核旧命名：{m["mp4"]}')
        if sha(f) != m['mp4_sha256']: bad.append(f'{i} {k} sha256 不符')
        if f.stat().st_size >= MAXZ: bad.append(f'{i} {k} 超过 1.9 GB')
        a = 命名.asset(i, k)
        if (up / a).exists(): (up / a).unlink()
        os.link(f, up / a)
        rows.append({'套': i, 'kind': k, 'asset': a, 'label': 命名.label(i,k), 'sha256': m['mp4_sha256'], 'bytes': f.stat().st_size})
    bad += 命名.problems([r['label'] for r in rows])
    bad += [f'资产名不是 ASCII：{r["asset"]}' for r in rows if not r['asset'].isascii()]
    if bad: sys.exit('停止：' + '；'.join(bad))
    (up / LIST).write_text('资产名\t中文文件名\tsha256\t字节数\n' + ''.join(f"{r['asset']}\t{r['label']}\t{r['sha256']}\t{r['bytes']}\n" for r in rows), 'utf-8')
    (up / 'plan.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), 'utf-8')
    cnt = ', '.join(f'{k} {sum(r["kind"] == k for r in rows)}' for k in ART)
    print(f'{len(rows)} 个视频齐全（{cnt}），资产名全部 ASCII')


def parts(rows):
    out, cur, n = [], [], 0
    for r in rows:
        if cur and n + r['bytes'] > MAXZ - (1 << 20): out.append(cur); cur, n = [], 0
        cur.append(r); n += r['bytes']
    return out + ([cur] if cur else [])


def zname(k):
    return f'gaokao-listening-{k + 1}.zip'


def pack(planf, out):
    rows = json.loads(Path(planf).read_text('utf-8')); up = Path(planf).parent
    for k, part in enumerate(parts(rows)):
        z = Path(out) / zname(k)
        with zipfile.ZipFile(z, 'w', zipfile.ZIP_STORED, allowZip64=True) as zf:
            for r in part:
                zi = zipfile.ZipInfo(FOLDER + r['label'], date_time=ZDATE); zi.compress_type = zipfile.ZIP_STORED; zi.external_attr = 0o644 << 16
                with open(up / r['asset'], 'rb') as src, zf.open(zi, 'w', force_zip64=True) as dst: shutil.copyfileobj(src, dst, 1 << 20)
        if z.stat().st_size >= 2 * 1024 ** 3: sys.exit(f'停止：{z.name} ≥ 2 GB')
        print(z.name, len(part), '个', round(z.stat().st_size / 1e9, 3), 'GB')


def zip_problems(zpath, part):
    bad = []
    with zipfile.ZipFile(zpath) as zf:
        il = zf.infolist()
        if [i.filename for i in il] != [FOLDER + r['label'] for r in part]: bad.append(f'{Path(zpath).name} 文件名 / 顺序不符：{[i.filename for i in il][:2]}')
        for i, r in zip(il, part):
            if not i.flag_bits & 0x800: bad.append(f'{i.filename} 没有 UTF-8 标记')
            if i.compress_type != zipfile.ZIP_STORED: bad.append(f'{i.filename} 压缩了')
            h = hashlib.sha256()
            with zf.open(i) as f:
                for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
            if h.hexdigest() != r['sha256']: bad.append(f'{i.filename} sha256 ≠ meta')
    return bad


def checkzip(planf, zpath):
    rows = json.loads(Path(planf).read_text('utf-8'))
    k = int(Path(zpath).stem.rsplit('-', 1)[1]) - 1
    try: bad = zip_problems(zpath, parts(rows)[k])
    except zipfile.BadZipFile as e: bad = [f'CRC / 包损坏：{e}']
    if bad: sys.exit('停止：' + '；'.join(bad))
    print(f'✅ {Path(zpath).name}：中文文件名、顺序、UTF-8 标记、不压缩、CRC、sha256 全部一致')


def zips(planf):
    print(' '.join(zname(k) for k in range(len(parts(json.loads(Path(planf).read_text('utf-8')))))))


def todo(planf, relf):
    rows = json.loads(Path(planf).read_text('utf-8'))
    have = {a['name']: a for a in json.loads(Path(relf).read_text('utf-8'))['assets']}
    for r in rows:
        x = have.get(r['asset'])
        if not x or x.get('digest') != 'sha256:' + r['sha256'] or x.get('label') != r['label']:
            print(r['asset'] + '\t' + r['label'])


def relabel(planf, relf):
    """内容和大小一致时只PATCH中文标签，保留已上传视频及资产ID。"""
    rows=json.loads(Path(planf).read_text())
    have={a['name']:a for a in json.loads(Path(relf).read_text())['assets']}
    for r in rows:
        x=have.get(r['asset'])
        if x and x.get('digest')=='sha256:'+r['sha256'] and x['size']==r['bytes'] and x.get('label')!=r['label']:
            print(str(x['id'])+'\t'+r['label'])


def notes(planf, out):
    rows = json.loads(Path(planf).read_text('utf-8'))
    ps = parts(rows)
    Path(out).write_text(
        f'高考英语听力 {len(rows)} 套（2019—2026，全国卷 / 新课标 / 新高考 / 浙江 / 江苏 / 上海）：视频版真题考试，4K，白纸黑字试卷样式；'
        '考试原声一律原音（只剪掉开头的音乐、试音和通用说明；个别录音被剪掉作答时间的，只补数字静音）。\n\n'
        '**要中文文件名请下载 zip 包**（解压后是文件夹“高考听力”，按年份、每年全国卷在前；不压缩，解压很快）：'
        + '；'.join(f"{zname(k)}：{p[0]['label'][:-4]} — {p[-1]['label'][:-4]}，{len(p)} 个" for k, p in enumerate(ps)) + '。\n\n'
        '**答案**：官方解析 × 独立做题一致；没有解析答案的套是两次独立做题一致。\n\n'
        'GitHub 不允许资产名里有中文：单个视频的资产名用英文，中文文件名是每个资产的标签，对照表如下（也见 gaokao-listening-filenames.txt）。\n\n'
        '| 资产名 | 中文文件名 | 大小 |\n|---|---|---|\n' + ''.join(f"| {r['asset']} | {r['label']} | {r['bytes'] / 1e6:.0f} MB |\n" for r in rows), 'utf-8')


def verify_digest(planf, relf):
    rows = json.loads(Path(planf).read_text('utf-8'))
    have = {a['name']: a for a in json.loads(Path(relf).read_text('utf-8'))['assets']}
    bad = []
    for r in rows:
        x = have.get(r['asset'])
        if not x: bad.append(f"缺 {r['asset']}"); continue
        if x.get('digest') != 'sha256:' + r['sha256']: bad.append(f"{r['asset']} digest {x.get('digest')} ≠ meta")
        if x['size'] != r['bytes']: bad.append(f"{r['asset']} 大小不符")
        if x.get('label') != r['label']: bad.append(f"{r['asset']} 标签不符")
    extra = set(have) - {r['asset'] for r in rows} - {LIST} - {zname(k) for k in range(len(parts(rows)))}
    if extra: bad.append(f'多出资产 {sorted(extra)}')
    if bad: sys.exit('停止：' + '；'.join(bad))
    print(f'✅ Release 资产 {len(rows)} 个视频：digest = meta sha256、大小、中文标签全部一致')


def selftest():
    import tempfile
    ok = True
    ids = ['2019-shc', '2019-xkb1', '2020-zj1']
    with tempfile.TemporaryDirectory() as t:
        t = Path(t); art = t / 'art'
        for i, n in zip(ids, [3000, 2000, 1000]):
            d = art / f'{ART["exam"]}{i}'; d.mkdir(parents=True)
            f = d / (命名.legacy_label(i,'exam') if i==ids[0] else 命名.label(i,'exam')); f.write_bytes(os.urandom(n))
            (d / 'meta.json').write_text(json.dumps({'套': i, 'kind': 'exam', 'mp4': f.name, 'mp4_sha256': sha(f), 'mp4_bytes': n}, ensure_ascii=False))
        plan(['exam'], ids, art, t / 'up')
        rows = json.loads((t / 'up/plan.json').read_text('utf-8'))
        ok &= [r['套'] for r in rows] == ['2019-xkb1', '2019-shc', '2020-zj1']
        pack(t / 'up/plan.json', t)
        ok &= not zip_problems(t / zname(0), parts(rows)[0])
        with zipfile.ZipFile(t / 'bad.zip', 'w') as zf:          # 雷：文件名不是 UTF-8、少文件 → 必须报
            zf.writestr(zipfile.ZipInfo(rows[0]['label']), b'x')
        ok &= bool(zip_problems(t / 'bad.zip', parts(rows)[0]))
        try:
            plan(['exam'], ids + ['2021-zj1'], art, t / 'up2'); ok = False      # 缺一套 → 必须停
        except SystemExit: pass
    print('✅ 发布自检' if ok else '❌ 发布自检'); sys.exit(0 if ok else 1)


if __name__ == '__main__':
    c = sys.argv[1]
    if c == '--自检': selftest()
    elif c == 'plan': plan(sys.argv[2].split(','), json.loads(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5]))
    elif c == 'todo': todo(sys.argv[2], sys.argv[3])
    elif c == 'relabel': relabel(sys.argv[2],sys.argv[3])
    elif c == 'notes': notes(sys.argv[2], sys.argv[3])
    elif c == 'pack': pack(sys.argv[2], sys.argv[3])
    elif c == 'zips': zips(sys.argv[2])
    elif c == 'checkzip': checkzip(sys.argv[2], sys.argv[3])
    elif c == 'verify-digest': verify_digest(sys.argv[2], sys.argv[3])
