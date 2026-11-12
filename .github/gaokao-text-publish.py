"""高考精读独立发布：复用通过成品，只改标签/打包；缺套或核查不符即停止。"""
import hashlib, json, os, shutil, sys, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '高考听力/精读/tools'))
import 命名

LIST = 'gaokao-text-filenames.txt'
ZDATE = (2026, 11, 5, 0, 0, 0)
FOLDER = '高考英语原文精读/'
MAXZ = 1900 * 2 ** 20
ART = {'text': 'gktext-'}
TEST_IDS=set()


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
        if m.get('kind') != k or m['套'] != i: bad.append(f'{i} {k} meta 不符')
        if m['mp4'] != 命名.label(i,k): bad.append(f'{i} 中文文件名不符')
        v=json.loads((d/'verification.json').read_text())
        if v.get('id')!=i or not v['ok'] or v['sha256']!=m['mp4_sha256'] or v['fingerprint']!=m['fingerprint']:
            bad.append(f'{i} 成品核查与meta不符')
        if i not in TEST_IDS:
            from 审校登记 import check as review_check
            row=review_check(i)
            if any(m.get(x)!=row[x] for x in ('定稿_sha256','译注_sha256')):bad.append(f'{i} 不是当前复核定稿')
            source=json.loads((Path(__file__).resolve().parents[1]/'高考听力/精读/定稿'/f'{i}.json').read_text())
            if m.get('原音_sha256')!=source['source_hash']:bad.append(f'{i} 原音不是当前已核来源')
        if m.get('mp4_bytes')!=f.stat().st_size:bad.append(f'{i} meta字节数不符')
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
    return f'gaokao-text-{k + 1}.zip'


def pack(planf, out, only=None):
    rows = json.loads(Path(planf).read_text('utf-8')); up = Path(planf).parent
    for k, part in enumerate(parts(rows)):
        if only is not None and zname(k)!=only:continue
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


def notes(planf, out):
    rows = json.loads(Path(planf).read_text('utf-8'))
    ps = parts(rows)
    Path(out).write_text(
        f'高考英语真题原文精读，共{len(rows)}套，2019—2026年。4K，考试原声，逐句英文、中文译文及词汇短语对应高亮。片头采用热气球与书本，年份和卷名突出显示。\n\n'
        '**下载zip可得到中文文件名**，解压后按年份及卷别排列；各包不超过1.9GiB。\n\n'
        + '；'.join(f"{zname(k)}：{len(p)}个" for k,p in enumerate(ps))+'。\n\n'
        '原文和译注经分组审校、跨组复核；每套通过原音SHA256、逐句时间、全屏排版、成品逐屏画面及原声完整比对。\n\n'
        '| 资产名 | 中文文件名 | 大小 |\n|---|---|---|\n'
        + ''.join(f"| {r['asset']} | {r['label']} | {r['bytes']/1e6:.0f} MB |\n" for r in rows),'utf-8')


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
    global TEST_IDS
    ids=['2019-shc','2019-xkb1','2020-zj1'];TEST_IDS=set(ids)
    with tempfile.TemporaryDirectory() as t:
        t=Path(t);art=t/'art'
        for sid,n in zip(ids,[3000,2000,1000]):
            d=art/f'{ART["text"]}{sid}';d.mkdir(parents=True)
            f=d/命名.label(sid);f.write_bytes(os.urandom(n))
            m={'套':sid,'kind':'text','mp4':f.name,'mp4_sha256':sha(f),'mp4_bytes':n,'fingerprint':'test'}
            (d/'meta.json').write_text(json.dumps(m,ensure_ascii=False))
            (d/'verification.json').write_text(json.dumps({'id':sid,'ok':True,'sha256':sha(f),'fingerprint':'test'}))
        plan(['text'],ids,art,t/'up')
        rows=json.loads((t/'up/plan.json').read_text())
        assert [r['套'] for r in rows]==['2019-xkb1','2019-shc','2020-zj1']
        pack(t/'up/plan.json',t)
        assert not zip_problems(t/zname(0),parts(rows)[0])
        try:plan(['text'],ids+['2021-zj1'],art,t/'missing')
        except SystemExit:pass
        else:raise AssertionError('缺套未拦截')
        f=next(art.rglob('*.mp4'));f.write_bytes(b'corrupt')
        try:plan(['text'],ids,art,t/'tampered')
        except SystemExit:pass
        else:raise AssertionError('文件篡改未拦截')
    TEST_IDS=set();print('精读发布正反例通过')


if __name__ == '__main__':
    c = sys.argv[1]
    if c == '--自检': selftest()
    elif c == 'plan': plan(sys.argv[2].split(','), json.loads(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5]))
    elif c == 'todo': todo(sys.argv[2], sys.argv[3])
    elif c == 'notes': notes(sys.argv[2], sys.argv[3])
    elif c == 'pack': pack(sys.argv[2], sys.argv[3])
    elif c == 'pack-one': pack(sys.argv[2],sys.argv[3],sys.argv[4])
    elif c == 'zips': zips(sys.argv[2])
    elif c == 'checkzip': checkzip(sys.argv[2], sys.argv[3])
    elif c == 'verify-digest': verify_digest(sys.argv[2], sys.argv[3])
