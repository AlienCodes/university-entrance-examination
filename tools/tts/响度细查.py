"""意群级响度细查（用户 2026-10-29：“偶尔会有一个地方声音突然就小了一点”）。

意群 = 合成时按逗号、分号、冒号、破折号切开的一段（timings.json 里每句的 parts）。
每个意群按 ITU-R BS.1770 测响度（K 计权、400 ms 块、75% 重叠、−70 LUFS 绝对门限 + 相对本意群 −10 LU 门限，只算有声部分），
再比三样：
  d_med   与全篇意群中位数之差；
  d_nb    与前后相邻意群（能量平均）之差；
  d_sent  句内最小意群与本句其余部分之差（只对两个意群以上的句子）。
测量函数 clause_loudness 也被 gaokao_tts.verify_loudness 的意群检查调用（规则只写一处）。

用法：
  /opt/ttsenv/bin/python tools/tts/响度细查.py              # 全部已发布项目，输出分布与最差的若干处
  /opt/ttsenv/bin/python tools/tts/响度细查.py --项目 四级 --top 30
"""
import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

# 项目 → (timings.json, 音色键, 音频目录)
PROJECTS = {
    '高考': ('audio/timings.json', 'female', 'audio'),
    '四级': ('四级/audio/timings.json', 'cet4_male', '四级/audio'),
    '六级': ('六级/audio/timings.json', 'cet4_male', '六级/audio'),
    '中考': ('中考/audio/timings.json', 'cet4_male', '中考/audio'),
    '考研': ('考研/audio/timings.json', 'cet4_male', '考研/audio'),
    '专八': ('专八/audio/timings.json', 'cet4_male', '专八/audio'),
    '四级作文': ('四级作文/audio/timings.json', 'cet4_male', '四级作文/audio'),
    '六级作文': ('六级作文/audio/timings.json', 'cet4_male', '六级作文/audio'),
    '考研作文': ('考研作文/audio/timings.json', 'cet4_male', '考研作文/audio'),
}


def kweight(a, sr):
    import pyloudnorm as pyln
    f = np.asarray(a, dtype=np.float64)
    for flt in pyln.Meter(sr)._filters.values():
        f = flt.apply_filter(f)
    return f


def gated(z2, sr, a, b):
    """z2：K 计权后的平方信号。返回 [a, b) 秒的 BS.1770 门限响度（LUFS）；有声部分不足一个块时按整段能量算。"""
    i0, i1 = int(a * sr), int(b * sr)
    seg = z2[i0:i1]
    W, H = int(0.4 * sr), int(0.1 * sr)
    if len(seg) < W:
        return -0.691 + 10 * np.log10(np.mean(seg) + 1e-12) if len(seg) else -120.0
    c = np.concatenate([[0.0], np.cumsum(seg)])
    st = np.arange(0, len(seg) - W + 1, H)
    e = (c[st + W] - c[st]) / W
    L = -0.691 + 10 * np.log10(e + 1e-12)
    e = e[L > -70]
    if not len(e):
        return -120.0
    rel = -0.691 + 10 * np.log10(np.mean(e)) - 10
    e2 = e[-0.691 + 10 * np.log10(e) > rel]
    return float(-0.691 + 10 * np.log10(np.mean(e2)))


def clause_loudness(a, sr, items):
    """每个意群的响度。返回 [(句号 k, 意群序号 j, 起, 止, LUFS)]，按时间顺序。"""
    z2 = kweight(a, sr) ** 2
    out = []
    for n, it in enumerate(items, 1):
        for j, (s, e) in enumerate(it.get('parts') or [[it['start'], it['end']]]):
            out.append((it.get('k', n), j, s, e, gated(z2, sr, s, e)))
    return out


def _epow(xs):
    return 10 * np.log10(np.mean([10 ** (x / 10) for x in xs]))


def clause_stats(cl):
    """给 clause_loudness 的结果算三样差值。返回 [dict]。"""
    L = np.array([c[4] for c in cl])
    med = float(np.median(L))
    rows = []
    by_sent = {}
    for i, c in enumerate(cl):
        by_sent.setdefault(c[0], []).append(i)
    for i, (k, j, s, e, l) in enumerate(cl):
        nb = [L[x] for x in (i - 1, i + 1) if 0 <= x < len(L)]
        rows.append({'k': k, 'j': j, 'start': s, 'end': e, 'dur': round(e - s, 2), 'lufs': round(l, 2),
                     'd_med': round(l - med, 2), 'd_nb': round(l - _epow(nb), 2) if nb else 0.0, 'd_sent': None,
                     'last': j == len(by_sent[k]) - 1, 'n_in_sent': len(by_sent[k])})
    for k, idx in by_sent.items():
        if len(idx) < 2:
            continue
        lo = min(idx, key=lambda x: L[x])
        rows[lo]['d_sent'] = round(float(L[lo] - _epow([L[x] for x in idx if x != lo])), 2)
    return rows


# 意群级检查的阈值（踩坑 85；由新处理链样片的实测分布定，见 tools/防复发/方法进化记录.md「复盘 音频 意群响度」）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from 合格证 import FINE_LIMITS  # noqa: E402  上限只写一处（合格证.py）
NB_MIN_DUR, TAIL_MIN_DUR, TAIL_LEN = 0.8, 1.6, 0.8


def vowel_frames(a, sr):
    """10 ms 帧：K 计权电平 L（dB）与“元音帧”标记。元音帧 = 100—1000 Hz 能量 > 2 kHz 以上能量的 2 倍（低频占优），
    且不比前后 1 秒内最响处低 25 dB 以上。清辅音（s、ts、sh）、停顿不算，所以 “texts” 这类清辅音结尾不会被当成“变小”。
    按频谱判断，与处理端 gaokao_tts.voiced（按周期性）是两种独立的方法（踩坑 2）。"""
    from scipy.ndimage import maximum_filter1d
    a = np.asarray(a, dtype=np.float64)
    f = kweight(a, sr)
    H = int(0.01 * sr)
    n = len(a) // H
    L = 10 * np.log10(np.mean(f[:n * H].reshape(n, H) ** 2, axis=1) + 1e-12)
    W = int(0.02 * sr)
    fr = np.lib.stride_tricks.sliding_window_view(np.concatenate([a, np.zeros(W)]), W)[::H][:n] * np.hanning(W)
    S = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    fq = np.fft.rfftfreq(W, 1 / sr)
    lf = S[:, (fq >= 100) & (fq < 1000)].sum(axis=1)
    hf = S[:, fq >= 2000].sum(axis=1)
    return L, (lf > 2 * hf) & (L > maximum_filter1d(L, 201) - 25)


def tail_drop(L, ok, s, e):
    """意群 [s, e) 最后 TAIL_LEN 秒的元音帧平均电平 − 其余部分的元音帧平均电平（dB）；元音帧不足 80 ms 返回 None。"""
    i0, i1, im = int(s / 0.01), int(e / 0.01), int((e - TAIL_LEN) / 0.01)
    A, B = ok[im:i1], ok[i0:im]
    if A.sum() < 8 or B.sum() < 8:
        return None
    eL = 10 ** (L / 10)
    return float(10 * np.log10(eL[im:i1][A].mean()) - 10 * np.log10(eL[i0:im][B].mean()))


def fine_check(a, sr, items):
    """意群级响度检查（成品 MP3 / 视频音轨）：
    ① 每个意群（≥ 0.8 秒）与前后相邻意群的 BS.1770 响度差 ≥ −clause_nb LU（某个意群整体“突然小一截”）；
    ② 每个意群（≥ 1.6 秒）最后 0.8 秒的元音电平比本意群其余部分低不超过 clause_tail dB（意群末尾的词被收小）。
    返回 (报告, 问题列表)。"""
    st = clause_stats(clause_loudness(a, sr, items))
    L, ok = vowel_frames(a, sr)
    errs, worst_nb, worst_tail = [], 0.0, 0.0
    for r in st:
        if r['dur'] >= NB_MIN_DUR:
            worst_nb = min(worst_nb, r['d_nb'])
            if r['d_nb'] < -FINE_LIMITS['clause_nb']:
                errs.append(f"第{r['k']}句第{r['j'] + 1}段（{r['start']:.2f}s）比相邻意群小 {-r['d_nb']:.2f} LU")
        if r['dur'] >= TAIL_MIN_DUR:
            d = tail_drop(L, ok, r['start'], r['end'])
            if d is not None:
                worst_tail = min(worst_tail, d)
                if d < -FINE_LIMITS['clause_tail']:
                    errs.append(f"第{r['k']}句第{r['j'] + 1}段末尾（{r['end'] - TAIL_LEN:.2f}s 起）比本段其余部分小 {-d:.2f} dB")
    rep = {'clause_nb_min_lu': round(float(worst_nb), 2), 'clause_tail_min_db': round(float(worst_tail), 2)}
    if errs:
        errs = [f"意群响度：{len(errs)} 处（上限：比相邻意群小 {FINE_LIMITS['clause_nb']} LU、末尾小 {FINE_LIMITS['clause_tail']} dB）：" + '；'.join(errs[:5])]
    return rep, errs


def load_mp3(rel):
    """仓库里的成品 MP3：工作区里有就读，没有（skip-worktree / 浅克隆）就从 git 取。"""
    p = ROOT / rel
    if p.exists() and p.stat().st_size > 0:
        data = p.read_bytes()
    else:
        data = subprocess.run(['git', '-c', 'core.quotepath=off', 'show', f'HEAD:{rel}'], cwd=ROOT,
                              capture_output=True, check=True).stdout
    import soundfile as sf
    a, sr = sf.read(io.BytesIO(data), dtype='float64')
    return (a.mean(1) if a.ndim > 1 else a), sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--项目', nargs='*', default=list(PROJECTS))
    ap.add_argument('--top', type=int, default=25)
    ap.add_argument('--out', default=str(ROOT / 'tools/tts/响度细查结果.json'))
    args = ap.parse_args()
    allrows = []
    for proj in args.项目:
        tf, voice, adir = PROJECTS[proj]
        tm = json.loads((ROOT / tf).read_text('utf-8'))[voice]
        for pid, t in tm.items():
            try:
                a, sr = load_mp3(f"{adir}/{t['file']}")
            except subprocess.CalledProcessError:
                print(f'  {proj} {pid}：取不到 {t["file"]}，跳过', file=sys.stderr)
                continue
            for r in clause_stats(clause_loudness(a, sr, t['sentences'])):
                r.update(proj=proj, pid=pid)
                allrows.append(r)
        print(f'{proj}：{len({r["pid"] for r in allrows if r["proj"] == proj})} 篇', file=sys.stderr, flush=True)
    Path(args.out).write_text(json.dumps(allrows, ensure_ascii=False), 'utf-8')
    report(allrows, args.top)


def report(rows, top):
    import collections
    print('\n## 分布（意群时长 ≥ 0.6 秒）')
    print('项目 | 意群数 | d_med P1/P5/中位 | d_nb 最小 | d_nb≤-1.5 | d_nb≤-2 | d_sent≤-2 | d_sent≤-3')
    by = collections.defaultdict(list)
    for r in rows:
        if r['dur'] >= 0.6:
            by[r['proj']].append(r)
    for proj, rs in by.items():
        dm = np.array([r['d_med'] for r in rs])
        dn = np.array([r['d_nb'] for r in rs])
        ds = np.array([r['d_sent'] for r in rs if r['d_sent'] is not None])
        print(f"{proj} | {len(rs)} | {np.percentile(dm, 1):.2f}/{np.percentile(dm, 5):.2f}/{np.median(dm):.2f} | {dn.min():.2f} | "
              f"{(dn <= -1.5).sum()} | {(dn <= -2).sum()} | {(ds <= -2).sum()} | {(ds <= -3).sum()}")
    print(f'\n## 最差的 {top} 处（按 d_nb，意群 ≥ 0.6 秒）')
    for r in sorted([r for r in rows if r['dur'] >= 0.6], key=lambda r: r['d_nb'])[:top]:
        print(f"{r['proj']} {r['pid']} 第{r['k']}句第{r['j'] + 1}段 {r['start']:.2f}-{r['end']:.2f}s "
              f"d_nb {r['d_nb']} d_med {r['d_med']} d_sent {r['d_sent']} 末段={r['last']}")


if __name__ == '__main__':
    main()
