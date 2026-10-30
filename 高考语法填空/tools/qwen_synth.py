"""Qwen3-TTS 合成（在 GitHub Actions 上跑：本机代理拦 HuggingFace；Actions 能联网、多台并行，不靠本容器醒着）。

任务清单（高考语法填空/tts/任务_*.json）：candidates × takes 组成作业，--shard 选一个作业；只输出原始 24 kHz WAV + meta，
响度、去电磁音、合格证等完整处理链在本机做（tools/tts/gaokao_tts 的 segment / master / final_check）。
模式：
  custom        预置音色（CustomVoice），instruct 控制语气；
  design_clone  先用 VoiceDesign 按文字描述设计一个音色（不是任何真人），再用 Base 模型以这段设计音频为提示合成全部段落，保证全片同一个声音。
用法：python qwen_synth.py --task 任务.json --list            # 打印作业数（给工作流建矩阵）
      python qwen_synth.py --task 任务.json --shard 3 --out out/
"""
import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def jobs(task):
    out = []
    for c in task['candidates']:
        for t in task['takes']:
            for part in range(task.get('parts', 1)):
                out.append((c, t, part))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', required=True)
    ap.add_argument('--shard', type=int)
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--out', default='out')
    a = ap.parse_args()
    task = json.loads(Path(a.task).read_text('utf-8'))
    J = jobs(task)
    if a.list:
        print(json.dumps(list(range(len(J)))))
        return
    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel
    torch.set_num_threads(4)
    c, take, part = J[a.shard]
    segs = json.loads((ROOT / task['script']).read_text('utf-8'))['segments']
    nparts = task.get('parts', 1)
    segs = [s for i, s in enumerate(segs) if i % nparts == part]
    od = Path(a.out) / c['id'] / f'take{take}'
    od.mkdir(parents=True, exist_ok=True)
    kw = dict(dtype=torch.float32, device_map='cpu')
    gen = dict(task.get('gen', {}))
    meta = {'candidate': c, 'take': take, 'part': part, 'segments': []}
    t0 = time.time()
    if c['mode'] == 'design_clone':
        dm = Qwen3TTSModel.from_pretrained(c['design_model'], **kw)
        torch.manual_seed(c.get('design_seed', 7))
        w, sr = dm.generate_voice_design(text=c['design_text'], instruct=c['design_instruct'], language='Chinese')
        sf.write(str(od / 'design_ref.wav'), w[0], sr)
        meta['design_ref_sec'] = round(len(w[0]) / sr, 2)
        del dm
        m = Qwen3TTSModel.from_pretrained(c['model'], **kw)
        prompt = m.create_voice_clone_prompt(ref_audio=(w[0], sr), ref_text=c['design_text'])
    else:
        m = Qwen3TTSModel.from_pretrained(c['model'], **kw)
        print('支持的音色', m.get_supported_speakers(), '语言', m.get_supported_languages(), flush=True)
    for s in segs:
        torch.manual_seed(take * 1000 + int(''.join(ch for ch in s['id'] if ch.isdigit()) or 0))
        ts = time.time()
        if c['mode'] == 'design_clone':
            w, sr = m.generate_voice_clone(text=s['text'], language=s['lang'], voice_clone_prompt=prompt, **gen)
        else:
            ins = task['instruct_en'] if s['lang'] == 'English' else task['instruct']
            w, sr = m.generate_custom_voice(text=s['text'], speaker=c['speaker'], language=s['lang'],
                                            instruct=ins, **gen)
        x = np.asarray(w[0], dtype=np.float32)
        sf.write(str(od / f"{s['id']}.wav"), x, sr)
        el = time.time() - ts
        meta['segments'].append({'id': s['id'], 'sec': round(len(x) / sr, 2), 'compute': round(el, 1), 'sr': sr})
        print(f"{c['id']} take{take} {s['id']} {len(x) / sr:.1f}s 音频，用时 {el:.0f}s", flush=True)
    meta['total_compute'] = round(time.time() - t0, 1)
    (od / f'meta_part{part}.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), 'utf-8')


if __name__ == '__main__':
    main()
