"""双向验证（踩坑 87 ⑤⑥）：写音频文件前的最后一道检查关不掉。
  ⑤ 项目包一层 verify_loudness（各 make_audio.py 加电磁音检查就是这样包的），包的时候把 fine 关掉，以前 render_passage
     照样写出 MP3 和 passed=True 的合格证。现在 render_passage 用 final_check：项目那一层 + 模块加载时存下的原始检查（fine=True）。
  ⑥ gaokao_tts.py say 以前直接写 MP3 / WAV，不检查、不写合格证。现在走 save_checked：不合格不写文件，合格写合格证。
用新处理链真实生成的 k48 前 4 句（样本/意群响度_k48新链.flac）当“合成结果”喂给真的 render_passage（引擎、读音换成桩，
master、编码、检查、合格证都是真的），LOUDNESS_TEST_DIP 把第 1 句第 1 段压低 2 dB（整体、句间、短时都还在限内，只有意群检查量得到）。
  旧版（render_passage 只调项目那一层 verify_loudness，等价于改之前的代码）+ 关掉 fine 的包装 → 重现漏洞：照样写出文件、合格证 passed=True；
  新版 + 同样的包装 → 报错、不写任何文件；新版正常 → 写出 MP3 与合格证，合格证核对 0 处。
    python3 tools/防复发/验证/最终检查.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
sys.path.insert(0, str(R / 'tools' / 'tts'))
import gaokao_tts as G  # noqa: E402
import 合格证 as CERT  # noqa: E402
from scipy.signal import resample_poly  # noqa: E402

A, SR0 = sf.read(str(HERE / '样本' / '意群响度_k48新链.flac'), dtype='float64')
ITEMS = json.loads((HERE / '样本' / '意群响度_k48新链.json').read_text('utf-8'))['sentences']
VCFG = json.loads((R / 'tools/tts/voices.json').read_text('utf-8'))['cet4_male']
P = {'id': 'x01', 'year': 2026, 'paper': '测试', 'part': 'C', 'sents': [[f'Sentence {i}, here.' for i in range(len(ITEMS))]]}
CORE = G._VERIFY_CORE
bad = []


class Stub:
    def style(self, s):
        return None

    def read_text(self, s, key=None):
        return s


def synth(read, key, engine, pron, style, speed, cfg):
    """桩：第 k 句的“合成结果”= 样本里第 k 句（24 kHz），段落位置照样本。"""
    it = ITEMS[int(key.split(':')[1]) - 1] if key else ITEMS[synth.n % len(ITEMS)]
    synth.n += 1
    seg = A[int(it['start'] * SR0):int(it['end'] * SR0)]
    return resample_poly(seg, 1, 2).astype(np.float32), [[a - it['start'], b - it['start']] for a, b in it['parts']]


synth.n = 0


def case(name, ok, detail):
    print(f"  {'✅' if ok else '❌'} {name}：{detail}")
    if not ok:
        bad.append(name)


def render(td, dip=None):
    out = Path(td) / 'cet4_male'
    if dip:
        os.environ['LOUDNESS_TEST_DIP'] = dip
    try:
        r = G.render_passage(P, 'cet4_male', VCFG, Stub(), Stub(), out, log=lambda *a: None)
        return r, None, sorted(x.name for x in out.glob('*'))
    except RuntimeError as e:
        return None, str(e), sorted(x.name for x in out.glob('*')) if out.exists() else []
    finally:
        os.environ.pop('LOUDNESS_TEST_DIP', None)


def no_fine(mp3, items, lufs, **kw):              # 项目包的一层：把意群检查关掉
    return CORE(mp3, items, lufs, **dict(kw, fine=False))


G.synth_sentence = synth
G.ANN = Path(tempfile.mkdtemp())
DIP = '1:1:2'                                      # 第 1 句第 1 段压低 2 dB（只有意群检查量得到：比相邻意群小）

with tempfile.TemporaryDirectory() as td:
    r, err, files = render(td)
    cp = CERT.problems(r, Path(td) / r['file']) if r else ['没写出']
    case('新版、正常 → 写出 MP3 与合格证，合格证核对 0 处', r is not None and not cp and any(f.endswith('.loudness.json') for f in files), err or cp or files)

final, cert0 = G.final_check, G.certificate
G.verify_loudness = no_fine
G.certificate = lambda mp3, rep: dict(cert0(mp3, rep), passed=True)                  # 改之前的 certificate：passed 一律写 True
G.final_check = lambda mp3, items, lufs, span=None: G.verify_loudness(mp3, items, lufs, **({'span': span} if span else {}))   # 等价于改之前的 render_passage
with tempfile.TemporaryDirectory() as td:
    r, err, files = render(td, DIP)
    case('旧版 + 项目包一层关掉 fine + 一段压低 2 dB → 重现漏洞（照样写出、合格证 passed=True）',
         r is not None and r['certificate']['passed'] is True and files, err or files)
G.final_check, G.certificate = final, cert0
with tempfile.TemporaryDirectory() as td:
    r, err, files = render(td, DIP)
    case('新版 + 同样的包装 → 报错、不写任何文件', r is None and '意群响度' in (err or '') and not files, (err or '')[:120] + f' 文件 {files}')
G.verify_loudness = CORE

# ⑥ say：save_checked（样本本身就是新处理链的成品，直接当 say 的结果）
x = A.astype(np.float32)
_d, _ = sf.read(__import__('io').BytesIO(G.encode_mp3(x)), dtype='float64')
x = (x * 10 ** ((-16.3 - __import__('pyloudnorm').Meter(G.OUT_SR).integrated_loudness(_d)) / 20)).astype(np.float32)   # 编成 MP3 后约 −16.3 LUFS
long_ = max((p for it in ITEMS for p in it['parts']), key=lambda p: p[1] - p[0])
with tempfile.TemporaryDirectory() as td:
    for ext in ('.mp3', '.wav'):
        o = Path(td) / f'say{ext}'
        try:
            c = G.save_checked(o, x, ITEMS, -16.0)
            case(f'say（{ext}）正常 → 写出文件与合格证', o.exists() and CERT.sidecar_of(o).exists() and c['passed'] is True,
                 {k: c['loudness'][k] for k in CERT.CORE + CERT.FINE})
        except RuntimeError as e:
            case(f'say（{ext}）正常 → 写出文件与合格证', False, str(e)[:160])
    y = x.copy()
    y[int((long_[1] - 0.8) * G.OUT_SR):int(long_[1] * G.OUT_SR)] *= 10 ** (-5 / 20)       # 最长一段的最后 0.8 秒压低 5 dB
    o = Path(td) / 'bad.mp3'
    try:
        G.save_checked(o, y, ITEMS, -16.0)
        case('say 一段末尾压低 5 dB → 报错、不写文件', False, '写出了')
    except RuntimeError as err:
        case('say 一段末尾压低 5 dB → 报错、不写文件', not o.exists() and not CERT.sidecar_of(o).exists() and '意群响度' in str(err), str(err)[:120])

if bad:
    sys.exit(f'最终检查双向验证失效：{bad}')
print('最终检查双向验证：全部通过')
