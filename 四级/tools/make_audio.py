"""生成四级 60 篇的朗读音频（男声 cet4_male：am_fenrir 0.6 + am_onyx 0.4，语速 0.95，用户 2026-10-07 选定）。

    /opt/ttsenv/bin/python 四级/tools/make_audio.py            # 全部
    /opt/ttsenv/bin/python 四级/tools/make_audio.py c01 c02    # 指定篇目

直接复用高考 tools/tts/gaokao_tts.py 的整套流程（分句分段合成、统一电平、压缩限幅、−16 LUFS、
成品 MP3 按 ITU-R BS.1770 独立测量响度，不合格不输出；片头 1.5 秒、句间 0.8 秒、结尾 2 秒），
只把输入换成 四级/仔细阅读/sents.json 和 四级/ann/ 的中文翻译，输出到 四级/audio/。
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'tts'))
import gaokao_tts as G  # noqa: E402

C4 = ROOT / '四级'
G.ANN = C4 / 'ann'
VOICE = 'cet4_male'


def stem(p):
    return f"{p['id']}_{p['paper'].replace(' ', '_')}_{p['passage'].replace(' ', '')}"


G.file_stem = stem


# 用户要求（2026-10-07）：冒号、分号、破折号处的停顿与逗号完全一样（高考版分号、冒号是逗号的 1.4 倍）。
# 复制高考 synth_sentence，只去掉 1.4 倍，其余（分段、补标点、淡入淡出）不变。
def synth_sentence(read, key, engine, pron, style, speed, cfg):
    cp = cfg.get('clause_pause', 0)
    # 原文破折号两侧不留空格（pesticides—in fact），高考的切分规则要求标点后有空格，会漏掉这里的停顿；先补一个空格再切
    read = G.re.sub(r'—(?=\S)', '— ', read)
    parts = [x for x in G.CLAUSE.split(read) if x.strip()] if cp else [read]
    merged = []
    for x in parts:
        if merged and len(merged[-1].split()) < 2:
            merged[-1] += ' ' + x
        else:
            merged.append(x)
    merged = [x if i == len(merged) - 1 or G.re.search(r'[,;:—.!?]["”’)]*$', x) else x + ','
              for i, x in enumerate(merged)]
    out, spans, t = [], [], 0.0
    for i, x in enumerate(merged):
        seg = G.fade(G.level(engine.synth(pron.phonemes(x, key), style, speed)))
        spans.append((t, t + len(seg) / G.SR))
        out.append(seg)
        t += len(seg) / G.SR
        if i < len(merged) - 1:
            out.append(np.zeros(int(cp * G.SR), np.float32))          # 逗号、分号、冒号、破折号一律同样长
            t += int(cp * G.SR) / G.SR
    return np.concatenate(out), spans


# 低沉男声的能量集中在低频，按普通电平（RMS）统一各段时，人耳听到的响度（K 加权）仍有起伏，
# 首篇试做短时响度波动 1.17 LU，超过铁律上限 1.0。改为按 K 加权后的有声电平统一每段（只用于四级，
# 不影响已定稿的高考音频），检查标准一项不放宽。
import numpy as np  # noqa: E402
import pyloudnorm as pyln  # noqa: E402
_meter = pyln.Meter(G.SR)
_K = -26.0


def level_k(x, target=None):
    f = x.astype(np.float64)
    for flt in _meter._filters.values():
        f = flt.apply_filter(f)
    g = np.clip(_K - G.active_db(f.astype(np.float32)), -12, 12)
    return (x * 10 ** (g / 20)).astype(np.float32)


G.level = level_k
G.synth_sentence = synth_sentence
_comp = G.compress
_meter48 = pyln.Meter(G.OUT_SR)


def leveler(x, sr, win=1.0, rng=4.0, smooth=0.4):
    """慢速电平控制（类似广播 AGC）：按 1 秒窗的 K 加权电平把有声部分拉到同一水平，
    增益限制在 ±4 dB 并平滑，停顿处保持前值、不放大底噪。"""
    f = x.astype(np.float64)
    for flt in _meter48._filters.values():
        f = flt.apply_filter(f)
    B = int(0.05 * sr)
    n = len(x) // B
    e = np.mean(f[:n * B].reshape(n, B) ** 2, axis=1)
    eb = 10 * np.log10(e + 1e-12)
    on = (eb > np.percentile(eb, 99) - 30).astype(float)       # 只统计有声的 50ms 块，窗口里的停顿不拉低电平
    w = int(win / 0.05)
    num = np.convolve(e * on, np.ones(w), mode='same')
    den = np.convolve(on, np.ones(w), mode='same')
    lv = 10 * np.log10(num / np.maximum(den, 1) + 1e-12)
    act = den >= 0.3 * w                                       # 窗口内有声部分不足 30% 时不调整，保持前值
    ref = np.median(lv[act])
    g = np.zeros(n)
    last = 0.0
    for i in range(n):
        if act[i]:
            last = float(np.clip(ref - lv[i], -rng, rng))
        g[i] = last
    a = int(smooth / 0.05)
    g = np.convolve(np.pad(g, (a, a), mode='edge'), np.ones(2 * a + 1) / (2 * a + 1), mode='valid')
    gs = np.repeat(10 ** (g / 20), B)
    gs = np.concatenate([gs, np.full(len(x) - len(gs), gs[-1])])
    return (x * gs).astype(np.float32)


G.compress = lambda x, sr: leveler(_comp(x, sr), sr)


def main(ids):
    vcfg = json.loads((G.HERE / 'voices.json').read_text('utf-8'))[VOICE]
    P = json.loads((C4 / '仔细阅读' / 'sents.json').read_text('utf-8'))
    if ids:
        byid = {p['id']: p for p in P}
        P = [byid[i] for i in ids]                 # 按给定顺序生成（用户要求从 2026 年往前做）
    out = C4 / 'audio'
    tpath = out / 'timings.json'
    timings = json.loads(tpath.read_text('utf-8')) if tpath.exists() else {}
    engine, pron = G.Engine(), G.Pronouncer()
    fails = []
    for i, p in enumerate(P, 1):
        t0 = time.time()
        try:
            r = G.render_passage(p, VOICE, vcfg, engine, pron, out / VOICE)
        except RuntimeError as e:                 # 检查不通过的不输出文件，记下来最后统一处理
            fails.append(str(e))
            print('未通过：', e, flush=True)
            continue
        r.update(name=f"{p['paper']} {p['passage']}")
        timings.setdefault(VOICE, {})[p['id']] = r
        out.mkdir(parents=True, exist_ok=True)
        tpath.write_text(json.dumps(timings, ensure_ascii=False, indent=1), 'utf-8')
        print(f'[{i}/{len(P)}] {r["file"]}  {r["duration"]:.1f}s，用时 {time.time() - t0:.0f}s', flush=True)
    if fails:
        sys.exit(f'{len(fails)} 篇未通过检查：\n' + '\n'.join(fails))


if __name__ == '__main__':
    main(sys.argv[1:])
