"""双向验证：短语高亮包进主语（踩坑 111）。
高考续写精读 x20：~be worried about{I’m worried about}、~be attached to{She’s that attached to}，画面上主语 I / She 也涂成短语色；
1be75a8 改成 {worried about}、{that attached to}。
  ① 旧 x20 标注（git show 1be75a8^:高考续写/精读/ann/x20.txt）→ 高考续写的 ann_lib.check 必须报 2 处“把主语也包进去了”；
  ② 现在的 x20 → 0 处；
  ③ 9 个项目现有标注 → 0 处（旧的 4 处已核登记在 text_rules.SUBJ_REVIEWED，只许减少；整句固定说法在 SUBJ_FIXED）；
  ⓪ 9 个项目的 ann_lib 都调用 subject_phrase_problem；
  ④ 把登记清空，必须恰好报出这 4 处（登记不是摆设）；把 SUBJ_FIXED 清空，x11 It’s over 必须报出。
    python3 tools/防复发/验证/短语包主语.py"""
import glob
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import text_rules  # noqa: E402

KEY = '把主语也包进去了'
PROJS = ['专八', '中考', '六级', '六级作文', '四级', '四级作文', '考研', '考研作文', '高考续写/精读']


def load(proj):
    t = ROOT / proj / 'tools'
    sys.path.insert(0, str(t))
    spec = importlib.util.spec_from_file_location('ann_lib_' + proj.replace('/', '_'), t / 'ann_lib.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.path.remove(str(t))
    return m


def scan(mods):
    out = []
    for proj, M, RR in mods:
        for a in sorted(glob.glob(str(ROOT / proj / 'ann' / '*.txt'))):
            pid = Path(a).stem
            if pid in RR:
                out += [(proj, pid, e) for e in M.check(pid, a, RR)[0] if KEY in e]
    return out


bad = []
for proj in PROJS:                                   # 每个项目的 ann_lib.check 都接上了
    src = (ROOT / proj / 'tools' / 'ann_lib.py').read_text('utf-8')
    if 'subject_phrase_problem as _subj_phr' not in src or '_subj_phr(e, en, sp)' not in src:
        bad.append(f'{proj} 的 ann_lib.check 没接 subject_phrase_problem')
mods = [(p, load(p), None) for p in PROJS]
mods = [(p, M, M.load_sents()) for p, M, _ in mods]
A, R = mods[-1][1], mods[-1][2]
old = subprocess.run(['git', '-C', str(ROOT), 'show', '1be75a8^:高考续写/精读/ann/x20.txt'],
                     capture_output=True, check=True).stdout.decode('utf-8')
f = Path(tempfile.mkdtemp()) / 'x20.txt'
f.write_text(old, 'utf-8')
e1 = [e for e in A.check('x20', f, R)[0] if KEY in e]
print(f'① 旧 x20：{len(e1)} 处')
for e in e1:
    print('   ', e[:80])
if len(e1) != 2:
    bad.append(f'① 旧 x20 报 {len(e1)} 处（应 2）')
e2 = [e for e in A.check('x20', ROOT / '高考续写/精读/ann/x20.txt', R)[0] if KEY in e]
print('② 现在的 x20：', len(e2), '处')
if e2:
    bad.append('② 现在的 x20 报了')
hits = scan(mods)
for h in hits:
    print('  ', *h)
print('③ 9 个项目：', len(hits), '处')
if hits:
    bad.append(f'③ {len(hits)} 处')
saved = set(text_rules.SUBJ_REVIEWED)
text_rules.SUBJ_REVIEWED.clear()
h4 = scan(mods)
text_rules.SUBJ_REVIEWED.update(saved)
print(f'④ 登记清空：{len(h4)} 处（应 = {len(saved)}）')
for p, i, e in h4:
    print('   ', p, i, e[:70])
if len(h4) != len(saved):
    bad.append(f'④ 登记清空报 {len(h4)} 处 ≠ 登记 {len(saved)}')
fx = set(text_rules.SUBJ_FIXED)
text_rules.SUBJ_FIXED.clear()
h5 = [h for h in scan(mods[-1:]) if h[1] == 'x11']
text_rules.SUBJ_FIXED.update(fx)
print('④ 固定说法清空：x11', len(h5), '处')
if not h5:
    bad.append('④ 固定说法清空，x11 It’s over 没报')
print('全部通过' if not bad else f'未通过：{bad}')
sys.exit(1 if bad else 0)
