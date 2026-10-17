"""去电磁音样片：c40 按完整处理链重新合成，只在压缩之前多一步 debuzz（9 个固定频点、60 Hz 带宽、单向滤波）。
输出到临时目录，不动正式音频。用法：python 去电磁音样片.py 输出目录"""
import sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'tools'))
import make_audio as A
import debuzz as D
G = A.G
out_root = Path(sys.argv[1]); out_root.mkdir(parents=True, exist_ok=True)
G.compress = lambda x, sr: A.leveler(A._comp(D.debuzz(x, sr), sr), sr)
vcfg = json.loads((G.HERE / 'voices.json').read_text('utf-8'))[A.VOICE]
P = {p['id']: p for p in json.loads((A.C4 / '仔细阅读' / 'sents.json').read_text('utf-8'))}
engine, pron = G.Engine(), G.Pronouncer()
r = G.render_passage(P['c40'], A.VOICE, vcfg, engine, pron, out_root / A.VOICE)
r.update(name=f"{P['c40']['paper']} {P['c40']['passage']}")
(out_root / 'timings.json').write_text(json.dumps({A.VOICE: {'c40': r}}, ensure_ascii=False, indent=1), 'utf-8')
print('audio ok', r['file'], r['loudness'])
