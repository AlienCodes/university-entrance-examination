"""Kokoro-82M v1.0（kokoro-onnx）西班牙语合成 worker（make_audio.py 的 Worker 调用）。

    /opt/ttsenv/bin/python kokoro_worker.py in.json 输出目录

in.json = {"texts": [片段文字, ...], "cfg": {voices.json 里这个音色的设置}}
输出：输出目录/000.wav、001.wav …（每段一个，单声道 float32，24000 Hz）。模型只加载一次。

cfg 里用到的键（都有默认值）：
  model_dir   模型文件夹，默认 /opt/es_tts_models/kokoro-v1.0；不存在时用仓库 tools/tts/models
  model       默认 kokoro-v1.0.onnx        voices  默认 voices-v1.0.bin
  voice       {"em_alex": 0.6, "em_santa": 0.4}（按权重混合）或单个名字 "em_alex"
  timbre      可选，同样的写法：只用来替换音色（声码器那一半），节奏和语调仍由 voice 决定
  speed       语速，默认 1.0              lang    espeak 语言，默认 "es"（西班牙本土发音，c/z 读 θ）
  num_threads onnxruntime 线程数，默认 4
  phoneme_replace  可选，[[正则, 替换], ...]：对 espeak 音标逐条 re.sub 后再合成（例如词尾 d 改成 ð：
              [["d(?=[ .,;:!?]|$)", "ð"]]）；每条规则命中几次会打印出来，一次都没命中会提示（不报错，试听只合成几句时可能本来就没有）
和 make_audio.py 里本进程的 KokoroES 完全同一种合成方式：整段一次送进模型，trim=True（模型自带的去首尾空白），
不额外插入停顿（sentence_pause=0、clause_pause=0），段间停顿由 make_audio.py 用数字静音统一加。
"""
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

DEFAULT_DIRS = [Path('/opt/es_tts_models/kokoro-v1.0'),
                Path(__file__).resolve().parents[3] / 'tools' / 'tts' / 'models']


def model_paths(cfg):
    dirs = [Path(cfg['model_dir'])] if cfg.get('model_dir') else DEFAULT_DIRS
    model, voices = cfg.get('model', 'kokoro-v1.0.onnx'), cfg.get('voices', 'voices-v1.0.bin')
    for d in dirs:
        if (d / model).exists() and (d / voices).exists():
            return d / model, d / voices
    raise SystemExit(f'找不到 Kokoro 模型文件 {model} / {voices}（查找位置：{", ".join(map(str, dirs))}）')


def blend(k, spec):
    if isinstance(spec, str):
        spec = {spec: 1.0}
    unknown = [v for v in spec if v not in k.voices]
    if unknown:
        raise SystemExit(f'Kokoro 没有这些音色：{unknown}')
    tot = float(sum(spec.values()))
    return sum(k.get_voice_style(v) * (w / tot) for v, w in spec.items()).astype(np.float32)


def make_style(k, cfg):
    """音色向量 (510, 1, 256)：前 128 维给声码器（音色），后 128 维给韵律预测（时长、音高、轻重）。
    cfg["timbre"] 存在时只替换前 128 维：音色用它的混合，节奏和语调仍按 cfg["voice"]（保持西语母语的韵律）。"""
    style = blend(k, cfg.get('voice', 'em_alex'))
    if cfg.get('timbre'):
        style = style.copy()
        style[..., :128] = blend(k, cfg['timbre'])[..., :128]
    return style


class KokoroWorker:
    def __init__(self, cfg):
        import onnxruntime as rt
        from kokoro_onnx import Kokoro
        mp, vp = model_paths(cfg)
        so = rt.SessionOptions()
        so.intra_op_num_threads = int(cfg.get('num_threads', 4))
        sess = rt.InferenceSession(str(mp), sess_options=so, providers=['CPUExecutionProvider'])
        self.k = Kokoro.from_session(sess, str(vp))
        self.style = make_style(self.k, cfg)
        self.speed = float(cfg.get('speed', 1.0))
        self.lang = cfg.get('lang', 'es')
        self.replace = [(re.compile(a), b) for a, b in cfg.get('phoneme_replace', [])]
        self.hits = [0] * len(self.replace)

    def synth(self, text):
        src, is_ph = text, False
        if self.replace:
            src, is_ph = self.phonemes(text), True
            for i, (rx, rep) in enumerate(self.replace):
                src, n = rx.subn(rep, src)
                self.hits[i] += n
        a, sr = self.k.create(src, voice=self.style, speed=self.speed, lang=self.lang, is_phonemes=is_ph, trim=True,
                              sentence_pause=0.0, clause_pause=0.0)
        return np.asarray(a, np.float32), sr

    def phonemes(self, text):
        return self.k.tokenizer.phonemize(text, self.lang)


def main():
    inp, out = Path(sys.argv[1]), Path(sys.argv[2])
    job = json.loads(inp.read_text('utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    w = KokoroWorker(job.get('cfg', {}))
    t1 = time.time()
    for i, text in enumerate(job['texts']):
        a, sr = w.synth(text)
        if not len(a) or not np.isfinite(a).all():
            raise SystemExit(f'第 {i + 1} 段合成失败（空音频或非法数值）：{text}')
        sf.write(str(out / f'{i:03d}.wav'), a, sr, subtype='FLOAT')
    for (rx, rep), n in zip(w.replace, w.hits):
        print(f'kokoro_worker: phoneme_replace {rx.pattern!r} → {rep!r} 命中 {n} 次' + ('（一次都没有命中，请核对）' if not n else ''),
              file=sys.stderr)
    print(f'kokoro_worker: 加载 {t1 - t0:.1f} 秒，合成 {len(job["texts"])} 段 {time.time() - t1:.1f} 秒', file=sys.stderr)


if __name__ == '__main__':
    main()
