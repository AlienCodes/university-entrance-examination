"""生成西班牙语朗读音频（和四级同一条处理链、同一套检查）。

    python 西班牙语/tools/make_audio.py es01                       # 用 voices.json 里 _final 指定的音色
    python 西班牙语/tools/make_audio.py es01 --voice 名字
    python 西班牙语/tools/make_audio.py es01 --voice 名字 --sample 试听.mp3 --sents 1-3   # 试听样片
（python = 工具包 .venv 里的 Python；开发机上是装好处理链依赖的那个环境。）

处理链沿用高考 tools/tts/gaokao_tts.py + 四级/tools/make_audio.py（不改它们，在这里组合）：
分段合成 → 去首尾空白 → 每段按 K 加权有声电平统一 → 5 毫秒淡入淡出 → 段间、句间插入精确的数字静音
→ 48 kHz → 去电磁音（Kokoro：固定频点 60 Hz 单向陷波；Supertonic：每段原始合成先减掉声码器帧频梳状线，见 buzz.py）→ 压缩 3:1 → 慢速电平
→ −16 LUFS → 前瞻限幅 → MP3 128k。
成品 MP3 独立测量：响度四项（铁律 2，见 loudness.py：3 秒短时波动只测朗读部分，不含片头片尾的规定静音）
+ 电磁音两项（梳状线自校准 + 全频段兜底，铁律 10，见 buzz.py），任何一项不合格就不输出。
时间：片头 1.5 秒、句间固定 0.8 秒、结尾 2 秒（铁律 3、4）。
标点：逗号、分号、冒号、破折号停顿 0.28 秒；列举的逗号不停顿（逐条判定写在 逗号停顿.json，铁律 11）。

音色在 voices.json：engine = kokoro（本进程）或 worker（用别的 Python 环境运行 engines/ 里的脚本，一次合成全部片段）。
worker 的 python 省略或写 "auto" = 用运行本程序的同一个 Python（工具包只有一个环境）；model_dir、ref_audio 写相对路径时
按 西班牙语/ 文件夹解析（工具包里写 models/supertonic3 这样的相对路径，换电脑、换文件夹都不用改）。绝对路径照旧可用。
列举的逗号按篇目登记在 逗号停顿.json：{"es01": {"2": [{"after": "lugares nuevos,", "why": …}]}, …}（键 = 篇目 id → 第几句）。
开始合成前先查音色能不能用（模型文件、参考录音、Python 包，voice_check.py，和 batch.py 同一份）：不能用就用中文说清楚缺什么、
怎么装，退出码 1，不会合成到一半才冒出一大段英文报错。
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ES = HERE.parent
ROOT = ES.parent
sys.path.insert(0, str(HERE))
import c4  # noqa: E402
import voice_check  # noqa: E402
import buzz  # noqa: E402
import loudness  # noqa: E402
G = c4.load('gaokao_tts', 'tools/tts/gaokao_tts.py')
C4A = c4.load('cet4_make_audio', '四级/tools/make_audio.py')   # 四级的 K 加权电平、慢速电平（导入时会改 G 的几个函数，下面全部明确重设）
sys.path.insert(0, str(HERE))                                    # 四级 make_audio 会把 四级/tools 插到最前面，这里恢复

VOICES = json.loads((HERE / 'voices.json').read_text('utf-8'))
PAUSES = {k: v for k, v in json.loads((HERE / '逗号停顿.json').read_text('utf-8')).items() if not k.startswith('_')}
if any(k.isdigit() for k in PAUSES):                              # 旧格式（句号直接放在最外层）会套到每一篇上，不许静默失效
    raise SystemExit('逗号停顿.json 是旧格式：请按篇目分组，写成 {"es01": {"2": [...]}, ...}')
SR, OUT_SR = G.SR, G.OUT_SR
CLAUSE = re.compile(r'(?<=[,;:—])\s+(?=\S)')
ALLOWED = re.compile(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ¿¡\s.,;:!?—\-]")


# ---------------------------------------------------------------- 文本 → 合成片段
def segments(text, k, pid=None):
    """按逗号、分号、冒号、破折号切成片段；逗号停顿.json 里这一篇（pid）登记为“不停顿”的逗号不切（整段一口气合成）。
    返回 [片段文字]，片段之间停顿 clause_pause 秒。"""
    if ALLOWED.search(text):
        raise RuntimeError(f'{pid or ""} 第 {k} 句朗读文本残留数字/符号/引号/括号：{text}')
    free = PAUSES.get(pid, {}).get(str(k), []) if pid else []
    parts = [x for x in CLAUSE.split(text) if x.strip()]
    used = set()
    merged = []
    for x in parts:
        prev = merged[-1] if merged else None
        key = next((f['after'] for f in free if prev is not None and prev.endswith(f['after'])), None)
        if key:
            used.add(key)
            merged[-1] += ' ' + x
        elif prev is not None and len(prev.split()) < 2:        # 单个词不单独成段，避免一字一顿
            merged[-1] += ' ' + x
        else:
            merged.append(x)
    miss = [f['after'] for f in free if f['after'] not in used]
    if miss:                                                     # 踩坑 17：修正匹配不到不能静默失效
        raise RuntimeError(f'逗号停顿.json：{pid} 第 {k} 句的 {miss} 匹配不到')
    return [x if i == len(merged) - 1 or re.search(r'[,;:—.!?]$', x) else x + ',' for i, x in enumerate(merged)]


# ---------------------------------------------------------------- 合成引擎
class KokoroES:
    def __init__(self, cfg):
        from kokoro_onnx import Kokoro
        m = ROOT / 'tools' / 'tts' / 'models'
        self.k = Kokoro(str(m / 'kokoro-v1.0.onnx'), str(m / 'voices-v1.0.bin'))
        spec = cfg['voice']
        tot = sum(spec.values())
        self.style = sum(self.k.get_voice_style(v) * (w / tot) for v, w in spec.items()).astype(np.float32)
        self.speed = cfg.get('speed', 1.0)

    def synth_all(self, texts):
        out = []
        for t in texts:
            a, sr = self.k.create(t, voice=self.style, speed=self.speed, lang='es', trim=True,
                                  sentence_pause=0.0, clause_pause=0.0)
            out.append((np.asarray(a, np.float32), sr))
        return out


PATH_KEYS = ('model_dir', 'ref_audio')


def resolve_cfg(cfg):
    """worker 设置里的 python 和路径：python 省略或 "auto" → 当前 Python；model_dir、ref_audio 是相对路径 → 按 西班牙语/ 解析。
    返回新的 dict（voices.json 原样不动，timings.json 里记的也是原样设置）。"""
    cfg = dict(cfg)
    if cfg.get('python') in (None, '', 'auto'):
        cfg['python'] = sys.executable
    for k in PATH_KEYS:
        if cfg.get(k) and not Path(cfg[k]).is_absolute():
            cfg[k] = str(ES / cfg[k])
    return cfg


class Worker:
    """在别的 Python 环境里运行 engines/<script>：输入 JSON（片段文字 + 设置），每段输出一个 wav。"""

    def __init__(self, cfg):
        self.cfg = resolve_cfg(cfg)

    def synth_all(self, texts):
        import soundfile as sf
        with tempfile.TemporaryDirectory(prefix='es_tts_') as td:
            td = Path(td)
            (td / 'in.json').write_text(json.dumps({'texts': texts, 'cfg': self.cfg}, ensure_ascii=False), 'utf-8')
            cmd = [self.cfg['python'], str(HERE / 'engines' / self.cfg['script']), str(td / 'in.json'), str(td)]
            rc = subprocess.run(cmd).returncode
            if rc:                                # 引擎自己的报错已经显示在上面；这里只用中文说一句，不再叠一层 Python 报错
                raise SystemExit(f'配音引擎 {self.cfg["script"]} 运行出错（退出码 {rc}），原因看上面的输出。'
                                 + voice_check.fix_hint(self.cfg))
            out = []
            for i in range(len(texts)):
                a, sr = sf.read(str(td / f'{i:03d}.wav'), dtype='float32')
                out.append((a if a.ndim == 1 else a.mean(1), sr))
            return out


def engine_for(cfg):
    return {'kokoro': KokoroES, 'worker': Worker}[cfg['engine']](cfg)


# ---------------------------------------------------------------- 处理链
def to_sr(a, sr):
    import soxr
    return a if sr == SR else soxr.resample(a, sr, SR, quality='VHQ').astype(np.float32)


def chain(cfg):
    """把 G 的电平、压缩换成西语这条链（四级的 K 加权电平 + 这个声音自己的去电磁音频点 + 压缩 + 慢速电平）。"""
    tones = cfg.get('debuzz', [])
    G.level = C4A.level_k
    G.compress = lambda x, sr: C4A.leveler(C4A._comp(buzz.debuzz(x, sr, tones), sr), sr)


def verify(mp3, items, lufs):
    import io
    import soundfile as sf
    a, sr = sf.read(io.BytesIO(mp3), dtype='float32')
    a = a if a.ndim == 1 else a.mean(1)
    rep, errs = loudness.measure(a, sr, items, lufs)         # 高考原版的响度四项（独立测量，ITU-R BS.1770）；短时波动只测朗读部分，见 loudness.py
    rp = buzz.report(a, sr, items)
    rep['buzz_hz'], rep['buzz_db'], rep['comb_db'] = rp['f0'], round(rp['r'], 1), round(rp['c'], 2)
    if rp['pr'] is not None:                                 # 全频段超过 7.5 dB 时的“前后两半都在”确认
        rep['buzz_persist_hz'], rep['buzz_persist_db'] = rp['pf'], round(rp['pr'], 1)
    rep['buzz_detail'] = buzz.detail(rp)
    return rep, errs + rp['errs']


def build(p, cfg, eng, sents=None, log=print):
    """合成整篇（或 sents 指定的几句），返回 (48 kHz 成品, 时间轴)。"""
    chain(cfg)
    allsent = [(pi, si, s) for pi, para in enumerate(p['paras']) for si, s in enumerate(para)]
    pick = [x for k, x in enumerate(allsent, 1) if not sents or k in sents]
    plan = []
    for pi, si, s in pick:
        k = allsent.index((pi, si, s)) + 1
        plan.append((k, pi, si, s, segments(s['es'], k, p['id'])))
    texts = [t for *_, segs in plan for t in segs]
    t0 = time.time()
    raw = eng.synth_all(texts)
    if cfg.get('deline'):                                         # Supertonic：每段原始输出（帧网格对齐、未裁剪）先去帧频梳状线
        comb = buzz.load_comb(cfg['deline'])
        raw = [(buzz.deline(a, sr, comb), sr) for a, sr in raw]
    audio = iter(raw)
    log(f'  合成 {len(texts)} 段，用时 {time.time() - t0:.0f} 秒')
    cp = cfg['clause_pause']
    pieces = [np.zeros(int(round(cfg['lead_in'] * SR)), np.float32)]
    t = len(pieces[0]) / SR
    items = []
    for n, (k, pi, si, s, segs) in enumerate(plan):
        sent, parts, st = [], [], t
        for j, x in enumerate(segs):
            a, sr = next(audio)
            seg = G.fade(G.level(G.trim(to_sr(a, sr))))
            parts.append([round(t, 3), round(t + len(seg) / SR, 3)])
            sent.append(seg)
            t += len(seg) / SR
            if j < len(segs) - 1:
                z = np.zeros(int(round(cp * SR)), np.float32)
                sent.append(z)
                t += len(z) / SR
        pieces += sent
        items.append({'k': k, 'para': pi + 1, 'start': round(st, 3), 'end': round(t, 3), 'parts': parts,
                      'segments': segs, 'text': s['es'], 'read': s['es']})
        last = n == len(plan) - 1
        g = cfg['tail'] if last else cfg['sentence_pause']        # 铁律：句间固定 0.8 秒（段落之间也一样）
        z = np.zeros(int(round(g * SR)), np.float32)
        pieces.append(z)
        t += len(z) / SR
    a = G.master(np.concatenate(pieces), cfg.get('lufs', -16.0))
    return a, items


def write_srt(path, items, p):
    zh = {k: s['zh'] for k, s in enumerate((s for para in p['paras'] for s in para), 1)}
    out = []
    for i, it in enumerate(items, 1):
        out += [str(i), f"{G.fmt_ts(it['start'])} --> {G.fmt_ts(it['end'])}", it['text'], zh[it['k']], '']
    Path(path).write_text('\n'.join(out), 'utf-8')


def stem(p):
    return f"{p['id']}_" + re.sub(r'[^A-Za-z0-9]+', '_', p['title_es'].translate(str.maketrans('áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN'))).strip('_')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pid')
    ap.add_argument('--voice')
    ap.add_argument('--sample', help='只做试听样片，写到这个 MP3（不写 timings.json）')
    ap.add_argument('--sents', help='试听用的句子，如 1-3 或 1,4,7')
    ap.add_argument('--draft', action='store_true', help='草稿：检查不通过也输出（问题写进 timings.json 的 draft_issues）')
    ap.add_argument('--seed', type=int, help='换随机种子（只对设了 seed 的音色有效，如 Qwen3）：检查没通过时整篇换下一个种子重做（batch.py 自动做）')
    a = ap.parse_args()
    name = a.voice or VOICES['_final']
    if name not in VOICES or name.startswith('_'):
        raise SystemExit(f'voices.json 里没有音色 {name}（可选：{", ".join(k for k in VOICES if not k.startswith("_"))}）')
    cfg = VOICES[name]
    probs = voice_check.voice_problems(cfg)
    if probs:
        ready = [k for k in VOICES if not k.startswith('_') and k != name and not voice_check.voice_problems(VOICES[k])]
        raise SystemExit(f'音色 {name} 还不能用：\n  ' + '\n  '.join(probs) + '\n' + voice_check.fix_hint(cfg)
                         + (f'\n现在能用的音色：{"、".join(ready)}（加 --voice 音色名）' if ready else ''))
    p = c4.load('es_make_video', '西班牙语/tools/make_video.py').load(a.pid)
    if a.seed is not None:
        if 'seed' not in cfg:
            raise SystemExit(f'音色 {name} 没有随机种子设置，--seed 无效')
        cfg = {**cfg, 'seed': a.seed}
    sents = None
    if a.sents:
        sents = set()
        for x in a.sents.split(','):
            lo, _, hi = x.partition('-')
            sents |= set(range(int(lo), int(hi or lo) + 1))
    eng = engine_for(cfg)
    a48, items = build(p, cfg, eng, sents)
    mp3 = G.encode_mp3(a48, kbps=cfg.get('kbps', 128))
    rep, errs = verify(mp3, items, cfg.get('lufs', -16.0))
    print(f"  响度：整体 {rep['integrated_lufs']} LUFS，句间最大偏差 {rep['sentence_max_dev_lu']} LU，短时波动 "
          f"{rep['short_term_std_lu']} LU（朗读部分），峰值 {rep['peak_dbfs']} dBFS；电磁音：{rep['buzz_detail']}")
    if a.sample:                                   # 试听样片也是给人听的音频：检查不通过就不写（铁律 10），--draft 才写（文件名加 _未通过）
        if errs and not a.draft:
            raise SystemExit(f'试听样片检查未通过，未输出文件：' + '；'.join(errs) + (
                '\n（选的句子太短：--sents 多选几句）' if any('测不了' in e for e in errs) else
                '\n（Supertonic 每次合成略有不同，直接再运行一次即可；Qwen3 用 --seed 换一个种子）'))
        dst = Path(a.sample)
        if errs:
            dst = dst.with_name(dst.stem + '_未通过' + dst.suffix)
        dst.write_bytes(mp3)
        print(('  草稿：以下检查未通过：' + '；'.join(errs)) if errs else '  检查全部通过', f'\n已保存试听样片 {dst}')
        return
    if errs and not a.draft:
        raise SystemExit(f'{p["id"]} {name} 检查未通过，未输出文件：' + '；'.join(errs))
    if errs:
        print('  草稿：以下检查未通过，仍然输出：' + '；'.join(errs))
    out = ES / 'audio' / name
    out.mkdir(parents=True, exist_ok=True)
    base = out / stem(p)
    Path(str(base) + '.mp3').write_bytes(mp3)
    write_srt(str(base) + '.srt', items, p)
    tpath = ES / 'audio' / 'timings.json'
    T = json.loads(tpath.read_text('utf-8')) if tpath.exists() else {}
    T.setdefault(name, {})[p['id']] = {'file': f'{name}/{base.name}.mp3', 'duration': round(len(a48) / OUT_SR, 3),
                                       'loudness': rep, 'voice_cfg': cfg, 'sentences': items,
                                       'draft_issues': errs}
    T['_final'] = VOICES['_final']
    tpath.write_text(json.dumps(T, ensure_ascii=False, indent=1), 'utf-8')
    print(f'已生成 {base}.mp3（{len(a48) / OUT_SR:.1f} 秒）' + ('，检查全部通过' if not errs else '（草稿）'))


if __name__ == '__main__':
    main()
