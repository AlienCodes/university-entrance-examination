#!/usr/bin/env python3
"""开头剪切点（老师要求 6：剪掉音乐、试音、通用说明，从“第一节 / Section A”说明开始）→ 识别/<套>/锚点.json
全国类：分块识别里第一处含“第一节”（不含“结束”）的中文块，连着的几块算一处，必须恰好一处；录音本身就从
“阅读第一小题”开始的（如 2021 浙江 6 月）不剪（cut = 0）。
上海：含 “section a” 的块用 SenseVoice 逐字时刻找到 section 一词，剪在它之前最安静的 20 毫秒处。
剪切点都在静音里：在锚点开口前 1 秒内取最安静的一帧（不早于上一块结束）。
用法：/opt/ttsenv/bin/python 锚点.py <解压目录> [套 ...]"""
import glob, json, re, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
K = ROOT / '高考听力/识别'


def quiet(db, lo, hi):
    i0, i1 = int(lo / 0.02), max(int(lo / 0.02) + 1, int(hi / 0.02))
    return round((i0 + int(np.argmin(db[i0:i1]))) * 0.02 + 0.01, 2)


def main():
    raw = Path(sys.argv[1]); only = sys.argv[2:]
    rec = None
    for d in sorted(K.iterdir()):
        if only and d.name not in only: continue
        B = json.loads((d / '分块.json').read_text('utf-8'))
        f = raw / (d / '原音.sha256').read_text('utf-8').split('  ', 1)[1].strip()
        sr = 16000                                   # 管道解码（只读，不写音频文件）
        a = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', str(f), '-map', '0:a:0', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
                                         capture_output=True, check=True).stdout, dtype=np.float32)
        n = len(a) // 320
        db = 10 * np.log10((a[:n * 320].reshape(n, 320) ** 2).mean(1) + 1e-12)
        if '上海' in d.name:
            hit = [i for i, b in enumerate(B) if b[0] < 200 and re.search(r'section\s*a\b', b[3], re.I)]
            hit = hit[:1]                                  # 第一处（说明里会再提一次 Section A）
            if not hit: print(d.name, '停止：没有 Section A 块'); continue
            b = B[hit[0]]
            if rec is None:
                import sherpa_onnx
                m = glob.glob(str(ROOT / 'tools/tts/models/sherpa-onnx-sense-voice-*'))[0]
                rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(model=m + '/model.int8.onnx', tokens=m + '/tokens.txt', language='auto', use_itn=True, num_threads=4)
            s0 = max(0, b[0] - 0.1)
            st = rec.create_stream(); st.accept_waveform(sr, a[int(s0 * sr):int((b[1] + 0.1) * sr)]); rec.decode_stream(st)
            tk = [(x.strip().lower(), s0 + ts) for x, ts in zip(st.result.tokens, st.result.timestamps)]
            j = [i for i in range(len(tk) - 1) if tk[i][0] == 'section' and tk[i + 1][0] == 'a']
            if not j: print(d.name, '停止：逐字时刻里没有 section A'); continue
            ts = tk[j[0]][1]
            prev = B[hit[0] - 1][1] if hit[0] else 0
            cut = quiet(db, max(prev, ts - 1.0), ts - 0.05)
            why = f'Section A（{b[3][:40]}…）section 开口 {ts:.2f}'
        else:
            zh = [i for i, b in enumerate(B) if re.search(r'第一节', b[3]) and '结束' not in b[3]]
            cl = []
            for i in zh:
                if cl and B[i][0] - B[cl[-1][-1]][1] < 6: cl[-1].append(i)
                else: cl.append([i])
            if len(cl) == 0 and re.search(r'第(一|1)小题|现在', B[0][3]) and B[0][0] < 3:
                cut, ts, why = 0.0, B[0][0], f'录音本身从第一节开始（{B[0][3]}{B[1][3]}）'
            elif len(cl) != 1:
                print(d.name, '停止：“第一节”找到', len(cl), '处', [B[c[0]][3] for c in cl]); continue
            else:
                i = cl[0][0]; ts = B[i][0]; prev = B[i - 1][1] if i else 0
                cut = quiet(db, max(prev, ts - 1.0), ts - 0.05) if ts > 0.5 else 0.0
                why = f'“{B[i][3]}” 开口 {ts:.2f}'
        (d / '锚点.json').write_text(json.dumps({'cut': cut, 'anchor': round(ts, 2), '依据': why}, ensure_ascii=False), 'utf-8')
        print(d.name, cut, why)


main()
