"""六级原音 → 视频用的音轨：整体增益到 −16 LUFS + 前瞻限幅（只压超过 −1.5 dBFS 的尖峰），其余一个样本不动。
为什么不是专八练习视频的“只整体增益”：六级原音普遍约 −20 LUFS、峰值接近 0 dBFS，30 套里 29 套只做整体增益到 −16 时峰值会到 +1—+6 dBFS（2026-11-04 实测）。
做法与专八听力原文精读（专八/听力/原文/tools/原音音轨.py 的 limit，直接导入，规则只写一处）相同：增益 → 限幅 → 补增益 → 限幅。
关卡：原音 sha256 必须在 六级/听力/原始材料/SHA256SUMS 里（协调会话审 5：豁免合格证只认这张表）；限幅最多压低 > 8 dB 或被压时长 > 0.5% 就停（说明原音有问题，要人听）。
用法：python 原音电平.py 原音.mp3 输出.wav [截到秒]      旁边写 输出.wav.json（原音 sha256、整体响度、峰值、限幅统计）
"""
import hashlib, importlib.util, json, sys
from pathlib import Path
import numpy as np, pyloudnorm as pl, soundfile as sf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('yuanyin', ROOT / '专八/听力/原文/tools/原音音轨.py')
yy = importlib.util.module_from_spec(spec); spec.loader.exec_module(yy)

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
sha = hashlib.sha256(src.read_bytes()).hexdigest()
ok = {l.split()[0] for l in (HERE.parent / '原始材料/SHA256SUMS').read_text().splitlines() if l.strip()}
if sha not in ok: sys.exit(f'停止：{src.name} 的 sha256 不在 原始材料/SHA256SUMS 里（只认老师的原音）')
a, sr = sf.read(src, dtype='float64', always_2d=True)
if len(sys.argv) > 3: a = a[:round(float(sys.argv[3]) * sr)]
m = pl.Meter(sr)
L0 = m.integrated_loudness(a)
y, gr = yy.limit(a * 10 ** ((-16 - L0) / 20), sr)
y, gr2 = yy.limit(y * 10 ** ((-16 - m.integrated_loudness(y)) / 20), sr)
L, pk = m.integrated_loudness(y), 20 * np.log10(np.abs(y).max())
rep = {'原音': src.name, '原音sha256': sha, '原音响度LUFS': round(L0, 2), '整体响度LUFS': round(L, 2), '峰值dBFS': round(pk, 2),
       '限幅最多压低dB': max(gr['max_db'], gr2['max_db']), '被压时长比例': gr['frac']}
if abs(L + 16) > 0.3 or pk > -1.0 or rep['限幅最多压低dB'] > 8 or gr['frac'] > 0.005: sys.exit(f'停止：{rep}')
sf.write(dst, y, sr, subtype='PCM_24')
Path(str(dst) + '.json').write_text(json.dumps(rep, ensure_ascii=False), 'utf-8')
print(rep)
