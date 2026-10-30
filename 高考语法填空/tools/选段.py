"""逐段选优 + 完整处理链（全片配音）：Actions 每段合成 N 次（runs/<任务>/<音色>/take*/<段>.wav），程序为每段挑一次：
  ① 识别回转（SenseVoice 中英混合；英文段再用 parakeet）：真错误数最少——同音字（它/他、形/型……）不算错，
     只比英文单词、以及中文按拼音（不计声调）比；
  ② 段内意群最匀：segment 之后各意群 BS.1770 响度的最大差、段尾 0.8 秒元音比本段低多少（与成品检查同一量法）；
  ③ 时长不离谱（语速：中文段每字 0.12—0.4 秒）。
然后走 讲解音频.render（陷波 → segment → 拼接 → master → final_check（含意群级）→ 合格证）。整篇检查没过，
就把报错的意群所在的段换成下一个候选，最多换 8 轮；还过不了就报错退出（不放宽检查）。
输出：成品 MP3 + 合格证 + timings、选段.json（每段选了哪次、为什么）、识别差异.md（每段最终的识别差异，供人工核对）。
用法：/opt/ttsenv/bin/python 选段.py --稿 稿.json --run runs/任务_全片-N/teacher_m --out 成品.mp3 [--only 段id…]
"""
import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / 'tools/tts')]
import gaokao_tts as G  # noqa: E402
import 讲解音频 as J  # noqa: E402
import 选型评测 as E  # noqa: E402


def pinyin_toks(s):
    from pypinyin import lazy_pinyin
    out = []
    for t in E.toks(s):
        out.append(lazy_pinyin(t)[0] if re.match(r'[一-鿿]', t) else t)
    return out


def seg_score(x):
    """segment 之后：意群响度最大差（LU）、段尾 0.8 秒元音落差（dB，负数 = 变小）。"""
    import 响度细查 as RX
    y, P = J.per_clause(J.notch(G.trim(x), G.SR))
    L = [G.gated_lufs(y[int(a * G.SR):int(b * G.SR)], G.SR) for a, b in P if b - a >= 0.8]
    spread = float(max(L) - min(L)) if len(L) > 1 else 0.0
    Lv, ok = RX.vowel_frames(y.astype(np.float64), G.SR)
    tails = [RX.tail_drop(Lv, ok, a, b) for a, b in P if b - a >= 1.6]
    tails = [t for t in tails if t is not None]
    return spread, (min(tails) if tails else 0.0)


def candidates(segs, run, ears, only=None):
    import soundfile as sf
    import soxr
    takes = sorted(Path(run).glob('take*'))
    table = {}
    for s in segs:
        if only and s['id'] not in only:
            continue
        rows = []
        for t in takes:
            w = t / f"{s['id']}.wav"
            if not w.exists():
                continue
            x = J.load(w)
            a16 = soxr.resample(x, G.SR, 16000).astype(np.float32)
            hyp = ears.rec(ears.sv, a16)
            ref, h = pinyin_toks(s['text']), pinyin_toks(hyp)
            err = E.ed(ref, h)
            diff = E.diff(E.toks(s['text']), E.toks(hyp))
            if s['lang'] == 'English' and ears.en:
                eh = E.toks(ears.rec(ears.en, a16))
                en_err = E.ed(E.toks(s['text']), eh)
                err = min(err, en_err)        # 两个识别器取较好的（识别器自己的错不算朗读的错）
                if en_err <= E.ed(ref, h):
                    diff = E.diff(E.toks(s['text']), eh)
            spread, tail = seg_score(x)
            n_zh = len(re.findall(r'[一-鿿]', s['text']))
            dur = len(x) / G.SR
            pace_bad = s['lang'] == 'Chinese' and n_zh and not (0.12 <= dur / max(n_zh + 2 * len(re.findall('[A-Za-z]+', s['text'])), 1) <= 0.4)
            score = err * 10 + max(0.0, spread - 1.0) * 3 + max(0.0, -tail - 2.0) * 2 + (20 if pace_bad else 0)
            rows.append({'take': t.name, 'err': err, 'diff': diff, 'spread': round(spread, 2), 'tail': round(tail, 2),
                         'dur': round(dur, 2), 'pace_bad': bool(pace_bad), 'score': round(score, 2)})
        rows.sort(key=lambda r: r['score'])
        table[s['id']] = rows
        print(s['id'], [(r['take'], r['score'], r['err']) for r in rows], flush=True)
    return table


def assemble(segs, run, table, out, lead, tail, max_rounds=8):
    pick = {sid: 0 for sid in table}
    for rnd in range(max_rounds + 1):
        tmp = Path(tempfile.mkdtemp(prefix='xd_'))
        try:
            for s in segs:
                r = table[s['id']][pick[s['id']]]
                shutil.copy(Path(run) / r['take'] / f"{s['id']}.wav", tmp / f"{s['id']}.wav")
            try:
                meta = J.render(segs, tmp, out, lead, tail)
                return pick, meta
            except RuntimeError as e:
                msg = str(e)
                print(f'第 {rnd + 1} 轮整篇检查未过：{msg[:300]}', flush=True)
                a, items = J.build(segs, tmp, lead, tail)
                bad = blame(a, items, msg)
                moved = False
                for sid in bad:
                    if pick[sid] + 1 < len(table[sid]):
                        pick[sid] += 1
                        moved = True
                if not moved:
                    raise RuntimeError('换遍候选仍过不了整篇检查（不放宽检查）：' + msg)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    raise RuntimeError('超过最多轮数')


def blame(a, items, msg):
    """从报错里的时间点找到对应的段（意群报 “（12.34s）” / “（12.34s 起）”）；短时波动等整体问题：段尾最差的段。"""
    import 响度细查 as RX
    ts = [float(x) for x in re.findall(r'（(\d+\.\d+)s', msg)]
    out = []
    for t in ts:
        for i, it in enumerate(items):
            if it['start'] - 0.3 <= t <= it['end'] + 0.3:
                out.append(it['id'])
                if '比相邻' in msg and i + 1 < len(items):
                    out.append(items[i + 1]['id'])      # 相邻意群小：也可能是后一段太响
                break
    if not out:
        st = RX.clause_stats(RX.clause_loudness(a.astype(np.float64), G.OUT_SR, items))
        worst = sorted(st, key=lambda r: r['d_nb'])[:2]
        out = [items[r['k'] - 1]['id'] for r in worst]
    return list(dict.fromkeys(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--稿', required=True)
    ap.add_argument('--run', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--lead', type=float, default=1.5)
    ap.add_argument('--tail', type=float, default=2.0)
    a = ap.parse_args()
    segs = json.loads(Path(a.稿).read_text('utf-8'))['segments']
    if a.only:
        segs = [s for s in segs if s['id'] in a.only]
    ears = E.Ears()
    table = candidates(segs, a.run, ears)
    pick, meta = assemble(segs, a.run, table, a.out, a.lead, a.tail)
    chosen = {sid: dict(table[sid][i], rank=i) for sid, i in pick.items()}
    out = Path(a.out)
    out.with_suffix('.选段.json').write_text(json.dumps({'run': str(a.run), 'chosen': chosen, 'all': table}, ensure_ascii=False, indent=1), 'utf-8')
    lines = [f"# 识别差异（{out.name}）", '', '每段最终选用那次的识别差异（同音字已按拼音放过；剩下的逐条人工核对）。', '']
    for s in segs:
        c = chosen[s['id']]
        if c['diff']:
            lines.append(f"- {s['id']}（{c['take']}，错 {c['err']}）：{'；'.join(c['diff'])}")
    out.with_suffix('.识别差异.md').write_text('\n'.join(lines) + '\n', 'utf-8')
    L = meta['certificate']['loudness']
    print(f"完成：{out}  {meta['duration']:.1f}s；整体 {L['integrated_lufs']}，句间 {L['sentence_max_dev_lu']}，短时 {L['short_term_std_lu']}，"
          f"峰值 {L['peak_dbfs']}，意群 {L['clause_nb_min_lu']} / 段尾 {L['clause_tail_min_db']}；电磁音 {meta['buzz_tone']}")


if __name__ == '__main__':
    main()
