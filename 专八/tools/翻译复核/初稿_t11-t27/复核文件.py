"""从标注草稿目录（不是 专八/ann/）生成复核文件，格式与 专八/tools/gen_review.py 完全相同（同一段代码），不动 vocab.json：
t01—t10 正在 GitHub 上按 vocab.json 生成视频（manifest 要求恰好 10 篇已标注），t11—t27 复核定稿后再并入 专八/ann/。
    python review_files.py <标注草稿目录> <输出目录> t11 t12 …"""
import json, sys
from pathlib import Path
R0 = Path('/home/user/university-entrance-examination/专八/tools')
sys.path.insert(0, str(R0))
import ann_lib as A
src, out, ids = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
out.mkdir(parents=True, exist_ok=True)
R = A.load_sents()
TIER = {'core': '单词', 'ext': '单词', 'phr': '短语'}
bad = []
for pid in ids:
    f = src / f'{pid}.txt'
    e, t, n = A.check(pid, f, R)
    if e or t:
        bad.append((pid, e + t)); continue
    meta, ann = A.parse(str(f))
    r = R[pid]
    L = [f"# {pid} 英语专业八级 {r['paper']} {r['passage']}", f"标题: {meta.get('T', '')}", f"体裁: {meta.get('G', '')}", f"概要: {meta.get('S', '')}", '']
    k = 0
    for para in r['sents']:
        for en in para:
            k += 1
            a = ann.get(k, {'zh': '', 'w': []})
            taken = []
            for w in sorted(a['w'], key=lambda w: -len(w['h'])):      # 与 build_vocab.py 相同：长的先找位置，输出按标注文件里的顺序
                sp = A.find(w, en, taken)
                if sp:
                    taken += sp
                    w['sp'] = sp
            L.append(f"[{k}] EN: {en}")
            L.append(f"    ZH: {a['zh']}")
            for w in [w for w in a['w'] if 'sp' in w]:
                surf = ' … '.join(en[a_:b] for a_, b in w['sp'])
                L.append(f"    - {w['h']}  ({TIER[w['t']]})  {w['m']}   ← 高亮原文: \"{surf}\"")
        L.append('')
    (out / f'{pid}.txt').write_text('\n'.join(L), 'utf-8')
print('written', len(ids) - len(bad), 'bad', bad)
