"""从用户本人的录音里挑声音克隆的参考片段（程序挑，不靠人听；Qwen3-TTS Base 的 clone_ref 用）。

用户 2026-10-30：配音改用本人的声音；本人同意录音与声音公开使用（原话：“我的声音可以被别人拿去使用，这个无所谓……
我的声音是完全可以公开使用的”），所以参考片段与录音可以进公开仓库。

做法（全部程序判断，零 token）：
  ① 解码成 24 kHz 单声道，整体按 BS.1770 拉到 −23 LUFS（只为量，参考片段另存）；
  ② 按停顿（≥ 0.35 秒）切成语句；每句：削波、底噪（相邻停顿）、呼吸处数（tools/tts/去呼吸.breath_check）、
     基频中位数、SenseVoice 识别（文字 + 事件标签：不是 Speech 的——笑、咳嗽、音乐——一律不要）；
  ③ 相邻语句拼成 MIN—MAX 秒的窗口，硬条件：无削波、全是 Speech、底噪 ≤ −55 dBFS、基频中位数与全录音中位数差 ≤ 3 半音
     （防混进别人的声音）、语速在全录音中位数的 0.7—1.35 倍；按 底噪低、呼吸少、语调起伏（讲课感）、中英混说 打分，取最好的；
  ④ build_ref：参考片段本身也去呼吸（克隆会学参考里的换气），停顿超过 0.6 秒的缩到 0.6 秒；ref_text 用带标点的识别结果。
输出：tts/音色/<名>.json（录音地址 + spans + ref_text；qwen_synth 的 clone_ref 用 build_ref 现做参考，不另存音频）+ <名>.挑选.md（前 5 名窗口）。
用法：/opt/ttsenv/bin/python 高考语法填空/tools/挑参考.py --录音 录音1.m4a [录音2 …] --名 用户本人 [--秒 12 25]
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools/tts'), str(Path(__file__).parent)]
import 去呼吸 as BR  # noqa: E402

SR = 24000
VOICE_DIR = ROOT / '高考语法填空/tts/音色'
RELEASE = 'https://github.com/aliencodes/university-entrance-examination/releases/download/user-voice'


def seams(x, min_run=0.005):
    """剪辑接缝：连续数字零（|x| < 1e-6）≥ 5 ms 的段 [(起样本, 止样本)]。用户自己剪掉呼吸后留下的整段零静音就是这种。"""
    z = np.r_[0, (np.abs(x) < 1e-6).astype(np.int8), 0]
    d = np.diff(z)
    st, en = np.where(d == 1)[0], np.where(d == -1)[0]
    k = (en - st) >= int(min_run * SR)
    return list(zip(st[k], en[k]))


def build_ref(x, spans):
    """录音（decode 的 24 kHz）里从第一句开头到最后一句结尾的原始连续音频（不剪不拼，句间停顿与底噪原样保留），−20 LUFS、峰值 ≤ 0.9。
    挑参考 与 qwen_synth（Actions 上合成时）都用它，参考片段不另存音频。片段里有剪辑接缝或呼吸就报错（不让模型学到断口和换气）。"""
    ref = np.array(x[spans[0][0]:spans[-1][1]], dtype=np.float32)
    if seams(ref):
        raise RuntimeError(f'参考片段里有剪辑接缝 {seams(ref)[:3]}')
    ref = (ref * 10 ** ((-20 - lufs(ref)) / 20)).astype(np.float32)
    ref = ref / max(1.0, float(np.abs(ref).max()) / 0.9)
    left = BR.breath_check(np.concatenate([np.zeros(SR // 4, np.float32), ref, np.zeros(SR // 4, np.float32)]), SR)
    if left:
        raise RuntimeError(f'参考片段里有呼吸 {left}')
    return ref


def decode(p):
    """录音 → 24 kHz 单声道 float32。WAV / FLAC 用 soundfile + soxr（GitHub 上的机器没有 ffmpeg；本机与 Actions 同一条路，样本位置一致），
    其他格式才用 ffmpeg。"""
    import soundfile as sf
    import soxr
    try:
        x, sr = sf.read(str(p), dtype='float32')
    except Exception:
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(p), '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'],
                             capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.float32).copy()
    x = x.mean(1) if x.ndim > 1 else x
    return soxr.resample(x, sr, SR, quality='VHQ').astype(np.float32) if sr != SR else x.astype(np.float32)


def lufs(x):
    import pyloudnorm as pyln
    return pyln.Meter(SR).integrated_loudness(x.astype(np.float64))


def utterances(x, min_pause=0.25):
    lvl, per, H, W = BR._frames(x, SR)
    ref = np.percentile(lvl, 99)
    floor = np.percentile(lvl, 10)
    act = lvl > max(floor + 15, ref - 40)
    spans, i, n = [], 0, len(lvl)
    while i < n:
        if not act[i]:
            i += 1
            continue
        j = i
        while j < n and act[j]:
            j += 1
        if spans and (i - spans[-1][1]) * H / SR < min_pause:
            spans[-1][1] = j
        else:
            spans.append([i, j])
        i = j
    return [(a * H, min(len(x), b * H + W)) for a, b in spans if (b - a) * H / SR >= 0.4], lvl, H


def f0_median(x):
    import librosa
    f0, v, _ = librosa.pyin(x, fmin=65, fmax=400, sr=SR, frame_length=1024)
    f = f0[v & ~np.isnan(f0)]
    return (float(np.median(f)), float(np.std(12 * np.log2(f / np.median(f))))) if len(f) > 20 else (None, None)


class ASR:
    def __init__(self):
        import glob
        import sherpa_onnx
        d = Path(glob.glob(str(ROOT / 'tools/tts/models/sherpa-onnx-sense-voice-*'))[0])
        self.r = sherpa_onnx.OfflineRecognizer.from_sense_voice(model=str(d / 'model.int8.onnx'), tokens=str(d / 'tokens.txt'),
                                                                use_itn=True, num_threads=4)

    def __call__(self, x):
        import soxr
        s = self.r.create_stream()
        s.accept_waveform(16000, soxr.resample(x, SR, 16000).astype(np.float32))
        self.r.decode_stream(s)
        r = s.result
        tags = re.findall(r'<\|([^|]*)\|>', r.text + str(getattr(r, 'event', '')) + str(getattr(r, 'emotion', '')))
        return re.sub(r'<\|[^|]*\|>', '', r.text).strip(), tags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--录音', nargs='+', required=True)
    ap.add_argument('--名', required=True)
    ap.add_argument('--秒', nargs=2, type=float, default=[4.5, 10])
    ap.add_argument('--个数', type=int, default=3)
    a = ap.parse_args()
    asr = ASR()
    U = []
    for k, p in enumerate(a.录音):
        x = decode(p)
        x = (x * 10 ** ((-23 - lufs(x)) / 20)).astype(np.float32)
        spans, lvl, H = utterances(x)
        cut = np.zeros(len(x) + 1, np.int8)                  # 接缝样本的前缀和：窗口里有没有接缝 O(1) 判断
        for s0, e0 in seams(x):
            cut[s0 + 1:e0 + 1] = 1
        cut = np.cumsum(cut, dtype=np.int64)
        for s, e in spans:
            y = x[s:e]
            pre = x[max(0, s - int(0.3 * SR)):s]
            text, tags = asr(y)
            f0, f0sd = f0_median(y)
            U.append({'file': k, 's': s, 'e': e, 'x': x, 'cut': cut, 'text': text, 'tags': tags,
                      'clip': int((np.abs(y) > 0.98).sum()),
                      'floor': float(10 * np.log10(np.mean(pre ** 2) + 1e-20)) if len(pre) > SR // 10 else -90.0,
                      'breath': len(BR.breath_check(np.concatenate([np.zeros(SR // 4, np.float32), y * 10 ** (7 / 20),
                                                                     np.zeros(SR // 4, np.float32)]), SR)),
                      'f0': f0, 'f0sd': f0sd,
                      'rate': len(re.findall(r'[一-鿿]|[A-Za-z]+', text)) / ((e - s) / SR)})
        print(f'{p}：{len(x) / SR:.0f} 秒，{len(spans)} 句', flush=True)
    f0s = [u['f0'] for u in U if u['f0']]
    g_f0 = float(np.median(f0s))
    rates = np.array([u['rate'] for u in U])
    r_lo, r_hi = np.median(rates) * 0.7, np.median(rates) * 1.35

    def ok(u):
        bad = []
        if u['clip']:
            bad.append('削波')
        if not any(t == 'Speech' for t in u['tags']) or any(t in ('Laughter', 'Cough', 'BGM', 'Applause', 'Sneeze', 'Cry') for t in u['tags']):
            bad.append(f"事件 {u['tags']}")
        if u['breath']:
            bad.append('呼吸')
        if u['floor'] > -50:
            bad.append(f"底噪 {u['floor']:.0f}")
        if not u['f0'] or abs(12 * np.log2(u['f0'] / g_f0)) > 3:
            bad.append('基频异常')
        if not (r_lo <= u['rate'] <= r_hi):
            bad.append('语速异常')
        if not u['text']:
            bad.append('识别为空')
        return bad

    W = []
    for i in range(len(U)):
        for j in range(i, len(U)):
            if U[j]['file'] != U[i]['file']:
                break
            dur = (U[j]['e'] - U[i]['s']) / SR
            if dur > a.秒[1]:
                break
            if dur < a.秒[0]:
                continue
            us = U[i:j + 1]
            if any(ok(u) for u in us):
                continue
            m = int(0.04 * SR)
            c = U[i]['cut']
            if c[min(len(c) - 1, U[j]['e'] + m)] - c[max(0, U[i]['s'] - m)]:
                continue                                       # 窗口（两头各多 0.04 秒）里有剪辑接缝
            text = ''.join(u['text'] for u in us)
            mix = bool(re.search(r'[A-Za-z]{2,}', text)) and bool(re.search(r'[一-鿿]', text))
            score = (-np.mean([u['floor'] for u in us]) / 10 - 2 * sum(u['breath'] for u in us)
                     + float(np.mean([u['f0sd'] or 0 for u in us])) + (1.5 if mix else 0) - abs(dur - 8) / 10)
            W.append((round(float(score), 2), i, j, dur, text))
    if not W:
        rej = {}
        for u in U:
            for b in ok(u):
                rej[b.split(' ')[0]] = rej.get(b.split(' ')[0], 0) + 1
        raise SystemExit(f'没有合格的 {a.秒[0]}—{a.秒[1]} 秒窗口（不放宽条件）。各句不合格原因计数：{rej}')
    W.sort(reverse=True)
    picked = []
    for w in W:                                        # 前 N 名，互不重叠
        if all(w[2] < p[1] or w[1] > p[2] for p in picked):
            picked.append(w)
        if len(picked) == a.个数:
            break
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    for n, (score, i, j, dur, text) in enumerate(picked, 1):
        spans = [[int(U[i]['s']) - int(0.03 * SR), int(U[j]['e']) + int(0.03 * SR)]]   # 两头各留 30 ms（窗口 ±0.04 秒内无接缝）
        src = Path(a.录音[U[i]['file']])
        ref = build_ref(decode(src), spans)          # 与合成时同一个函数、同一份原始解码，先在本机试一遍
        meta = {'说明': f'用户本人录音（Release user-voice 的 {src.name}）里程序挑出的参考片段（挑参考.py：无削波、全是语音、没有剪辑接缝、'
                      '没有呼吸、底噪低、基频一致、语速正常，按底噪、语调起伏、中英混说打分）。不另存音频：合成时 qwen_synth 从 Release 下载录音，'
                      '用 挑参考.build_ref 按 spans 取原始连续音频（不剪不拼）。用户 2026-10-30 同意声音克隆与公开使用。',
                'source': src.name, 'source_url': f'{RELEASE}/{src.name}', 'spans': spans, 'ref_text': text,
                'window_sec': [round(U[i]['s'] / SR, 2), round(U[j]['e'] / SR, 2)], 'score': score, 'sec': round(len(ref) / SR, 2)}
        (VOICE_DIR / f'{a.名}_{n}.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), 'utf-8')
        print(f'参考片段 {n}：{src.name} {meta["window_sec"]}（{meta["sec"]} 秒，分 {score}）ref_text：{text}')
    lines = [f'# 参考片段挑选（{a.名}）', '', f'全录音 {len(U)} 句，基频中位数 {g_f0:.0f} Hz，合格窗口 {len(W)} 个。前 10 名（前 {len(picked)} 个互不重叠的已选用）：', '',
             '| 分 | 文件 | 起—止（秒） | 长 | 文字 |', '|---|---|---|---|---|']
    for sc, i2, j2, d2, t2 in W[:10]:
        lines.append(f"| {sc} | {Path(a.录音[U[i2]['file']]).name} | {U[i2]['s'] / SR:.1f}—{U[j2]['e'] / SR:.1f} | {d2:.1f} | {t2} |")
    (VOICE_DIR / f'{a.名}.挑选.md').write_text('\n'.join(lines) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
