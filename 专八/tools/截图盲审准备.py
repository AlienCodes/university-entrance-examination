"""专八水墨截图盲审：按批复制截图（WebP → JPG）到审阅副本，每批在一篇里埋 5 个排版雷（canary_layout.py，与考研同一做法）。
    DZB_VARIANT=水墨 python 专八/tools/截图盲审准备.py <审阅副本目录> b01=t01,t02,t03@t02 b02=…   → 打印 args JSON（mines 只用于计分）"""
import json, re, shutil, subprocess, sys, os
from pathlib import Path
from PIL import Image
R = Path('/home/user/university-entrance-examination')
SRC = R / '专八/大字版水墨/截图'
# 铁律 17（用户 2026-10-23）：整屏盲审一晚上能用掉一周一半的 token，淘汰。审阅只看 新情况检测.py 挑出的屏（每次 ≤ 40 屏），超过就拒绝
CAP = 40
if '--破例' not in sys.argv:
    want = sum(len(list((SRC / pid).glob('screen*.*'))) for spec in sys.argv[2:] if '=' in spec for pid in spec.split('=')[1].split('@')[0].split(','))
    if want > CAP:
        sys.exit(f'要审 {want} 屏，超过上限 {CAP}（铁律 17：不许整屏盲审；先跑 新情况检测.py，只审它挑出的屏）')
sys.argv = [x for x in sys.argv if x != '--破例']
out = Path(sys.argv[1]); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
mine_dir = out.parent / (out.name + '_mine'); shutil.rmtree(mine_dir, ignore_errors=True); (mine_dir / 'ref').mkdir(parents=True)
batches = []
for spec in sys.argv[2:]:
    b, rest = spec.split('='); ps, host = rest.split('@'); ps = ps.split(',')
    shutil.copytree(SRC / host, mine_dir / host); shutil.copy(SRC / 'ref' / f'{host}.txt', mine_dir / 'ref' / f'{host}.txt')
    r = subprocess.run([sys.executable, str(R / '中考/tools/画面核查/canary_layout.py'), '--project', '专八', '--style', 'C', str(mine_dir), host, host + 'm'],
                       capture_output=True, text=True, env=dict(os.environ, DZB_VARIANT='水墨'))
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    mines = [{'pid': host, 'screen': m.group(1), 'what': m.group(2)} for m in re.finditer(r'^(screen\d\d) (?:第 \d+ 句|片头|原题屏) (.+?)\s*（变化', r.stdout, re.M)]
    assert len(mines) == 5, r.stdout
    for pid in ps:
        src = mine_dir / (host + 'm') if pid == host else SRC / pid
        d = out / b / pid; d.mkdir(parents=True)
        for f in sorted(src.glob('screen*.*')):
            Image.open(f).convert('RGB').save(d / (f.stem + '.jpg'), quality=92)
        (out / b / 'ref').mkdir(exist_ok=True)
        shutil.copy(SRC / 'ref' / f'{pid}.txt', out / b / 'ref' / f'{pid}.txt')
        n_src = len(list((SRC / pid).glob('screen*.*'))); n = len(list(d.glob('*.jpg')))
        assert n == n_src, (pid, n, n_src)
    batches.append({'batch': b, 'passages': ps, 'mines': mines})
    print(b, ps, '雷：', host, [m['screen'] for m in mines], file=sys.stderr)
print(json.dumps({'dir': str(out), 'batches': batches}, ensure_ascii=False))
