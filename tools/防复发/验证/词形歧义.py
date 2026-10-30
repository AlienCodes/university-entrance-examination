"""踩坑 72（toiled 被当成 toile 读成 twald）：tools/tts/pron_lint.ambiguous_inflections 的双向验证。
去掉 toiled 的读音修正必须报出 toiled；加上修正（现在的词典）必须不报 toiled。"""
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R / 'tools' / 'tts'), str(R / '专八' / 'tools')]
import make_audio as M  # noqa: E402
import pron_lint  # noqa: E402

pron = M.G.Pronouncer()
P = {p['id']: p for p in json.loads((R / '专八' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
items = [(f't25:{k}', pron.read_text(s['en'], f't25:{k}')) for k, s in enumerate([x for pa in P['t25']['paras'] for x in pa], 1)]
now = pron_lint.ambiguous_inflections(pron, items)
pron.lexicon.pop('toiled', None)
old = pron_lint.ambiguous_inflections(pron, items)
ok = 'toiled' in old and 'toiled' not in now
print(f"去掉修正：{'报出' if 'toiled' in old else '没报'} toiled（{old.get('toiled', {}).get('音标')}）；现在：{'不报' if 'toiled' not in now else '仍报'}")
print('词形歧义：双向通过' if ok else '词形歧义：不通过')
sys.exit(0 if ok else 1)
