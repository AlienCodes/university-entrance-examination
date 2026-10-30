"""双向验证：停顿里的呼吸声（踩坑 89）。不依赖 git 历史（CI 只检出最新一个提交）。
  ① 有问题的版本：旧样音 A（高考语法填空/样音/A_男老师_设计音色.mp3 前 45 秒，用户听出呼吸声）→ breath_check 必须报出 ≥ 5 处；
  ② 修好的版本：同一批原始合成走新处理链的样音（A_男老师_去呼吸.mp3 前 45 秒）→ 0 处；
  ③ 把错误放回去：Qwen 男老师一段真实原始合成（样本 呼吸声_qwen男老师s03原始.flac），走讲解音频的处理链（逐意群 segment + master），
     去呼吸关掉 → 必须报出；打开 → 0 处；且浊音帧电平逐帧不变（< 0.5 dB，不伤语音）；
  ④ 人造：纯静音、纯浊音 0 处；浊音 + 静音 + 0.3 秒噪声 + 静音 + 浊音 → 1 处；
  ⑤ 入口：讲解音频 的 build、选段 都走 prep（含 debreath），checks（render 与 Actions 上的 qwen_synth）和视频成品核查都调 breath_check。
    python3 tools/防复发/验证/呼吸声.py"""
import ast
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tools/tts'), str(ROOT / '高考语法填空/tools')]
import 去呼吸 as BR  # noqa: E402

bad = []


def load(p):
    x, sr = sf.read(str(p), dtype='float32')
    return (x.mean(1) if x.ndim > 1 else x), sr


S = Path(__file__).parent / '样本'          # 成品 MP3 的前 45 秒（CI 不检出 mp3，存成 24 kHz FLAC）
x, sr = load(S / '呼吸声_旧样音A前45秒.flac')
n_old = len(BR.breath_check(x, sr))
x, sr = load(S / '呼吸声_新样音A前45秒.flac')
n_new = len(BR.breath_check(x, sr))
print(f'① 旧样音 A：{n_old} 处（应 ≥ 5）  ② 新样音 A：{n_new} 处（应 0）')
if n_old < 5:
    bad.append('① 旧样音没报出')
if n_new:
    bad.append('② 新样音有呼吸')

import gaokao_tts as G  # noqa: E402
import 讲解音频 as J  # noqa: E402
raw = J.load(Path(__file__).parent / '样本/呼吸声_qwen男老师s03原始.flac')


def chain(on):
    real = BR.debreath
    if not on:
        BR.debreath = lambda y, s: (y, [])
    try:
        y, parts = J.per_clause(J.prep(raw))
    finally:
        BR.debreath = real
    return G.master(np.concatenate([np.zeros(int(0.5 * J.SR), np.float32), y, np.zeros(J.SR, np.float32)]), -16.0)


off, on = BR.breath_check(chain(False), G.OUT_SR), BR.breath_check(chain(True), G.OUT_SR)
lv0, per0, _, _ = BR._frames(raw, J.SR)
lv1, _, _, _ = BR._frames(BR.debreath(raw, J.SR)[0], J.SR)
v = (per0 > 0.5) & (lv0 > np.percentile(lv0, 99) + BR.CORE_FLOOR)   # 词核里的浊音帧
moved = float(np.abs(lv0[v] - lv1[v]).max())
print(f'③ 原始样本走处理链：去呼吸关 {len(off)} 处（应 ≥ 1），开 {len(on)} 处（应 0）；浊音帧最大变化 {moved:.3f} dB（应 < 0.5）')
if not off:
    bad.append('③ 关掉去呼吸没报出')
if on:
    bad.append(f'③ 打开去呼吸仍有 {on}')
if moved >= 0.5:
    bad.append('③ 去呼吸伤了浊音')

sr = 48000
tone = (0.3 * np.sin(2 * np.pi * 150 * np.arange(sr) / sr)).astype(np.float32)
sil = np.zeros(sr, np.float32)
noise = 0.003 * np.random.default_rng(0).standard_normal(int(0.3 * sr)).astype(np.float32)
r = [len(BR.breath_check(sil, sr)), len(BR.breath_check(tone, sr)), len(BR.breath_check(np.concatenate([tone, sil[:sr // 4], noise, sil, tone]), sr))]
print('④ 人造（静音、浊音、浊音+噪声）：', r, '（应 [0, 0, 1]）')
if r != [0, 0, 1]:
    bad.append('④ 人造样本')


def calls(path, func, name):
    tree = ast.parse((ROOT / path).read_text('utf-8'))
    for f in ast.walk(tree):
        if isinstance(f, ast.FunctionDef) and f.name == func:
            return any(isinstance(c, ast.Call) and getattr(c.func, 'attr', getattr(c.func, 'id', None)) == name for c in ast.walk(f))
    return False


need = [('高考语法填空/tools/讲解音频.py', 'prep', 'debreath'), ('高考语法填空/tools/讲解音频.py', 'build', 'prep'),
        ('高考语法填空/tools/选段.py', 'seg_score', 'prep'), ('高考语法填空/tools/讲解音频.py', 'checks', 'breath_check'),
        ('高考语法填空/tools/讲解音频.py', 'render', 'checks'), ('高考语法填空/tools/qwen_synth.py', 'main', 'checks'),
        ('高考语法填空/tools/讲解视频.py', 'verify', 'breath_check')]
miss = [f'{p}:{f}→{n}' for p, f, n in need if not calls(p, f, n)]
print('⑤ 入口：', '全部接上' if not miss else miss)
bad += miss
print('呼吸声双向验证', '通过' if not bad else f'失败：{bad}')
sys.exit(1 if bad else 0)
