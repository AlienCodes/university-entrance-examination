"""双向验证（行为测试，踩坑 87）：真正调用 tools/video/verify_videos.check，看“音频合格证”“响度一致”两行的结论。
以前的验证只看源码里有没有某几个字，把 check 改成永远通过（ok(...,True)、certificate_problems(tm) and []、fine=... and False）三个验证照样 exit 0。

用新处理链真实生成的 k48 前 4 句（样本/意群响度_k48新链.flac）造一个临时项目：<临时>/项目/audio/cet4_male/x.mp3 + 合格证，
<临时>/项目/最终视频/x.mp4（ffmpeg 合成；本机、GitHub 都用真 MP4，没有 ffmpeg 时改用同一段音频直接喂给 check 的解码函数）。
check 不传 MP3 路径（专八、中考引擎就是这样调的），由它自己从视频位置找到 MP3、核旁证和 sha256。
  用例：① 合格 → 两行都 ✅；② 没有合格证；③ 手写最小合格证；④ 合格证里写超标值；⑤ 旁证 passed=False 而 timings 写 True；
        ⑥ MP3 在检查之后被改过；⑦ 视频音轨里一个意群末尾被压低 5 dB（合格证照旧）→ 响度一致必须 ❌（意群检查自己判，不靠崩溃）；
        ⑧ 找不到 MP3 → 合格证必须 ❌。
  变异：把 verify_videos / gaokao_tts 改成“永远通过”的 5 种写法，每一种都必须让上面至少一个用例失败（证明本验证真能抓住）。
    python3 tools/防复发/验证/合格证视频核查.py"""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
sys.path[:0] = [str(R / 'tools' / 'tts'), str(R / 'tools' / 'video')]
import gaokao_tts as G0  # noqa: E402
import 合格证 as CERT  # noqa: E402

A, SR = sf.read(str(HERE / '样本' / '意群响度_k48新链.flac'), dtype='float32')
ITEMS = json.loads((HERE / '样本' / '意群响度_k48新链.json').read_text('utf-8'))['sentences']
_d, _ = sf.read(__import__('io').BytesIO(G0.encode_mp3(A)), dtype='float64')
A = (A * 10 ** ((-16.3 - __import__('pyloudnorm').Meter(SR).integrated_loudness(_d)) / 20)).astype('float32')   # 编成 MP3 后整体 −16.3 LUFS（离峰值上限留点余量）
FF = shutil.which('ffmpeg') and shutil.which('ffprobe')
CERT_ROW, LOUD_ROW = '音频合格证（处理链版本、意群响度检查）', '响度一致（第一项检查）'
P = {'year': 2026, 'paper': '测试卷', 'part': 'C', 'title': '合格证', 'paras': [[{'en': f's{i}', 'w': [1]} for i in range(len(ITEMS))]]}


def load(name, path, src=None):
    """按源码（可变异）加载模块，并登记到 sys.modules（verify_videos.check 里 from gaokao_tts import … 取的就是它）。"""
    if src is not None:
        d = Path(tempfile.mkdtemp())
        path = d / f'{name}.py'
        path.write_text(src, 'utf-8')
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def dip(x, s, e, db):
    y = x.copy()
    y[int(s * SR):int(e * SR)] *= 10 ** (-db / 20)
    return y


def make(root, mp3_bytes, video_audio):
    """临时项目：audio/ 下放 MP3，最终视频/ 下放 MP4（音轨 = video_audio）。"""
    (root / 'audio' / 'cet4_male').mkdir(parents=True, exist_ok=True)
    (root / '最终视频').mkdir(exist_ok=True)
    (root / 'audio' / 'cet4_male' / 'x.mp3').write_bytes(mp3_bytes)
    mp4 = root / '最终视频' / 'x.mp4'
    wav = root / 'v.wav'
    sf.write(str(wav), video_audio, SR, subtype='FLOAT')
    if FF:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=black:s=320x180:r=30:d={len(video_audio) / SR:.3f}',
                        '-i', str(wav), '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
                        '-shortest', str(mp4)], check=True)
    else:
        mp4.write_bytes(wav.read_bytes())
    return mp4


def run_check(V, mp4):
    V.frame = lambda mp4, t, tmp: np.zeros(4, np.float32)      # 画面切换与合格证无关，免得抽几十帧
    if not FF:                                                # 没有 ffmpeg：解码函数直接读同一段音频
        x, _ = sf.read(str(mp4), dtype='float32')
        d = len(x) / SR
        V.audio_of = lambda m, sr=48000: (x, SR)
        V.run = lambda cmd: (json.dumps({'streams': [{'codec_type': 'video', 'width': 3840, 'height': 2160, 'duration': d},
                                                     {'codec_type': 'audio', 'duration': d}]}) if 'stream=codec_type,width,height,duration' in cmd
                             else '\n'.join(f'{i / 30:.6f}' + (',0.021' if 'a' in cmd else '') for i in range(int(d * 30))))
    return {n: (c, dt) for n, c, dt in V.check(mp4, P, TM)}


def prepare(G, top):
    """造 7 个用例的临时项目（只造一次，现在的程序和每种变异都用同一批 MP4）。"""
    mp3 = G.encode_mp3(A)
    rep, errs = G.final_check(mp3, ITEMS, -16.0)
    assert not errs, errs
    cert = G.certificate(mp3, rep)
    base = {'file': 'cet4_male/x.mp3', 'duration': round(len(A) / SR, 3), 'loudness': rep, 'sentences': ITEMS,
            'clause_check': CERT.CHAIN, 'certificate': cert}
    dec, _ = sf.read(__import__('io').BytesIO(mp3), dtype='float32')
    RX = __import__('响度细查')
    long_ = max((r for r in RX.clause_stats(RX.clause_loudness(dec, SR, ITEMS)) if r['dur'] >= 1.6), key=lambda r: r['dur'])
    hi = dict(cert, loudness=dict(rep, clause_nb_min_lu=-1.9))
    mini = {'chain': CERT.CHAIN, 'passed': True}
    cases = [
        ('① 合格的新音频 → 合格证 ✅、响度 ✅', base, cert, mp3, dec, {CERT_ROW: True, LOUD_ROW: True}),
        ('② 没有合格证 → 合格证 ❌', {k: v for k, v in base.items() if k not in ('clause_check', 'certificate')}, None, mp3, dec, {CERT_ROW: False}),
        ('③ 手写最小合格证 {chain, passed} → 合格证 ❌', dict(base, certificate=mini), mini, mp3, dec, {CERT_ROW: False}),
        ('④ 合格证里写超标值（相邻意群 −1.9 LU）→ 合格证 ❌', dict(base, certificate=hi, loudness=hi['loudness']), hi, mp3, dec, {CERT_ROW: False}),
        ('⑤ 旁证 passed=False、timings 写 True → 合格证 ❌', base, dict(cert, passed=False), mp3, dec, {CERT_ROW: False}),
        ('⑥ MP3 在检查之后被改过（check 自己找 MP3）→ 合格证 ❌', base, cert, mp3[:-200] + bytes(200), dec, {CERT_ROW: False}),
        ('⑦ 视频音轨一个意群末尾压低 5 dB（合格证照旧）→ 响度 ❌', base, cert, mp3,
         dip(dec, long_['end'] - 0.8, long_['end'], 5.0), {CERT_ROW: True, LOUD_ROW: False}),
        ('⑧ 找不到 MP3（磁盘和仓库 audio 里都没有）→ 合格证 ❌', base, cert, None, dec, {CERT_ROW: False}),
    ]
    out = []
    for i, (name, tm, side, data, vaudio, want) in enumerate(cases):
        root = Path(top) / f'c{i}' / '项目'
        mp4 = make(root, mp3 if data is None else data, vaudio)
        if data is None:                          # ⑧：视频做好后 MP3 不见了
            (root / 'audio' / 'cet4_male' / 'x.mp3').unlink()
        if side is not None:
            (root / 'audio' / 'cet4_male' / 'x.loudness.json').write_text(json.dumps(side), 'utf-8')
        out.append((name, tm, mp4, want))
    return out


def suite(V, cases):
    """跑全部用例，返回失败的用例名。"""
    global TM
    bad = []
    for name, tm, mp4, want in cases:
        TM = tm
        try:
            got = run_check(V, mp4)
            miss = [f"{k} 应为 {'✅' if w else '❌'}，实际 {'✅' if got[k][0] else '❌'}（{got[k][1][:80]}）"
                    for k, w in want.items() if k not in got or got[k][0] != w]
        except Exception as e:                      # 崩溃不算拦住（以前关掉 if fine: 只靠 KeyError 被拦）
            miss = [f'check 崩溃：{type(e).__name__}: {e}']
        print(f"    {'✅' if not miss else '❌'} {name}" + (f'：{miss}' if miss else ''))
        if miss:
            bad.append(name)
    return bad


def main():
    print(f"合格证视频核查（{'真 MP4，ffmpeg' if FF else '没有 ffmpeg：解码函数读同一段音频'}）")
    vsrc = (R / 'tools/video/verify_videos.py').read_text('utf-8')
    gsrc = (R / 'tools/tts/gaokao_tts.py').read_text('utf-8')
    fails = []
    top = tempfile.mkdtemp()
    cases = prepare(G0, top)
    print('  现在的程序：')
    bad = suite(load('verify_videos', R / 'tools/video/verify_videos.py'), cases)
    if bad:
        fails.append(f'现在的程序有用例失败：{bad}')
    MUT = [
        ('verify_videos：合格证那一行永远通过 ok(…, True, …)', 'v', f"ok('{CERT_ROW}', not cp,", f"ok('{CERT_ROW}', True,"),
        ('verify_videos：cert_check(...) and []', 'v', 'cp = cert_check(mp4, tm, mp3_path)', 'cp = cert_check(mp4, tm, mp3_path) and []'),
        ('verify_videos：fine=not is_legacy(tm) and False', 'v', 'fine=not is_legacy(tm))', 'fine=not is_legacy(tm) and False)'),
        ('verify_videos：找不到 MP3 就放行 return [] and [...]（协调会话复核补）', 'v', '        return [f"找不到这个视频用的 MP3', '        return [] and [f"找不到这个视频用的 MP3'),
        ('gaokao_tts：关掉 if fine:（意群检查不跑）', 'g', '    if fine:\n        import importlib', '    if False:\n        import importlib'),
    ]
    for name, which, a, b in MUT:
        src = vsrc if which == 'v' else gsrc
        if src.count(a) != 1:
            fails.append(f'变异「{name}」的原文在程序里找不到（程序改了，变异也要跟着改）')
            continue
        print(f'  变异：{name}')
        load('gaokao_tts', None, src.replace(a, b) if which == 'g' else gsrc)
        V = load('verify_videos', None, src.replace(a, b) if which == 'v' else vsrc)
        caught = suite(V, cases)
        print(f"    {'✅ 抓到' if caught else '❌ 没抓到'}（{len(caught)} 个用例失败）")
        if not caught:
            fails.append(f'变异「{name}」没被抓到')
    shutil.rmtree(top, ignore_errors=True)
    if fails:
        sys.exit('合格证视频核查双向验证失效：\n  ' + '\n  '.join(fails))
    print('合格证视频核查双向验证：全部通过')


if __name__ == '__main__':
    main()
