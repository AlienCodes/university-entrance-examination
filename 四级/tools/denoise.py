"""降噪（候选方案，用户看样片确认前不得用于成品）。

用户要求（2026-10-08）：声音其他一切不变，只给背景做彻底降噪，去掉朗读时背后很轻的电磁音。
做法：DeepFilterNet3（专门的语音增强神经网络：保留人声，去掉人声以外的一切），不设衰减上限；
放在整篇合成、统一电平之后，压缩和响度统一之前，所以响度、停顿、时间轴等后续处理和检查全部照旧。
原本完全无声的片头、句间停顿保持为 0。
"""
import os
import sys
from pathlib import Path

import numpy as np

DF_PKGS = os.environ.get('DF_PKGS', '')
DF_MODEL = os.environ.get('DF_MODEL', '')
_m = None


def _load():
    global _m
    if _m is None:
        if DF_PKGS and DF_PKGS not in sys.path:
            sys.path.insert(0, DF_PKGS)
        from df.enhance import init_df
        model, state, _ = init_df(model_base_dir=DF_MODEL or None, log_level='ERROR')
        _m = (model, state)
    return _m


def denoise(x, sr):
    import torch
    import soxr
    model, state = _load()
    from df.enhance import enhance
    dsr = state.sr()
    y = soxr.resample(x, sr, dsr).astype(np.float32) if sr != dsr else x.astype(np.float32)
    out = enhance(model, state, torch.from_numpy(y)[None]).squeeze(0).numpy()
    out = soxr.resample(out, dsr, sr).astype(np.float32) if sr != dsr else out.astype(np.float32)
    out = out[:len(x)]
    if len(out) < len(x):
        out = np.pad(out, (0, len(x) - len(out)))
    out[x == 0] = 0
    return out
