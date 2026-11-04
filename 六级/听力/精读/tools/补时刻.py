"""定稿.json 里一串没有时刻的词（转写有、识别.json 漏了的整句，如 202009-1 的 Section B 说明），用原音再识别一遍补上逐词时刻（踩坑 124）。

原音音轨.py 对没有时刻的词按前后均分；整句都没有时刻、前后又隔着长静音时，均分会把句子放进静音里（202009-1 第 66、67 句）。
这里只补 ≥ MIN_RUN 个词连续没有时刻的段：在前一个有时刻的词的终点与后一个的起点之间，用 parakeet 识别原音，
逐词对上（与原文同词）就写识别出的开口 / 收尾时刻；对不上的词仍留 None（由原音音轨均分）。对上不到一半就停，不写。

    /opt/ttsenv/bin/python 六级/听力/精读/tools/补时刻.py 202009-1 --mp3 /home/user/wav/cet6-202009-1.mp3
"""
import argparse
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools' / 'tts'))
import 听对 as H  # noqa: E402

MIN_RUN = 5
norm = lambda w: re.sub(r'[^a-z0-9]', '', w.lower())


def words_with_times(a16, t0, t1):
    asr = H.recognizer()
    st = asr.create_stream()
    st.accept_waveform(16000, a16[int(t0 * 16000): int(t1 * 16000)])
    asr.decode_stream(st)
    out = []
    for tok, t in zip(st.result.tokens, st.result.timestamps):
        if tok.startswith(' ') or not out:
            out.append([tok.strip(), t0 + t])
        else:
            out[-1][0] += tok
    for i, w in enumerate(out):                      # 收尾：下一个词的开口（最后一个词 + 0.5 秒）
        w.append(out[i + 1][1] if i + 1 < len(out) else min(t1, w[1] + 0.5))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sid')
    ap.add_argument('--mp3', required=True)
    a = ap.parse_args()
    h = hashlib.sha256(Path(a.mp3).read_bytes()).hexdigest()
    if f'{h}  cet6-{a.sid}.mp3' not in (ROOT / '六级/听力/原始材料/SHA256SUMS').read_text('utf-8'):
        sys.exit('原音 sha256 不在 SHA256SUMS')
    f = ROOT / '六级' / '听力' / a.sid / '定稿.json'
    d = json.loads(f.read_text('utf-8'))
    W = d['词']
    a16 = H.load16(a.mp3)
    i, n_fix = 0, 0
    while i < len(W):
        if W[i][1] is not None:
            i += 1
            continue
        j = i
        while j < len(W) and W[j][1] is None:
            j += 1
        if j - i >= MIN_RUN and i and j < len(W):
            t0, t1 = W[i - 1][2], W[j][1]
            heard = words_with_times(a16, t0, t1)
            A, B = [norm(w[0]) for w in W[i:j]], [norm(w[0]) for w in heard]
            got = 0
            for m in difflib.SequenceMatcher(None, A, B, autojunk=False).get_matching_blocks():
                for q in range(m.size):
                    W[i + m.a + q][1], W[i + m.a + q][2] = round(heard[m.b + q][1], 2), round(heard[m.b + q][2], 2)
                    got += 1
            if got < (j - i) / 2:
                sys.exit(f'{a.sid} 第 {i}—{j - 1} 词只对上 {got}/{j - i}：{" ".join(w[0] for w in W[i:j])[:80]} ｜ 听到 {" ".join(B)[:80]}')
            print(f'{a.sid} 第 {i}—{j - 1} 词（{t0:.2f}—{t1:.2f}s）补上 {got}/{j - i}：{" ".join(w[0] for w in W[i:i + 8])} …')
            n_fix += got
        i = j
    f.write_text(json.dumps(d, ensure_ascii=False, indent=0), 'utf-8')
    print(f'{a.sid}：共补 {n_fix} 个词的时刻')


if __name__ == '__main__':
    main()
