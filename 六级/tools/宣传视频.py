"""六级学习资料的 B 站商品介绍短视频（用户 2026-10-21）：用 六级/宣传图/ 的 7 张 1:1 商品图做成 1080×1080 短视频，
每张 4 秒、缓慢推近、0.6 秒淡入淡出，背景声音是第 1 篇的真实男声朗读（与资料里的朗读音频同一份）。程序生成，零 token。

    /opt/ttsenv/bin/python 六级/tools/宣传视频.py   # → 六级/宣传图/六级资料介绍.mp4
"""
import json
import subprocess
from pathlib import Path

C6 = Path(__file__).resolve().parent.parent
IMGS = sorted((C6 / '宣传图').glob('0*.png'))
OUT = C6 / '宣传图' / '六级资料介绍.mp4'
D, X, S, FPS = 4.0, 0.6, 1080, 30          # 每张时长、淡入淡出、边长、帧率
T = json.loads((C6 / 'audio' / 'timings.json').read_text('utf-8'))['cet4_male']['s01']
AUDIO = C6 / 'audio' / T['file']


def main():
    assert len(IMGS) == 7, IMGS
    n = len(IMGS)
    total = n * D - (n - 1) * X
    args = ['ffmpeg', '-y', '-loglevel', 'error']
    for f in IMGS:
        args += ['-loop', '1', '-t', str(D), '-i', str(f)]
    args += ['-ss', '1.4', '-t', f'{total:.2f}', '-i', str(AUDIO)]
    fr = int(D * FPS)
    parts = [f"[{i}:v]scale=3240:3240,zoompan=z='1+0.045*on/{fr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s={S}x{S}:fps={FPS},"
             f"format=yuv420p,setsar=1[v{i}]" for i in range(n)]
    last = 'v0'
    for i in range(1, n):
        parts.append(f"[{last}][v{i}]xfade=transition=fade:duration={X}:offset={i * (D - X):.2f}[x{i}]")
        last = f'x{i}'
    parts.append(f"[{n}:a]afade=t=in:d=0.5,afade=t=out:st={total - 1.5:.2f}:d=1.5[a]")
    args += ['-filter_complex', ';'.join(parts), '-map', f'[{last}]', '-map', '[a]',
             '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', str(FPS),
             '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-t', f'{total:.2f}', str(OUT)]
    subprocess.run(args, check=True)
    print(OUT, f'{total:.1f} 秒')


if __name__ == '__main__':
    main()
