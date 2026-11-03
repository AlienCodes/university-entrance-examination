"""4K 成品 → 1080p 预览（发给用户看片用，不发布）。
转之前：核对这份音频的合格证（timings + MP3，gaokao_tts.certificate_problems，踩坑 85、87），4K 必须是 3840×2160。
转之后：1920×1080、音轨与 4K 逐包相同（-c:a copy，比 md5）、时长差 < 0.05 秒、文件 < 95 MB；有一项不过就删掉输出、退出码 1。
用法：/opt/ttsenv/bin/python 高考续写/tools/转1080预览.py 4K.mp4 音频.mp3 输出.mp4"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/tts'))
MAX_BYTES = 95_000_000


def probe(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(p)],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def size_of(info):
    v = [s for s in info['streams'] if s['codec_type'] == 'video']
    return (v[0]['width'], v[0]['height']) if v else None


def audio_md5(p):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(p), '-map', '0:a', '-c', 'copy', '-f', 'md5', '-'],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def main(src, mp3, out):
    import gaokao_tts as G
    src, mp3, out = Path(src), Path(mp3), Path(out)
    tm = json.loads(mp3.with_suffix('.timings.json').read_text('utf-8'))
    errs = ['合格证：' + x for x in G.certificate_problems(tm, mp3)]
    a = probe(src)
    if size_of(a) != (3840, 2160):
        errs.append(f'4K 成品分辨率是 {size_of(a)}，不是 3840×2160')
    if errs:
        print('\n'.join(errs))
        return 1
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-vf', 'scale=1920:1080:flags=lanczos', '-c:v', 'libx264',
                    '-preset', 'slow', '-crf', '20', '-tune', 'stillimage', '-pix_fmt', 'yuv420p', '-c:a', 'copy',
                    '-movflags', '+faststart', str(out)], check=True)
    b = probe(out)
    if size_of(b) != (1920, 1080):
        errs.append(f'预览分辨率是 {size_of(b)}')
    if audio_md5(src) != audio_md5(out):
        errs.append('预览的音轨与 4K 成品不是逐包相同')
    da, db = float(a['format']['duration']), float(b['format']['duration'])
    if abs(da - db) >= 0.05:
        errs.append(f'时长不一致：4K {da:.3f} 秒，预览 {db:.3f} 秒')
    sz = out.stat().st_size
    if sz >= MAX_BYTES:
        errs.append(f'预览太大：{sz} 字节（上限 {MAX_BYTES}）')
    if errs:
        out.unlink(missing_ok=True)
        print('\n'.join(errs))
        return 1
    print(f'预览通过：{out.name}  {sz} 字节  {db:.2f} 秒')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:]))
