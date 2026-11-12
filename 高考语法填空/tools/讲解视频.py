"""高考语法填空讲解视频引擎（可复用：换一份 稿 + 原文 就是下一篇）。

画面状态 = 稿里的每一段（board 逐段累加、answer 段起空格显示答案、全文通读高亮当前句）；每段开口前 0.25 秒切到它的画面。
  --stills  截图（1920×1080 CSS 像素 × 2 = 3840×2160），每张跑排版检查，有一处就停；
  --video   截图 → 逐屏无损编码 → 整片压缩 → 合上音频 → 成品核查，任何一项不过就删成品。
排版检查（每张截图）：出画面 / 溢出卡片 / 块与块重叠 / 板书每行必须单行且字号 ≥ 下限 / 中文孤字与行首标点 /
  英文单词被断开 / 字体回退（CDP 实测，只许 Inter 与 Noto Sans SC）/ 一屏多题跑铁律 19 的 QGAP_JS / 别的项目贴纸文字（踩坑 57）。
成品核查：3840×2160、恒定 30 帧、声画等长（差 ≤ 1 帧）、开头静音 ≥ 1.5 秒、结尾静音 ≥ 2.0 秒、视频音轨重新量响度（含意群级）、
  合格证（MP3 sha256 与合格证一致）、电磁音全频段 ≤ +3 dB、逐屏抽帧与截图像素一致。
用法：/opt/ttsenv/bin/python 讲解视频.py --稿 稿.json --音频 成品.mp3 --stills|--video [--out 目录]
"""
import argparse
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools/tts'), str(Path(__file__).parent)]
FPS = 30
W, H = 1920, 1080
LEAD, TAIL = 1.5, 2.0
SWITCH_EARLY = 0.25
FONTS = {'Inter', 'Noto Sans SC'}
OTHER_PROJECTS = ['专八', '六级', '考研', '四级', '中考', 'TEM', 'CET']
BOARD_MIN = 40      # 板书最小字号（CSS 像素，1080p）：手机上看得清（铁律 5）
EN_MIN = 44

CSS = """
@import url('file://%(zk)s/noto-sans-sc/400.css'); @import url('file://%(zk)s/noto-sans-sc/500.css'); @import url('file://%(zk)s/noto-sans-sc/700.css');
@import url('file://%(inter)s/inter.css');
:root { --ink:#1f2a37; --muted:#6b7280; --accent:#e4572e; --blue:#2563eb; --paper:#fbf8f1; --card:#ffffff; --line:#e7e2d6; --hl:#fff1a8; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1920px; height: 1080px; overflow: hidden; background: var(--paper); color: var(--ink);
  font-family: 'Inter', 'Noto Sans SC'; -webkit-font-smoothing: antialiased; }
.zh, .board, .title, .hd, .steps { line-break: strict; word-break: normal; text-wrap: pretty; }
.hd { position: absolute; left: 60px; right: 60px; top: 34px; height: 64px; display: flex; align-items: center; justify-content: space-between; }
.hd .src { font-size: 32px; color: var(--muted); font-weight: 500; }
.chips { display: flex; gap: 10px; }
.chip { width: 66px; height: 50px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 28px;
  font-weight: 700; color: var(--muted); background: #efe9dc; }
.chip.on { background: var(--accent); color: #fff; }
.chip.done { background: #d9ecd9; color: #2f6b2f; }
.card { position: absolute; left: 60px; right: 60px; background: var(--card); border-radius: 28px; box-shadow: 0 6px 24px rgba(60,40,10,.08); padding: 38px 54px; overflow: hidden; }
.sent { font-size: var(--en, 54px); line-height: 1.55; font-weight: 500; }
.qn { display: inline-block; background: var(--accent); color: #fff; border-radius: 14px; padding: 0 18px; margin-right: 18px; font-weight: 800; }
.blank { display: inline-block; white-space: nowrap; min-width: 4.2em; text-align: center; border-bottom: 5px solid var(--accent); line-height: 1.2; padding: 0 .2em; }
.blank.empty { color: transparent; }
.blank.ans { color: var(--accent); font-weight: 800; }
.blank.other { min-width: 2.6em; border-bottom-color: #b9b2a3; color: transparent; }
.hint { color: var(--blue); font-weight: 600; white-space: nowrap; }
.note { white-space: nowrap; color: var(--muted); }
.steps { position: absolute; left: 60px; right: 60px; display: flex; gap: 14px; }
.st { flex: 1; text-align: center; font-size: 30px; padding: 10px 0; border-radius: 12px; background: #efe9dc; color: var(--muted); font-weight: 500; }
.st.on { background: var(--blue); color: #fff; font-weight: 700; }
.st.done { background: #dbe6fb; color: #1e3a8a; }
.board { font-size: var(--bd, 50px); line-height: 1.5; }
.board .ln { white-space: nowrap; padding: 6px 18px; border-radius: 12px; margin: 4px 0; width: fit-content; }
.board .ln.new { background: var(--hl); }
.board .ln.sub { margin-left: 64px; }
.ttl { font-size: 60px; font-weight: 700; margin-bottom: 18px; }
.title { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 34px; }
.title .y { font-size: 120px; font-weight: 800; color: var(--accent); letter-spacing: 4px; }
.title .p { font-size: 84px; font-weight: 700; }
.title .s { font-size: 72px; font-weight: 500; }
.title .q { font-size: 60px; color: var(--muted); }
.sum { display: grid; grid-template-columns: 1fr 1fr; column-gap: 90px; }
.qg { display: flex; align-items: baseline; gap: 34px; padding: 22px 6px; border-bottom: 2px solid #c9c9c9; font-size: 58px; }
.qg .no { font-weight: 800; color: var(--accent); width: 90px; }
.qg .a { font-weight: 700; }
.full { font-size: var(--fu, 46px); line-height: 1.6; }
.full .dim { color: #a3a3a3; }
.full b { color: var(--accent); }
"""


def esc(s):
    return html.escape(s, quote=False)


def en_html(s, answers, show, cur):
    """英文句子：___N___ (hint) → 空格（本题高亮；show 时填答案）；中文注释整体不断行。"""
    def blank(m):
        n, hint = m.group(1), m.group(2)
        if int(n) != cur:
            return f'<span class="blank other">__</span>' + (f' <span class="hint">({esc(hint)})</span>' if hint else '')
        a = answers[n].split(' / ')[0] if n != '63' else answers[n]
        b = f'<span class="blank ans">{esc(a)}</span>' if show else '<span class="blank empty">____</span>'
        return b + (f' <span class="hint">({esc(hint)})</span>' if hint else '')
    out, pos = [], 0
    for m in re.finditer(r'___(\d+)___(?:\s*\(([^()]*)\))?|\(([^()]*[一-鿿][^()]*)\)', s):
        out.append(esc(s[pos:m.start()]))
        out.append(blank(m) if m.group(1) else f'<span class="note">({esc(m.group(3))})</span>')
        pos = m.end()
    out.append(esc(s[pos:]))
    return ''.join(out)


def head(doc, cur=None, done=()):
    src = json.loads((ROOT / doc['原文']).read_text('utf-8'))
    chips = ''.join(f'<div class="chip{" on" if q == cur else (" done" if q in done else "")}">{q}</div>' for q in range(56, 66))
    return f'<div class="hd"><div class="src zh">{src["year"]} {esc(src["paper"])} · {esc(src["section"])}</div><div class="chips">{chips}</div></div>'


STEPS = ['读句', '提示', '词性', '成分', '形式', '答案', '口诀']


def frames(doc):
    """每段一个画面：返回 [(段 id, html 主体)]，第一项是片头。"""
    src = json.loads((ROOT / doc['原文']).read_text('utf-8'))
    A = doc['answers']
    out = [('title', f'<div class="title"><div class="y">{src["year"]}</div><div class="p zh">{esc(src["paper"])}</div>'
                     f'<div class="s zh">{esc(src["section"])} · 逐题讲解</div><div class="q zh">第 {esc(src["questions"])} 题</div></div>')]
    boards, done_steps, shown = {}, {}, set()
    sent_of = {}
    for s in doc['segments']:
        if 'en' in s and s.get('q'):
            sent_of.setdefault(s['q'], s['en'])
    paras = src['paragraphs']
    full_i = {'full1': 0, 'full2': 1, 'full3': 2}
    for s in doc['segments']:
        scr = s['screen']
        if s.get('board'):
            boards.setdefault(scr, []).append(s['board'])
        bl = boards.get(scr, [])
        sub = scr in ('method', 'review')
        board = ''.join(f'<div class="ln{" new" if (i == len(bl) - 1 and s.get("board")) else ""}{" sub" if sub and not re.match("[①②③④⑤]", x) else ""}">{bhtml(x)}</div>'
                        for i, x in enumerate(bl))
        if scr in ('method', 'review'):
            t = '做语法填空，第一件事先干嘛？' if scr == 'method' else '方法回顾'
            body = head(doc) + f'<div class="card" style="top:130px;bottom:60px"><div class="ttl zh">{t}</div><div class="board">{board}</div></div>'
        elif scr.startswith('q'):
            q = s['q']
            if s.get('answer'):
                shown.add(q)
            done_steps.setdefault(q, [])
            cur_steps = s.get('steps', [])
            done_steps[q] += cur_steps
            sts = ''.join(f'<div class="st{" on" if x in cur_steps else (" done" if x in done_steps[q] else "")}">{x}</div>' for x in STEPS)
            done = {x for x in range(56, q)}
            body = (head(doc, q, done) + f'<div class="card" id="sc" style="top:126px"><div class="sent"><span class="qn">{q}</span>{en_html(sent_of[q], A, q in shown, q)}</div></div>'
                    f'<div class="steps" id="st">{sts}</div>'
                    f'<div class="card" id="bc" style="bottom:50px"><div class="board">{board}</div></div>')
        elif scr == 'summary':
            rows = ''.join(f'<div class="qg"><span class="no">{q}</span><span class="a">{esc(A[str(q)])}</span></div>' for q in [56, 61, 57, 62, 58, 63, 59, 64, 60, 65])
            body = head(doc) + f'<div class="card" style="top:130px;bottom:60px"><div class="ttl zh">答案汇总</div><div class="sum">{rows}</div></div>'
        elif scr in full_i:
            p = paras[full_i[scr]]
            filled = re.sub(r'___(\d+)___(\s*\([^()]*\))?', lambda m: '\x01' + A[m.group(1)].split(' / ')[0] + '\x02', p)
            filled = re.sub(r'\s*\([^()]*[一-鿿][^()]*\)', '', filled)
            sents = re.split(r'(?<=[.!?])\s+', filled)
            cur = s['text'] if s.get('full') else None
            parts = []
            for x in sents:
                plain = x.replace('\x01', '').replace('\x02', '')
                h = esc(x).replace('\x01', '<b>').replace('\x02', '</b>')
                parts.append(h if (cur is None or plain == cur) else f'<span class="dim">{h}</span>')
            body = head(doc) + f'<div class="card" style="top:130px;bottom:60px"><div class="ttl zh">全文通读（第 {full_i[scr] + 1} 段）</div><div class="full">{" ".join(parts)}</div></div>'
        else:
            raise ValueError(scr)
        out.append((s['id'], body))
    return out


def bhtml(x):
    return esc(x)


def page(body):
    css = CSS % {'zk': ROOT / '中考/tools/fonts', 'inter': ROOT / '专八/tools/fonts/inter'}
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>'


FIT_JS = r"""() => {
  // 题目屏：英文句卡 + 步骤条 + 板书卡竖排，按内容定位；放不下先缩英文、再缩板书（不低于下限）
  const sc = document.getElementById('sc'), st = document.getElementById('st'), bc = document.getElementById('bc');
  const bd = document.querySelector('.board'), body = document.body;
  const layout = () => { if (!sc) return true; st.style.top = (sc.offsetTop + sc.offsetHeight + 26) + 'px';
    bc.style.top = (st.offsetTop + st.offsetHeight + 26) + 'px';
    return bc.scrollHeight <= bc.clientHeight + 1 && sc.offsetTop + sc.offsetHeight < 1000; };
  let en = 54, b = 50;
  const lineFits = () => [...document.querySelectorAll('.board .ln')].every(l => l.getBoundingClientRect().right <= l.closest('.card').getBoundingClientRect().right - 40);
  for (let i = 0; i < 40; i++) {
    body.style.setProperty('--en', en + 'px'); body.style.setProperty('--bd', b + 'px');
    if (layout() && lineFits()) break;
    if (!lineFits() || (b > 44 && en <= 48)) b -= 1; else if (en > 44) en -= 1; else b -= 1;
  }
  return {en, b};
}"""

CHECK_JS = r"""(args) => {
  const [others] = args; const bad = [];
  const R = e => e.getBoundingClientRect();
  for (const c of document.querySelectorAll('.card, .steps, .hd, .title')) {
    const r = R(c);
    if (r.left < 0 || r.top < 0 || r.right > 1920 + 0.5 || r.bottom > 1080 + 0.5) bad.push('出画面：' + c.className + ' ' + JSON.stringify([r.left, r.top, r.right, r.bottom].map(Math.round)));
    if (c.classList.contains('card') && (c.scrollHeight > c.clientHeight + 1 || c.scrollWidth > c.clientWidth + 1)) bad.push('卡片溢出：' + c.textContent.slice(0, 20));
  }
  const blocks = [...document.querySelectorAll('.card, .steps, .hd')];
  for (let i = 0; i < blocks.length; i++) for (let j = i + 1; j < blocks.length; j++) {
    const a = R(blocks[i]), b = R(blocks[j]);
    if (a.left < b.right && b.left < a.right && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) bad.push('重叠：' + blocks[i].className + ' / ' + blocks[j].className);
  }
  const bdfs = parseFloat(getComputedStyle(document.body).getPropertyValue('--bd') || '50');
  const enfs = parseFloat(getComputedStyle(document.body).getPropertyValue('--en') || '54');
  if (document.querySelector('.board') && bdfs < args[1]) bad.push('板书字号 ' + bdfs + ' < ' + args[1]);
  if (document.querySelector('.sent') && enfs < args[2]) bad.push('英文字号 ' + enfs + ' < ' + args[2]);
  for (const l of document.querySelectorAll('.board .ln')) {
    const card = l.closest('.card').getBoundingClientRect();
    if (R(l).right > card.right - 40) bad.push('板书一行放不下：' + l.textContent);
    const rs = [...l.getClientRects()]; if (rs.length > 1 || R(l).height > bdfs * 1.5 + 14) bad.push('板书折行：' + l.textContent);
  }
  // 中文孤字 / 行首标点 / 英文单词断开：逐字量位置分行
  const lines = el => { const out = []; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) for (let i = 0; i < n.textContent.length; i++) {
      const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1); const b = r.getClientRects()[0]; if (!b || !b.width) continue;
      const ch = n.textContent[i]; let L = out.find(x => Math.abs(x.top - b.top) < b.height * 0.5);
      if (!L) { L = {top: b.top, s: []}; out.push(L); } L.s.push([b.left, ch]); }
    out.sort((a, b) => a.top - b.top); return out.map(x => x.s.sort((a, b) => a[0] - b[0]).map(y => y[1]).join('')); };
  for (const el of document.querySelectorAll('.ttl, .sent, .full, .title > div, .hd .src')) {
    const ls = lines(el).map(x => x.trim()).filter(Boolean);
    if (ls.length > 1) {
      const last = ls[ls.length - 1].replace(/[，。、；：？！）”’,.;:?!)]/g, '');
      if (/[一-鿿]/.test(last) && [...last].length <= 1) bad.push('孤字：' + ls[ls.length - 1]);
      for (const x of ls.slice(1)) if (/^[，。、；：？！）”’]/.test(x)) bad.push('行首标点：' + x.slice(0, 10));
    }
    for (let i = 0; i + 1 < ls.length; i++) if (/[A-Za-z]$/.test(ls[i]) && /^[a-z]/.test(ls[i + 1]) && !/\s$/.test(lines(el)[i])) {
      const txt = el.textContent.replace(/\s+/g, ' '); const tail = ls[i].split(' ').pop(), headw = ls[i + 1].split(' ')[0];
      if (txt.includes(tail + headw)) bad.push('英文单词被断开：' + tail + '|' + headw);
    }
  }
  const txt = document.body.innerText;
  for (const o of others) if (txt.includes(o)) bad.push('出现别的项目的文字：' + o);
  return bad;
}"""


def fonts_used(page_, cdp):
    """CDP 实测：页面上每个文字元素实际用到的字体（只许 Inter、Noto Sans SC）。"""
    doc = cdp.send('DOM.getDocument', {'depth': -1})
    bad = set()

    def walk(n):
        if n.get('nodeType') == 1 and n.get('nodeName') not in ('STYLE', 'HEAD', 'SCRIPT', 'HTML'):
            try:
                r = cdp.send('CSS.getPlatformFontsForNode', {'nodeId': n['nodeId']})
                for f in r.get('fonts', []):
                    if not any(f['familyName'] == x or f['familyName'].startswith(x + ' ') for x in FONTS):
                        bad.add(f"{f['familyName']}（{n.get('nodeName')}）")
            except Exception:
                pass
        for c in n.get('children', []):
            walk(c)
    walk(doc['root'])
    return sorted(bad)


def stills(doc, outdir, only=None):
    from playwright.sync_api import sync_playwright
    from 题目间隔 import QGAP_JS, MIN_GAP
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    F = frames(doc)
    if only:
        F = [f for f in F if f[0] in only]
    probs, info = [], {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=2)
        cdp = pg.context.new_cdp_session(pg)
        cdp.send('DOM.enable')
        cdp.send('CSS.enable')
        for i, (fid, body) in enumerate(F):
            h = page(body)
            hp = outdir / f'{i:03d}_{fid}.html'
            hp.write_text(h, 'utf-8')
            pg.goto(hp.as_uri())
            pg.evaluate('document.fonts.ready')
            fit = pg.evaluate(FIT_JS)
            e = pg.evaluate(CHECK_JS, [OTHER_PROJECTS, BOARD_MIN, EN_MIN])
            e += pg.evaluate(QGAP_JS, MIN_GAP)
            fb = fonts_used(pg, cdp)
            if fb:
                e.append('字体回退：' + '、'.join(fb))
            png = outdir / f'{i:03d}_{fid}.png'
            pg.screenshot(path=str(png))
            hp.unlink()
            info[fid] = {'png': png.name, 'fit': fit, 'sha256': hashlib.sha256(png.read_bytes()).hexdigest()}
            for x in e:
                probs.append(f'{fid}：{x}')
        b.close()
    (outdir / 'stills.json').write_text(json.dumps(info, ensure_ascii=False, indent=1), 'utf-8')
    return [f[0] for f in F], probs


def timeline(doc, tm, ids):
    """每个画面的起止（秒）：片头 0→第一段开口；之后每段开口前 SWITCH_EARLY 秒切（不早于上一段读完）。"""
    items = {it['id']: it for it in tm['items']}
    cuts = [0.0]
    prev_end = 0.0
    for fid in ids[1:]:
        it = items[fid]
        t = it['start'] if fid == ids[1] else max(prev_end + 0.05, it['start'] - SWITCH_EARLY)
        cuts.append(t)
        prev_end = it['end']
    cuts.append(tm['duration'])
    return cuts


def encode(pngdir, ids, cuts, mp3, out):
    tmp = Path(tempfile.mkdtemp(prefix='gram_'))
    try:
        fr = [round(c * FPS) for c in cuts[:-1]] + [math.ceil(cuts[-1] * FPS)]
        lst = []
        info = json.loads((Path(pngdir) / 'stills.json').read_text('utf-8'))
        for i, fid in enumerate(ids):
            n = fr[i + 1] - fr[i]
            assert n > 0, (fid, n)
            sf = tmp / f'seg{i:03d}.mp4'
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-framerate', str(FPS), '-i', str(Path(pngdir) / info[fid]['png']),
                            '-frames:v', str(n), '-vf', 'format=yuv420p', '-c:v', 'libx264', '-preset', 'ultrafast', '-qp', '0',
                            '-pix_fmt', 'yuv420p', str(sf)], check=True)
            lst.append(f"file '{sf}'")
        (tmp / 'list.txt').write_text('\n'.join(lst))
        total = fr[-1] / FPS
        silent = tmp / 'v.mp4'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(tmp / 'list.txt'),
                        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-tune', 'stillimage', '-pix_fmt', 'yuv420p',
                        '-g', str(FPS * 30), '-x264-params', 'scenecut=0', str(silent)], check=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(silent), '-i', str(mp3), '-map', '0:v', '-map', '1:a',
                        '-c:v', 'copy', '-af', f'apad=whole_dur={total:.3f}', '-t', f'{total:.3f}', '-c:a', 'aac', '-b:a', '192k',
                        '-movflags', '+faststart', str(out)], check=True)
        return fr
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def verify(mp4, mp3, tm, pngdir, ids, fr):
    """成品核查，返回问题列表。"""
    import gaokao_tts as G
    from 讲解音频 import tone_check, BUZZ_MAX_DB
    errs = []
    pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(mp4)], capture_output=True, text=True).stdout)
    v = next(s for s in pr['streams'] if s['codec_type'] == 'video')
    au = next(s for s in pr['streams'] if s['codec_type'] == 'audio')
    if (v['width'], v['height']) != (3840, 2160):
        errs.append(f"分辨率 {v['width']}×{v['height']}")
    if v['r_frame_rate'] != '30/1' or v['avg_frame_rate'] != '30/1':
        errs.append(f"帧率 {v['r_frame_rate']} / {v['avg_frame_rate']}")
    ts = [float(x) for x in subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'packet=pts_time', '-of', 'csv=p=0', str(mp4)],
                                           capture_output=True, text=True).stdout.split()]
    ts.sort()
    d = np.diff(ts)
    if len(d) and (abs(d.max() - 1 / FPS) > 1e-3 or abs(d.min() - 1 / FPS) > 1e-3):
        errs.append(f'帧间隔不恒定：{d.min():.4f}—{d.max():.4f}')
    vd, ad = float(v['duration']), float(au['duration'])
    if abs(vd - ad) > 1 / FPS + 1e-3 or len(ts) != fr[-1]:
        errs.append(f'声画不等长：画面 {vd:.3f}s（{len(ts)} 帧），声音 {ad:.3f}s')
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32)
    env = 20 * np.log10(np.sqrt(np.convolve(a ** 2, np.ones(480) / 480, mode='same')) + 1e-9)
    loud = np.where(env > -45)[0]
    lead, tail = loud[0] / 48000, (len(a) - loud[-1]) / 48000
    if lead < LEAD - 0.02:
        errs.append(f'开头静音 {lead:.2f}s < {LEAD}')
    if tail < TAIL:
        errs.append(f'结尾静音 {tail:.2f}s < {TAIL}')
    import io
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, a, 48000, format='WAV')
    items = tm['items']
    rep, e2 = G._VERIFY_CORE(Path(mp3).read_bytes(), items, -16.0, fine=True)
    errs += ['MP3 ' + x for x in e2]
    # 视频音轨（AAC 解码后）再量一次整体、短时、峰值、意群
    import pyloudnorm as pyln
    il = pyln.Meter(48000).integrated_loudness(a.astype(np.float64))
    if abs(il + 16) > 0.7:
        errs.append(f'视频音轨整体响度 {il:.2f}')
    import 响度细查
    frep, fe = 响度细查.fine_check(a.astype(np.float64), 48000, items)
    errs += ['视频音轨 ' + x for x in fe]
    errs += ['合格证：' + x for x in G.certificate_problems(tm, Path(mp3))]
    f0, mx = tone_check(a, 48000, items)
    if mx > BUZZ_MAX_DB:
        errs.append(f'电磁音：{f0} Hz 高出周围 {mx} dB')
    if any('‖' in it.get('text', '') or '？' in it.get('text', '') for it in items):   # 标记边界停顿、问句尾音（视频音轨上独立量）
        import 讲解节奏
        _, rerr = 讲解节奏.check(a, 48000, items, {it['id']: it['text'] for it in items})
        errs += ['视频音轨节奏：' + x for x in rerr]
    import 去呼吸
    br = 去呼吸.breath_check(a, 48000)
    if br:
        errs.append(f'视频音轨呼吸声 {len(br)} 处：{br[:6]}')
    # 逐屏抽帧（每屏中间一帧）与截图比较
    info = json.loads((Path(pngdir) / 'stills.json').read_text('utf-8'))
    from PIL import Image
    tmp = Path(tempfile.mkdtemp(prefix='gramchk_'))
    try:
        for i, fid in enumerate(ids):
            t = (fr[i] + fr[i + 1]) / 2 / FPS
            o = tmp / f'{i}.png'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', str(mp4), '-frames:v', '1', str(o)], check=True)
            x = np.asarray(Image.open(o).convert('RGB'), np.float32)
            y = np.asarray(Image.open(Path(pngdir) / info[fid]['png']).convert('RGB'), np.float32)
            md = float(np.abs(x - y).mean())
            if md > 2.0:
                errs.append(f'第 {i} 屏 {fid} 与截图不一致（平均差 {md:.2f}）')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return errs, {'lead': round(lead, 3), 'tail': round(tail, 3), 'video_lufs': round(il, 2), 'buzz': mx, 'duration': vd, **frep}


def selftest():
    """双向验证：正常页 0 处；每颗雷都必须报出。"""
    from playwright.sync_api import sync_playwright
    from 题目间隔 import QGAP_JS, MIN_GAP
    ok_body = '<div class="card" style="top:130px;bottom:60px"><div class="ttl zh">答案汇总</div><div class="sum"><div class="qg">56 a</div><div class="qg">57 b</div><div class="qg">58 c</div><div class="qg">59 d</div></div></div>'
    mines = {
        '卡片溢出': '<div class="card" style="top:130px;height:200px"><div class="board">' + '<div class="ln">一行</div>' * 8 + '</div></div>',
        '出画面': '<div class="card" style="top:900px;height:400px">x</div>',
        '重叠': '<div class="card" style="top:100px;height:300px">a</div><div class="card" style="top:300px;height:300px">b</div>',
        '板书放不下': '<div class="card" style="top:130px;bottom:60px"><div class="board"><div class="ln">' + '很长的一行板书' * 8 + '</div></div></div>',
        '字号过小': '<div class="card" style="top:130px;bottom:60px"><div class="board" style="--bd:30px"><div class="ln">小字</div></div></div><style>body{--bd:30px}</style>',
        '字体回退': '<div class="card" style="top:130px;bottom:60px"><div class="ttl" style="font-family:DejaVu Serif">Fallback</div></div>',
        '孤字': '<div class="card" style="top:130px;bottom:60px;width:900px;right:auto"><div class="ttl zh" style="width:600px;text-wrap:wrap">一二三四五六七八九十甲</div></div>',
        '别的项目': '<div class="card" style="top:130px;bottom:60px"><div class="ttl">专八精读</div></div>',
        '题间无线': '<div class="card" style="top:130px;bottom:60px"><div class="sum">' + '<div class="qg" style="border:none;padding:0">5 a</div>' * 4 + '</div></div>',
    }
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': W, 'height': H})
        cdp = pg.context.new_cdp_session(pg)
        cdp.send('DOM.enable')
        cdp.send('CSS.enable')
        tmp = Path(tempfile.mkdtemp())
        for name, body in [('正常', ok_body)] + list(mines.items()):
            f = tmp / 'x.html'
            f.write_text(page(body), 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            e = pg.evaluate(CHECK_JS, [OTHER_PROJECTS, BOARD_MIN, EN_MIN]) + pg.evaluate(QGAP_JS, MIN_GAP)
            e += ['字体回退'] if fonts_used(pg, cdp) else []
            res[name] = e
        b.close()
    good = not res['正常'] and all(res[k] for k in mines)
    for k, v in res.items():
        print(f'  {k}：{len(v)} 处' + (f'（{v[0][:40]}）' if v else ''))
    print('自检', '通过' if good else '失败')
    return good


def main():
    if '--自检' in sys.argv:
        sys.exit(0 if selftest() else 1)
    ap = argparse.ArgumentParser()
    ap.add_argument('--稿', required=True)
    ap.add_argument('--音频')
    ap.add_argument('--stills', action='store_true')
    ap.add_argument('--video', action='store_true')
    ap.add_argument('--out', required=True)
    ap.add_argument('--png', help='截图目录（默认 out/截图）')
    ap.add_argument('--name')
    a = ap.parse_args()
    doc = json.loads(Path(a.稿).read_text('utf-8'))
    out = Path(a.out)
    png = Path(a.png) if a.png else out / '截图'
    only = None
    if a.音频:
        tm = json.loads(Path(a.音频).with_suffix('.timings.json').read_text('utf-8'))
        import gaokao_tts as G
        cp = G.certificate_problems(tm, Path(a.音频))      # 生成前核对音频合格证（踩坑 85、87）：没有合格证、处理链不对、MP3 被改过都不许生成
        if cp:
            sys.exit('音频合格证不通过，不生成：' + '；'.join(cp))
        only = {'title'} | {it['id'] for it in tm['items']}
    ids, probs = stills(doc, png, only)
    print(f'截图 {len(ids)} 张，排版检查 {len(probs)} 处')
    for x in probs:
        print('  ✗', x)
    if probs:
        sys.exit(1)
    if a.video:
        cuts = timeline(doc, tm, ids)
        mp4 = out / (a.name or 'video.mp4')
        fr = encode(png, ids, cuts, a.音频, mp4)
        errs, rep = verify(mp4, a.音频, tm, png, ids, fr)
        print('成品核查：', json.dumps(rep, ensure_ascii=False))
        if errs:
            mp4.unlink()
            for x in errs:
                print('  ✗', x)
            sys.exit(1)
        print('成品核查全部通过：', mp4)


if __name__ == '__main__':
    main()
