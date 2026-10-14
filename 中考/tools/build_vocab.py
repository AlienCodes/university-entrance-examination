"""把 中考/ann/ 下的标注汇总成 中考/data/vocab.json（网页、视频、听写卡的数据源），并逐篇做全部检查。

    python3 中考/tools/build_vocab.py            # 与复核定稿不一致会报错
    python3 中考/tools/build_vocab.py --reseal z01 z02 …   # 这些篇复核通过后登记（按篇；不列编号就登记全部已标注的篇）

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
    rec = {k: r[k] for k in ('id', 'year', 'region', 'passage', 'paper', 'part', 'words')}
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
# 复核定稿：记录每篇标注文件的指纹（中考/ann/复核通过.json）。之后任何改动都报错，必须重新复核并 --reseal。
import hashlib  # noqa: E402
seal = A.ANN / '复核通过.json'
fp = {p: hashlib.sha256((A.ANN / f'{p}.txt').read_bytes()).hexdigest()[:16] for p in R if (A.ANN / f'{p}.txt').exists()}
# 按篇登记（用户 2026-10-14：40 篇分两波做）：已登记的篇目标注一改就报错；未登记的篇目（初稿、复核中）照常输出，但 reviewed=False，
# make_video.py 不给未通过复核的篇目生成视频。
old = json.loads(seal.read_text('utf-8'))['指纹'] if seal.exists() else {}
if '--reseal' in sys.argv:
    import re  # noqa: E402
    ids = [a for a in sys.argv[sys.argv.index('--reseal') + 1:] if re.fullmatch(r'z\d\d', a)]
    missing = [i for i in ids if i not in fp]
    if missing:
        sys.exit(f'没有标注文件，不能登记：{missing}')
    old.update({k: fp[k] for k in (ids or fp)})
    seal.write_text(json.dumps({'说明': '中考阅读翻译与标注经多轮多人复核（埋雷全部查出）后的定稿指纹（按篇登记）；改动后须重新复核再 --reseal 编号…。', '指纹': old},
                               ensure_ascii=False, indent=1), 'utf-8')
    print(f'登记 {len(ids or fp)} 篇，已复核共 {len(old)} 篇')
else:
    diff = sorted(k for k in old if old[k] != fp.get(k))
    if diff:
        sys.exit(f'以下标注文件与复核定稿不一致（改动未经复核）：{diff}；复核后用 --reseal 编号… 重新登记。')
for rec in out:
    rec['reviewed'] = rec['id'] in old and old[rec['id']] == fp.get(rec['id'])
(A.ROOT / 'data').mkdir(exist_ok=True)
(A.ROOT / 'data' / 'vocab.json').write_text(json.dumps({'passages': out}, ensure_ascii=False), 'utf-8')
done = [p for p in out if p.get('done')]
print(f'{len(done)}/{len(out)} 篇已标注（复核通过 {sum(p["reviewed"] for p in out)} 篇），词条 {sum(p["nv"] for p in done)} 个，检查全部通过')
