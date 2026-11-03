"""读后续写配音“声音太尖太细”→ 浑厚（用户 2026-11-03：“能不能让我的声音更加浑厚一些？稍微调节一下就行……非常接近我原来的声色”）。

不重新合成：输入 = 选段记录（选段.py 写的 <成品>.选段.json）+ 原始合成小段（分支 gram-tts-out 的 runs/…，按 覆盖.txt 还原）；
处理放在原始合成段上：去呼吸 → 去首尾静音 →【降音高（保共振峰）→ 音色还原（可选）】→ 陷波 → 段内电平 / 母带 / 合格证（讲解音频.render 原样，全部检查照跑）。
处理是 讲解音频.prep 的正式参数 PITCH_SEMIS / PITCH_METHOD / TIMBRE_EQ；另加一项检查：成品浊音基频中位数与目标差 ≤ 1 半音（pitch_check，与处理不同的量法：librosa.pyin）。

用法：
  /opt/ttsenv/bin/python 高考续写/tools/声音浑厚.py --稿 稿.json --选段 X.选段.json --覆盖 X.覆盖.txt --out 成品.mp3 \
      [--只 t01 t02 …] [--降 2.9] [--方法 rubberband|world] [--音色还原 eq.json] [--目标 128.0] [--拆分 mark] [--停顿上限 0.45]
  --降 0 且不给 --音色还原 = 原样（样音 A）。
"""
import argparse
import json
import re
import subprocess
import tempfile
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '高考语法填空/tools'), str(ROOT / 'tools/tts')]
import 讲解音频 as J  # noqa: E402

SR = J.SR
PITCH_TOL = 1.0           # 半音
BR_REF = 'origin/gram-tts-out'


def f0_median(a, sr):
    import librosa
    import soxr
    x = soxr.resample(a, sr, 24000).astype(np.float32) if sr != 24000 else a
    fs = []
    for i in range(0, len(x), 24000 * 20):
        f0, v, _ = librosa.pyin(x[i:i + 24000 * 20], fmin=65, fmax=400, sr=24000, frame_length=1024)
        fs.append(f0[v & ~np.isnan(f0)])
    return float(np.median(np.concatenate(fs)))


def pitch_check(a, sr, target_hz, tol=PITCH_TOL):
    """成品浊音基频中位数与目标差 ≤ tol 半音；返回 (中位数 Hz, 差几个半音, 问题列表)。"""
    m = f0_median(a, sr)
    d = 12 * np.log2(m / target_hz)
    return m, round(float(d), 2), ([] if abs(d) <= tol else [f'浊音基频中位数 {m:.1f} Hz，比目标 {target_hz:.1f} Hz 差 {d:+.2f} 半音（> {tol}）'])


def resolve(sel, cover_txt, run_rel):
    """选段记录里每个小段用的那次 → gram-tts-out 上的原始 WAV 路径（覆盖.txt 的补合成、锁定照还原）。"""
    over, lock = {}, {}
    for line in (cover_txt.splitlines() if cover_txt else []):
        m = re.match(r'(take\d+)/(\S+)\.wav ← (runs/\S+)', line)
        if m:
            over[(m[1], m[2])] = m[3]
        m = re.match(r'锁定 (\S+) = (take\d+)', line)
        if m:
            lock[m[1]] = m[2]
    out = {}
    voice = Path(sel['run']).name
    for u, c in sel['chosen'].items():
        take = lock.get(u, c['take'])
        run = over.get((take, u), run_rel)
        out[u] = f'{run}/{voice}/{take}/{u}.wav'
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--稿', required=True)
    ap.add_argument('--选段', required=True)
    ap.add_argument('--覆盖')
    ap.add_argument('--out', required=True)
    ap.add_argument('--只', nargs='*')
    ap.add_argument('--降', type=float, default=0.0, help='降几个半音（保共振峰）')
    ap.add_argument('--方法', default='rubberband', choices=['rubberband', 'world'])
    ap.add_argument('--音色还原', help='JSON：[[f_lo, f_hi, dB], …]')
    ap.add_argument('--目标', type=float, help='目标浊音基频中位数（Hz）；给了就检查 ≤ 1 半音')
    ap.add_argument('--拆分', default='mark')
    ap.add_argument('--停顿上限', type=float, default=0.45)
    ap.add_argument('--lead', type=float, default=1.5)
    ap.add_argument('--tail', type=float, default=2.0)
    a = ap.parse_args()
    J.SPLIT, J.GAP_MAX = a.拆分, a.停顿上限
    eq = json.loads(Path(a.音色还原).read_text('utf-8')) if a.音色还原 else None
    J.PITCH_SEMIS, J.PITCH_METHOD, J.TIMBRE_EQ = a.降, a.方法, eq   # 讲解音频.prep 里正式的可开关步（去呼吸之后、陷波与电平处理之前）
    segs = json.loads(Path(a.稿).read_text('utf-8'))['segments']
    if a.只:
        segs = [s for s in segs if s['id'] in a.只]
    sel = json.loads(Path(a.选段).read_text('utf-8'))
    run_rel = 'runs/' + Path(sel['run']).parent.name
    src = resolve(sel, Path(a.覆盖).read_text('utf-8') if a.覆盖 else '', run_rel)
    tmp = Path(tempfile.mkdtemp(prefix='hh_'))
    for u in J.expand(segs):
        p = src[u['id']]
        (tmp / f"{u['id']}.wav").write_bytes(subprocess.run(['git', '-C', str(ROOT), 'show', f'{BR_REF}:{p}'], check=True, capture_output=True).stdout)
    meta = J.render(segs, tmp, a.out, a.lead, a.tail)
    import soundfile as sf
    y, s = sf.read(a.out, dtype='float32')
    y = y.mean(1) if y.ndim > 1 else y
    rec = {'降半音': a.降, '方法': a.方法 if a.降 else None, '音色还原': eq, '来源': src}
    if a.目标:
        m, d, err = pitch_check(y[int(a.lead * s):len(y) - int(a.tail * s)], s, a.目标)
        rec.update(f0_median_hz=round(m, 1), target_hz=a.目标, diff_semitones=d)
        if err:
            Path(a.out).unlink()
            raise SystemExit('音高：' + '；'.join(err) + '，未输出')
    else:
        rec['f0_median_hz'] = round(f0_median(y[int(a.lead * s):len(y) - int(a.tail * s)], s), 1)
    Path(a.out).with_suffix('.浑厚.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1), 'utf-8')
    c = meta['certificate']['loudness']
    print(f"{a.out}：{meta['duration']:.1f}s；f0 中位数 {rec['f0_median_hz']} Hz；整体 {c['integrated_lufs']} LUFS，峰值 {c['peak_dbfs']}，"
          f"意群 {c.get('clause_nb_min_lu')} / 段尾 {c.get('clause_tail_min_db')}，呼吸 {c.get('breath_count')}")


if __name__ == '__main__':
    main()
