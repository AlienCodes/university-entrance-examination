"""诊断呼吸声报错：照常合成，final_check 前把 MP3 和每句时刻存到指定目录（不写仓库），用法：/opt/ttsenv/bin/python 高考续写/精读/tools/呼吸定位.py <输出目录> x21 x27"""
import sys, json, runpy, pickle
from pathlib import Path
S = Path(sys.argv[1]); ids = sys.argv[2:]
sys.argv = ['make_audio.py']
ns = runpy.run_path('高考续写/精读/tools/make_audio.py', run_name='lib')
G = ns['G']
orig = G.final_check
cur = {}
def fc(mp3, items, lufs, span=None):
    (S / f'{cur["id"]}.mp3').write_bytes(mp3)
    (S / f'{cur["id"]}_items.pkl').write_bytes(pickle.dumps(items))
    return orig(mp3, items, lufs, span)
G.final_check = fc
vcfg = json.loads((G.HERE / 'voices.json').read_text('utf-8'))[ns['VOICE']]
P = {p['id']: p for p in json.loads(Path('高考续写/精读/阅读/sents.json').read_text('utf-8'))}
engine, pron = G.Engine(), G.Pronouncer()
for pid in ids:
    cur['id'] = pid
    try:
        G.render_passage(P[pid], ns['VOICE'], vcfg, engine, pron, S / 'out')
        print(pid, '通过')
    except RuntimeError as e:
        print(pid, '未通过：', str(e)[:500])
