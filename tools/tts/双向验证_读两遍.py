"""踩坑 72 双向验证：标了读音的缩写后面紧跟另一个标了读音的词，misaki 会把后一个词读两遍。

    /opt/ttsenv/bin/python tools/tts/双向验证_读两遍.py 专八 [考研 …]     # 不写 = 全部项目（含高考）

对每个项目里所有带读音标注的句子：修正关掉（ABBR_FIX=False）时 check_double 报出的句子，必须正好是“缩写 + 下一个标注词”这种写法的句子
（至少一句，否则检查无效）；修正打开时必须 0 句。另外用两条人造句子（Mr. Smith、Co. Ltd.）证明检查本身能报出。
"""
import json
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1].parent
ALL = ['专八', '考研', '考研作文', '六级', '四级', '中考', '高考']
SRC = {'六级': '仔细阅读', '四级': '仔细阅读', '考研作文': '作文'}

CHILD = r'''
import json, re, sys
from pathlib import Path
R = Path(sys.argv[1]); proj = sys.argv[2]
sys.path[:0] = [str(R / 'tools' / 'tts')]
if proj == '高考':
    import gaokao_tts as G
    P = G.load_passages()
else:
    sys.path.insert(0, str(R / proj / 'tools'))
    if proj in ('四级', '六级'):
        sys.path.insert(1, str(R / '四级' / 'tools'))
    import make_audio as M
    G = M.G
    P = json.loads((R / proj / sys.argv[3] / 'sents.json').read_text('utf-8'))
pron = G.Pronouncer()
out = {}
for fix in (False, True):
    G.ABBR_FIX = fix
    bad = []
    for p in P:
        k = 0
        for para in p['sents']:
            for s in para:
                k += 1
                key = f"{p['id']}:{k}"
                try:
                    read = pron.read_text(s, key)
                except Exception:
                    continue
                if '](/' not in pron._mark(read, key):
                    continue
                try:
                    pron.phonemes(read, key)
                except RuntimeError as e:
                    if '读两遍' in str(e):
                        bad.append(key)
    out[str(fix)] = bad
G.ABBR_FIX = False
syn = []
for t in ['He met [Mr](/mˈɪstəɹ/). [Smith](/smˈɪθ/), a man', 'Smith [Co](/kˈO/). [Ltd](/lˈɪmɪTᵻd/), x']:
    try:
        pron.check_double(t, pron.g2p(t)[0]); syn.append(False)
    except RuntimeError:
        syn.append(True)
out['synthetic'] = syn
print('JSON' + json.dumps(out, ensure_ascii=False))
'''


def main():
    projs = sys.argv[1:] or ALL
    ok = True
    total_old = 0
    for pj in projs:
        r = subprocess.run(['/opt/ttsenv/bin/python', '-c', CHILD, str(R), pj, SRC.get(pj, '阅读')], capture_output=True, text=True)
        line = next((x for x in r.stdout.splitlines() if x.startswith('JSON')), None)
        if not line:
            print(pj, '运行出错：', r.stderr[-800:]); ok = False; continue
        d = json.loads(line[4:])
        total_old += len(d['False'])
        good = not d['True'] and all(d['synthetic'])
        ok &= good
        print(f"{'✅' if good else '❌'} {pj}：修正关掉时报 {len(d['False'])} 句 {d['False']}；修正打开时报 {len(d['True'])} 句 {d['True']}；人造句子报出 {sum(d['synthetic'])}/2")
    if total_old == 0 and not sys.argv[1:]:
        print('❌ 修正关掉时一句都没报：检查无效'); ok = False
    print('全部双向通过' if ok else '有不通过的项目')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
