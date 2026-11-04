"""双向验证：清晰度（踩坑 115；老师 2026-11-04：“很多发音都没有发清楚……起码声音要清晰一点”）。needs tts（两个中文识别器）。
  ① v3 样段（老师说不清楚的那份）必须报出：Paraformer 拼音错误率、4 kHz 以上能量、擦音对元音三项；
  ② v4 样段（清晰版）0 处；
  ③ v4 去掉 4 kHz 以上（低通，模拟发闷）必须报频谱两项；
  ④ 入口：讲解音频.render 调 清晰度.check、选段 用第二个识别器。
    /opt/ttsenv/bin/python tools/防复发/验证/清晰度.py"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tools/tts')]
import 清晰度 as QX  # noqa: E402

P = ROOT / '高考续写/预览'
V3 = P / '2026 新课标Ⅰ卷 读后续写 讲解 样段 v3 讲法（老师模型 g1）'
V4 = P / '2026 新课标Ⅰ卷 读后续写 讲解 样段 v4（老师模型，清晰）'


def dec(p, sr=48000):
    pcm = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', str(p), '-f', 'f32le', '-ac', '1', '-ar', str(sr), '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, np.float32).copy()


bad = []
ears = QX.Ears()
items = lambda v: json.loads(Path(str(v) + '.timings.json').read_text('utf-8'))['items']  # noqa: E731
_, e3 = QX.check(dec(str(V3) + '.mp3'), 48000, items(V3), ears)
print('① v3', len(e3), '处：', '；'.join(x[:40] for x in e3))
if not (any('Paraformer' in x for x in e3) and any('4 kHz' in x for x in e3) and any('擦音' in x for x in e3)):
    bad.append('① v3 没报全三项')
a4 = dec(str(V4) + '.mp3')
_, e4 = QX.check(a4, 48000, items(V4), ears)
print('② v4', len(e4), '处', e4)
if e4:
    bad.append('② v4 应为 0')
from scipy.signal import butter, sosfiltfilt  # noqa: E402
lp = sosfiltfilt(butter(8, 3500, fs=48000, output='sos'), a4).astype(np.float32)
_, e5 = QX.check(lp, 48000, items(V4), ears)
print('③ v4 低通 3.5 kHz', len(e5), '处')
if not (any('4 kHz' in x for x in e5) and any('擦音' in x for x in e5)):
    bad.append('③ 低通后频谱两项没报')
src = (ROOT / '高考语法填空/tools/讲解音频.py').read_text('utf-8')
if 'QX.check(' not in src:
    bad.append('④ 讲解音频.render 没调 清晰度.check')
if 'ears.pf' not in (ROOT / '高考语法填空/tools/选段.py').read_text('utf-8'):
    bad.append('④ 选段 没用第二个识别器')
print('不通过：' + '；'.join(bad) if bad else '通过')
sys.exit(1 if bad else 0)
