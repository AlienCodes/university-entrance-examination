"""双向验证：带空位的短语前一段落到远处别的分句（踩坑 103）。
高考续写精读 x05 第 2 句 “She had prepared lots of snacks, while my job was to have the backyard in order.”
旧标注 ~have…in order（没写原文词形）：have 落到前一分句的 had；复核员查出后改成 {have…in order}。
  ① 旧标注 → 高考续写的 ann_lib.check 必须报“前一段落到了远处”；
  ② 现在的标注 → 不报；
  ③ 全部项目（专八 中考 六级 六级作文 四级 四级作文 考研 考研作文 高考续写）现有标注 → 0 处（旧的 4 处已核登记在 text_rules.SLOT_REVIEWED，只许减少）。
    /opt/ttsenv/bin/python tools/防复发/验证/短语空位远落.py"""
import glob
import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KEY = '前一段落到了远处'


def load(proj):
    t = ROOT / proj / 'tools'
    sys.path.insert(0, str(t))
    spec = importlib.util.spec_from_file_location('ann_lib_' + proj.replace('/', '_'), t / 'ann_lib.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.path.remove(str(t))
    return m


bad = []
A = load('高考续写/精读')
R = A.load_sents()
cur = (ROOT / '高考续写/精读/ann/x05.txt').read_text('utf-8')
assert '~have…in order{have…in order}=' in cur, '现在的 x05 标注变了，更新这个验证'
old = cur.replace('~have…in order{have…in order}=', '~have…in order=')
f = Path(tempfile.mkdtemp()) / 'x05.txt'
f.write_text(old, 'utf-8')
e1 = [e for e in A.check('x05', f, R)[0] if KEY in e]
print('① 旧标注：', e1 or '没报出')
if not e1:
    bad.append('① 旧标注没报出')
e2 = [e for e in A.check('x05', ROOT / '高考续写/精读/ann/x05.txt', R)[0] if KEY in e]
print('② 现在的标注：', e2 or '0 处')
if e2:
    bad.append('② 现在的标注报了')
for proj in ['专八', '中考', '六级', '六级作文', '四级', '四级作文', '考研', '考研作文', '高考续写/精读']:
    M = A if proj == '高考续写/精读' else load(proj)
    RR = M.load_sents()
    n = 0
    for a in sorted(glob.glob(str(ROOT / proj / 'ann' / '*.txt'))):
        pid = Path(a).stem
        if pid in RR:
            hits = [e for e in M.check(pid, a, RR)[0] if KEY in e]
            n += len(hits)
            for h in hits:
                print('  ', proj, pid, h[:120])
    print(f'③ {proj}：{n} 处')
    if n:
        bad.append(f'③ {proj} {n} 处')
print('全部通过' if not bad else f'未通过：{bad}')
sys.exit(1 if bad else 0)
