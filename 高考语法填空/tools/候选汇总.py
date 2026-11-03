"""第 56 题配音候选的评分汇总与推荐（程序算，不靠感觉）。
每个候选：英文地道分（口音分.py，选中那次的英文小段平均）、英文词错率（选段.json：parakeet / SenseVoice 回转，选中那次）、
说话人相似度（整段 / 英文部分，像不像.py 的表）、UTMOS 自然度、语速与音高起伏（语速语调.py，对照用户录音）。
硬条件（不满足不推荐）：整段相似度 ≥ 0.80、英文部分相似度 ≥ 0.80（用户 2026-11-03：英文也必须是本人音色）、语速与音高起伏合格。
推荐：满足硬条件的里，按 英文地道分 − 词错率 + 相似度 排序。
用法：/opt/ttsenv/bin/python 候选汇总.py --稿 稿.json --像不像 表.md --out 评分.md 候选1.mp3 候选2.mp3 …
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [str(Path(__file__).parent)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--像不像', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--稿', required=True)
    ap.add_argument('mp3', nargs='+')
    a = ap.parse_args()
    import 挑参考 as PR
    import 讲解音频 as J
    import 语速语调 as SY
    EN = {u['id'] for u in J.expand(json.loads(Path(a.稿).read_text('utf-8'))['segments']) if u['lang'] == 'English'}
    tgt = json.loads(SY.TARGET.read_text('utf-8'))
    sim = {}
    for l in Path(a.像不像).read_text('utf-8').splitlines():
        c = [x.strip() for x in l.split('|')]
        if len(c) > 4 and c[1].endswith('.mp3'):
            sim[c[1]] = (float(c[2]), float(c[3]), None if c[4] == '—' else float(c[4]))
    asr, rows = PR.ASR(), []
    for p in map(Path, a.mp3):
        ch = json.loads(p.with_suffix('.选段.json').read_text('utf-8'))['chosen']
        en = {k: v for k, v in ch.items() if k in EN}
        nat = [v['native'] for v in en.values() if v.get('native') is not None]
        nw = sum(v['n_words'] for v in en.values())
        wer = sum(v['err'] for v in en.values()) / nw if nw else None
        m, errs = SY.check_file(p, asr)
        s_all, mos, s_en = sim.get(p.name, (None, None, None))
        hard = []
        if s_all is None or s_all < 0.80:
            hard.append(f'整段相似度 {s_all}')
        if s_en is None or s_en < 0.80:
            hard.append(f'英文部分相似度 {s_en}')
        hard += errs
        rows.append({'name': p.name, 'native': round(float(np.mean(nat)), 3) if nat else None, 'wer': None if wer is None else round(wer, 3),
                     'sim': s_all, 'sim_en': s_en, 'mos': mos, 'rate': m['rate'], 'f0sd': m['f0sd_median'], 'hard': hard})
    ok = [r for r in rows if not r['hard']]
    for r in rows:
        r['score'] = round((r['native'] or 0) - (r['wer'] or 0) + (r['sim'] or 0), 3)
    best = max(ok, key=lambda r: r['score']) if ok else None
    L = [f"# 第 56 题配音候选评分（用户录音：语速 {tgt['rate']:.2f} 字/秒，音高起伏各句中位 {tgt['f0sd_median']} 半音、75% 分位 {tgt['f0sd_p75']}）", '',
         '| 候选 | 英文地道分（母语口音概率） | 英文词错率 | 相似度（整段） | 相似度（英文部分） | UTMOS 自然度 | 语速（字/秒） | 音高起伏（半音） | 不合格项 |',
         '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        L.append(f"| {r['name']} | {r['native']} | {r['wer']} | {r['sim']} | {r['sim_en']} | {r['mos']} | {r['rate']:.2f} | {r['f0sd']} | {'；'.join(r['hard']) or '—'} |")
    L += ['', f"推荐：{best['name'] if best else '没有满足全部硬条件的候选'}"]
    Path(a.out).write_text('\n'.join(L) + '\n', 'utf-8')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
