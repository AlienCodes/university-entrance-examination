"""GPT-SoVITS（v2ProPlus，老师用声音分身 VoiceTwin 训练的专属模型）在 GitHub Actions 的 CPU 上合成讲解配音。

与 qwen_synth.py 同一个任务清单格式、同一个输出结构（out/<候选>/take<n>/<小段>.wav + meta_part<k>.json），
所以 选段.py / 合成完整性.py / 处理链（讲解音频 去呼吸 → segment → 母带 → 合格证）不用改就能用。候选写法：

  {"id": "g1", "mode": "gptsovits", "weights": "base"}                     底模（只证明环境可用）
  {"id": "g1", "mode": "gptsovits", "weights": "teacher", "voice": "…json"} 老师的模型（工作流从云盘取到 $SOVITS_DIR）

voice：与 Qwen 同一种参考写法（Release 录音 + spans + ref_text）；weights=teacher 且没写 voice 时，
用 $SOVITS_DIR/ref.json 里按 VoiceTwin 的做法挑好的参考（取模型.py 写）。

隐私：模型、老师素材只在 $SOVITS_DIR（runner 本地），本脚本不复制、不打印路径以外的内容。
"""
import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from qwen_synth import jobs, trim_heap, rss_mb, RSS_WARN_MB  # noqa: E402

GSV = Path(os.environ.get('GSV_ROOT', 'GPT-SoVITS')).resolve()     # 官方代码（abe9843，老师电脑上的版本）
PRE = GSV / 'GPT_SoVITS/pretrained_models'
BASE = {'gpt': PRE / 's1v3.ckpt', 'sovits': PRE / 'v2Pro/s2Gv2ProPlus.pth'}
LANG = {'Chinese': 'zh', 'English': 'en'}      # v2 的 zh = 中英混合（VoiceTwin 同样：有汉字就按 zh 发）
INFER = dict(top_k=15, top_p=1.0, temperature=1.0, repetition_penalty=1.35)   # VoiceTwin default_config.yaml 的 infer


def load_tts(gpt, sovits):
    os.chdir(GSV)                                   # 官方代码里 sv、G2PW 等路径都是相对仓库根目录写的
    sys.path[:0] = [str(GSV), str(GSV / 'GPT_SoVITS')]
    from TTS_infer_pack.TTS import TTS, TTS_Config
    cfg = TTS_Config({'custom': {
        'device': 'cpu', 'is_half': False, 'version': 'v2ProPlus',
        't2s_weights_path': str(gpt), 'vits_weights_path': str(sovits),
        'bert_base_path': str(PRE / 'chinese-roberta-wwm-ext-large'),
        'cnhuhbert_base_path': str(PRE / 'chinese-hubert-base')}})
    return TTS(cfg)


def weights(c):
    if c.get('weights', 'base') == 'base':
        return BASE['gpt'], BASE['sovits']
    d = Path(os.environ['SOVITS_DIR'])
    sel = json.loads((d / 'ref.json').read_text('utf-8'))
    return d / sel['gpt'], d / sel['sovits']


def references(c):
    """返回 {语言: (参考 wav, 参考文字, prompt_lang, 辅助参考列表, 语速)}。参考必须 3—10 秒（官方 TTS.py 的限制）。
    voice（Release 录音 + spans）：中英文都用这一条中文参考；weights=teacher 且没写 voice：用 取模型.py 按 VoiceTwin
    的做法挑好的参考（每种语言主参考 + 2 条辅助参考，英文句用英文参考）和 models.json 的各语言语速。"""
    import soundfile as sf
    sp = float(c.get('speed', 1.0))
    if c.get('voice'):
        import subprocess
        import tempfile
        import 挑参考 as PR
        v = json.loads((ROOT / c['voice']).read_text('utf-8'))
        if 'source_url' in v:
            tmp = Path(tempfile.mkdtemp())
            src = tmp / v['source']
            subprocess.run(['curl', '-sSfL', '--retry', '5', '--retry-all-errors', '-o', str(src), v['source_url']], check=True)
            rw = PR.build_ref(PR.decode(src), v['spans'], fill=v.get('fill_seams', False))
            src.unlink()
            p = tmp / 'ref.wav'
            sf.write(str(p), rw, PR.SR)
        else:
            p = ROOT / v['wav']
        one = (p, v['ref_text'], 'zh', [], sp)
        return {'Chinese': one, 'English': one}
    d = Path(os.environ['SOVITS_DIR'])
    sel = json.loads((d / 'ref.json').read_text('utf-8'))
    out = {}
    for lang, code in (('Chinese', 'zh'), ('English', 'en')):
        key = 'en_tx' if code == 'en' and c.get('en_ref') == 'tx' else code   # en_ref: tx = 老师本人英文切片（取模型.py 从 transcripts.csv 挑）
        r = sel['refs'].get(key) or sel['refs']['zh']
        rc = ('en' if key == 'en_tx' else code) if key in sel['refs'] else 'zh'
        speed = float(c.get('speed', (sel.get('speed') or {}).get(rc, 1.0)))
        out[lang] = (d / r['main']['wav'], r['main']['text'], rc, [d / x['wav'] for x in r['aux']], speed)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', required=True)
    ap.add_argument('--shard', type=int)
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--out', default='out')
    a = ap.parse_args()
    task = json.loads(Path(a.task).read_text('utf-8'))
    JOBS = jobs(task)
    if a.list:
        print(json.dumps(list(range(len(JOBS)))))
        return
    import numpy as np
    import soundfile as sf
    sys.path[:0] = [str(ROOT / 'tools/tts'), str(Path(__file__).parent)]
    import gaokao_tts as G          # 处理链的依赖开头就导入：缺什么第一秒就停（铁律 15）
    import 讲解音频 as J
    import 多音字 as PY
    import 去呼吸  # noqa: F401
    import pyloudnorm, soxr, lameenc, scipy.signal  # noqa: F401
    out = Path(a.out).resolve()
    c, take, part = JOBS[a.shard]
    assert c['mode'] == 'gptsovits', c
    segs = json.loads((ROOT / task['script']).read_text('utf-8'))['segments']
    if task.get('only'):
        segs = [s for s in segs if s['id'] in task['only']]
        assert len(segs) == len(task['only']), '任务的 only 里有稿中没有的段'
    J.SPLIT = c.get('split', task.get('split', 'mark'))
    J.GAP_MAX = c.get('gap_max', task.get('gap_max'))
    nparts = task.get('parts', 1)
    segs = [s for i, s in enumerate(segs) if i % nparts == part]
    od = out / c['id'] / f'take{take}'
    od.mkdir(parents=True, exist_ok=True)
    meta = {'candidate': c, 'take': take, 'part': part, 'split': J.SPLIT, 'segments': [], 'engine': 'GPT-SoVITS v2ProPlus @ abe9843 (CPU)'}
    t0 = time.time()
    REFS = references(c)
    meta['refs'] = {k: {'text_chars': len(v[1]), 'lang': v[2], 'aux': len(v[3]), 'speed': v[4], 'wav': Path(v[0]).name} for k, v in REFS.items()}
    gc.collect()
    trim_heap()
    import torch
    torch.set_num_threads(4)
    tts = load_tts(*weights(c))
    meta['rss_after_load_mb'] = rss_mb()
    print('模型加载后常驻内存', meta['rss_after_load_mb'], 'MB', flush=True)
    gen = {**INFER, **task.get('gen', {}), **c.get('gen', {})}
    gen_en = {**gen, **c.get('gen_en', {})}   # 英文小段另用的采样参数（协调会话 2026-11-04：英文用 g1lt 的 top_k 10、温度 0.8，中文照旧）
    base_seed = lambda sid: take * 1000 + int(''.join(ch for ch in sid if ch.isdigit()) or 0)  # noqa: E731
    for s in J.expand(segs):
        ts = time.time()
        cap = J.token_cap(s['text'], s['lang'])
        mt = PY.model_text(s['text'])

        ref, ref_text, plang, aux, speed = REFS[s['lang']]
        if s['lang'] == 'English' and c.get('ref_free_en'):   # 无参考文本模式（官方 TTS.py：prompt_text 为空 → no_prompt_text；v2ProPlus 支持）
            ref_text = ''

        def gen1(seed, s=s, mt=mt, ref=ref, ref_text=ref_text, plang=plang, aux=aux, speed=speed):
            inp = {'text': mt, 'text_lang': LANG[s['lang']], 'ref_audio_path': str(ref),
                   'aux_ref_audio_paths': [str(x) for x in aux], 'prompt_text': ref_text, 'prompt_lang': plang,
                   'text_split_method': 'cut0', 'batch_size': 1, 'speed_factor': speed,
                   'fragment_interval': 0.3, 'seed': int(seed), 'parallel_infer': True, 'return_fragment': False,
                   'streaming_mode': False, 'super_sampling': False, 'sample_steps': 32,
                   **(gen_en if s['lang'] == 'English' else gen)}
            chunks, sr = [], None
            for sr, w in tts.run(inp):
                chunks.append(np.asarray(w))
            x = np.concatenate(chunks).astype(np.float32)
            if np.abs(x).max() > 1.5:          # 官方输出 int16
                x = x / 32768.0
            return x, sr

        x, sr, tries = J.run_unit(gen1, base_seed(s['id']), cap)
        sf.write(str(od / f"{s['id']}.wav"), x, sr)
        el = time.time() - ts
        gc.collect()
        trim_heap()
        rss = rss_mb()
        meta['rss_peak_mb'] = max(meta.get('rss_peak_mb') or 0, rss or 0)
        if rss and rss > RSS_WARN_MB:
            meta.setdefault('rss_over', []).append([s['id'], rss])
        meta['segments'].append({'id': s['id'], 'sec': round(len(x) / sr, 2), 'compute': round(el, 1), 'sr': sr, 'cap': cap,
                                 'tries': tries, 'rss_mb': rss})
        print(f"{c['id']} take{take} {s['id']} {meta['segments'][-1]['sec']}s 音频，用时 {el:.0f}s，内存 {rss} MB", flush=True)
    meta['total_compute'] = round(time.time() - t0, 1)
    if nparts == 1:                       # 整份稿在这一台机器上：就地走完整处理链（与 qwen_synth 同一段）
        a_, items = J.build(segs, od)
        mx, top = J.tonal_scan(a_, G.OUT_SR, items)
        meta['buzz_top'] = top
        try:
            meta['buzz_tone'] = list(J.checks(a_, items))
            cert = G.save_checked(od / '成品.mp3', a_, items, -16.0)
            meta['chain'] = {'passed': True, 'loudness': cert['loudness']}
            (od / '成品.timings.json').write_text(json.dumps({'duration': round(len(a_) / G.OUT_SR, 3), 'items': items, 'buzz_top': top,
                                                          'certificate': cert, 'loudness': cert['loudness'], 'clause_check': G.CHAIN},
                                                         ensure_ascii=False, indent=1), 'utf-8')
        except RuntimeError as e:
            meta['chain'] = {'passed': False, 'error': str(e)}
        print('处理链：', meta['chain'], flush=True)
    (od / f'meta_part{part}.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), 'utf-8')


if __name__ == '__main__':
    main()
