"""英文逐词核对（踩坑 27：识别差异必须核对，不能直接判成识别器的问题）：合成目录里某小段的每一次，
用识别对齐找到英文词的位置，前后各多留 0.3 秒切出来，纯英文识别（parakeet）再识别；识别结果里有这个词 = 这一次读对。
输出第一个全部词都读对的那一次（给 续写全片.sh 的 LOCK），没有就输出空并在 stderr 列出每次读成了什么。
用法：/opt/ttsenv/bin/python 高考续写/tools/英文逐词核对.py <合成目录…/<候选>> <稿.json> <小段 id> <词> [词…]"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import soxr

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '高考语法填空/tools'), str(ROOT / 'tools/tts')]
import gaokao_tts as G  # noqa: E402
import 讲解音频 as J  # noqa: E402
import 讲解节奏 as NJ  # noqa: E402
import 选型评测 as E  # noqa: E402


def main():
    run, script, uid, *words = sys.argv[1:]
    J.SPLIT = 'mark'
    U = {u['id']: u for u in J.expand(json.loads(Path(script).read_text('utf-8'))['segments'])}
    text = U[uid]['text']
    ears, al = E.Ears(), NJ.Aligner()
    ref = [z for z in NJ.toks(text) if z not in '？?']
    for d in sorted(Path(run).glob('take*'), key=lambda p: int(p.name[4:])):
        w = d / f'{uid}.wav'
        if not w.exists():
            continue
        x = J.load(w)
        hyp = al(x, G.SR)
        m = NJ.align_index(ref, hyp)
        got = {}
        for word in words:
            for i, z in enumerate(ref):
                if z.lower() != word.lower():
                    continue
                if i not in m:
                    got.setdefault(word, []).append('（对不上）')
                    continue
                j = m[i]
                t0 = hyp[j][1]
                t1 = hyp[j + 1][1] if j + 1 < len(hyp) else len(x) / G.SR
                seg = x[max(0, int((t0 - 0.3) * G.SR)):int((t1 + 0.3) * G.SR)]
                got.setdefault(word, []).append(ears.rec(ears.en, soxr.resample(seg, G.SR, 16000).astype(np.float32)))
        ok = all(any(re.search(rf'\b{re.escape(wd)}\b', r, re.I) for r in got.get(wd, [])) for wd in words)
        print(f'{uid} {d.name}: {got} → {"读对" if ok else "不对"}', file=sys.stderr)
        if ok:
            print(d.name)
            return
    print('')


if __name__ == '__main__':
    main()
