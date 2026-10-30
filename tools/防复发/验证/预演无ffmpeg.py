"""双向验证：合成机上没有 ffmpeg（踩坑 91）。
  ① 预演.sh 跑合成时把 ffmpeg / ffprobe 遮掉（与 GitHub 合成机一致）；
  ② 挑参考.decode（合成时现做用户声音参考用）在没有 ffmpeg 的 PATH 下能读 WAV；把旧写法（一律走 ffmpeg）放回去 → 必须失败。
    python3 tools/防复发/验证/预演无ffmpeg.py"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
bad = []
sh = (ROOT / 'tools/防复发/预演_qwen/预演.sh').read_text('utf-8')
if 'PATH="$NOBIN:$PATH"' not in sh or 'ffmpeg ffprobe' not in sh:
    bad.append('① 预演.sh 没有遮掉 ffmpeg')
d = Path(tempfile.mkdtemp())
(d / 'ffmpeg').write_text('#!/bin/sh\nexit 127\n')
(d / 'ffmpeg').chmod(0o755)
src = (ROOT / '高考语法填空/tools/挑参考.py').read_text('utf-8')
old = src.replace("        x, sr = sf.read(str(p), dtype='float32')\n    except Exception:", "        raise RuntimeError\n    except Exception:", 1)
assert old != src, '挑参考.decode 的写法变了，更新这个验证'
(d / '挑参考_旧.py').write_text(old, 'utf-8')
code = '''import sys, numpy as np, soundfile as sf
sys.path[:0] = [sys.argv[1], sys.argv[2] + "/tools/tts", sys.argv[2] + "/高考语法填空/tools"]
import importlib; P = importlib.import_module(sys.argv[3])
w = sys.argv[1] + "/x.wav"; sf.write(w, (0.1 * np.sin(np.arange(48000) / 10)).astype(np.float32), 48000)
print(len(P.decode(w)))'''
env = dict(os.environ, PATH=f'{d}:{os.environ["PATH"]}')
r_new = subprocess.run([sys.executable, '-c', code, str(d), str(ROOT), '挑参考'], env=env, capture_output=True, text=True)
r_old = subprocess.run([sys.executable, '-c', code, str(d), str(ROOT), '挑参考_旧'], env=env, capture_output=True, text=True)
print(f'② 现在：{"能读" if r_new.returncode == 0 else "失败"}（应能读）；旧写法：{"能读" if r_old.returncode == 0 else "失败"}（应失败）')
if r_new.returncode != 0:
    bad.append('② 现在没有 ffmpeg 就读不了：' + r_new.stderr[-300:])
if r_old.returncode == 0:
    bad.append('② 旧写法没报出')
print('预演无 ffmpeg 双向验证', '通过' if not bad else f'失败：{bad}')
sys.exit(1 if bad else 0)
