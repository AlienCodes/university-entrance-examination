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


def find_mp3(mp4, tm):
    """成品视频用的 MP3：从视频所在目录往上找 <某一级>/audio/<tm['file']>（中考/最终视频 → 中考/audio，最终视频 → audio），
    找不到再在仓库里所有 audio 目录找（样片目录等）。返回候选列表（可能为空）。专八、中考引擎在截图指纹里不能改，
    所以由 check 自己找，不靠调用者传（踩坑 87）。"""
    f = tm.get('file')
    if not f:
        return []
    out = []
    d = Path(mp4).resolve().parent
    for _ in range(6):
        c = d / 'audio' / f
        if c.exists() and c not in out:
            out.append(c)
        if d == d.parent:
            break
        d = d.parent
    if not out:
        out = [c for c in [ROOT / 'audio' / f, *ROOT.glob(f'*/audio/{f}'), *ROOT.glob(f'*/*/*/audio/{f}')] if c.exists()]
    return out


def cert_check(mp4, tm, mp3_path=None):
    """音频合格证：旧成品放行；新音频核对 timings 里的合格证、MP3 旁的合格证文件、MP3 的 sha256（规则见 tools/tts/合格证.py）。"""
    from gaokao_tts import certificate_problems, is_legacy
    if is_legacy(tm):
        return []
    cands = [Path(mp3_path)] if mp3_path is not None else find_mp3(mp4, tm)
    if not cands:
        return [f"找不到这个视频用的 MP3（{tm.get('file')}），无法核对合格证"]
    tries = [certificate_problems(tm, c) for c in cands]
    return next((t for t in tries if not t), tries[0])


def check(mp4, p, tm, mp3_path=None):
    from gaokao_tts import verify_loudness, LIMITS
    res = []
    ok = lambda name, cond, detail: res.append((name, bool(cond), detail))

    # 1. 文件名
    paper = re.sub(r'·[^）]*', '', p['paper'])
    ok('文件名：年份 试卷 篇目 题目', mp4.name.startswith(f"{p['year']} {paper} 阅读{p.get('part', '')} {p['title']}"), mp4.name)
    # 2. 分辨率与时长
    info = json.loads(run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height,duration',
                           '-of', 'json', str(mp4)]))['streams']
    v = next(s for s in info if s['codec_type'] == 'video')
    a = next(s for s in info if s['codec_type'] == 'audio')
    w, h = int(v['width']), int(v['height'])
    ok('分辨率 ≥ 2K 且 16:9', w >= 2560 and w * 9 == h * 16, f'{w}×{h}')
    vd, ad = float(v['duration']), float(a['duration'])
    ok('画面与声音等长', abs(vd - ad) < 0.1, f'画面 {vd:.2f}s，声音 {ad:.2f}s')
    # 流畅：逐帧检查时间戳，帧间隔必须恒定（无卡顿、无跳帧、无重复帧时间）
    pts = sorted(float(x) for x in run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'packet=pts_time',
                                        '-of', 'csv=p=0', str(mp4)]).split() if x and x != 'N/A')
    gaps = np.diff(pts)
    ok('画面流畅（帧间隔恒定 1/30 秒）', len(gaps) and np.allclose(gaps, gaps[0], atol=1e-3) and abs(gaps[0] - 1 / 30) < 1e-3,
       f'{len(pts)} 帧，帧间隔 {gaps.min():.4f}–{gaps.max():.4f} 秒')
    apts = sorted(float(x) for x in run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'packet=pts_time,duration_time',
                                         '-of', 'csv=p=0', str(mp4)]).replace(',', ' ').split()[0::2] if x != 'N/A')
    ag = np.diff(apts)
    ok('声音连续（无断档）', len(ag) and ag.max() < 0.05, f'音频包间隔最大 {ag.max() * 1000:.1f} 毫秒')

    sents = [s for para in p['paras'] for s in para]
    times = tm['sentences']
    ok('音频句数 = 文章句数', len(sents) == len(times), f'{len(times)} / {len(sents)}')
    # 踩坑：英文订正后如果没重新生成音频，画面上的英文和朗读的内容会不一致
    stale = [i + 1 for i, (s, t) in enumerate(zip(sents, times)) if s['en'] != t.get('text')]
    ok('朗读内容与画面英文逐句一致', not stale, f'不一致：第 {stale} 句' if stale else f'{len(sents)} 句全部一致')
    # 3. 每句至少一个生词
    empty = [i + 1 for i, s in enumerate(sents) if not s['w']]
    ok('每句至少标注一个单词', not empty, f'空句 {empty}' if empty else f'{len(sents)} 句全部有标注')

    x, sr = audio_of(mp4)
    seg = lambda t0, t1: x[int(t0 * sr):int(t1 * sr)]
    # 4. 开头 1.5 秒静音、结尾 2 秒静音
    lead = p.get('lead', 1.5)      # 第一句开口时刻：片头 1.5 秒；考研作文另有原题屏（片头 1.5 秒 + 原题屏，都静音，数据里的 lead）
    ok('开头静音 1.5 秒' if lead == 1.5 else f'开头静音 {lead:g} 秒（片头 1.5 秒 + 原题屏）', abs(times[0]['start'] - lead) < 0.01 and peak_db(seg(0, lead - 0.05)) < -60,
       f"第一句从 {times[0]['start']:.2f}s 开始，前 {lead - 0.05:.2f}s 峰值 {peak_db(seg(0, lead - 0.05)):.0f} dB")
    tail = ad - times[-1]['end']
    ok('结尾静音 2 秒', tail >= 1.999 and peak_db(seg(times[-1]['end'] + 0.1, ad)) < -60,
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
    from gaokao_tts import edge_span, is_legacy, certificate_problems
    cp = cert_check(mp4, tm, mp3_path)                # 合格证 + 旁证 + sha256（踩坑 87：以前不传 MP3，sha256 与旁证从没核过）
    ok('音频合格证（处理链版本、意群响度检查）', not cp, '；'.join(cp) if cp else ('旧成品（响度旧成品清单，不追溯）' if is_legacy(tm) else '合格'))
    rep, errs = verify_loudness(buf.getvalue(), times, -16.0, **({'span': edge_span(times, p['edge'])} if p.get('edge') else {}),
                                 fine=not is_legacy(tm))     # 意群级检查：2026-10-29 之后生成的一律查（踩坑 85），已发布的旧成品不追溯
    ok('响度一致（第一项检查）', not errs,
       f"整体 {rep['integrated_lufs']} LUFS，句间最大偏差 {rep['sentence_max_dev_lu']} LU，"
       f"短时波动 {rep['short_term_std_lu']} LU，峰值 {rep['peak_dbfs']} dBFS"
       + (f"；意群：比相邻意群最多小 {-rep.get('clause_nb_min_lu', 0):.2f} LU（上限 1.2），段尾最多小 {-rep.get('clause_tail_min_db', 0):.2f} dB（上限 4.0）"
          if 'clause_nb_min_lu' in rep else '') + ('；' + '；'.join(errs) if errs else ''))
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
    files = sorted(FINAL.glob('*.mp4'))
    # 踩坑记录：同一年同一试卷有两次考试（天津、上海、浙江），文件名必须能区分
    keys = [re.sub(r'\s\S+$', '', f.stem) for f in files]
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        print('❌ 文件名重复：', dup)
        allok = False
    for mp4 in files:
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


def duplicate_names(passages, name):
    """踩坑 11：同一项目里两篇的成品文件名相同（天津卷两次考试）。各项目 verify_all.py 原来用 {文件名: 篇目} 建表，重名时后一篇悄悄覆盖前一篇
    （防复发审计 2026-10-23 查出）；返回 {文件名: [篇目…]}，非空就不通过。"""
    seen = {}
    for p in passages:
        seen.setdefault(name(p), []).append(p['id'])
    return {k: v for k, v in seen.items() if len(v) > 1}
