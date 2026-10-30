"""双向验证：停顿里的呼吸声（踩坑 89）。不依赖 git 历史（CI 只检出最新一个提交）。
  ① 有问题的版本：旧样音 A（高考语法填空/样音/A_男老师_设计音色.mp3 前 45 秒，用户听出呼吸声）→ breath_check 必须报出 ≥ 5 处；
  ② 修好的版本：同一批原始合成走新处理链的样音（A_男老师_去呼吸.mp3 前 45 秒）→ 0 处；
  ③ 把错误放回去：Qwen 男老师一段真实原始合成（样本 呼吸声_qwen男老师s03原始.flac），走讲解音频的处理链（逐意群 segment + master），
     去呼吸关掉 → 必须报出；打开 → 0 处；且浊音帧电平逐帧不变（< 0.5 dB，不伤语音）；
  ④ 人造：纯静音、纯浊音 0 处；浊音 + 静音 + 0.3 秒 600—2500 Hz 带通噪声（换气）→ 1 处；浊音 + 短成阻 + 高通噪声（-ts 尾音）→ 0 处；
  ⑤ 入口：讲解音频 的 build、选段 都走 prep（含 debreath），checks（render 与 Actions 上的 qwen_synth）和视频成品核查都调 breath_check；
  ⑥ 铁律 22 发布关口：gaokao_tts.final_check（所有项目写音频前都跑）对旧 A 报呼吸、新 A 不报；合格证 breath_count ≠ 0、
     2026-10-31 起缺这一项都报，之前的合格证不追溯。
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
w = np.random.default_rng(0).standard_normal(int(0.3 * sr))
Wf = np.fft.rfft(w)
fq = np.fft.rfftfreq(len(w), 1 / sr)
Wf[(fq < 600) | (fq > 2500)] = 0
breath = (0.003 * np.fft.irfft(Wf, len(w)) / np.std(np.fft.irfft(Wf, len(w)))).astype(np.float32)   # 600—2500 Hz 带通噪声：像换气
fric = (0.003 * np.diff(w, prepend=0)).astype(np.float32)                          # 高通噪声：像 s、-ts 尾音
r = [len(BR.breath_check(sil, sr)), len(BR.breath_check(tone, sr)),
     len(BR.breath_check(np.concatenate([tone, sil[:sr // 4], breath, sil, tone]), sr)),
     len(BR.breath_check(np.concatenate([tone, sil[:sr // 20], fric, sil, tone]), sr))]
print('④ 人造（静音、浊音、浊音+带通噪声、浊音+成阻+高通噪声）：', r, '（应 [0, 0, 1, 0]）')
if r != [0, 0, 1, 0]:
    bad.append('④ 人造样本')


def calls(path, func, name):
    tree = ast.parse((ROOT / path).read_text('utf-8'))
    for f in ast.walk(tree):
        if isinstance(f, ast.FunctionDef) and f.name == func:
            return any(isinstance(c, ast.Call) and getattr(c.func, 'attr', getattr(c.func, 'id', None)) == name for c in ast.walk(f))
    return False


need = [('高考语法填空/tools/讲解音频.py', 'prep', 'debreath'), ('高考语法填空/tools/讲解音频.py', '_build_units', 'prep'), ('高考语法填空/tools/讲解音频.py', 'build', '_build_units'),
        ('高考语法填空/tools/选段.py', 'seg_score', 'prep'), ('高考语法填空/tools/讲解音频.py', 'checks', 'breath_check'),
        ('高考语法填空/tools/讲解音频.py', 'render', 'checks'), ('高考语法填空/tools/qwen_synth.py', 'main', 'checks'),
        ('高考语法填空/tools/讲解视频.py', 'verify', 'breath_check')]
miss = [f'{p}:{f}→{n}' for p, f, n in need if not calls(p, f, n)]
print('⑤ 入口：', '全部接上' if not miss else miss)
bad += miss
# ⑥ 铁律 22 的发布关口：写文件前 final_check 量呼吸、写进合格证；合格证规则要求 breath_count = 0
import copy  # noqa: E402
import json  # noqa: E402
import soxr  # noqa: E402
import 合格证 as CERT  # noqa: E402
for name, want in [('呼吸声_旧样音A前45秒.flac', True), ('呼吸声_新样音A前45秒.flac', False)]:
    y, s0 = load(S / name)
    y48 = soxr.resample(y, s0, G.OUT_SR).astype(np.float32)
    its = [{'start': t0, 'end': min(t0 + 5.0, len(y48) / G.OUT_SR)} for t0 in np.arange(0.0, len(y48) / G.OUT_SR - 1, 5.0)]
    rep, errs = G.final_check(G.encode_mp3(y48), its, -16.0)
    got = any('呼吸' in e for e in errs)
    print(f"⑥ final_check {name}：breath_count={rep.get('breath_count')}，报呼吸 {got}（应 {want}）")
    if got != want or 'breath_count' not in rep:
        bad.append(f'⑥ final_check {name}')
c0 = json.loads((ROOT / '高考语法填空/样音/A_男老师_去呼吸.loudness.json').read_text('utf-8'))
cases = []
for tag, date, br, want in [('10-30 无 breath_count（不追溯）', '2026-10-30', None, False), ('有 3 处', '2026-10-31', 3, True),
                            ('10-31 起缺 breath_count', '2026-10-31', None, True), ('10-31 起 0 处', '2026-10-31', 0, False),
                            ('旧日期但写了 2 处', '2026-10-30', 2, True)]:
    c = copy.deepcopy(c0)
    c['date'] = date
    if br is not None:
        c['loudness']['breath_count'] = br
    got = bool(CERT.cert_problems(c))
    cases.append(got == want)
    print(f'⑥ 合格证 {tag}：报 {got}（应 {want}）')
if not all(cases):
    bad.append('⑥ 合格证 breath_count 规则')
print('呼吸声双向验证', '通过' if not bad else f'失败：{bad}')
sys.exit(1 if bad else 0)
