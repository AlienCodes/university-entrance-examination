#!/usr/bin/env python3
"""本机跑全部录音的分块识别（同录音按 sha256 复用）：高考听力/识别/<套>/分块.json + 原音.sha256（文件名 + sha256）。
用法：python3 -I 全部识别.py <解压目录>（带 #i 的是同一套的第 i 段录音，如山东第 1 / 2 次）"""
import hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
RAW = Path(sys.argv[1]); OUT = ROOT / '高考听力/识别'
done = {}
for k, v in json.loads((ROOT / '高考听力/原始材料/清单.json').read_text('utf-8')).items():
    for i, a in enumerate(v.get('音频', [])):
        key = k if len(v['音频']) == 1 else f'{k}#{i + 1}'
        d = OUT / key; d.mkdir(parents=True, exist_ok=True)
        f = RAW / a['文件']; h = hashlib.sha256(f.read_bytes()).hexdigest()
        (d / '原音.sha256').write_text(f'{h}  {a["文件"]}\n', 'utf-8')
        if (d / '分块.json').exists(): done[h] = d; continue
        if h in done: shutil.copy(done[h] / '分块.json', d); print(key, '同录音', done[h].name, flush=True); continue
        with tempfile.TemporaryDirectory() as t:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(f), '-c:a', 'pcm_s16le', f'{t}/a.wav'], check=True)
            r = subprocess.run(['/opt/ttsenv/bin/python', str(ROOT / '高考听力/tools/分块识别.py'), f'{t}/a.wav', str(d)], capture_output=True, text=True)
            print(key, r.stdout.strip(), r.stderr[-300:] if r.returncode else '', flush=True)
        done[h] = d
print('全部完成')
