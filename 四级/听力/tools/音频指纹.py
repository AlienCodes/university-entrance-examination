"""四级听力原始音频清点：sha256、解码长度（按解码样本数，踩坑 118）、采样率 / 声道、能量包络指纹。
用法：python3 音频指纹.py 输出.json 音频1 音频2 ...
包络：单声道、每 50 ms 一帧的 dB（用于判断两个文件是不是同一段录音，不受重新编码影响）。"""
import json, sys, subprocess, hashlib
import numpy as np

def probe(f):
    j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-select_streams', 'a:0',
        '-show_format', '-of', 'json', f], capture_output=True, check=True).stdout)
    s = j['streams'][0]
    return int(s['sample_rate']), int(s['channels']), s.get('codec_name'), float(j['format'].get('duration', 0)), int(j['format'].get('bit_rate', 0) or 0)

def one(f):
    sr, ch, codec, hdr, br = probe(f)
    h = hashlib.sha256(open(f, 'rb').read()).hexdigest()
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', f, '-f', 'f32le', '-ac', '1', '-'], stdout=subprocess.PIPE)
    a = np.frombuffer(p.stdout.read(), dtype=np.float32); p.wait()
    n = len(a); H = sr // 20; m = n // H
    env = 10 * np.log10((a[:m * H].reshape(m, H) ** 2).mean(1) + 1e-10)
    return {'file': f, 'sha256': h, 'bytes': len(open(f, 'rb').read()), 'sr': sr, 'channels': ch, 'codec': codec,
            'bitrate': br, 'header_dur': round(hdr, 3), 'decoded_dur': round(n / sr, 3),
            'peak_db': round(float(20 * np.log10(np.abs(a).max() + 1e-12)), 2), 'env': [round(float(x), 1) for x in env]}

out = sys.argv[1]
json.dump([one(f) for f in sys.argv[2:]], open(out, 'w'), ensure_ascii=False)
