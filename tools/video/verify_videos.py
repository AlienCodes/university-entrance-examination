"""独立核查“最终视频”里的每个视频是否符合全部铁律（见仓库根目录 CLAUDE.md）。

    python verify_videos.py            # 核查全部，结果写到 最终视频/核查报告.md

全部是对成品 MP4 的实测（解码音轨、抽取画面），不依赖生成时的自检结果。
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FINAL = ROOT / '最终视频'
sys.path.insert(0, str(HERE.parent / 'tts'))


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def audio_of(mp4, sr=48000):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32), sr


def frame(mp4, t, tmp):
    f = tmp / f'{t:.3f}.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', str(mp4), '-frames:v', '1',
                    '-vf', 'scale=480:270', '-f', 'rawvideo', '-pix_fmt', 'gray', str(f)], check=True)
    return np.frombuffer(f.read_bytes(), np.uint8).astype(np.float32)


def peak_db(x):
    return 20 * np.log10(np.max(np.abs(x)) + 1e-12) if len(x) else -120


def check(mp4, p, tm):
    from gaokao_tts import verify_loudness, LIMITS
    res = []
    ok = lambda name, cond, detail: res.append((name, bool(cond), detail))

    # 1. 文件名
    paper = re.sub(r'·[^）]*', '', p['paper'])
    ok('文件名：年份 试卷 篇目 题目', mp4.name.startswith(f"{p['year']} {paper} 阅读{p['part']} {p['title']}"), mp4.name)
    # 2. 分辨率与时长
    info = json.loads(run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height,duration',
                           '-of', 'json', str(mp4)]))['streams']
    v = next(s for s in info if s['codec_type'] == 'video')
    a = next(s for s in info if s['codec_type'] == 'audio')
    w, h = int(v['width']), int(v['height'])
    ok('分辨率 ≥ 2K 且 16:9', w >= 2560 and w * 9 == h * 16, f'{w}×{h}')
    vd, ad = float(v['duration']), float(a['duration'])
    ok('画面与声音等长', abs(vd - ad) < 0.1, f'画面 {vd:.2f}s，声音 {ad:.2f}s')

    sents = [s for para in p['paras'] for s in para]
    times = tm['sentences']
    ok('音频句数 = 文章句数', len(sents) == len(times), f'{len(times)} / {len(sents)}')
    # 3. 每句至少一个生词
    empty = [i + 1 for i, s in enumerate(sents) if not s['w']]
    ok('每句至少标注一个单词', not empty, f'空句 {empty}' if empty else f'{len(sents)} 句全部有标注')

    x, sr = audio_of(mp4)
    seg = lambda t0, t1: x[int(t0 * sr):int(t1 * sr)]
    # 4. 开头 1.5 秒静音、结尾 2 秒静音
    ok('开头静音 1.5 秒', abs(times[0]['start'] - 1.5) < 0.01 and peak_db(seg(0, 1.45)) < -60,
       f"第一句从 {times[0]['start']:.2f}s 开始，前 1.45s 峰值 {peak_db(seg(0, 1.45)):.0f} dB")
    tail = ad - times[-1]['end']
    ok('结尾静音 2 秒', tail >= 1.95 and peak_db(seg(times[-1]['end'] + 0.1, ad)) < -60,
       f'读完后 {tail:.2f}s，峰值 {peak_db(seg(times[-1]["end"] + 0.1, ad)):.0f} dB')
    # 5. 句间停顿 0.8 秒，且确实静音
    gaps = [times[i + 1]['start'] - times[i]['end'] for i in range(len(times) - 1)]
    loud_gaps = [i + 2 for i in range(len(times) - 1)
                 if peak_db(seg(times[i]['end'] + 0.08, times[i + 1]['start'] - 0.08)) > -50]
    ok('句间停顿 0.8 秒', all(abs(g - 0.8) <= 0.01 for g in gaps),
       f'最短 {min(gaps):.3f}s，最长 {max(gaps):.3f}s')
    ok('句间停顿确实无声', not loud_gaps, f'有声音的间隙：第 {loud_gaps} 句前' if loud_gaps else '全部无声')
    # 6. 响度（对视频里的音轨实测）
    import io
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, x, sr, format='WAV')
    rep, errs = verify_loudness(buf.getvalue(), times, -16.0)
    ok('响度一致（第一项检查）', not errs,
       f"整体 {rep['integrated_lufs']} LUFS，句间最大偏差 {rep['sentence_max_dev_lu']} LU，"
       f"短时波动 {rep['short_term_std_lu']} LU，峰值 {rep['peak_dbfs']} dBFS" + ('；' + '；'.join(errs) if errs else ''))
    # 7. 画面切换：读完后 0.45s 仍是本句，0.55s 已是下一句；片头在开头
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        bad = []
        for i in range(len(times) - 1):
            cur = frame(mp4, times[i]['start'] + 0.2, td)
            nxt = frame(mp4, times[i + 1]['start'] + 0.2, td)
            before = frame(mp4, times[i]['end'] + 0.45, td)
            after = frame(mp4, times[i]['end'] + 0.55, td)
            if np.abs(before - cur).mean() > 1 or np.abs(after - nxt).mean() > 1:
                bad.append(i + 1)
        ok('读完停留 0.5 秒再切屏，0.3 秒后开读', not bad, f'不符合：第 {bad} 句' if bad else f'{len(times) - 1} 处切换全部正确')
        title = frame(mp4, 0.7, td)
        first = frame(mp4, times[0]['start'] + 0.2, td)
        ok('片头在前 1.5 秒', np.abs(title - first).mean() > 1, '片头画面与第一句不同')
    return res


def main():
    data = json.loads((ROOT / 'data' / 'vocab.json').read_text('utf-8'))
    P = {p['id']: p for p in data['passages']}
    T = json.loads((ROOT / 'audio' / 'timings.json').read_text('utf-8'))['female']
    lines = ['# 最终视频核查报告', '', '对每个 MP4 成品实测（解码音轨、抽取画面），逐项核对 CLAUDE.md 里的铁律。', '']
    allok = True
    for mp4 in sorted(FINAL.glob('*.mp4')):
        p = next((x for x in P.values() if x.get('done') and mp4.name.startswith(
            f"{x['year']} {re.sub(r'·[^）]*', '', x['paper'])} 阅读{x['part']} ")), None)
        if not p:
            lines += [f'## {mp4.name}', '', '- ❌ 找不到对应的文章数据', '']
            allok = False
            continue
        res = check(mp4, p, T[p['id']])
        good = all(r[1] for r in res)
        allok &= good
        print(('✅ ' if good else '❌ ') + mp4.name, flush=True)
        lines += [f"## {'✅' if good else '❌'} {mp4.stem}", '']
        lines += [f"- {'✅' if c else '❌'} {n}：{d}" for n, c, d in res]
        lines.append('')
    lines.insert(3, f"**总结：{'全部视频符合所有铁律' if allok else '有视频不符合，见下方 ❌ 项'}**\n")
    (FINAL / '核查报告.md').write_text('\n'.join(lines), 'utf-8')
    print('报告：', FINAL / '核查报告.md')
    sys.exit(0 if allok else 1)


if __name__ == '__main__':
    main()
