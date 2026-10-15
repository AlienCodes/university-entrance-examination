"""响度一致（四项）：西班牙语成品（朗读音频 MP3、视频音轨）的测量。

四项的标准、限值和算法全部来自高考 tools/tts/gaokao_tts.py 的 verify_loudness（ITU-R BS.1770 独立测量；不改它，这里原样调用）：
整体 −16±0.7 LUFS、每句与中位数相差 ≤ 2 LU、3 秒短时响度波动 ≤ 1 LU、峰值 ≤ −1 dBFS。

唯一的区别是测量范围：朗读部分，即第一句开始到最后一句结束（句间 0.8 秒、逗号 0.28 秒的停顿都在里面，照样计入）。
片头 1.5 秒和结尾 2 秒的规定静音不进 3 秒窗。这两段是不是静音、够不够长，由视频核查的「开头静音」「结尾静音 2 秒」单独检查。

为什么这样测（2026-10-15，工具包外部测试：新写的短文用 Supertonic 试 28 次全部没过）：
3 秒窗一跨进规定静音，量到的是“这个窗里静音占几成”，不是朗读的响度波动；文章越短，这样的窗占比越大，结果和文章长短有关：
  · 平稳信号代替朗读（每句同一电平，test_loudness.py）：2 句短文整段算法 0.92 LU、朗读部分 0.70 LU；30 句长文 0.64 / 0.62 LU；
  · 中考 40 篇、四级 60 篇成品（83–166 秒）：两种算法相差中位 0.06 LU、最多 0.2 LU；西语 es01 Qwen3 成品（49 秒）0.75 → 0.72；
  · Supertonic 新短文：es02（2 句，12 秒）8 次 1.09–1.48 → 0.93–1.34；es03（6 句，28 秒）6 次 1.10–1.44 → 0.88–1.07。
整体响度、每句偏差、峰值仍按整段测量（和高考程序完全相同）；只有短时波动去掉了跨进片头片尾的窗。
句间 0.8 秒、逗号 0.28 秒的停顿照样计入（句子越短、停顿越密，短时波动越大——这是朗读本身的节奏，照常要求 ≤ 1 LU）。
限值一项不改。整段算法的值照样算出来写进报告（short_term_std_whole_lu），方便对照。
朗读部分太短、3 秒窗不到 3 个时没法测短时波动，直接报错（不静默跳过）。
"""
import io
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import c4  # noqa: E402

# 单独载入一份高考程序：四级 make_audio 导入时会把 gaokao_tts.verify_loudness 换成带四级电磁音检查的版本，这里要原版
G = c4.load('gaokao_tts_loudness', 'tools/tts/gaokao_tts.py')
LIMITS = G.LIMITS
MIN_WINDOWS = 3
NAME = '响度一致（第一项检查）'


def _wav(a, sr):
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, a, sr, format='WAV', subtype='FLOAT')
    return buf.getvalue()


def windows(n, sr):
    """长 n 个采样的音频里，verify_loudness 取的 3 秒窗（每 0.5 秒一个）个数。"""
    return len(range(0, n - 3 * sr, sr // 2))


def measure(a, sr, items, target_lufs=-16.0):
    """a：整段音频（含片头片尾，单声道或多声道 float）；items：[{start, end, …}]（秒，按整段计）。
    返回 (报告, 错误列表)。报告的键和 verify_loudness 相同（short_term_std_lu 是朗读部分的值），
    另加 short_term_std_whole_lu（整段算法，参考）、short_term_windows、span_s。"""
    a = np.asarray(a, np.float64)
    if a.ndim > 1:
        a = a.mean(1)
    s0, s1 = float(items[0]['start']), float(items[-1]['end'])
    i0, i1 = int(round(s0 * sr)), min(len(a), int(round(s1 * sr)))
    seg = a[i0:i1]
    its = [{**it, 'start': it['start'] - s0, 'end': it['end'] - s0} for it in items]
    whole, werrs = G.verify_loudness(_wav(a, sr), items, target_lufs)      # 整体、句间偏差、峰值：整段测量，原样
    span, serrs = G.verify_loudness(_wav(seg, sr), its, target_lufs)       # 短时波动：只取朗读部分
    rep = {**whole, 'short_term_std_lu': span['short_term_std_lu'], 'short_term_std_whole_lu': whole['short_term_std_lu']}
    errs = [e for e in werrs if '短时' not in e] + [e for e in serrs if '短时' in e]
    n = windows(len(seg), sr)
    rep.update(short_term_windows=n, span_s=round(s1 - s0, 2))
    if n < MIN_WINDOWS:
        errs = [e for e in errs if '短时' not in e] + [
            f'朗读部分只有 {s1 - s0:.1f} 秒，3 秒短时响度波动测不了（要超过 {3 + 0.5 * (MIN_WINDOWS - 1):g} 秒）：请多选几句']
    return rep, errs


def measure_mp3(mp3_bytes, items, target_lufs=-16.0):
    import soundfile as sf
    a, sr = sf.read(io.BytesIO(mp3_bytes), dtype='float64')
    return measure(a, sr, items, target_lufs)


def detail(rep, errs=()):
    """核查报告里的一行说明。"""
    return (f"整体 {rep['integrated_lufs']} LUFS，句间最大偏差 {rep['sentence_max_dev_lu']} LU，"
            f"短时波动 {rep['short_term_std_lu']} LU（朗读部分 {rep['span_s']} 秒；连片头片尾静音一起算是 {rep['short_term_std_whole_lu']} LU），"
            f"峰值 {rep['peak_dbfs']} dBFS" + ('；' + '；'.join(errs) if errs else ''))
