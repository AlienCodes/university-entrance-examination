"""原文疑点 → 原文订正.json（零 token）：标注员报的疑点逐条分两类处理，文字永远以录音为准（画面英文 = 录音说的话）。

    /opt/ttsenv/bin/python 四级/听力/精读/tools/订正核对.py 202206-1 [… ] [--写]

疑点文件 原文疑点_<套>.json：[{"句": k, "原": "切句后全文里恰好出现一次的片段（可跨句）", "改为": "…", "理由": "…"}]
- 只改标点 / 大小写 / 撇号 / 连字符（去掉这些后词序列不变）：直接采用；
- 改了词（补词、删词、换词、拼写）：按 定稿.json 逐词时刻截出这一段原音（前后各多 1.5 秒），parakeet 独立识别，
  新旧两种写法（各带前后 4 个词）与识别结果比，新写法明显更像（相似度高 0.02 以上）才采用；
  打平（识别器认不出的人名拼写）时，新写法出现在官方原文（解析文字/<套>.txt）里也采用；其余一律不采用，列出来。
- “原”必须在该套全文里恰好出现一次（踩坑 17）；采用的写进 原文订正.json（不加 --写 只打印）。
"""
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
ROOT = C4.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools' / 'tts'))
import 切句  # noqa: E402


def norm(s):
    return re.sub(r'[^a-z0-9 ]', ' ', s.lower().replace('’', '').replace("'", '').replace('-', ' ')).split()


def full_text(sid, fixes):
    """切句.one 用的同一份全文（排版统一 + 标题标点 + 已有订正）。"""
    d = json.loads((C4.parent / sid / '定稿.json').read_text('utf-8'))
    P = 切句.one(sid, fixes)
    return ' '.join(s for p in P for s in p), d


def window(words, frag_toks, ctx_before):
    """定稿逐词里找这一段（按规范化词序列），返回 (起秒, 止秒)。"""
    W = [(norm(w[0]), w[1], w[2]) for w in words]
    flat = [(t, a, b) for ts, a, b in W for t in ts]
    toks = [t for t, _, _ in flat]
    key = (ctx_before[-2:] + frag_toks)[:8] or ctx_before[-4:]
    for i in range(len(toks) - len(key) + 1):
        if toks[i:i + len(key)] == key:
            seg = [x for x in flat[max(0, i - 4):i + len(key) + 8] if x[1] is not None]
            if seg:
                return seg[0][1], seg[-1][2]
    return None


def asr(mp3, a, b):
    import numpy as np
    import 听对 as H
    y = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, a - 1.5):.2f}', '-t', f'{b - a + 3:.2f}', '-i', str(mp3),
                        '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    x = np.frombuffer(y, dtype=np.float32)
    r = H.recognizer()
    st = r.create_stream()
    st.accept_waveform(16000, x)
    r.decode_stream(st)
    return norm(st.result.text)


def main():
    a = sys.argv[1:]
    ids = [x for x in a if not x.startswith('--')]
    ff = C4 / '原文订正.json'
    fixes = json.loads(ff.read_text('utf-8'))
    wav = Path(__import__('os').environ.get('CET4_WAV', '/home/user/wav4'))
    bad = 0
    for sid in ids:
        qf = C4 / f'原文疑点_{sid}.json'
        if not qf.exists():
            print(f'{sid}：没有疑点文件')
            continue
        Q = json.loads(qf.read_text('utf-8'))
        text, d = full_text(sid, fixes)
        mp3 = wav / f"cet4-{d['录音']}.mp3"
        off = (ROOT / '四级' / '听力' / '解析文字' / f'{sid}.txt')
        official = off.read_text('utf-8') if off.exists() else ''
        have = {tuple(f[:2]) for f in fixes.get(sid, [])}
        take = []
        for q in Q:
            o, n, why = q['原'], q['改为'], q.get('理由', '')
            if (o, n) in have:
                continue
            c = text.count(o)
            if c != 1:
                print(f'  ✗ {sid} 第{q.get("句")}句 “{o}” 在全文出现 {c} 次（要恰好 1 次）')
                bad += 1
                continue
            if norm(o) == norm(n):
                take.append([o, n, f'{why}（只改标点）'])
                print(f'  ✓ 标点 {sid} “{o}” → “{n}”')
                continue
            i = text.index(o)
            before, after = norm(text[:i])[-4:], norm(text[i + len(o):])[:4]
            win = window(d['词'], norm(o), before)
            if not win:
                print(f'  ✗ {sid} “{o}” 在定稿逐词里找不到时刻')
                bad += 1
                continue
            heard = asr(mp3, *win)
            ro = difflib.SequenceMatcher(None, before + norm(o) + after, heard).ratio()
            rn = difflib.SequenceMatcher(None, before + norm(n) + after, heard).ratio()
            off_ok = bool(official) and re.sub(r'\W+', ' ', n).strip().lower() in re.sub(r'\W+', ' ', official).lower()
            if rn > ro + 0.02 or (abs(rn - ro) <= 0.02 and off_ok and len(norm(o)) == len(norm(n))):
                take.append([o, n, f'{why}（录音识别核对：旧 {ro:.2f} → 新 {rn:.2f}{"，官方原文同" if off_ok else ""}）'])
                print(f'  ✓ 改词 {sid} “{o}” → “{n}”（{ro:.2f} → {rn:.2f}{"，官方原文同" if off_ok else ""}）')
            else:
                print(f'  ✗ 不采用 {sid} “{o}” → “{n}”（{ro:.2f} → {rn:.2f}；识别：{" ".join(heard)}）')
        if '--写' in a and take:
            fixes.setdefault(sid, []).extend(take)
            fixes[sid] = fixes[sid]
        print(f'{sid}：疑点 {len(Q)} 条，采用 {len(take)} 条')
    if '--写' in a:
        ff.write_text(json.dumps(fixes, ensure_ascii=False, indent=1), 'utf-8')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
