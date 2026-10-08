"""逗号停顿规则对比样音：每句先放旧规则（每个逗号都切开合成、插入 0.28 秒静音），再放新规则（不该停的逗号一口气读）。"""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'tools'))
import make_audio as A
G = A.G
import json
vcfg = json.loads((G.HERE / 'voices.json').read_text('utf-8'))[A.VOICE]
engine, pron = G.Engine(), G.Pronouncer()
style, speed = engine.style(vcfg['style']), vcfg.get('speed', 1.0)
S = [("I like it, too.", None),
     ("Students no longer spend summers farming, but they aren't in school, either.", None),
     ("Recent open debates on scientific research, health, and policy have aroused greater public attention.", None),
     ("Shopping for food involved mud, noisy chickens, clouds of flies, nasty smells, bargaining, and getting short-changed.", None),
     ("They all seem to stick to the ethos of regional, seasonal produce.", None)]
real = A.pause_free
out = []
for text, key in S:
    read = pron.read_text(text, key)
    for name, f in (('旧', lambda r, p, o='': [(False, '')] * len(p)), ('新', real)):
        A.pause_free = f
        a, parts = A.synth_sentence(read, key, engine, pron, style, speed, vcfg)
        print(name, len(parts), '段', text)
        out += [a, np.zeros(int(0.9 * G.SR), np.float32)]
    out.append(np.zeros(int(0.8 * G.SR), np.float32))
A.pause_free = real
x = np.concatenate(out)
x = x / np.max(np.abs(x)) * 0.7
import soundfile as sf
sf.write(str(HERE / '逗号停顿对比.wav'), x, G.SR)
