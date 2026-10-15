"""Qwen3-TTS-12Hz 1.7B 西班牙语合成 worker（make_audio.py 的 Worker 调用）：克隆（Base）和文字设计声音（VoiceDesign）两种用法。

    /opt/es_tts_envs/qwen3tts/bin/python qwen3tts.py in.json 输出目录

in.json = {"texts": [片段文字, ...], "cfg": {voices.json 里这个音色的设置}}
输出：输出目录/000.wav、001.wav …（每段一个，单声道 float32，24000 Hz，模型原样输出，不裁剪、不归一化）。
模型只加载一次（克隆用的参考声音也只分析一次）。另写 输出目录/worker_stats.json（加载用时、每段用时、种子、重试），
make_audio.py 不读它。

模型：Qwen3-TTS-12Hz-1.7B-Base / -VoiceDesign（Apache-2.0）。代码 PyPI qwen-tts 0.1.1；权重放在仓库外
（/opt/es_tts_models/…，Hugging Face 打不开，从 Docker Hub 镜像层取，下载方法见 research 记录）。
环境（CPU 版 PyTorch，约 2.5 GB，和评测环境共用 conda 缓存）：
  micromamba create -p /opt/es_tts_envs/qwen3tts -c conda-forge python=3.11 "pytorch=2.13.0=cpu_mkl*" torchaudio=2.11.0 numpy
  uv pip install -p /opt/es_tts_envs/qwen3tts/bin/python transformers==4.57.3 accelerate==1.12.0 librosa soundfile onnxruntime einops sox
  uv pip install -p /opt/es_tts_envs/qwen3tts/bin/python --no-deps qwen-tts==0.1.1

cfg 里用到的键：
  mode          "clone"（Base 模型 + 参考录音）或 "design"（VoiceDesign 模型 + 文字描述）（必填）
  model_dir     模型文件夹（必填），如 /opt/es_tts_models/qwen3-tts-base/models/Qwen3-TTS-12Hz-1.7B-Base
  language      默认 "spanish"
  seed          随机种子，默认 1234。每一段合成前都重新设成这个种子：同一段文字 + 同样设置 → 每次结果完全一样
                （和段落的先后顺序无关；只在同一台机器、同样线程数下保证逐位一致）
  num_threads   PyTorch 线程数，默认 4
  dtype         "float32"（默认；这台 CPU 没有 bf16 指令）或 "bfloat16"
  克隆：ref_audio  参考 wav 的路径（必须是合成出来的声音，不用真人录音）
        ref_text   参考 wav 的逐字文本（ICL 模式必填）
        x_vector_only  true = 只用声纹向量、不用参考文本（音色像度差一些），默认 false
  设计：instruct    声音的文字描述（英文或中文）
  采样参数（默认取模型自带 generation_config.json：do_sample=true, temperature=0.9, top_k=50, top_p=1.0,
            repetition_penalty=1.05，subtalker_* 同样 0.9/50/1.0）：
        temperature top_k top_p repetition_penalty subtalker_temperature subtalker_top_k subtalker_top_p
  防失控：模型偶尔会念不完就停、或者停不下来（一直输出声音）。每段合成后按字数检查时长，
        时长 < min_s_per_char × 字数，或 > max_s_per_char × 字数 + 2 秒，就换种子（seed + 1、+2 …）重来，
        最多 retries 次（默认 3），全部记进 worker_stats.json。默认 min 0.035、max 0.20 秒/字（正常约 0.07）。
        max_new_tokens 默认按字数算（12 帧/秒 ×（0.25 秒/字 × 字数 + 6 秒），最多 2048）。
每段整段一次送进模型；段间停顿由 make_audio.py 用数字静音统一加。
"""
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf


def need(cfg, key):
    if key not in cfg or cfg[key] in (None, ''):
        raise SystemExit(f'qwen3tts.py：cfg 缺少 "{key}"')
    return cfg[key]


GEN_KEYS = ('do_sample', 'temperature', 'top_k', 'top_p', 'repetition_penalty',
            'subtalker_dosample', 'subtalker_temperature', 'subtalker_top_k', 'subtalker_top_p')


def set_seed(seed):
    import torch
    random.seed(seed)
    np.random.seed(seed % (2 ** 32))
    torch.manual_seed(seed)


class QwenWorker:
    def __init__(self, cfg):
        import torch
        torch.set_num_threads(int(cfg.get('num_threads', 4)))
        from qwen_tts import Qwen3TTSModel
        self.cfg = cfg
        self.mode = need(cfg, 'mode')
        if self.mode not in ('clone', 'design'):
            raise SystemExit(f'qwen3tts.py：不认识的 mode "{self.mode}"（只支持 clone、design）')
        d = Path(need(cfg, 'model_dir'))
        if not (d / 'model.safetensors').exists() or not (d / 'speech_tokenizer' / 'config.json').exists():
            raise SystemExit(f'qwen3tts.py：{d} 里没有完整的模型（要有 model.safetensors 和 speech_tokenizer/），请先下载解压')
        dtype = {'float32': torch.float32, 'bfloat16': torch.bfloat16}[cfg.get('dtype', 'float32')]
        self.tts = Qwen3TTSModel.from_pretrained(str(d), dtype=dtype, device_map='cpu', local_files_only=True)
        kind = self.tts.model.tts_model_type
        want = {'clone': 'base', 'design': 'voice_design'}[self.mode]
        if kind != want:
            raise SystemExit(f'qwen3tts.py：mode={self.mode} 要用 {want} 模型，但 {d} 是 {kind} 模型')
        self.language = cfg.get('language', 'spanish')
        self.seed = int(cfg.get('seed', 1234))
        self.gen = {k: cfg[k] for k in GEN_KEYS if k in cfg}
        self.prompt = None
        if self.mode == 'clone':
            ref = Path(need(cfg, 'ref_audio'))
            if not ref.exists():
                raise SystemExit(f'qwen3tts.py：找不到参考录音 {ref}')
            xvec = bool(cfg.get('x_vector_only', False))
            a, sr = sf.read(str(ref), dtype='float32')
            a = a if a.ndim == 1 else a.mean(1)
            self.prompt = self.tts.create_voice_clone_prompt(
                ref_audio=(a, sr), ref_text=None if xvec else need(cfg, 'ref_text'), x_vector_only_mode=xvec)
        else:
            self.instruct = need(cfg, 'instruct')

    def _once(self, text, seed):
        set_seed(seed)
        n = len(text)
        mnt = int(cfg_get(self.cfg, 'max_new_tokens', min(2048, int(12 * (0.25 * n + 6)))))
        kw = dict(self.gen, max_new_tokens=mnt)
        if self.mode == 'clone':
            wavs, sr = self.tts.generate_voice_clone(text=text, language=self.language,
                                                     voice_clone_prompt=self.prompt, **kw)
        else:
            wavs, sr = self.tts.generate_voice_design(text=text, instruct=self.instruct,
                                                      language=self.language, **kw)
        return np.asarray(wavs[0], np.float32).reshape(-1), int(sr), mnt

    def synth(self, text):
        lo = float(self.cfg.get('min_s_per_char', 0.035))
        hi = float(self.cfg.get('max_s_per_char', 0.20))
        retries = int(self.cfg.get('retries', 3))
        n = len(text)
        tries = []
        for k in range(retries + 1):
            seed = self.seed + k
            a, sr, mnt = self._once(text, seed)
            dur = len(a) / sr
            ok = bool(len(a)) and np.isfinite(a).all() and lo * n <= dur <= hi * n + 2.0 and len(a) < mnt * sr / 12 - sr
            tries.append({'seed': seed, 'audio_s': round(dur, 3), 'ok': bool(ok)})
            if ok:
                return a, sr, tries
        raise SystemExit(f'qwen3tts.py：试了 {len(tries)} 个种子都不正常（时长 {[t["audio_s"] for t in tries]} 秒）：{text}')


def cfg_get(cfg, k, default):
    return cfg[k] if cfg.get(k) is not None else default


def main():
    inp, out = Path(sys.argv[1]), Path(sys.argv[2])
    job = json.loads(inp.read_text('utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    w = QwenWorker(job.get('cfg', {}))
    load = time.time() - t0
    stats = {'load_s': round(load, 3), 'mode': w.mode, 'seed': w.seed, 'items': []}
    for i, text in enumerate(job['texts']):
        t = time.time()
        a, sr, tries = w.synth(text)
        dt = time.time() - t
        sf.write(str(out / f'{i:03d}.wav'), a, sr, subtype='FLOAT')
        stats['items'].append({'text': text, 'synth_s': round(dt, 3), 'audio_s': round(len(a) / sr, 3), 'sr': sr,
                               'tries': tries})
        print(f'qwen3tts.py: {i + 1}/{len(job["texts"])} {len(a) / sr:.1f} 秒音频，用时 {dt:.0f} 秒'
              f'{"（重试 " + str(len(tries) - 1) + " 次）" if len(tries) > 1 else ""}', file=sys.stderr, flush=True)
    (out / 'worker_stats.json').write_text(json.dumps(stats, ensure_ascii=False, indent=1), 'utf-8')
    tot = sum(x['synth_s'] for x in stats['items'])
    print(f'qwen3tts.py: 加载 {load:.1f} 秒，合成 {len(job["texts"])} 段 {tot:.1f} 秒', file=sys.stderr)


if __name__ == '__main__':
    main()
