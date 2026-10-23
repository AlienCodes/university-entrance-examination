"""踩坑 4 / 23 / 27 / 72：tools/tts/识别分诊.py 的双向验证。
改读音之前的提交（b6e49a8）里的 t25、t14 音频必须报出 toiled、Antonapoulos loved（退出码 1）；现在的音频必须 0 待核。"""
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
PY = '/opt/ttsenv/bin/python'
old = subprocess.run([PY, str(R / 'tools/tts/识别分诊.py'), '专八', 't25', 't14', '--rev', 'b6e49a8'], capture_output=True, text=True)
now = subprocess.run([PY, str(R / 'tools/tts/识别分诊.py'), '专八', 't25', 't14'], capture_output=True, text=True)
ok = old.returncode == 1 and 'toiled' in old.stdout and 'antonapoulos loved' in old.stdout and now.returncode == 0
print(f'旧音频：退出码 {old.returncode}，报出 toiled {"toiled" in old.stdout}、Antonapoulos {"antonapoulos loved" in old.stdout}；现在：退出码 {now.returncode}')
print('识别分诊：双向通过' if ok else '识别分诊：不通过')
sys.exit(0 if ok else 1)
