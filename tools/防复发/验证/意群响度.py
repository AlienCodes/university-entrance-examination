"""双向验证：意群级响度检查（踩坑 85，用户 2026-10-29“偶尔一个地方声音突然就小了一点”）。
用新处理链（clause-v1）真实生成的考研 k48 前 4 句（样本/意群响度_k48新链.flac），测仓库里真正在用的 verify_loudness：
  ① 修好的音频 → 0 处；
  ② 把一个与相邻持平的意群压低 2 dB、1.5 dB → 必须报出（“比相邻意群低 1.5 dB 以上”）；
  ③ 把一个意群最后 0.8 秒压低 5 dB（末尾的词被收小）→ 必须报出；
  ④ 原来四项（整体、句间、短时、峰值）的测量值与开关意群检查无关，逐项相同；
  ⑤ 如实列出：每个 ≥ 0.8 秒的意群各压低 2 dB / 1.5 dB 时的检出率（天然比邻居响的意群压低后仍不比邻居小，不算漏）。
GitHub 每次推送都跑（needs: pip）。
    python3 tools/防复发/验证/意群响度.py"""
import io
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'tts'))
import gaokao_tts as G  # noqa: E402
import 响度细查 as RX  # noqa: E402

a, sr = sf.read(str(HERE / '样本' / '意群响度_k48新链.flac'), dtype='float64')
items = json.loads((HERE / '样本' / '意群响度_k48新链.json').read_text('utf-8'))['sentences']
bad = []


def run(x, fine=True):
    buf = io.BytesIO()
    sf.write(buf, x.astype(np.float32), sr, format='WAV', subtype='FLOAT')
    return G.verify_loudness(buf.getvalue(), items, -16.0, fine=fine)


def dip(x, s, e, db):
    y = x.copy()
    y[int(s * sr):int(e * sr)] *= 10 ** (-db / 20)
    return y


def case(name, errs, want):
    ok = (not errs) if want is None else any(want in e for e in errs)
    print(f"  {'✅' if ok else '❌'} {name}：{errs or '0 处'}")
    if not ok:
        bad.append(name)


rep, errs = run(a)
case('修好的音频（新处理链）→ 0', errs, None)
print(f"     意群相邻最差 {rep['clause_nb_min_lu']} LU，末尾最差 {rep['clause_tail_min_db']} dB")

st = [r for r in RX.clause_stats(RX.clause_loudness(a, sr, items)) if r['dur'] >= RX.NB_MIN_DUR]
flat = min(st, key=lambda r: abs(r['d_nb']))                  # 与相邻持平的意群
for db in (2.0, 1.5):
    case(f"第{flat['k']}句第{flat['j'] + 1}段（与相邻差 {flat['d_nb']:+.2f}）压低 {db} dB → 报出",
         run(dip(a, flat['start'], flat['end'], db))[1], '比相邻意群小')
long_ = max(st, key=lambda r: r['dur'])
case(f"第{long_['k']}句第{long_['j'] + 1}段最后 0.8 秒压低 5 dB → 报出",
     run(dip(a, long_['end'] - RX.TAIL_LEN, long_['end'], 5.0))[1], '末尾')

r0, e0 = run(a, fine=False)
four = ('integrated_lufs', 'sentence_max_dev_lu', 'short_term_std_lu', 'peak_dbfs')
same = all(r0[k] == rep[k] for k in four) and e0 == [e for e in errs if not e.startswith('意群响度')]
case('原来四项的测量值不变（开 / 关意群检查逐项相同）', [] if same else [f'{r0} vs {rep}'], None)

for db in (2.0, 1.5):
    hit = [r for r in st if any('比相邻意群小' in e for e in run(dip(a, r['start'], r['end'], db))[1])]
    expect = [r for r in st if r['d_nb'] - db < -RX.FINE_LIMITS['clause_nb'] - 0.2]     # 压低后明显比邻居小的
    miss = [f"第{r['k']}句第{r['j'] + 1}段" for r in expect if r not in hit]
    print(f"     每个意群各压低 {db} dB：检出 {len(hit)}/{len(st)}（压低后比邻居小 1.4 LU 以上的 {len(expect)} 个必须全部检出）")
    case(f'压低 {db} dB、明显比邻居小的意群全部检出', miss, None)

# 合格证：没有合格证 / 不是当前处理链 / MP3 被改过 → verify_videos 与视频引擎拒绝；2026-10-29 前的旧成品放行
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    mp3 = Path(td) / 'x.mp3'
    data = G.encode_mp3(a.astype(np.float32))
    mp3.write_bytes(data)
    rep = dict(rep, breath_count=G.breath_core(data)[0])      # 铁律 22：合格证带呼吸检查（final_check 写的）
    cert = G.certificate(data, rep)
    (Path(td) / 'x.loudness.json').write_text(json.dumps(cert), 'utf-8')
    tm = {'file': 'cet4_male/x.mp3', 'duration': 1.0, 'loudness': rep, 'clause_check': G.CHAIN, 'certificate': cert}
    case('新音频带合格证 → 放行', G.certificate_problems(tm, mp3), None)
    case('新音频没有合格证（旧处理链）→ 拒绝', G.certificate_problems({k: v for k, v in tm.items() if k not in ('clause_check', 'certificate')}, mp3), '不是当前处理链')
    mp3.write_bytes(data[:-100] + bytes(100))
    case('MP3 在检查之后被改过 → 拒绝', G.certificate_problems(tm, mp3), '被改过')
old = json.loads((HERE.parents[2] / '考研' / 'audio' / 'timings.json').read_text('utf-8'))['cet4_male']['k48']
case('已发布的旧成品（k48）→ 放行（不追溯）', G.certificate_problems(old), None)
yuan = json.loads((HERE.parents[2] / '专八' / '听力' / '原文' / 'audio' / 'timings.json').read_text('utf-8'))['cet4_male']
case('专八听力考试原声（不是 TTS）→ 放行', [e for v in yuan.values() for e in G.certificate_problems(v)], None)

if bad:
    sys.exit(f'意群响度双向验证失效：{bad}')
print('意群响度双向验证：全部通过')
