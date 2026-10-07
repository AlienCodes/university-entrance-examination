"""生成四级逐句精读视频（设计方案 C「杂志编号注释」，用户 2026-10-07 选定）。

    /opt/ttsenv/bin/python 四级/tools/make_video.py c01 [--scale 2]

画面：米白底、左侧墨绿竖带；英文 EB Garamond，生词右上角带编号，单词墨绿、短语砖红；
中文思源宋体；右侧词汇栏按编号一一对应。字体文件在 四级/tools/fonts/。
时间轴、编码和成品核查与高考 tools/video/make_video.py 完全相同（片头静音 1.5 秒、句间 0.8 秒、
读完后画面停留 0.5 秒再切换、结尾静音 ≥ 2 秒、恒定 30 帧逐屏编码后无损拼接），
生成后立即运行高考同一套 verify_videos.check 核查，任何一项不通过就删除成品。
输入：四级/data/vocab.json（复核定稿）、四级/audio/timings.json（cet4_male）。输出：四级/最终视频/。
"""
import argparse
import html
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
ROOT = C4.parent
VOICE = 'cet4_male'
W, H = 1920, 1080

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:#fbf9f4;color:#1c2421;font-family:'Noto Serif SC',serif}
.band{position:absolute;left:0;top:0;bottom:0;width:22px;background:#1f5c4a}
.top{position:absolute;left:110px;right:90px;top:52px;display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid #1c2421;padding-bottom:16px}
.top b{font-family:'Inter';font-weight:800;font-size:24px;letter-spacing:.14em}
.top span{color:#6b746f;font-size:24px}
.main{position:absolute;left:110px;top:140px;bottom:96px;width:1070px;display:flex;align-items:center}
#box{width:100%}
.en{font-family:'EB Garamond',serif;font-size:var(--fs);line-height:1.5}
.w{font-weight:600;color:#1f5c4a}.ph{font-weight:600;color:#a14a2a}
sup{font-family:'Inter';font-size:calc(var(--fs)*.36);font-weight:700;color:#fff;background:#1f5c4a;border-radius:1em;padding:.05em .45em;margin-left:.12em;vertical-align:.95em;line-height:1}
.ph sup{background:#a14a2a}
.zh{font-size:calc(var(--fs)*.68);line-height:1.65;color:#3c4642;margin-top:calc(var(--fs)*.5);padding-left:24px;border-left:4px solid #d7d2c3}
.side{position:absolute;right:90px;top:140px;bottom:96px;width:600px;background:#eef2ec;border-radius:6px;padding:30px 36px;display:flex;flex-direction:column;justify-content:center}
#list{display:flex;flex-direction:column;gap:calc(var(--vs)*.42)}
.side h3{font-family:'Inter';font-size:20px;letter-spacing:.2em;color:#1f5c4a;margin-bottom:14px}
.v{display:grid;grid-template-columns:calc(var(--vs)*1.3) 1fr;column-gap:12px;font-size:var(--vs);line-height:1.32}
.v em{font-style:normal;font-family:'Inter';font-weight:700;font-size:calc(var(--vs)*.7);color:#fff;background:#1f5c4a;border-radius:50%;width:calc(var(--vs)*1.2);height:calc(var(--vs)*1.2);display:flex;align-items:center;justify-content:center;margin-top:.1em}
.v.ph em{background:#a14a2a}
.v b{font-family:'EB Garamond';font-weight:600;font-size:calc(var(--vs)*1.3)}
.v.ph b{color:#a14a2a}
.v i{font-style:italic;font-family:'EB Garamond';color:#6b746f;margin-left:8px}
.v span{color:#3c4642;margin-left:10px}
.bot{position:absolute;left:110px;right:90px;bottom:40px;display:flex;justify-content:space-between;align-items:center;font-family:'Inter';font-size:22px;color:#6b746f;letter-spacing:.1em}
.bar{flex:1;height:3px;background:#dcd8cc;margin:0 30px}.bar i{display:block;height:100%;background:#1f5c4a}
.ttl{position:absolute;left:150px;right:150px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center}
.ttl .tag{font-family:'Inter';font-weight:800;letter-spacing:.3em;font-size:28px;color:#1f5c4a}
.ttl h1{font-size:96px;font-weight:700;margin:30px 0 26px;line-height:1.25}
.ttl .sub{font-size:44px;color:#3c4642}
.ttl .sub i{font-family:'EB Garamond';font-style:italic}
.ttl .meta{margin-top:50px;padding-top:26px;border-top:2px solid #1c2421;font-size:30px;color:#6b746f;display:flex;justify-content:space-between}
.legend{position:absolute;right:120px;bottom:60px;display:flex;gap:30px;font-size:24px;color:#3c4642}
.legend em{display:inline-block;width:22px;height:22px;border-radius:50%;margin-right:8px;vertical-align:-3px}
"""
POS = re.compile(r'^((?:n|v|adj|adv|prep|conj|pron|num|det|int|abbr|pref|suf)\.)\s*(.*)$')


def esc(s):
    return html.escape(s, quote=True)


def page(body):
    fonts = (HERE / 'fonts' / 'fonts.css').as_uri()
    return f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{fonts}"><style>{CSS}</style></head><body><div class="band"></div>{body}</body></html>'


def ordered(s):
    """词条按在句中第一次出现的位置编号。"""
    return sorted(s['w'], key=lambda w: w['sp'][0][0])


def sentence_html(s):
    ws = ordered(s)
    num = {id(w): i + 1 for i, w in enumerate(ws)}
    spans = sorted((a, b, w, j) for w in s['w'] for j, (a, b) in enumerate(w['sp']))
    out, pos = '', 0
    for a, b, w, j in spans:
        if a < pos:
            continue
        cls = 'ph' if w['t'] == 'phr' else 'w'
        sup = f'<sup>{num[id(w)]}</sup>' if j == len(w['sp']) - 1 else ''     # 分开的短语，编号标在最后一段
        out += esc(s['en'][pos:a]) + f'<span class="{cls}">{esc(s["en"][a:b])}{sup}</span>'
        pos = b
    return out + esc(s['en'][pos:])


def vocab_html(s):
    out = []
    for i, w in enumerate(ordered(s), 1):
        m = POS.match(w['m'])
        pos, mean = (m.group(1), m.group(2)) if m else ('', w['m'])
        out.append(f'<div class="v {"ph" if w["t"] == "phr" else ""}"><em>{i}</em><div><b>{esc(w["h"])}</b>'
                   f'{f"<i>{pos}</i>" if pos else ""}<span>{esc(mean)}</span></div></div>')
    return ''.join(out)


def head(p):
    return f'{esc(p["paper"])} · {esc(p["passage"])}'


def title_slide(p):
    return page(f'''<div class="ttl"><div class="tag">CET-4 · READING · SECTION C</div><h1>{esc(p.get("title") or "")}</h1>
      <div class="sub">大学英语四级 {esc(p["paper"])} · <i>{esc(p["passage"])}</i></div>
      <div class="meta"><span>{esc(p.get("genre") or "")}</span><span>全文 {p["words"]} 词 · 逐句精读</span></div></div>
      <div class="legend"><span><em style="background:#1f5c4a"></em>单词</span><span><em style="background:#a14a2a"></em>短语</span></div>''')


def sentence_slide(p, s, k, n):
    return page(f'''<div class="top"><b>CET-4 READING</b><span>{head(p)}　{esc(p.get("title") or "")}</span></div>
      <div class="main"><div id="box"><div class="en">{sentence_html(s)}</div><div class="zh">{esc(s["zh"])}</div></div></div>
      <div class="side" id="side"><h3>VOCABULARY</h3><div id="list">{vocab_html(s)}</div></div>
      <div class="bot"><span>SENTENCE {k} / {n}</span><div class="bar"><i style="width:{k / n * 100:.2f}%"></i></div><span>逐句精读</span></div>''')


# 左侧句子区与右侧词汇栏分别缩放字号，直到都放得下
FIT = """() => { const r=document.documentElement.style, main=document.querySelector('.main'), box=document.getElementById('box'),
  side=document.getElementById('side'), list=document.getElementById('list');
  let fs=64, vs=30; r.setProperty('--fs', fs+'px'); r.setProperty('--vs', vs+'px');
  while (box.scrollHeight > main.clientHeight && fs > 30) { fs -= 2; r.setProperty('--fs', fs+'px'); }
  while (side.scrollHeight > side.clientHeight && vs > 16) { vs -= 1; r.setProperty('--vs', vs+'px'); }
  return [fs, vs, box.scrollHeight <= main.clientHeight && side.scrollHeight <= side.clientHeight]; }"""


def video_name(p):
    title = (p.get('title') or '').translate(str.maketrans('/\\:*?"<>|', '／＼：＊？＂＜＞｜'))
    return f"{p['paper']} {p['passage']} {title}.mp4"     # 用户指定：年份月份 第几套 第几篇 题目，前面不加“四级”


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pid')
    ap.add_argument('--scale', type=int, default=2, help='2 = 3840×2160（4K）')
    ap.add_argument('--out', default=str(C4 / '最终视频'))
    a = ap.parse_args()

    data = json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))
    p = next(x for x in data['passages'] if x['id'] == a.pid)
    tm = json.loads((C4 / 'audio' / 'timings.json').read_text('utf-8'))[VOICE][a.pid]
    sents = [s for para in p['paras'] for s in para]
    times = tm['sentences']
    assert len(sents) == len(times), '音频句数与文章句数不一致，请重新生成音频'
    empty = [i + 1 for i, s in enumerate(sents) if not s['w']]
    if empty:                                   # 铁律：每一句至少标出一个单词
        raise SystemExit(f'第 {empty} 句没有标注单词，不生成视频')
    audio = C4 / 'audio' / tm['file']

    from playwright.sync_api import sync_playwright
    tmp = Path(tempfile.mkdtemp())
    slides = [title_slide(p)] + [sentence_slide(p, s, i + 1, len(sents)) for i, s in enumerate(sents)]
    sizes = []
    with sync_playwright() as pw:
        exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': W, 'height': H}, device_scale_factor=a.scale)
        for i, h in enumerate(slides):
            f = tmp / f'{i:03d}.html'
            f.write_text(h, 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            pg.wait_for_timeout(150)
            if i:
                fs, vs, fits = pg.evaluate(FIT)
                if not fits:                    # 缩到最小仍放不下会被裁切——直接报错
                    raise SystemExit(f'第 {i} 句内容太多，英文 {fs}px、词汇 {vs}px 仍放不下')
                sizes.append((fs, vs))
            pg.screenshot(path=str(tmp / f'{i:03d}.png'))
        br.close()

    starts = [x['start'] for x in times]
    ends = [x['end'] for x in times]
    TAIL = 2.0
    total = max(tm['duration'], ends[-1] + TAIL)
    HOLD, GAP = 0.5, 0.8
    bad = [i + 2 for i in range(len(times) - 1) if abs(starts[i + 1] - ends[i] - GAP) > 0.01]
    if bad:
        raise SystemExit(f'第 {bad} 句之前的停顿不是 {GAP} 秒，请用最新设置重新生成音频')
    cuts = [0.0, starts[0]] + [ends[i] + HOLD for i in range(len(times) - 1)] + [total]
    FPS = 30
    frames = [round(c * FPS) for c in cuts[:-1]] + [math.ceil(cuts[-1] * FPS)]
    lst = []
    for i in range(len(slides)):
        n = frames[i + 1] - frames[i]
        segf = tmp / f'seg{i:03d}.mp4'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-framerate', str(FPS),
                        '-i', str(tmp / f'{i:03d}.png'), '-frames:v', str(n), '-vf', 'format=yuv420p',
                        '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-tune', 'stillimage',
                        '-pix_fmt', 'yuv420p', '-g', str(FPS * 10), str(segf)], check=True)
        lst.append(f"file '{segf}'")
    (tmp / 'list.txt').write_text('\n'.join(lst))
    total = frames[-1] / FPS

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = video_name(p)
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
    if dur - ends[-1] < TAIL - 0.05:
        raise SystemExit(f'结尾静音只有 {dur - ends[-1]:.2f} 秒，不足 {TAIL} 秒')
    # 成品核查：复用高考 verify_videos.check（分辨率、流畅度、声画等长、朗读与画面逐句一致、静音、停顿、响度……）
    sys.path[:0] = [str(ROOT / 'tools' / 'video'), str(ROOT / 'tools' / 'tts')]
    from verify_videos import check
    fails = [f'{n}：{d}' for n, c, d in check(out / name, p, tm) if not c and not n.startswith('文件名')]
    if not re.fullmatch(r'20\d\d年(6|12)月 第[123]套 Passage (One|Two) \S.*\.mp4', name) or name != video_name(p):
        fails.append(f'文件名：{name}')
    if fails:
        (out / name).unlink()
        raise SystemExit('核查未通过，已删除成品：\n  ' + '\n  '.join(fails))
    print(f'  英文字号 {min(x[0] for x in sizes)}–{max(x[0] for x in sizes)}px，词汇栏字号 {min(x[1] for x in sizes)}–{max(x[1] for x in sizes)}px')
    print(f'已生成并核查通过 {out / name}（时长 {dur:.2f} 秒，读完后静音 {dur - ends[-1]:.2f} 秒）')


if __name__ == '__main__':
    sys.exit(main())
