"""sherpa-onnx 西班牙语合成 worker（make_audio.py 的 Worker 调用）：Supertonic 2/3 和 Piper（VITS）两类模型。

    /opt/es_tts_envs/sherpa/bin/python sherpa.py in.json 输出目录

in.json = {"texts": [片段文字, ...], "cfg": {voices.json 里这个音色的设置}}
输出：输出目录/000.wav、001.wav …（每段一个，单声道 float32，模型自己的采样率：Supertonic 44100 Hz，Piper 22050 Hz）。
模型只加载一次。另写 输出目录/worker_stats.json（加载用时、每段合成用时），make_audio.py 不读它。

环境：uv venv -p 3.12 /opt/es_tts_envs/sherpa && uv pip install -p /opt/es_tts_envs/sherpa/bin/python sherpa-onnx soundfile numpy
（实测 sherpa-onnx 1.13.8）。模型放在仓库外（/opt/es_tts_models/<名字>/），从 sherpa-onnx 的 GitHub 发布页下载：
https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/<模型>.tar.bz2

cfg 里用到的键：
  kind         "supertonic" 或 "vits"（必填）
  model_dir    模型文件夹（必填），如 /opt/es_tts_models/supertonic3、/opt/es_tts_models/piper-es_ES-davefx-medium
  sid          说话人编号，默认 0（Supertonic 3：0–4 = F1–F5 女声，5–9 = M1–M5 男声；sharvard：0 男、1 女）
  speed        语速（越大越快），默认 1.0
  num_threads  onnxruntime 线程数，默认 4
  Supertonic： lang 语言，默认 "es"；num_steps 去噪步数，默认 32（越大越细，见 research 记录）
  VITS：       model 文件夹里的 .onnx 文件名（默认唯一那个）；noise_scale / noise_scale_w / length_scale
               默认取模型自带 .onnx.json 的 inference 设置（Piper 都是 0.667 / 0.8 / 1.0）
每段整段一次送进模型，不做任何后处理（不裁剪、不归一化）；段间停顿由 make_audio.py 用数字静音统一加。
注意：两类模型合成时都带随机噪声，同一句每次合成结果略有不同。
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf


def need(cfg, key):
    if key not in cfg:
        raise SystemExit(f'sherpa.py：cfg 缺少 "{key}"')
    return cfg[key]


def exists(p):
    if not Path(p).exists():
        raise SystemExit(f'sherpa.py：找不到模型文件 {p}（模型要先下载解压到 cfg 的 model_dir）')
    return str(p)


def supertonic_model(cfg, d):
    import sherpa_onnx as so
    return so.OfflineTtsModelConfig(
        supertonic=so.OfflineTtsSupertonicModelConfig(
            duration_predictor=exists(d / 'duration_predictor.int8.onnx'),
            text_encoder=exists(d / 'text_encoder.int8.onnx'),
            vector_estimator=exists(d / 'vector_estimator.int8.onnx'),
            vocoder=exists(d / 'vocoder.int8.onnx'),
            tts_json=exists(d / 'tts.json'),
            unicode_indexer=exists(d / 'unicode_indexer.bin'),
            voice_style=exists(d / 'voice.bin'),
        ),
        num_threads=int(cfg.get('num_threads', 4)), debug=False, provider='cpu')


def vits_model(cfg, d):
    import sherpa_onnx as so
    if cfg.get('model'):
        onnx = d / cfg['model']
    else:
        found = sorted(d.glob('*.onnx'))
        if len(found) != 1:
            raise SystemExit(f'sherpa.py：{d} 里有 {len(found)} 个 .onnx，请在 cfg 里写明 "model"')
        onnx = found[0]
    inf = {}
    js = Path(str(onnx) + '.json')
    if js.exists():
        inf = json.loads(js.read_text('utf-8')).get('inference', {})
    espeak = d / 'espeak-ng-data'
    return so.OfflineTtsModelConfig(
        vits=so.OfflineTtsVitsModelConfig(
            model=exists(onnx), tokens=exists(d / 'tokens.txt'), lexicon='',
            data_dir=str(espeak) if espeak.exists() else '',
            noise_scale=float(cfg.get('noise_scale', inf.get('noise_scale', 0.667))),
            noise_scale_w=float(cfg.get('noise_scale_w', inf.get('noise_w', 0.8))),
            length_scale=float(cfg.get('length_scale', inf.get('length_scale', 1.0))),
        ),
        num_threads=int(cfg.get('num_threads', 4)), debug=False, provider='cpu')


class SherpaWorker:
    def __init__(self, cfg):
        import sherpa_onnx as so
        kind = need(cfg, 'kind')
        d = Path(need(cfg, 'model_dir'))
        if kind == 'supertonic':
            model = supertonic_model(cfg, d)
        elif kind == 'vits':
            model = vits_model(cfg, d)
        else:
            raise SystemExit(f'sherpa.py：不认识的 kind "{kind}"（只支持 supertonic、vits）')
        conf = so.OfflineTtsConfig(model=model, max_num_sentences=1)
        if not conf.validate():
            raise SystemExit(f'sherpa.py：模型设置检查不通过，请看上面的 sherpa-onnx 报错（{d}）')
        self.tts = so.OfflineTts(conf)
        self.kind = kind
        self.sid = int(cfg.get('sid', 0))
        if not 0 <= self.sid < max(1, self.tts.num_speakers):
            raise SystemExit(f'sherpa.py：sid={self.sid} 超出范围（这个模型有 {self.tts.num_speakers} 个说话人）')
        self.gen = so.GenerationConfig()
        self.gen.sid = self.sid
        self.gen.speed = float(cfg.get('speed', 1.0))
        if kind == 'supertonic':
            self.gen.num_steps = int(cfg.get('num_steps', 32))
            self.gen.extra['lang'] = cfg.get('lang', 'es')

    def synth(self, text):
        a = self.tts.generate(text, self.gen)
        return np.asarray(a.samples, np.float32), int(a.sample_rate)


def main():
    inp, out = Path(sys.argv[1]), Path(sys.argv[2])
    job = json.loads(inp.read_text('utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    w = SherpaWorker(job.get('cfg', {}))
    load = time.time() - t0
    stats = {'load_s': round(load, 3), 'num_speakers': w.tts.num_speakers, 'items': []}
    for i, text in enumerate(job['texts']):
        t = time.time()
        a, sr = w.synth(text)
        dt = time.time() - t
        if not len(a) or not np.isfinite(a).all():
            raise SystemExit(f'第 {i + 1} 段合成失败（空音频或非法数值）：{text}')
        sf.write(str(out / f'{i:03d}.wav'), a, sr, subtype='FLOAT')
        stats['items'].append({'text': text, 'synth_s': round(dt, 3), 'audio_s': round(len(a) / sr, 3), 'sr': sr})
    (out / 'worker_stats.json').write_text(json.dumps(stats, ensure_ascii=False, indent=1), 'utf-8')
    tot = sum(x['synth_s'] for x in stats['items'])
    print(f'sherpa.py: 加载 {load:.1f} 秒，合成 {len(job["texts"])} 段 {tot:.1f} 秒', file=sys.stderr)


if __name__ == '__main__':
    main()
