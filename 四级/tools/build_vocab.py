"""把 四级/ann/ 下的标注汇总成 四级/data/vocab.json（网页、视频、听写卡的数据源），并逐篇做全部检查。

    python3 四级/tools/build_vocab.py

格式与高考 data/vocab.json 相同：passages[{id, name, title, genre, summary, done, paras:[[{en, zh, w:[{t,h,m,sp}]}]]}]。
任何一篇检查不通过（找不到高亮、空句、加了 * 前缀、中文排版问题等）都报错，不输出。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ann_lib as A  # noqa: E402

R = A.load_sents()
out, errs = [], []
for pid, r in R.items():
    rec = {k: r[k] for k in ('id', 'year', 'month', 'set', 'passage', 'paper', 'part', 'words')}
    rec['name'] = f"{r['paper']} {r['passage']}"
    f = A.ANN / f'{pid}.txt'
    if not f.exists():
        rec.update(done=False, paras=[[{'en': s, 'zh': '', 'w': []} for s in para] for para in r['sents']])
        out.append(rec)
        continue
    e, t, n = A.check(pid, f, R)
    errs += [f'{pid} {x}' for x in e + t]
    meta, ann = A.parse(str(f))
    rec.update(done=True, title=meta.get('T', ''), genre=meta.get('G', ''), summary=meta.get('S', ''))
    paras, k = [], 0
    for para in r['sents']:
        P = []
        for en in para:
            k += 1
            a = ann.get(k, {'zh': '', 'w': []})
            taken, words = [], []
            for w in sorted(a['w'], key=lambda w: -len(w['h'])):
                sp = A.find(w, en, taken)
                if sp:
                    taken += sp
                    w['sp'] = sp
            words = [{'t': w['t'], 'h': w['h'], 'm': w['m'], 'sp': w['sp']} for w in a['w'] if 'sp' in w]
            P.append({'en': en, 'zh': a['zh'], 'w': words})
        paras.append(P)
    rec['paras'] = paras
    rec['nv'] = n
    out.append(rec)
if errs:
    sys.exit('检查未通过：\n  ' + '\n  '.join(errs))
(A.ROOT / 'data').mkdir(exist_ok=True)
(A.ROOT / 'data' / 'vocab.json').write_text(json.dumps({'passages': out}, ensure_ascii=False), 'utf-8')
done = [p for p in out if p.get('done')]
print(f'{len(done)}/{len(out)} 篇已标注，词条 {sum(p["nv"] for p in done)} 个，检查全部通过')
