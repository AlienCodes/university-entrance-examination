"""批量生成西班牙语逐句精读视频：每篇 朗读音频（make_audio.py）→ 4K 视频（make_video.py）→ 自动核查，一条命令做完。

    python 西班牙语/tools/batch.py es01                         # 一篇（默认音色 = voices.json 的 _final，默认背景 C）
    python 西班牙语/tools/batch.py es01 es02 es05 --voice supertonic3_M1F5_25 --style 5
    python 西班牙语/tools/batch.py all                          # 文章/ 里的全部篇目（模板.json 和 _ 开头的不算）
    python 西班牙语/tools/batch.py all --stills                 # 只出截图（西班牙语/截图/<篇目>_<背景>/），先看画面再生成视频
    python 西班牙语/tools/batch.py --list                       # 列出音色、背景、篇目和每篇的生成情况
    python 西班牙语/tools/batch.py --check                      # 安装自检（Python 包、ffmpeg、浏览器、模型）

做法（一次启动、自动做到底）：
1. 开工前先把要做的每一篇全部检查一遍（文章格式、每句都有生词、生词在句中恰好出现一次、朗读文本没有数字和符号、
   逗号停顿.json 能匹配上），还有音色模型、ffmpeg 是否就绪。有一处不对就在开工前报错，不会做到一半才发现。
2. 逐篇：音频 → 视频。已经是最新的就跳过（--force 强制重做）：
   - 音频“最新”= timings.json 里有这一篇、检查全部通过、每句原文和停顿切分与现在的文章一致、音色设置没改过（种子、路径不算）；
   - 视频“最新”= 成品和 _核查.json 都在、核查全部通过、用的是同一个音色，并且 文章、插图、音频、背景样式、--scale 都和
     上次生成时一样（指纹记在 最终视频/批量生成记录.json）。
3. 音频检查没通过（响度、电磁音）时自动重做：设了随机种子的音色（Qwen3）整篇换下一个种子（1234 → 1235 → 1236，整篇只用一个种子），
   Supertonic 直接重新合成（每次合成都带随机性：2026-10-15 工具包实测 es01 三次的梳状线 1.07、2.29、0.72 dB，第三次通过）；
   最多 --tries 次（默认 Qwen3 3 次、Supertonic 6 次）。视频的检查没通过不重试（画面、时间轴的问题重做也一样）。
4. 任何一步失败就停下，说清楚是哪一篇、哪一步、怎么处理；最后打印汇总表。成品在 西班牙语/最终视频/。

所有检查都在 make_audio.py / make_video.py 里（响度四项、电磁音两项、片头 1.5 秒、句间 0.8 秒、结尾 2 秒、4K、30 帧、画面与朗读逐句一致……），
这里不放宽任何一项。
"""
import argparse
import collections
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ES = HERE.parent
sys.path.insert(0, str(HERE))
import c4  # noqa: E402

ART = ES / '文章'
AUD = ES / 'audio'
OUT = ES / '最终视频'
SHOTS = ES / '截图'
RECORD = OUT / '批量生成记录.json'
VOICES = json.loads((HERE / 'voices.json').read_text('utf-8'))
IGNORE = {'label', 'python', 'model_dir', 'ref_audio', 'seed', 'num_threads'}   # 不影响“要不要重做”的设置（路径、种子、线程数）
HELP = '处理办法见 使用说明.md「检查没通过怎么办」'


def say(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- 篇目
def article_ids(names):
    if names == ['all']:
        ids = sorted(p.stem for p in ART.glob('*.json') if not p.stem.startswith(('模板', '_')))
        if not ids:
            raise SystemExit(f'{ART} 里没有文章（*.json）')
        return ids
    ids = []
    for n in names:
        n = Path(n).stem if n.endswith('.json') else n
        if not (ART / f'{n}.json').is_file():
            raise SystemExit(f'找不到文章 {ART / (n + ".json")}（篇目名就是文件名，不带 .json）')
        if n not in ids:
            ids.append(n)
    return ids


def validate(pid, MA, MV):
    """开工前检查一篇：格式、生词（make_video.load）、朗读文本与逗号停顿（make_audio.segments）。返回文章。"""
    try:
        raw = json.loads((ART / f'{pid}.json').read_text('utf-8'))
    except json.JSONDecodeError as e:
        raise SystemExit(f'{pid}.json 不是合法的 JSON：第 {e.lineno} 行第 {e.colno} 列 {e.msg}（常见原因：少了逗号、引号是中文引号、最后一项后面多了逗号）')
    miss = [k for k in ('id', 'title_es', 'title_zh', 'paras') if not raw.get(k)]
    if miss:
        raise SystemExit(f'{pid}.json 缺少 {miss}')
    if raw['id'] != pid:
        raise SystemExit(f'{pid}.json 里的 "id" 是 {raw["id"]!r}，必须和文件名 {pid} 一样')
    try:
        p = MV.load(pid)
    except SystemExit as e:
        raise SystemExit(f'{pid}：{e}')
    sents = [s for para in p['paras'] for s in para]
    for k, s in enumerate(sents, 1):
        for key in ('es', 'zh'):
            if not str(s.get(key, '')).strip():
                raise SystemExit(f'{pid} 第 {k} 句缺少 "{key}"')
        for w in s['w']:
            bad = [x for x in ('h', 'pos', 'zh', 'surface') if not str(w.get(x, '')).strip() and not (x == 'pos' and 'pos' in w)]
            if bad:
                raise SystemExit(f'{pid} 第 {k} 句的词条 {w.get("h") or w.get("surface")} 缺少 {bad}')
        try:
            MA.segments(s['es'], k, pid)
        except RuntimeError as e:
            raise SystemExit(f'{pid}：{e}')
    extra = [k for k in MA.PAUSES.get(pid, {}) if not k.startswith('_') and not (k.isdigit() and 1 <= int(k) <= len(sents))]
    if extra:
        raise SystemExit(f'逗号停顿.json：{pid} 只有 {len(sents)} 句，却登记了第 {extra} 句')
    return p


# ---------------------------------------------------------------- 是否已是最新
def norm(cfg):
    return {k: v for k, v in cfg.items() if k not in IGNORE and not k.startswith('_') and not k.endswith('说明')}


def timings():
    f = AUD / 'timings.json'
    return json.loads(f.read_text('utf-8')) if f.is_file() else {}


def audio_state(p, voice, MA):
    e = timings().get(voice, {}).get(p['id'])
    if not e:
        return False, '还没有音频'
    if e.get('draft_issues'):
        return False, '上次是草稿（有检查没通过）'
    if not (AUD / e['file']).is_file():
        return False, '音频文件不见了'
    sents = [s for para in p['paras'] for s in para]
    if len(e['sentences']) != len(sents):
        return False, '句数变了'
    for k, (s, t) in enumerate(zip(sents, e['sentences']), 1):
        if t['text'] != s['es'] or t.get('segments') != MA.segments(s['es'], k, p['id']):
            return False, f'第 {k} 句原文或逗号停顿改过'
    if norm(e.get('voice_cfg', {})) != norm(VOICES[voice]):
        return False, '音色设置改过'
    return True, '已是最新'


def sha(*parts):
    h = hashlib.sha256()
    for x in parts:
        h.update(x if isinstance(x, bytes) else str(x).encode('utf-8'))
        h.update(b'\0')
    return h.hexdigest()


def video_key(p, voice, style, scale, MV):
    e = timings()[voice][p['id']]
    img = ES / '图片' / f'{p["id"]}_插图.jpg'
    css = MV.STYLES[style].get('file')
    return sha((ART / f'{p["id"]}.json').read_bytes(), img.read_bytes() if img.is_file() else b'',
               (AUD / e['file']).read_bytes(), json.dumps(e['sentences'], sort_keys=True),
               (HERE / '样式' / css).read_bytes() if css else b'', voice, style, scale)


def records():
    return json.loads(RECORD.read_text('utf-8')) if RECORD.is_file() else {}


def video_name(p, style, MV):
    MV.STYLE = style
    try:
        return MV.video_name(p)
    finally:
        MV.STYLE = 'C'


def video_state(p, voice, style, scale, MV):
    name = video_name(p, style, MV)
    f, chk = OUT / name, OUT / (Path(name).stem + '_核查.json')
    if not f.is_file():
        return False, '还没有视频', name
    if not chk.is_file():
        return False, '没有核查记录', name
    c = json.loads(chk.read_text('utf-8'))
    if not c.get('checks') or not all(x.get('ok') for x in c['checks']):
        return False, '上次的核查没有全部通过', name
    if c.get('voice') != voice:
        return False, f'现有视频用的是音色 {c.get("voice")}', name
    key = video_key(p, voice, style, scale, MV)
    r = records().get(name)
    if r is None:                       # 没有批量记录（如工具包自带的示例）：成品比文章和音频都新，且分辨率对得上，就登记下来
        e = timings()[voice][p['id']]
        newer = f.stat().st_mtime >= max((ART / f'{p["id"]}.json').stat().st_mtime, (AUD / e['file']).stat().st_mtime)
        if newer and probe_width(f) == 1920 * scale:
            remember(name, key, voice, style, scale)
            return True, '已是最新（已有成品，核查通过）', name
        return False, '没有生成记录', name
    if r.get('key') != key:
        return False, '文章、插图、音频、背景或尺寸改过', name
    return True, '已是最新', name


def probe_width(f):
    try:
        out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width',
                              '-of', 'csv=p=0', str(f)], capture_output=True, text=True).stdout.strip()
        return int(out)
    except (ValueError, OSError):
        return 0


def remember(name, key, voice, style, scale):
    R = records()
    R[name] = {'key': key, 'voice': voice, 'style': style, 'scale': scale, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
    OUT.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(R, ensure_ascii=False, indent=1), 'utf-8')


# ---------------------------------------------------------------- 运行子程序（输出实时显示，同时留最后几十行判断原因）
def run(args):
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    cmd = [sys.executable, '-X', 'utf8'] + [str(x) for x in args]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                            text=True, encoding='utf-8', errors='replace', bufsize=1)
    tail = collections.deque(maxlen=60)
    for line in proc.stdout:
        print('    ' + line, end='', flush=True)
        tail.append(line)
    return proc.wait(), ''.join(tail)


# ---------------------------------------------------------------- 安装与模型自检
def voice_problems(name):
    """这个音色能不能用：模型文件、参考录音、Python 包。返回问题列表（空 = 能用）。"""
    cfg = VOICES[name]
    probs = []
    if cfg.get('engine') == 'worker':
        md = Path(cfg.get('model_dir', ''))
        md = md if md.is_absolute() else ES / md
        script = cfg.get('script')
        need = {'sherpa.py': ['tts.json', 'voice.bin', 'vocoder.int8.onnx'] if cfg.get('kind') == 'supertonic' else [],
                'qwen3tts.py': ['model.safetensors', 'speech_tokenizer/config.json']}.get(script, [])
        miss = [f for f in need if not (md / f).is_file()]
        if not md.is_dir() or miss:
            probs.append(f'模型没装好：{md}' + (f' 缺 {miss}' if md.is_dir() else ' 不存在'))
        if cfg.get('ref_audio'):
            ra = Path(cfg['ref_audio'])
            ra = ra if ra.is_absolute() else ES / ra
            if not ra.is_file():
                probs.append(f'找不到参考录音 {ra}')
        if cfg.get('python') in (None, '', 'auto'):
            mods = {'sherpa.py': ['sherpa_onnx'], 'qwen3tts.py': ['torch', 'transformers', 'qwen_tts', 'librosa'],
                    'kokoro_worker.py': ['kokoro_onnx']}.get(script, [])
            lack = [m for m in mods if importlib.util.find_spec(m) is None]
            if lack:
                probs.append(f'缺少 Python 包 {lack}')
        elif not Path(cfg['python']).exists() and not shutil.which(cfg['python']):
            probs.append(f'找不到 Python {cfg["python"]}')
    elif cfg.get('engine') == 'kokoro':
        if importlib.util.find_spec('kokoro_onnx') is None:
            probs.append('缺少 Python 包 kokoro_onnx')
        if not (ES.parent / 'tools' / 'tts' / 'models' / 'kokoro-v1.0.onnx').is_file():
            probs.append('缺少 Kokoro 模型 tools/tts/models/kokoro-v1.0.onnx')
    return probs


def fix_hint(name):
    cfg = VOICES[name]
    if cfg.get('script') == 'qwen3tts.py':
        return ('Qwen3 配音需要另外安装：①运行安装脚本时加 --qwen3（Windows：install_windows.bat -Qwen3）装 PyTorch 等；'
                '②下载 Release 里的 qwen3-tts-1.7b-base.zip.001、.002 … 放进工具包文件夹，运行 python 西班牙语/tools/join_parts.py 解压模型。'
                '或者先用快速的 Supertonic 音色：--voice supertonic3_M1F5_25')
    return '请重新运行安装脚本（install.sh / install_windows.bat），看 使用说明.md「安装」'


def env_problems(stills=False):
    probs = []
    for exe in ('ffmpeg', 'ffprobe'):
        if not shutil.which(exe):
            probs.append(f'找不到 {exe}：没装或不在 PATH 里（安装方法见 使用说明.md「安装 ffmpeg」）')
    for m in ('numpy', 'scipy', 'soundfile', 'soxr', 'pyloudnorm', 'lameenc', 'num2words', 'playwright'):
        if importlib.util.find_spec(m) is None:
            probs.append(f'缺少 Python 包 {m}（请用工具包的 .venv 里的 Python 运行，或重新运行安装脚本）')
    free = shutil.disk_usage(ES).free / 2**30
    if free < (0.5 if stills else 3):
        probs.append(f'磁盘剩余只有 {free:.1f} GB（生成视频至少要 3 GB）')
    return probs


def browser_ok():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
            br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
            pg = br.new_page()
            pg.set_content('<p>ok</p>')
            br.close()
        return ''
    except Exception as e:      # noqa: BLE001  自检：任何错误都转成说明
        return str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__


def self_check():
    say(f'Python：{sys.executable}（{sys.version.split()[0]}）')
    probs = env_problems()
    for p in probs:
        say('  ❌ ' + p)
    if not probs:
        say('  ✅ Python 包、ffmpeg、磁盘空间')
    b = browser_ok()
    say('  ✅ 浏览器（截图用的 Chromium）' if not b else f'  ❌ 浏览器打不开：{b}\n     请运行：{sys.executable} -m playwright install chromium'
        + ('（Linux 还可能要：sudo ' + sys.executable + ' -m playwright install-deps chromium）' if sys.platform.startswith('linux') else ''))
    say('音色：')
    ok_any = False
    for name in (k for k in VOICES if not k.startswith('_')):
        pr = voice_problems(name)
        ok_any |= not pr
        mark = '✅' if not pr else '❌'
        say(f'  {mark} {name}{"（默认）" if name == VOICES["_final"] else ""}：{VOICES[name].get("label", "")}')
        for x in pr:
            say(f'       {x}')
    bad = probs or b or not ok_any
    if voice_problems(VOICES['_final']):
        say(f'提示：默认音色 {VOICES["_final"]} 还不能用。{fix_hint(VOICES["_final"])}')
    say('自检通过，可以生成视频。' if not bad else '自检没有通过，请按上面的提示处理。')
    return 0 if not bad else 1


# ---------------------------------------------------------------- 主流程
def main():
    MV = c4.load('es_make_video', '西班牙语/tools/make_video.py')        # 只用标准库，先载入（背景样式清单）
    voices = [k for k in VOICES if not k.startswith('_')]
    ap = argparse.ArgumentParser(description='批量生成西班牙语逐句精读视频（音频 → 视频 → 核查）')
    ap.add_argument('articles', nargs='*', help='篇目（文章/ 里的文件名，不带 .json），或 all')
    ap.add_argument('--voice', choices=voices, help=f'音色（默认 {VOICES["_final"]}）')
    ap.add_argument('--style', default='C', choices=list(MV.STYLES),
                    help='背景样式：' + '，'.join(f'{k} {v["name"]}' for k, v in MV.STYLES.items()) + '（默认 C；预览见 西班牙语/背景样式/）')
    ap.add_argument('--scale', type=int, help='画面倍数：2 = 3840×2160（4K，视频默认）；--stills 默认 1（1920×1080）')
    ap.add_argument('--force', action='store_true', help='已是最新也重新生成')
    ap.add_argument('--tries', type=int, help='音频检查没通过时最多做几次：默认 Qwen3（换种子，每次十几分钟）3 次，Supertonic（重新合成，每次两三分钟）6 次')
    ap.add_argument('--stills', action='store_true', help='只出截图（不生成音频和视频），写到 西班牙语/截图/<篇目>_<背景>/')
    ap.add_argument('--list', action='store_true', help='列出音色、背景、篇目和生成情况')
    ap.add_argument('--check', action='store_true', help='安装自检')
    a = ap.parse_args()
    if a.check:
        return self_check()
    try:
        MA = c4.load('es_make_audio', '西班牙语/tools/make_audio.py')
    except ImportError as e:
        raise SystemExit(f'缺少 Python 包（{e.name}）：请用工具包 .venv 里的 Python 运行（生成视频.sh / 生成视频.bat 会自动用它），'
                         '或重新运行安装脚本。先运行 --check 自检。')
    voice = a.voice or VOICES['_final']
    if a.list:
        return show_list(voice, a.style, a.scale or 2, MA, MV)
    if not a.articles:
        ap.error('请给出篇目（如 es01），或 all')
    scale = a.scale or (1 if a.stills else 2)
    if scale < 1 or (not a.stills and scale < 2):
        raise SystemExit('--scale 至少 2（成品要求 4K：3840×2160）' if not a.stills else '--scale 至少 1')

    # 1. 开工前全部检查
    ids = article_ids(a.articles)
    arts = {pid: validate(pid, MA, MV) for pid in ids}
    need_audio = not a.stills and (a.force or any(not audio_state(arts[pid], voice, MA)[0] for pid in ids))
    vprobs = [f'音色 {voice}：{x}' for x in voice_problems(voice)] if need_audio else []    # 音频都已是最新时不需要配音模型
    probs = env_problems(a.stills) + vprobs
    if probs:
        raise SystemExit('开工前检查没通过：\n  ' + '\n  '.join(probs) + ('\n' + fix_hint(voice) if vprobs else ''))
    say(f'共 {len(ids)} 篇：{" ".join(ids)}；音色 {voice}；背景 {a.style} {MV.STYLES[a.style]["name"]}；'
        f'{"只出截图" if a.stills else f"{1920 * scale}×{1080 * scale}"}。开工前检查全部通过。')

    rows, t_all = [], time.time()
    tools = HERE
    for n, pid in enumerate(ids, 1):
        p, t0 = arts[pid], time.time()
        head = f'[{n}/{len(ids)}] {pid} {p["title_es"]} {p["title_zh"]}'
        if a.stills:
            out = SHOTS / f'{pid}_{a.style}'
            say(f'\n{head}：截图 → {out}')
            rc, tail = run([tools / 'make_video.py', pid, '--stills', '--style', a.style, '--scale', scale, '--out', out])
            if rc:
                rows.append((pid, '—', '截图失败', time.time() - t0))
                return stop(rows, f'{pid} 截图失败（画面排版检查没通过或出错，看上面的输出）。{HELP}')
            rows.append((pid, '—', f'截图 {out.relative_to(ES)}', time.time() - t0))
            continue

        # 2. 音频
        ok, why = (False, '--force') if a.force else audio_state(p, voice, MA)
        if ok:
            astat = '已是最新，跳过'
            say(f'\n{head}：音频{why}，跳过')
        else:
            say(f'\n{head}：生成音频（{why}）')
            cfg = VOICES[voice]
            tries = max(1, a.tries or (3 if 'seed' in cfg else 6))
            seeds = [None] + ([cfg['seed'] + i for i in range(1, tries)] if 'seed' in cfg else [None] * (tries - 1))
            for i, seed in enumerate(seeds):
                args = [tools / 'make_audio.py', pid, '--voice', voice] + (['--seed', seed] if seed is not None else [])
                rc, tail = run(args)
                if not rc:
                    break
                retry = '检查未通过' in tail or '都不正常' in tail
                if not retry or i == len(seeds) - 1:
                    rows.append((pid, '失败', '—', time.time() - t0))
                    what = '朗读音频检查没通过' + (f'（已试 {i + 1} 次）' if retry else '')
                    return stop(rows, f'{pid} {what}，看上面的输出。{HELP}')
                nxt = seeds[i + 1]
                say(f'  检查没通过，{"换种子 " + str(nxt) if nxt is not None else "重新合成"}再做一次（第 {i + 2}/{len(seeds)} 次）')
            astat = '新生成' + (f'（种子 {seed}）' if seed is not None else '')

        # 3. 视频
        ok, why, name = (False, '--force', video_name(p, a.style, MV)) if a.force else video_state(p, voice, a.style, scale, MV)
        if ok:
            say(f'  视频{why}，跳过：{name}')
            rows.append((pid, astat, '已是最新，跳过', time.time() - t0))
            continue
        say(f'  生成视频（{why}）')
        rc, tail = run([tools / 'make_video.py', pid, '--voice', voice, '--style', a.style, '--scale', scale])
        if rc:
            rows.append((pid, astat, '失败', time.time() - t0))
            return stop(rows, f'{pid} 视频生成或核查没通过（没通过的成品已删除），看上面的输出。{HELP}')
        remember(name, video_key(p, voice, a.style, scale, MV), voice, a.style, scale)
        rows.append((pid, astat, '新生成，核查通过', time.time() - t0))
    summary(rows)
    say(f'\n全部完成（{len(ids)} 篇，用时 {fmt(time.time() - t_all)}）。' +
        (f'截图在 {SHOTS}' if a.stills else f'成品在 {OUT}'))
    return 0


def fmt(s):
    s = int(s)
    return f'{s // 3600} 小时 {s % 3600 // 60} 分' if s >= 3600 else f'{s // 60} 分 {s % 60} 秒'


def summary(rows):
    say('\n汇总：')
    say(f'  {"篇目":<8}{"音频":<16}{"视频":<20}用时')
    for pid, au, vi, t in rows:
        say(f'  {pid:<10}{au:<16}{vi:<20}{fmt(t)}')


def stop(rows, msg):
    summary(rows)
    say(f'\n❌ 停止：{msg}')
    return 1


def show_list(voice, style, scale, MA, MV):
    say('音色（--voice）：')
    for k in (k for k in VOICES if not k.startswith('_')):
        pr = voice_problems(k)
        say(f'  {k}{"（默认）" if k == VOICES["_final"] else ""}{"" if not pr else "（未就绪）"}：{VOICES[k].get("label", "")}')
    say('背景样式（--style，预览图在 西班牙语/背景样式/）：')
    for k, v in MV.STYLES.items():
        say(f'  {k} {v["name"]}：{v.get("feature", "")}')
    say(f'篇目（文章/，按音色 {voice}、背景 {style}、{1920 * scale}×{1080 * scale} 判断）：')
    for pid in article_ids(['all']):
        try:
            p = validate(pid, MA, MV)
        except SystemExit as e:
            say(f'  {pid}：❌ 文章有问题：{e}')
            continue
        n = sum(len(x) for x in p['paras'])
        au = audio_state(p, voice, MA)
        vi = video_state(p, voice, style, scale, MV) if au[0] else (False, '—', '')
        say(f'  {pid} {p["title_es"]} {p["title_zh"]}（{n} 句）：音频 {au[1]}；视频 {vi[1]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
