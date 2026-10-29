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
    for it in items:
        for j, (s, e) in enumerate(it.get('parts') or [[it['start'], it['end']]]):
            out.append((it['k'], j, s, e, gated(z2, sr, s, e)))
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
