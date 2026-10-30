"""双向验证：段内电平统一 even() 遇到数字静音不出 NaN（踩坑 88）。
样本：Qwen3-TTS 真实合成的一段（段首约 2000 个采样纯零），2026-10-30 高考语法填空选型时整段变 NaN、成品报“整体响度 −inf”。
  ① 修正前的 even（从现在的源码临时还原两处旧写法，故意把错误放回去；不依赖 git 历史）→ 必须出 NaN（证明样本能触发）；
  ② 现在的 even / segment → 全部有限；
  ③ 从没触发过的普通音频（意群响度样本 k48 的前 3 秒）：现在与修正前逐字节相同（修正只改了原来会出 NaN 的地方）；
  ④ segment 遇到 NaN 输入当场报错，不往下传。
    python3 tools/防复发/验证/段内电平NaN.py"""
import importlib.util
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'tts'))
import gaokao_tts as G  # noqa: E402

bad = []
x, sr = sf.read(str(HERE / '样本' / '段内电平NaN_qwen段首静音.flac'), dtype='float32')
assert sr == G.SR, sr

# 把错误放回去：从现在的源码临时还原那两处旧写法（不依赖 git 历史，CI 只检出最新一个提交）
src = (ROOT / 'tools' / 'tts' / 'gaokao_tts.py').read_text('utf-8')
old_src = src
for new, old in [("10 * np.log10(np.maximum(num[idx], 1e-20) / den[idx])", "10 * np.log10(num[idx] / den[idx])"),
                 ("10 * np.log10(np.maximum(uniform_filter1d(e, 5, mode='nearest'), 1e-20))", "10 * np.log10(uniform_filter1d(e, 5, mode='nearest'))"),
                 ("    if not np.isfinite(y).all():", "    if False:")]:
    assert new in old_src, f'修正的写法变了，还原不了（更新这个验证）：{new}'
    old_src = old_src.replace(new, old)
d = Path(tempfile.mkdtemp())
(d / 'gaokao_tts_old.py').write_text(old_src, 'utf-8')
spec = importlib.util.spec_from_file_location('gaokao_tts_old', d / 'gaokao_tts_old.py')
OLD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OLD)

import warnings  # noqa: E402
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    o = OLD.even(G.trim(x))
print(f'① 修正前 even：NaN {int(np.isnan(o).sum())} 个采样', '（报出）' if np.isnan(o).any() else '（漏：样本没能触发）')
if not np.isnan(o).any():
    bad.append('修正前的 even 在样本上没出 NaN：样本失效')

n = G.even(G.trim(x))
s = G.segment(G.trim(x))
print(f'② 现在 even / segment：NaN {int(np.isnan(n).sum())} / {int(np.isnan(s).sum())}')
if not (np.isfinite(n).all() and np.isfinite(s).all()):
    bad.append('现在的 even / segment 仍出 NaN')

k, ksr = sf.read(str(HERE / '样本' / '意群响度_k48新链.flac'), dtype='float32')
import soxr  # noqa: E402
k = soxr.resample(k[:3 * ksr], ksr, G.SR).astype(np.float32)
same = np.array_equal(OLD.even(k), G.even(k)) and np.array_equal(OLD.segment(k), G.segment(k))
print('③ 普通音频与修正前逐字节相同：', same)
if not same:
    bad.append('普通音频的 even / segment 输出变了（修正不该影响没出 NaN 的情况）')

try:
    G.segment(np.full(24000, np.nan, np.float32))
    bad.append('segment 遇到 NaN 没报错')
    print('④ segment 遇到 NaN：没报错（漏）')
except RuntimeError:
    print('④ segment 遇到 NaN：当场报错')

print('段内电平 NaN 双向验证：', '通过' if not bad else '失败：' + '；'.join(bad))
sys.exit(1 if bad else 0)
