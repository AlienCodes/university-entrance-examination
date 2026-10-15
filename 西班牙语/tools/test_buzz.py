"""电磁音检查自身的双向验证（踩坑 37）：该过的必须过、该报的必须报。

    /opt/ttsenv/bin/python 西班牙语/tools/test_buzz.py

① 用户确认过“没有电磁音”的中考男声 40 篇（中考/audio/cet4_male）：必须全部通过；
② 埋雷：在其中 5 篇里人为加入 (a) Kokoro 原来那样的单频细线（9600 Hz，高出周围约 11 dB）、(b) Supertonic 那样的帧频梳状线
   （supertonic3_comb.json 的 51 条，每条与原 Supertonic 实测强度相当）：每一处都必须报出来；
③ 有 西班牙语/audio 成品时：每个 MP3 必须通过。
④ 短文（2026-10-15 补）：从上面埋雷的 5 篇里切出 8 秒、12 秒、20 秒的片段（只取有声部分约这么长的连续几句），各埋 (a)、(b) 两种雷：每一处都必须报出来。
⑤ 全频段“两半都在才算”的确认，双向验证：在每 4 篇取 1 篇（共 10 篇）的 12 秒片段里加 0.25 秒的哨音（Supertonic 短文里实测过的那种；频率选原音频在整段和前后两半
   都干净的地方，先试 11054 Hz），幅度校准到整段长时谱高出约 10 dB——只在前一半出现：必须不报（不是固定频点）；
   前后两半各出现一次、同一频率：必须报。
另外打印用户确认过的音频切成短片段时的通过率（只看，不判）。任何一条不符合就报错退出。
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import buzz  # noqa: E402


def tone_at(a, sr, items, f, rel_db):
    """在有声部分加一条频率 f 的细线，强度约为该频率附近语音长时谱的 rel_db（相对）。"""
    from scipy.signal import welch
    sp = np.concatenate([a[int(s['start'] * sr): int(s['end'] * sr)] for s in items]).astype(np.float64)
    fr, P = welch(sp, sr, nperseg=65536)
    near = np.median(P[(fr > f - 22) & (fr < f + 22)])
    amp = np.sqrt(2 * near * (fr[1] - fr[0]) * 1.5 * 10 ** (rel_db / 10))   # 汉宁窗等效噪声带宽 1.5 个频点
    t = np.arange(len(a)) / sr
    on = np.zeros(len(a))
    for s in items:
        on[int(s['start'] * sr): int(s['end'] * sr)] = 1
    return amp * np.sin(2 * np.pi * f * t + np.random.default_rng(int(f)).uniform(0, 6.28)) * on


def chunks(items, L, n=2):
    """有声部分约 L 秒的连续几句，最多 n 段。"""
    out, j0 = [], 0
    while j0 < len(items) and len(out) < n:
        tot, j = 0.0, j0
        while j < len(items) and tot < L:
            tot += items[j]['end'] - items[j]['start']
            j += 1
        if tot < 0.8 * L:
            break
        out.append(items[j0:j])
        j0 = j
    return out


def quiet_freq(a, sr, items, cands=(11054.0, 9300.0, 7400.0, 5300.0, 3700.0, 2600.0)):
    """原音频在整段、前一半、后一半里 ±40 Hz 内都没有明显峰（< 4 dB）的频率：埋在这里，验证的只是“两半”这条规则本身。"""
    sp = buzz._voiced(a, sr, items)
    h = len(sp) // 2
    n = min(65536, h)
    specs = [buzz._rel(sp, sr), buzz._rel(sp[:h], sr, n), buzz._rel(sp[h:], sr, n)]
    for f in cands:
        if all(r[(fr > f - 40) & (fr < f + 40)].max() < 4.0 for fr, r in specs):
            return f
    return None


def at_voiced(items, frac, dur=0.25):
    """有声部分（各句首尾相接）的 frac 处，换回原时间轴上的秒数；保证从这里起 dur 秒都在同一句里（不落进停顿）。"""
    goal = frac * sum(s['end'] - s['start'] for s in items)
    for s in items:
        d = s['end'] - s['start']
        if goal <= d:
            return max(s['start'], min(s['start'] + goal, s['end'] - dur - 0.02))
        goal -= d
    return items[-1]['end'] - dur - 0.02


def burst_at(a, sr, items, f, target_db, starts, dur=0.25):
    """在 starts（秒）处各加一段 dur 秒、频率 f 的哨音（汉宁窗包络）；幅度逐步校准到整段长时谱在 f 处高出周围约 target_db。"""
    n = int(dur * sr)
    tone = np.hanning(n) * np.sin(2 * np.pi * f * np.arange(n) / sr)
    x = np.zeros(len(a))
    for t0 in starts:
        i = int(t0 * sr)
        x[i:i + n] += tone
    amp = 0.05 * np.sqrt(np.mean(buzz._voiced(a, sr, items) ** 2))
    for _ in range(5):
        fr, r = buzz._rel_spectrum((a + amp * x).astype(np.float32), sr, items)
        got = r[(fr > f - 10) & (fr < f + 10)].max()
        amp *= 10 ** ((target_db - got) / 20)
    return amp * x


def short_tests(a, sr, items, comb, bad, tally, pid, planted=True):
    period, H = comb
    for L in (8, 12, 20):
        for sub in chunks(items, L):
            e0 = buzz.check(a, sr, sub)[3]
            tally['clean'] += 1
            tally['clean_ok'] += not e0
            tally['clean_old'] += buzz.scan(a, sr, sub, top=1)[0][1] <= buzz.FULL_MAX_DB and buzz.comb_excess(a, sr, sub) <= buzz.COMB_MAX_DB
            for name, x in () if not planted else (('9600 Hz 单频细线', a.astype(np.float64) + tone_at(a, sr, sub, 9600.0, 11.0)),
                            ('帧频梳状线', a.astype(np.float64) + sum(tone_at(a, sr, sub, h * 44100 / period, 8.0) for h in H))):
                tally['planted'] += 1
                if buzz.check(x.astype(np.float32), sr, sub)[3]:
                    tally['caught'] += 1
                else:
                    bad.append(f'{pid} {L} 秒片段：埋的{name}没查出')
            if L != 12:
                continue
            if e0:                                                   # 前提：原片段本身通过（否则分不清是谁触发的）
                tally['whistle_skip'] += 1
                continue
            f = quiet_freq(a, sr, sub)
            if f is None:
                tally['whistle_skip'] += 1
                continue
            t1, t2 = at_voiced(sub, 0.2), at_voiced(sub, 0.7)       # 有声部分的 20%、70% 处：分别在前一半、后一半
            one = a.astype(np.float64) + burst_at(a, sr, sub, f, 10.0, [t1])
            two = a.astype(np.float64) + burst_at(a, sr, sub, f, 10.0, [t1, t2])
            r1 = buzz.report(one.astype(np.float32), sr, sub)
            r2 = buzz.report(two.astype(np.float32), sr, sub)
            tally['whistle'] += 1
            if r1['r'] <= buzz.FULL_MAX_DB or r2['r'] <= buzz.FULL_MAX_DB:
                bad.append(f'{pid} 12 秒片段：哨音没把整段长时谱顶过 {buzz.FULL_MAX_DB} dB（{r1["r"]:.1f} / {r2["r"]:.1f}），这条验证无效，请加大')
            elif any('前后两半都在' in e for e in r1['errs']):
                bad.append(f'{pid} 12 秒片段：只在前一半出现的哨音被判成电磁音：{r1["errs"]}')
            elif not any('前后两半都在' in e for e in r2['errs']):
                bad.append(f'{pid} 12 秒片段：前后两半都有的同频哨音没查出（两半较小值 {r2["pr"]}）')
            else:
                tally['whistle_ok'] += 1


def main():
    T = json.loads((ROOT / '中考/audio/timings.json').read_text('utf-8'))['cet4_male']
    files = [(k, v) for k, v in sorted(T.items()) if isinstance(v, dict) and 'file' in v]
    assert len(files) == 40, len(files)
    bad = []
    comb = buzz.load_comb('supertonic3_comb.json')
    caught = 0
    tally = dict.fromkeys(('clean', 'clean_ok', 'clean_old', 'planted', 'caught', 'whistle', 'whistle_ok', 'whistle_skip'), 0)
    for i, (pid, d) in enumerate(files):
        a, sr = sf.read(str(ROOT / '中考/audio' / d['file']), dtype='float32')
        a = a.mean(1) if a.ndim > 1 else a
        items = d['sentences']
        f0, r, c, e = buzz.check(a, sr, items)
        if e:
            bad.append(f'{pid} 用户确认过的音频被判不合格：{e}')
        if i % 8 == 0:                                                   # 5 篇埋雷
            x = a.astype(np.float64) + tone_at(a, sr, items, 9600.0, 11.0)
            if not buzz.check(x.astype(np.float32), sr, items)[3]:
                bad.append(f'{pid} 埋的 9600 Hz 单频细线没查出')
            else:
                caught += 1
            period, H = comb
            x = a.astype(np.float64) + sum(tone_at(a, sr, items, h * 44100 / period, 8.0) for h in H)
            if not buzz.check(x.astype(np.float32), sr, items)[3]:
                bad.append(f'{pid} 埋的帧频梳状线没查出')
            else:
                caught += 1
        if i % 4 == 0:                                                   # 短片段：其中 5 篇埋雷，10 篇做哨音双向验证
            short_tests(a, sr, items, comb, bad, tally, pid, planted=i % 8 == 0)
    print(f'用户确认过的 40 篇：{40 - sum("用户确认" in b for b in bad)} 篇通过；埋雷 10 处查出 {caught} 处')
    print(f'短片段（8 / 12 / 20 秒）：埋雷 {tally["planted"]} 处查出 {tally["caught"]} 处；'
          f'哨音“只在一半不报、两半都在要报”{tally["whistle"]} 组对 {tally["whistle_ok"]} 组'
          f'（另有 {tally["whistle_skip"]} 段原片段本身没通过或找不到干净频率，没用来做这项）')
    if tally['whistle'] < 5:
        bad.append(f'哨音双向验证只做成 {tally["whistle"]} 组（至少 5 组），这项验证无效')
    print(f'（只看不判）用户确认过的音频切成短片段：{tally["clean"]} 段里通过 {tally["clean_ok"]} 段；'
          f'不做“两半都在”确认的话只通过 {tally["clean_old"]} 段')
    es = HERE.parent / 'audio' / 'timings.json'
    if es.exists():
        for v, d in json.loads(es.read_text('utf-8')).items():
            if not isinstance(d, dict):
                continue
            for pid, x in d.items():
                a, sr = sf.read(str(HERE.parent / 'audio' / x['file']), dtype='float32')
                e = buzz.check(a.mean(1) if a.ndim > 1 else a, sr, x['sentences'])[3]
                print(f'西班牙语成品 {v} {pid}：', '通过' if not e else e)
                if e and not x.get('draft_issues'):
                    bad.append(f'西班牙语成品 {v} {pid} 不合格：{e}')
    if bad:
        raise SystemExit('电磁音检查自测不通过：\n' + '\n'.join(bad))
    print('电磁音检查自测全部通过')


if __name__ == '__main__':
    main()
