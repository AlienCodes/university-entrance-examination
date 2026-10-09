"""Kokoro-82M v1.0（kokoro-onnx）西班牙语合成 worker（make_audio.py 的 Worker 调用）。

    /opt/ttsenv/bin/python kokoro_worker.py in.json 输出目录

in.json = {"texts": [片段文字, ...], "cfg": {voices.json 里这个音色的设置}}
输出：输出目录/000.wav、001.wav …（每段一个，单声道 float32，24000 Hz）。模型只加载一次。

cfg 里用到的键（都有默认值）：
  model_dir   模型文件夹，默认 /opt/es_tts_models/kokoro-v1.0；不存在时用仓库 tools/tts/models
  model       默认 kokoro-v1.0.onnx        voices  默认 voices-v1.0.bin
  voice       {"em_alex": 0.6, "em_santa": 0.4}（按权重混合）或单个名字 "em_alex"
  speed       语速，默认 1.0              lang    espeak 语言，默认 "es"（西班牙本土发音，c/z 读 θ）
  num_threads onnxruntime 线程数，默认 4
和 make_audio.py 里本进程的 KokoroES 完全同一种合成方式：整段一次送进模型，trim=True（模型自带的去首尾空白），
不额外插入停顿（sentence_pause=0、clause_pause=0），段间停顿由 make_audio.py 用数字静音统一加。
"""
import json
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


class KokoroWorker:
    def __init__(self, cfg):
        import onnxruntime as rt
        from kokoro_onnx import Kokoro
        mp, vp = model_paths(cfg)
        so = rt.SessionOptions()
        so.intra_op_num_threads = int(cfg.get('num_threads', 4))
        sess = rt.InferenceSession(str(mp), sess_options=so, providers=['CPUExecutionProvider'])
        self.k = Kokoro.from_session(sess, str(vp))
        spec = cfg.get('voice', 'em_alex')
        if isinstance(spec, str):
            spec = {spec: 1.0}
        unknown = [v for v in spec if v not in self.k.voices]
        if unknown:
            raise SystemExit(f'Kokoro 没有这些音色：{unknown}')
        tot = float(sum(spec.values()))
        self.style = sum(self.k.get_voice_style(v) * (w / tot) for v, w in spec.items()).astype(np.float32)
        self.speed = float(cfg.get('speed', 1.0))
        self.lang = cfg.get('lang', 'es')

    def synth(self, text):
        a, sr = self.k.create(text, voice=self.style, speed=self.speed, lang=self.lang, trim=True,
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
    print(f'kokoro_worker: 加载 {t1 - t0:.1f} 秒，合成 {len(job["texts"])} 段 {time.time() - t1:.1f} 秒', file=sys.stderr)


if __name__ == '__main__':
    main()
