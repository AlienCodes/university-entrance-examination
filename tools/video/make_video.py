"""把一篇文章做成逐句朗读视频（16:9，默认 3840×2160 4K）。

    python make_video.py p58                  # 女声
    python make_video.py p58 --voice male
    python make_video.py p58 --scale 1        # 1920×1080

画面：片头（年份 · 试卷 · C/D 篇 · 标题）静音 1.5 秒，之后一句一屏：
英文（生词高亮）、中文翻译、本句生词表；声音与画面按 audio/timings.json 逐句同步。
需要先用 tools/tts/gaokao_tts.py 生成该篇音频，并用 tools/build.py 生成 data/vocab.json。
"""
import argparse
import html
import math
import re
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FONTS = HERE / 'fonts'
W, H = 1920, 1080
TIER = {'core': '高中核心', 'ext': '超纲拓展', 'phr': '短语搭配'}

CSS = """
@font-face{font-family:'SC';src:url('FONTS/NotoSansSC-Regular.ttf');font-weight:400}
@font-face{font-family:'SC';src:url('FONTS/NotoSansSC-Medium.ttf');font-weight:500}
@font-face{font-family:'SC';src:url('FONTS/NotoSansSC-Bold.ttf');font-weight:700}
@font-face{font-family:'Serif';src:url('FONTS/SourceSerif4-Regular.otf');font-weight:400}
@font-face{font-family:'Serif';src:url('FONTS/SourceSerif4-Semibold.otf');font-weight:600}
:root{--bg:#fbfaf6;--ink:#1d1d1b;--ink2:#55534d;--ink3:#9a978f;--line:#e6e3da;--accent:#2f5d8a;
 --core:#b45309;--core-bg:#fdf0dc;--ext:#7c3aed;--ext-bg:#efe7fd;--phr:#0f766e;--phr-bg:#dcf3ef}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:var(--bg);color:var(--ink);font-family:'SC',sans-serif}
.top{position:absolute;left:96px;right:96px;top:52px;display:flex;justify-content:space-between;align-items:baseline;font-size:26px;color:var(--ink3)}
.top b{color:var(--accent);font-weight:700;letter-spacing:.04em}
.bot{position:absolute;left:96px;right:96px;bottom:48px;display:flex;align-items:center;gap:24px;font-size:24px;color:var(--ink3);font-variant-numeric:tabular-nums}
.bar{flex:1;height:6px;border-radius:3px;background:var(--line);overflow:hidden}.bar i{display:block;height:100%;background:var(--accent)}
.stage{position:absolute;left:80px;right:80px;top:110px;bottom:100px;display:flex;align-items:center}
.box{display:grid;grid-template-columns:70px 1fr;column-gap:22px;width:100%}
.k{font-family:'Serif';font-size:34px;color:var(--ink3);text-align:right;padding-top:.35em}
.en{font-family:'Serif',serif;font-size:var(--fs);line-height:1.62;letter-spacing:.003em}
mark{background:none;color:inherit;border-radius:6px;padding:0 3px;border-bottom:4px solid}
mark.core{color:var(--core);background:var(--core-bg);border-color:var(--core)}
mark.ext{color:var(--ext);background:var(--ext-bg);border-color:var(--ext)}
mark.phr{color:var(--phr);background:var(--phr-bg);border-color:var(--phr)}
.zh{font-size:calc(var(--fs)*.82);color:#3d3b36;line-height:1.5;margin-top:calc(var(--fs)*.4);font-weight:500}
.chips{display:flex;flex-wrap:wrap;gap:calc(var(--fs)*.26) calc(var(--fs)*.3);margin-top:calc(var(--fs)*.55)}
.chip{font-size:calc(var(--fs)*.72);line-height:1.3;border-radius:14px;padding:.22em .6em;font-weight:500}
.chip b{font-family:'Serif';font-weight:600;margin-right:.45em}
.chip.core{background:var(--core-bg)}.chip.core b{color:var(--core)}
.chip.ext{background:var(--ext-bg)}.chip.ext b{color:var(--ext)}
.chip.phr{background:var(--phr-bg)}.chip.phr b{color:var(--phr)}
/* title */
.title{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;padding:0 160px}
.yr{font-family:'Serif';font-size:150px;font-weight:600;color:var(--accent);line-height:1}
.paper{font-size:64px;font-weight:700;margin-top:30px;letter-spacing:.04em}
.paper span{display:inline-block;margin-left:28px;padding:4px 26px;border-radius:14px;background:var(--accent);color:var(--bg);font-size:58px}
.rule{width:140px;height:8px;background:var(--accent);border-radius:4px;margin:56px 0 44px}
.name{font-size:76px;font-weight:700;line-height:1.3}
.meta{font-size:30px;color:var(--ink3);margin-top:30px;letter-spacing:.05em}
.legend{position:absolute;right:96px;bottom:56px;display:flex;gap:28px;font-size:24px;color:var(--ink2)}
.legend i{display:inline-block;width:20px;height:20px;border-radius:5px;margin-right:8px;vertical-align:-3px}
"""


def page(body):
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>'
            f'{CSS.replace("FONTS", FONTS.as_uri())}</style></head><body>{body}</body></html>')


def esc(s):
    return html.escape(s, quote=True)


def sentence_html(s):
    spans = sorted((a, b, w['t']) for w in s['w'] for a, b in w['sp'])
    out, pos = '', 0
    for a, b, t in spans:
        if a < pos:
            continue
        out += esc(s['en'][pos:a]) + f'<mark class="{t}">{esc(s["en"][a:b])}</mark>'
        pos = b
    return out + esc(s['en'][pos:])


def chips_html(s):
    ws = sorted(s['w'], key=lambda w: w['sp'][0][0])
    return ''.join(f'<span class="chip {w["t"]}"><b>{esc(w["h"])}</b>{esc(w["m"])}</span>' for w in ws)


def title_slide(p):
    paper = p['paper'].split('（')[0]
    sub = p['paper'][len(paper):].strip('（）').replace('·', ' · ')
    legend = ''.join(f'<span><i style="background:var(--{t})"></i>{n}</span>' for t, n in TIER.items())
    return page(f'''<div class="title"><div class="yr">{p["year"]}</div>
      <div class="paper">{esc(paper)}{f" <small style='font-size:40px;color:var(--ink3);font-weight:500'>{esc(sub)}</small>" if sub else ""}<span>阅读 {p["part"]}</span></div>
      <div class="rule"></div><div class="name">{esc(p.get("title") or "")}</div>
      <div class="meta">{esc(p.get("genre") or "")}　·　全文 {p["words"]} 词　·　逐句精读</div></div>
      <div class="legend">{legend}</div>''')


def sentence_slide(p, s, k, n):
    head = f'<b>{p["year"]} {esc(p["paper"])} · 阅读{p["part"]}</b><span>{esc(p.get("title") or "")}</span>'
    zh = f'<div class="zh">{esc(s["zh"])}</div>' if s.get('zh') else ''
    chips = f'<div class="chips">{chips_html(s)}</div>' if s['w'] else ''
    return page(f'''<div class="top">{head}</div>
      <div class="stage"><div class="box" id="box"><div class="k">{k}</div>
        <div><div class="en">{sentence_html(s)}</div>{zh}{chips}</div></div></div>
      <div class="bot"><div class="bar"><i style="width:{k / n * 100:.2f}%"></i></div><span>{k} / {n}</span></div>''')


FIT = """() => { const st=document.querySelector('.stage'), box=document.getElementById('box');
  let fs=64; document.documentElement.style.setProperty('--fs', fs+'px');
  while (box.scrollHeight > st.clientHeight && fs > 26) { fs -= 2; document.documentElement.style.setProperty('--fs', fs+'px'); }
  return fs; }"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pid')
    ap.add_argument('--voice', default='female')
    ap.add_argument('--scale', type=int, default=2, help='2 = 3840×2160（4K），1 = 1920×1080')
    ap.add_argument('--out', default=str(ROOT / '最终视频'))
    a = ap.parse_args()

    data = json.loads((ROOT / 'data' / 'vocab.json').read_text('utf-8'))
    p = next(x for x in data['passages'] if x['id'] == a.pid)
    tm = json.loads((ROOT / 'audio' / 'timings.json').read_text('utf-8'))[a.voice][a.pid]
    sents = [s for para in p['paras'] for s in para]
    times = tm['sentences']
    assert len(sents) == len(times), '音频句数与文章句数不一致，请重新生成音频'
    empty = [i + 1 for i, s in enumerate(sents) if not s['w']]
    if empty:                                   # 铁律：每一句至少标出一个单词
        raise SystemExit(f'第 {empty} 句没有标注单词，不生成视频')
    audio = ROOT / 'audio' / tm['file']

    from playwright.sync_api import sync_playwright
    tmp = Path(tempfile.mkdtemp())
    slides = [title_slide(p)] + [sentence_slide(p, s, i + 1, len(sents)) for i, s in enumerate(sents)]
    with sync_playwright() as pw:
        exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': W, 'height': H}, device_scale_factor=a.scale)
        font_sizes = []
        for i, h in enumerate(slides):
            f = tmp / f'{i:03d}.html'
            f.write_text(h, 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            if i:
                fs = pg.evaluate(FIT)
                # 踩坑预防：字号缩到最小仍放不下时，文字会被裁掉——直接报错
                fits = pg.evaluate("() => document.getElementById('box').scrollHeight <= document.querySelector('.stage').clientHeight")
                if not fits:
                    raise SystemExit(f'第 {i} 句内容太多，字号缩到 {fs}px 仍放不下，画面会被裁切')
                font_sizes.append(fs)
            pg.screenshot(path=str(tmp / f'{i:03d}.png'))
        br.close()

    # 每屏的显示时长：片头到第一句开口；之后在两句之间的静音中点切换
    starts = [x['start'] for x in times]
    ends = [x['end'] for x in times]
    TAIL = 2.0                                  # 读完最后一句后至少保留 2 秒静音
    total = max(tm['duration'], ends[-1] + TAIL)
    # 铁律：句与句之间停顿 0.8 秒；读完后画面停留 0.5 秒再切换，切换 0.3 秒后开始读下一句
    HOLD, LEAD, GAP = 0.5, 0.3, 0.8
    bad = [i + 2 for i in range(len(times) - 1) if abs(starts[i + 1] - ends[i] - GAP) > 0.01]
    if bad:
        raise SystemExit(f'第 {bad} 句之前的停顿不是 {GAP} 秒，请用最新设置重新生成音频')
    cuts = [0.0, starts[0]] + [ends[i] + HOLD for i in range(len(times) - 1)] + [total]
    # 每屏单独编码成一段（一张图循环，内存恒定），按累计时间换算帧数，再无损拼接
    FPS = 30
    frames = [round(c * FPS) for c in cuts[:-1]] + [math.ceil(cuts[-1] * FPS)]   # 结尾向上取整，保证静音不少于 2 秒
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
    # 文件名与片头一致：年份 试卷 篇目 题目，例如“2026 全国Ⅰ卷 阅读C 纽约大规模种树的“隐患”.mp4”
    paper = re.sub(r'·[^）]*', '', p['paper'])
    title = (p.get('title') or '').translate(str.maketrans('/\\:*?"<>|', '／＼：＊？＂＜＞｜'))
    name = f"{p['year']} {paper} 阅读{p['part']} {title}".strip() + ('' if a.voice == 'female' else '（男声）') + '.mp4'
    # 分两步：先只编码画面，再合入声音（同一步编码 4K 画面和声音时内存会暴涨）
    silent = tmp / 'video.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(tmp / 'list.txt'),
                    '-c', 'copy', str(silent)], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(silent), '-i', str(audio),
                    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', f'apad=whole_dur={total:.3f}',
                    '-t', f'{total:.3f}', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
                    str(out / name)], check=True)
    # 检查：成品视频在最后一句读完后的静音不少于 2 秒
    durs = [float(x) for x in subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=duration', '-of', 'csv=p=0',
                                str(out / name)], capture_output=True, text=True).stdout.split()]
    dur = min(durs)                              # 画面和声音都必须撑到结尾
    if dur - ends[-1] < TAIL - 0.05:
        raise SystemExit(f'结尾静音只有 {dur - ends[-1]:.2f} 秒，不足 {TAIL} 秒')
    # 踩坑记录：所有问题都要在交付前自动拦下——生成后立即对成品做完整核查，不合格就删除
    from verify_videos import check
    fails = [f'{n}：{d}' for n, c, d in check(out / name, p, tm) if not c]
    if fails:
        (out / name).unlink()
        raise SystemExit('核查未通过，已删除成品：\n  ' + '\n  '.join(fails))
    print(f'  英文字号：最大 {max(font_sizes)}px，最小 {min(font_sizes)}px（第 {font_sizes.index(min(font_sizes)) + 1} 句）')
    print(f'已生成并核查通过 {out / name}（时长 {dur:.2f} 秒，读完后静音 {dur - ends[-1]:.2f} 秒）')


if __name__ == '__main__':
    sys.exit(main())
