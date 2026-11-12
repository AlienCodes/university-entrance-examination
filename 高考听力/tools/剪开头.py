"""高考听力开头剪切的唯一规则（老师要求 6，铁律 25 的例外：只许剪开头）：
保留部分必须与原音从剪切点起逐样本相同（不增益、不剪中间、不重采样、声道不变），剪切点不能晚于锚点（“第一节 / Section A”开口）。"""
import numpy as np


def check(a, b, k, anchor_k):
    """a 原音（样本 × 声道），b 剪后，k 剪切样本，anchor_k 锚点开口样本；返回问题列表"""
    bad = []
    if k > anchor_k: bad.append(f'剪到锚点之后（剪切点 {k} > 锚点 {anchor_k}）')
    if k < 0: bad.append('剪切点为负')
    if b.shape != a[k:].shape: bad.append(f'剪后长度 / 声道 {b.shape} ≠ 原音剪切点之后 {a[k:].shape}（只许剪开头）')
    elif not np.array_equal(b, a[k:]): bad.append('剪后与原音对应段不是逐样本相同')
    return bad
