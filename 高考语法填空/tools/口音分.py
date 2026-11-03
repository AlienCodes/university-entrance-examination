"""英文口音分（在 GitHub Actions 上跑：模型在 HuggingFace，本机代理拦）。用户 2026-11-03：英文中文口音太重。

每个候选、每次合成的英文小段（讲解音频.expand 里 lang = English 的）原始 WAV，用 speechbrain 的 CommonAccent 口音分类器
（Jzuluaga/accent-id-commonaccent_ecapa，16 种英语口音）算各口音概率；“地道分” = us + england + canada + australia + newzealand + ireland
+ scotland 的概率之和（母语口音），同时记录 hongkong（最接近中式口音的一类）。只作选优与汇报的参考分，不作关卡。
用法：python 口音分.py --task 任务.json --out out     # 对 out/<候选>/take*/ 写 口音分.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ['us', 'england', 'canada', 'australia', 'newzealand', 'ireland', 'scotland']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', required=True)
    ap.add_argument('--out', default='out')
    a = ap.parse_args()
    sys.path[:0] = [str(ROOT / 'tools/tts'), str(Path(__file__).parent)]
    import soundfile as sf
    import soxr
    import torch
    from speechbrain.inference.classifiers import EncoderClassifier
    import 讲解音频 as J
    task = json.loads(Path(a.task).read_text('utf-8'))
    segs = json.loads((ROOT / task['script']).read_text('utf-8'))['segments']
    if task.get('only'):
        segs = [s for s in segs if s['id'] in task['only']]
    en = [u for u in J.expand(segs) if u['lang'] == 'English']
    clf = EncoderClassifier.from_hparams(source='Jzuluaga/accent-id-commonaccent_ecapa', savedir='/tmp/accent_model')
    labs = [clf.hparams.label_encoder.ind2lab[i] for i in range(len(clf.hparams.label_encoder.ind2lab))]
    for td in sorted(Path(a.out).glob('*/take*')):
        res = {}
        for u in en:
            w = td / f"{u['id']}.wav"
            if not w.exists():
                continue
            x, sr = sf.read(str(w), dtype='float32')
            x = soxr.resample(x, sr, 16000).astype(np.float32)
            out = clf.classify_batch(torch.from_numpy(x)[None])[0][0].detach().numpy().astype(np.float64)
            p = np.exp(out - out.max()) if out.max() <= 0 else out    # 输出是对数概率时取指数
            p = p / p.sum()
            pr = dict(zip(labs, p.tolist()))
            res[u['id']] = {'text': u['text'], 'native': round(sum(pr.get(k, 0) for k in NATIVE), 3),
                            'hongkong': round(pr.get('hongkong', 0), 3), 'top': max(pr, key=pr.get)}
        (td / '口音分.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), 'utf-8')
        nat = [r['native'] for r in res.values()]
        print(td, '地道分均值', round(float(np.mean(nat)), 3) if nat else None, flush=True)


if __name__ == '__main__':
    main()
