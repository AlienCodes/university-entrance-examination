"""电磁音排查：同样两句话，只改一个因素，请用户逐个听，指出哪些有电磁音。"""
import sys, json, subprocess
from pathlib import Path
import numpy as np, soundfile as sf
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'tools'))
import make_audio as A
G = A.G
eng, pron = G.Engine(), G.Pronouncer()
T = "There have been many changes in the engineering field, and women have played a bigger part in them. However, they still face many challenges at work."
ph = pron.phonemes(T, None)
def save(name, x, sr):
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.5
    w = HERE / 'tmp.wav'; sf.write(str(w), x, sr)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(w), '-ar', '48000', '-b:a', '256k', str(HERE / f'{name}.mp3')], check=True)
    w.unlink()
clips = [
    ('2_同一男声_原始合成_不做任何后期处理', {"am_fenrir": 0.6, "am_onyx": 0.4}),
    ('3_男声onyx单独_原始', 'am_onyx'),
    ('4_男声fenrir单独_原始', 'am_fenrir'),
    ('5_男声michael_原始', 'am_michael'),
    ('6_男声puck_原始', 'am_puck'),
    ('7_英式男声george_原始', 'bm_george'),
    ('8_高考用的女声_原始', json.loads((G.HERE / 'voices.json').read_text('utf-8'))['female']['style']),
]
for name, st in clips:
    save(name, eng.synth(ph, eng.style(st), 0.95), G.SR)
# 1：现在成品的处理链（男声 + 统一电平 + 压缩 + 慢速电平 + 去电磁音 + 响度 + 限幅）
vcfg = json.loads((G.HERE / 'voices.json').read_text('utf-8'))[A.VOICE]
a, _ = A.synth_sentence(pron.read_text(T, None), None, eng, pron, eng.style(vcfg['style']), vcfg['speed'], vcfg)
import soxr
a48 = soxr.resample(a, G.SR, G.OUT_SR, quality='VHQ').astype(np.float32)
a48 = G.compress(a48, G.OUT_SR)
save('1_现在成品的处理方式', a48, G.OUT_SR)
