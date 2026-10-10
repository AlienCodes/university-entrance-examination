import sys, numpy as np
from pathlib import Path
sys.path.insert(0, 'tools/tts')
import gaokao_tts as G
TEXT = ("Our society places a high value on physical beauty. Americans spend an average of over $722 each year on their appearance. "
        "There’s nothing wrong with trying to look our best, but excessive focus on physical appearance misses the soulful aspects of what it means to be beautiful.")
V = {
 'A_michael': {'am_michael': 1},
 'B_fenrir': {'am_fenrir': 1},
 'C_puck': {'am_puck': 1},
 'D_onyx': {'am_onyx': 1},
 'E_echo': {'am_echo': 1},
 'F_eric': {'am_eric': 1},
 'G_liam': {'am_liam': 1},
 'H_adam': {'am_adam': 1},
 'I_michael+onyx': {'am_michael': 0.6, 'am_onyx': 0.4},
 'J_michael+fenrir': {'am_michael': 0.5, 'am_fenrir': 0.5},
 'K_fenrir+onyx': {'am_fenrir': 0.6, 'am_onyx': 0.4},
 'L_george_英音': {'bm_george': 1},
 'M_fable_英音': {'bm_fable': 1},
 'N_lewis_英音': {'bm_lewis': 1},
}
import json
cfg = json.loads(Path('tools/tts/voices.json').read_text('utf-8'))['male']
eng, pron = G.Engine(), G.Pronouncer()
sents = __import__('re').split(r'(?<=[.!?])\s+', TEXT)
for name, spec in V.items():
    st = eng.style(spec)
    pcs = [np.zeros(int(0.4 * G.SR), np.float32)]
    for s in sents:
        pcs.append(G.synth_sentence(pron.read_text(s), None, eng, pron, st, 0.95, cfg)[0])
        pcs.append(np.zeros(int(0.8 * G.SR), np.float32))
    a = G.master(np.concatenate(pcs), -16.0)
    G.write_mp3(Path(f'四级/音色试听/{name}.mp3'), a)
    print(name, flush=True)
