"""Extract one 1920px frame per distinct screen from a TEM-8 video (keyframes only, consecutive duplicates removed).
python extract.py <mp4> <outdir>  -> prints number of screens"""
import subprocess, sys, tempfile, shutil
from pathlib import Path
import numpy as np
from PIL import Image
mp4, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
for f in out.glob('*.png'):
    f.unlink()
with tempfile.TemporaryDirectory() as td:
    subprocess.run(['nice', '-n', '10', 'ffmpeg', '-v', 'error', '-skip_frame', 'nokey', '-i', mp4, '-vf', 'scale=1920:-1',
                    '-fps_mode', 'passthrough', f'{td}/k%04d.png'], check=True)
    prev, n = None, 0
    for f in sorted(Path(td).glob('k*.png')):
        a = np.asarray(Image.open(f).convert('L'), dtype=np.int16)
        if prev is not None and np.abs(a - prev).mean() < 0.5:
            continue
        prev = a
        n += 1
        shutil.copy(f, out / f'screen{n:02d}.png')
print(n)
