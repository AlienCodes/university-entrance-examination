"""踩坑 13：逐句读音修正必须对得上那一句（pron_lint.stale_sentence_fixes，专八 pron_check 调用）。
把 t20:46 的 Ms 修正挪到 t20:45（模拟切句后编号平移）必须报出；现在的修正表必须 0 处。"""
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R / 'tools' / 'tts'), str(R / '专八' / 'tools')]
import make_audio as M  # noqa: E402
import pron_lint  # noqa: E402

pron = M.G.Pronouncer()
P = json.loads((R / '专八' / 'data' / 'vocab.json').read_text('utf-8'))['passages']
items = [(f"{p['id']}:{k}", pron.read_text(s['en'], f"{p['id']}:{k}")) for p in P for k, s in enumerate([x for pa in p['paras'] for x in pa], 1)]
now = pron_lint.stale_sentence_fixes(pron, items)
pron.sentence['t20:45'] = pron.sentence.pop('t20:46')
moved = pron_lint.stale_sentence_fixes(pron, items)
ok = not now and any('t20:45' in x for x in moved)
print(f'现在：{len(now)} 处 {now[:2]}；编号平移后：{moved[:1]}')
print('逐句修正：双向通过' if ok else '逐句修正：不通过')
sys.exit(0 if ok else 1)
