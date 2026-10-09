"""生成西班牙语逐句精读视频（沿用四级设计方案 C「杂志编号注释」，用户给的参考图就是四级视频的一帧）。

    /opt/ttsenv/bin/python 西班牙语/tools/make_video.py es01 [--voice 音色名] [--scale 2]

画面、时间轴、编码、成品核查都沿用 四级/tools/make_video.py（不改四级程序，在这里覆盖西班牙语需要不同的部分）：
- 米白底、左侧墨绿竖带；西语原文 EB Garamond，生词右上角带编号，单词墨绿、短语砖红；中文思源宋体；右侧词汇栏按编号一一对应
- 片头静音 1.5 秒；句间 0.8 秒（读完后画面停留 0.5 秒再切换，0.3 秒后开读）；结尾静音 ≥ 2 秒
- 3840×2160，恒定 30 帧逐屏编码后无损拼接；生成后立即运行高考同一套 verify_videos.check 核查，任何一项不通过就删除成品
西班牙语不同的地方：
- 词条数据来自 西班牙语/文章/<id>.json（w：h 词头、pos 词性、zh 释义、surface 句中原形），词性按《现代西班牙语》习惯（m. f. adj. adv. tr. loc.）
- 多词词条（comida típica、cada vez que……）算短语（砖红色）；短语不显示 loc.，名词短语保留阴阳性（f. / m.）
- 片头：西语标题 + 中文标题 + 文档里的插图；页眉「SPANISH READING」
- 电磁音检查：在 2–16 kHz 全频段找窄带峰（新的语音模型声码器频点和 Kokoro 不同，不能只查四级那 9 个频点）
输入：西班牙语/文章/<id>.json、西班牙语/audio/timings.json（make_audio.py 生成）。输出：西班牙语/最终视频/。
"""
import argparse
import atexit
import html
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ES = HERE.parent
ROOT = ES.parent
sys.path[:0] = [str(ROOT / '四级' / 'tools'), str(ROOT / 'tools' / 'video'), str(ROOT / 'tools' / 'tts'), str(HERE)]
import make_video as C4V  # noqa: E402  四级的设计 C（CSS、字体、自动缩放字号）

W, H = C4V.W, C4V.H
MIN_FS, MIN_VS = C4V.MIN_FS, C4V.MIN_VS
LETTERS = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")

CSS_ES = """
.ttl{right:110px}
.ttl .tag{font-size:26px}
.ttl .row{display:flex;align-items:center;gap:70px}
.ttl .txt{flex:1;min-width:0}
.ttl h1{font-family:'EB Garamond',serif;font-weight:600;font-size:104px;line-height:1.12;margin:34px 0 24px;text-wrap:balance}
.ttl .sub{font-size:52px;color:#3c4642}
.ttl figure{width:640px;flex:none;background:#fff;padding:14px;border-radius:6px;box-shadow:0 2px 0 #e6e1d4,0 18px 40px rgba(31,92,74,.10)}
.ttl figure img{display:block;width:100%;border-radius:3px}
.v .pos{font-style:italic;font-family:'EB Garamond';color:#6b746f;margin-left:8px}
"""


def esc(s):
    return html.escape(s, quote=True)


def page(body):
    fonts = (ROOT / '四级' / 'tools' / 'fonts' / 'fonts.css').as_uri()
    return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><link rel="stylesheet" href="{fonts}">'
            f'<style>{C4V.CSS}{CSS_ES}</style></head><body><div class="band"></div>{body}</body></html>')


def load(pid):
    """读文章，给每个词条算出在句中的位置；任何一条对不上都报错（不静默失效）。"""
    p = json.loads((ES / '文章' / f'{pid}.json').read_text('utf-8'))
    for k, s in enumerate((s for para in p['paras'] for s in para), 1):
        if not s['w']:
            raise SystemExit(f'第 {k} 句没有标注单词（铁律 1）')
        taken = []
        for w in s['w']:
            n = s['es'].count(w['surface'])
            if n != 1:
                raise SystemExit(f'第 {k} 句：词条「{w["h"]}」的原形「{w["surface"]}」在句中出现 {n} 次（必须恰好 1 次）')
            a = s['es'].index(w['surface'])
            b = a + len(w['surface'])
            if any(a < y and x < b for x, y in taken):
                raise SystemExit(f'第 {k} 句：词条「{w["h"]}」与别的词条重叠')
            taken.append((a, b))
            w['sp'] = [(a, b)]
            w['t'] = 'phr' if ' ' in w['h'].strip() else 'word'
        s['w'].sort(key=lambda w: w['sp'][0][0])          # 编号 = 在句中出现的先后顺序
    return p


def sentence_html(s):
    out, pos = '', 0
    for i, w in enumerate(s['w'], 1):
        a, b = w['sp'][0]
        cls = 'ph' if w['t'] == 'phr' else 'w'
        out += esc(s['es'][pos:a]) + f'<span class="{cls}">{esc(s["es"][a:b])}<sup>{i}</sup></span>'
        pos = b
    return out + esc(s['es'][pos:])


def vocab_html(s):
    out = []
    for i, w in enumerate(s['w'], 1):
        pos = '' if w['pos'] == 'loc.' else w['pos']          # 短语不写 loc.（颜色已经表示短语），名词短语保留阴阳性
        out.append(f'<div class="v {"ph" if w["t"] == "phr" else ""}"><em>{i}</em><div><b lang="es">{esc(w["h"])}</b>'
                   f'{f"<i class=pos>{esc(pos)}</i>" if pos else ""}<span>{esc(w["zh"])}</span></div></div>')
    return ''.join(out)


def head(p):
    return f'每日一练 · <i lang="es" style="font-family:\'EB Garamond\'">{esc(p["title_es"])}</i>　{esc(p["title_zh"])}'


def words(p):
    return sum(len(LETTERS.findall(s['es'])) for para in p['paras'] for s in para)


def title_slide(p):
    img = (ES / '图片' / f'{p["id"]}_插图.jpg')
    fig = f'<figure><img src="{img.as_uri()}"></figure>' if img.exists() else ''
    n = sum(len(x) for x in p['paras'])
    return page(f'''<div class="ttl"><div class="tag">SPANISH · READING · 西班牙语阅读</div>
      <div class="row"><div class="txt"><h1 lang="es">{esc(p["title_es"])}</h1><div class="sub">{esc(p["title_zh"])}</div></div>{fig}</div>
      <div class="meta"><span>{esc(p.get("series") or "")}</span><span>全文 {words(p)} 词 · {n} 句 · 逐句精读</span></div></div>
      <div class="legend"><span><em style="background:#1f5c4a"></em>单词</span><span><em style="background:#a14a2a"></em>短语</span></div>''')


def sentence_slide(p, s, k, n):
    return page(f'''<div class="top"><b>SPANISH READING</b><span>{head(p)}</span></div>
      <div class="main"><div id="box"><div class="en" lang="es">{sentence_html(s).rstrip()}</div><div class="zh">{esc(s["zh"])}</div></div></div>
      <div class="side" id="side"><h3>VOCABULARY</h3><div id="list">{vocab_html(s)}</div></div>
      <div class="bot"><span>SENTENCE {k} / {n}</span><div class="bar"><i style="width:{k / n * 100:.2f}%"></i></div><span>逐句精读</span></div>''')


def render_slides(slides, outdir, scale):
    """逐屏截图；句子屏自动缩放字号，放不下或字太小就报错（不硬挤）。返回每屏的 (英文字号, 词汇字号)。"""
    from playwright.sync_api import sync_playwright
    sizes = []
    with sync_playwright() as pw:
        exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': W, 'height': H}, device_scale_factor=scale)
        for i, h in enumerate(slides):
            f = outdir / f'{i:03d}.html'
            f.write_text(h, 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            pg.wait_for_timeout(150)
            missing = pg.evaluate("""() => [...document.fonts].filter(f => f.status === 'error').map(f => f.family)""")
            if missing:
                raise SystemExit(f'第 {i} 屏字体加载失败：{missing}')
            if i:
                fs, vs, fits = pg.evaluate(C4V.FIT)
                if not fits or fs < MIN_FS or vs < MIN_VS:
                    raise SystemExit(f'第 {i} 句一屏放不下（原文 {fs}px、词汇 {vs}px，下限 {MIN_FS}/{MIN_VS}px）')
                sizes.append((fs, vs))
            pg.screenshot(path=str(outdir / f'{i:03d}.png'))
        br.close()
    return sizes


# ---------------------------------------------------------------- 电磁音（全频段扫描）
BUZZ_MAX_DB = 3.0          # 与四级相同：任何频点高出周围超过 +3 dB 就报错


def buzz_scan(x, sr, items, lo=2000, hi=16000):
    """在有声部分的长时频谱里找窄带峰：每个频点减去周围 ±22 Hz 的中位数。返回 [(频率, 高出 dB)]，从强到弱。"""
    import numpy as np
    from scipy.ndimage import median_filter
    from scipy.signal import welch
    sp = np.concatenate([x[int(s['start'] * sr): int(s['end'] * sr)] for s in items]).astype(np.float64)
    f, P = welch(sp, sr, nperseg=65536)
    r = 10 * np.log10(P + 1e-20)
    r = r - median_filter(r, 61)
    m = (f >= lo) & (f <= hi)
    fm, rm = f[m], r[m]
    peaks = []
    for i in np.argsort(rm)[::-1]:
        if rm[i] < 1.5 or len(peaks) >= 12:
            break
        if all(abs(fm[i] - q) > 30 for q, _ in peaks):
            peaks.append((float(fm[i]), float(rm[i])))
    return peaks


def buzz_check(mp4, times):
    import numpy as np
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    pk = buzz_scan(np.frombuffer(raw, np.float32), 48000, times)
    top = pk[0] if pk else (0.0, 0.0)
    return ('无电磁音（2–16 kHz 全频段）', top[1] <= BUZZ_MAX_DB, f'最强 {top[0]:.0f} Hz {top[1]:+.1f} dB（上限 {BUZZ_MAX_DB:+.1f}）')


def video_name(p):
    return f'西班牙语 每日一练 {p["title_es"]} {p["title_zh"]}.mp4'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pid')
    ap.add_argument('--voice', help='timings.json 里的音色名（默认用 timings.json 的 "_final"）')
    ap.add_argument('--scale', type=int, default=2, help='2 = 3840×2160（4K）')
    ap.add_argument('--out', default=str(ES / '最终视频'))
    ap.add_argument('--audio-root', default=str(ES / 'audio'))
    ap.add_argument('--name', help='输出文件名（默认「西班牙语 每日一练 标题.mp4」）')
    ap.add_argument('--stills', action='store_true', help='只截图（写到 --out），不编码视频')
    a = ap.parse_args()

    p = load(a.pid)
    sents = [s for para in p['paras'] for s in para]
    free = shutil.disk_usage(ES).free / 2**30
    if free < 3:                                    # 踩坑 29
        raise SystemExit(f'磁盘剩余只有 {free:.1f} GB（至少需要 3 GB），先清理临时文件再生成视频')
    tmp = Path(tempfile.mkdtemp(prefix='esvideo_'))
    atexit.register(shutil.rmtree, tmp, True)
    slides = [title_slide(p)] + [sentence_slide(p, s, k, len(sents)) for k, s in enumerate(sents, 1)]
    sizes = render_slides(slides, tmp, a.scale)
    print(f'  原文字号 {min(x[0] for x in sizes)}–{max(x[0] for x in sizes)}px，词汇栏字号 {min(x[1] for x in sizes)}–{max(x[1] for x in sizes)}px')
    if a.stills:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        for f in sorted(tmp.glob('*.png')):
            shutil.copy(f, out / f.name)
        print('截图已保存到', out)
        return

    T = json.loads((Path(a.audio_root) / 'timings.json').read_text('utf-8'))
    voice = a.voice or T['_final']
    tm = T[voice][a.pid]
    times = tm['sentences']
    if len(times) != len(sents):
        raise SystemExit('音频句数与文章句数不一致，请重新生成音频')
    stale = [k for k, (s, t) in enumerate(zip(sents, times), 1) if s['es'] != t['text']]
    if stale:
        raise SystemExit(f'第 {stale} 句的朗读文本和画面原文不一致，请重新生成音频')
    audio = Path(a.audio_root) / tm['file']
    starts, ends = [x['start'] for x in times], [x['end'] for x in times]
    TAIL, HOLD, GAP, FPS = 2.0, 0.5, 0.8, 30
    bad = [i + 2 for i in range(len(times) - 1) if abs(starts[i + 1] - ends[i] - GAP) > 0.01]
    if bad:
        raise SystemExit(f'第 {bad} 句之前的停顿不是 {GAP} 秒，请用最新设置重新生成音频')
    total = max(tm['duration'], ends[-1] + TAIL)
    cuts = [0.0, starts[0]] + [ends[i - 1] + HOLD for i in range(1, len(sents))] + [total]
    frames = [round(c * FPS) for c in cuts[:-1]] + [math.ceil(cuts[-1] * FPS)]
    lst = []
    for i in range(len(slides)):
        segf = tmp / f'seg{i:03d}.mp4'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-framerate', str(FPS),
                        '-i', str(tmp / f'{i:03d}.png'), '-frames:v', str(frames[i + 1] - frames[i]), '-vf', 'format=yuv420p',
                        '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-tune', 'stillimage',
                        '-pix_fmt', 'yuv420p', '-g', str(FPS * 10), str(segf)], check=True)
        lst.append(f"file '{segf}'")
    (tmp / 'list.txt').write_text('\n'.join(lst))
    total = frames[-1] / FPS
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = a.name or video_name(p)
    silent = tmp / 'video.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(tmp / 'list.txt'),
                    '-c', 'copy', str(silent)], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(silent), '-i', str(audio),
                    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', f'apad=whole_dur={total:.3f}',
                    '-t', f'{total:.3f}', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
                    str(out / name)], check=True)
    durs = [float(x) for x in subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=duration', '-of', 'csv=p=0',
                                              str(out / name)], capture_output=True, text=True).stdout.split()]
    dur = min(durs)
    # 成品核查：高考 / 四级同一套 verify_videos.check（分辨率、流畅度、声画等长、朗读与画面逐句一致、静音、停顿、响度、切屏……）
    from verify_videos import check
    pv = {'year': '', 'paper': '', 'part': '', 'title': '',
          'paras': [[{'en': s['es'], 'w': s['w']} for s in para] for para in p['paras']]}
    tmv = {**tm, 'sentences': [{**t, 'text': t['text']} for t in times]}
    res = [r for r in check(out / name, pv, tmv) if not r[0].startswith('文件名')]
    res.append(buzz_check(out / name, times))
    fails = [f'{n}：{d}' for n, c, d in res if not c]
    for n, c, d in res:
        print(f"  {'✅' if c else '❌'} {n}：{d}")
    if fails:
        (out / name).unlink()
        raise SystemExit('核查未通过，已删除成品：\n  ' + '\n  '.join(fails))
    (out / (Path(name).stem + '_核查.json')).write_text(json.dumps(
        {'video': name, 'voice': voice, 'duration': round(dur, 3), 'checks': [{'item': n, 'ok': c, 'detail': d} for n, c, d in res]},
        ensure_ascii=False, indent=1), 'utf-8')
    print(f'已生成并核查通过 {out / name}（时长 {dur:.2f} 秒，读完后静音 {dur - ends[-1]:.2f} 秒）')


if __name__ == '__main__':
    sys.exit(main())
