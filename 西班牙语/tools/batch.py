"""批量生成西班牙语逐句精读视频：每篇 朗读音频（make_audio.py）→ 4K 视频（make_video.py）→ 自动核查，一条命令做完。

    python 西班牙语/tools/batch.py es01                         # 一篇（默认音色 = voices.json 的 _final，默认背景 C）
    python 西班牙语/tools/batch.py es01 es02 es05 --voice supertonic3_M1F5_25 --style 5
    python 西班牙语/tools/batch.py all                          # 文章/ 里的全部篇目（模板.json 和 _ 开头的不算）
    python 西班牙语/tools/batch.py all --stills                 # 只出截图（西班牙语/截图/<篇目>_<背景>/），先看画面再生成视频
    python 西班牙语/tools/batch.py --list                       # 列出音色、背景、篇目和每篇的生成情况
    python 西班牙语/tools/batch.py --check                      # 安装自检（Python 包、ffmpeg、浏览器、模型）

做法（一次启动、自动做到底）：
1. 开工前先把要做的每一篇全部检查一遍（文章格式、每句都有生词、生词在句中恰好出现一次、朗读文本没有数字和符号、
   逗号停顿.json 能匹配上），还有音色模型、ffmpeg 是否就绪。有问题就在开工前把所有篇目的所有问题一次列出来（哪一篇、第几句）再停下，
   不会做到一半才发现，也不用改一处、跑一次。
2. 逐篇：音频 → 视频。已经是最新的就跳过（--force 强制重做）：
   - 音频“最新”= timings.json 里有这一篇、检查全部通过、每句原文和停顿切分与现在的文章一致、音色设置没改过（种子、路径不算）；
   - 视频“最新”= 成品和 _核查.json 都在、核查全部通过、用的是同一个音色，并且 文章、插图、音频、背景样式、--scale 都和
     上次生成时一样（指纹记在 最终视频/批量生成记录.json）。
3. 音频检查没通过（响度、电磁音）时自动重做：设了随机种子的音色（Qwen3）整篇换下一个种子（1234 → 1235 → 1236，整篇只用一个种子），
   Supertonic 直接重新合成（每次合成都带随机性：2026-10-15 工具包实测 es01 三次的梳状线 1.07、2.29、0.72 dB，第三次通过；
   新写的短文每次通过的机会更小：2 句、句中还有逗号停顿的 es02 约 1/4（卡在短时响度波动），6 句的 es03 约 1/4（卡在梳状线残留），
   2 句的模板文章约 2/3）；最多 --tries 次（默认 Qwen3 3 次、Supertonic 15 次）。“朗读部分太短、测不了”这类重做也没用的，不重试。
   视频核查只在响度 / 电磁音（视频音轨重新测量）上没过时，当作音频没过：换种子 / 重新合成，音频和视频一起重做（共用 --tries）；
   视频别的核查项没过不重试（画面、时间轴的问题重做也一样）。
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
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ES = HERE.parent
sys.path.insert(0, str(HERE))
import c4  # noqa: E402
import voice_check as VC  # noqa: E402

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
    ids, miss = [], []
    for n in names:
        n = Path(n).stem if n.endswith('.json') else n
        if not (ART / f'{n}.json').is_file():
            miss.append(str(ART / f'{n}.json'))
        elif n not in ids:
            ids.append(n)
    if miss:
        raise SystemExit('找不到文章：' + '、'.join(miss) + '（篇目名就是文件名，不带 .json）')
    return ids


def tag(pid, msg):
    """问题前面加上篇目名；原话里已经有篇目名的（make_audio.py 的报错）不再重复。"""
    msg = str(msg).strip()
    return msg if re.search(rf'(?<![\w-]){re.escape(pid)}(?![\w-])', msg) else f'{pid} {msg}'


def validate(pid, MA, MV):
    """开工前检查一篇，把能查到的问题全部找出来（不是查到第一处就停）：格式、每句的原文 / 翻译 / 生词
    （生词的检查和 make_video.load 一样，最后再用 make_video.load 本身核对一遍）、朗读文本与逗号停顿（make_audio.segments）。
    返回 (文章, 问题列表)；有问题时文章是 None。每条问题都以篇目名开头，如“es03 第 1 句没有标生词……”。"""
    probs = []
    try:
        raw = json.loads((ART / f'{pid}.json').read_text('utf-8'))
    except UnicodeDecodeError:
        return None, [f'{pid}.json 不是 UTF-8 编码：用文本编辑器“另存为”，编码选 UTF-8']
    except json.JSONDecodeError as e:
        return None, [f'{pid}.json 不是合法的 JSON：第 {e.lineno} 行第 {e.colno} 列 {e.msg}'
                      '（常见原因：少了逗号、引号是中文引号、最后一项后面多了逗号）']
    if not isinstance(raw, dict):
        return None, [f'{pid}.json 最外层必须是 {{ … }}']
    miss = [k for k in ('id', 'title_es', 'title_zh', 'paras') if not raw.get(k)]
    if miss:
        probs.append(f'{pid}.json 缺少 {miss}')
    if raw.get('id') and raw['id'] != pid:
        probs.append(f'{pid}.json 里的 "id" 是 {raw["id"]!r}，必须和文件名 {pid} 一样')
    paras = raw.get('paras')
    if paras and not (isinstance(paras, list) and all(isinstance(x, list) and x and all(isinstance(s, dict) for s in x) for x in paras)):
        return None, probs + [f'{pid}.json 的 "paras" 格式不对：应该是段落列表，每段是句子列表 [ {{"es": …, "zh": …, "w": [ … ]}}, … ]（照 模板.json 写）']
    sents = [s for para in (paras or []) for s in para]
    for k, s in enumerate(sents, 1):
        for key in ('es', 'zh'):
            if not isinstance(s.get(key), str) or not s[key].strip():
                probs.append(f'{pid} 第 {k} 句缺少 "{key}"')
        es = s.get('es') if isinstance(s.get('es'), str) else ''
        ws = s.get('w')
        if not isinstance(ws, list) or not ws:
            probs.append(f'{pid} 第 {k} 句没有标生词：每一句至少要标一个（"w" 里至少一个词条）')
            ws = []
        taken = []
        for w in ws:
            if not isinstance(w, dict):
                probs.append(f'{pid} 第 {k} 句的 "w" 里有一项不是 {{"h": …, "pos": …, "zh": …, "surface": …}}')
                continue
            name = w.get('h') or w.get('surface')
            bad = [x for x in ('h', 'pos', 'zh', 'surface') if not str(w.get(x, '')).strip() and not (x == 'pos' and 'pos' in w)]
            if bad:
                probs.append(f'{pid} 第 {k} 句的词条 {name} 缺少 {bad}')
            sf = w.get('surface')
            if not isinstance(sf, str) or not sf or not es:
                continue
            n = es.count(sf)
            if n != 1:
                probs.append(f'{pid} 第 {k} 句：词条「{name}」的 surface（句中要高亮的原样文字）「{sf}」在这一句里出现 {n} 次'
                             '（必须恰好 1 次，大小写、重音都要和原文一模一样；出现多次就多写几个字，让它只匹配一处）')
                continue
            a = es.index(sf)
            if any(a < y and x < a + len(sf) for x, y in taken):
                probs.append(f'{pid} 第 {k} 句：词条「{name}」与别的词条重叠')
            taken.append((a, a + len(sf)))
        if es:
            try:
                MA.segments(es, k, pid)
            except RuntimeError as e:
                probs.append(tag(pid, e))
    extra = [k for k in MA.PAUSES.get(pid, {}) if not k.startswith('_') and not (k.isdigit() and 1 <= int(k) <= len(sents))]
    if extra:
        probs.append(f'逗号停顿.json：{pid} 只有 {len(sents)} 句，却登记了第 {extra} 句')
    if probs:
        return None, probs
    try:                                    # 上面没查出问题：再用生成视频时的同一个函数核对一遍（以它为准）
        return MV.load(pid), []
    except SystemExit as e:
        return None, [tag(pid, e)]


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
    """这个音色能不能用（检查写在 voice_check.py，make_audio.py 也用同一份）。返回问题列表（空 = 能用）。"""
    return VC.voice_problems(VOICES[name])


def fix_hint(name):
    return VC.fix_hint(VOICES[name])


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


def browser_ok(MV):
    """真的打开一次截图用的浏览器、画一页。用的就是 make_video.py 的 launch_browser（同一个规则：环境变量 ES_CHROMIUM →
    Playwright 自带的 Chromium → 都打不开才试开发机上的），所以这里通过 = 生成视频时也打得开。
    返回空字符串 = 正常，否则是出错原因（第一行）。"""
    if importlib.util.find_spec('playwright') is None:
        return '缺少 Python 包 playwright'
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            br = MV.launch_browser(pw)
            pg = br.new_page()
            pg.set_content('<p>ok</p>')
            br.close()
        return ''
    except Exception as e:      # noqa: BLE001  自检：任何错误都转成说明
        return str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__


def py_cmd():
    """给老师看的“用这个 Python 运行”的写法：工具包的 .venv 写相对路径（在工具包文件夹里运行），别的写完整路径。"""
    try:
        if Path(sys.prefix).resolve() == (ES.parent / '.venv').resolve():
            return '.venv\\Scripts\\python' if os.name == 'nt' else '.venv/bin/python'
    except OSError:
        pass
    return f'"{sys.executable}"' if ' ' in sys.executable else sys.executable


def browser_fix(err):
    """浏览器打不开时的处理办法（可以直接复制运行的命令）。"""
    if err == '缺少 Python 包 playwright':
        return '先按上面的提示装好 Python 包（重新运行安装脚本），再运行一次自检'
    exe = os.environ.get('ES_CHROMIUM', '').strip()
    if exe and Path(exe).exists():
        return (f'环境变量 ES_CHROMIUM 指定的浏览器 {exe} 打不开：把它改成能用的 Chromium / Chrome 程序的完整路径，'
                '或者去掉这个环境变量（改用安装脚本装的浏览器）')
    where = '在工具包文件夹里' if py_cmd().startswith('.venv') else ''
    fix = f'请{where}运行：{py_cmd()} -m playwright install chromium（国内网络慢：重新运行安装脚本，加 --mirror / -Mirror）'
    if sys.platform.startswith('linux'):
        fix += f'\n     装好后还打不开（Linux 缺系统库）：sudo {py_cmd()} -m playwright install-deps chromium'
    return fix


def self_check(MV):
    say(f'Python：{sys.executable}（{sys.version.split()[0]}）')
    probs = env_problems()
    for p in probs:
        say('  ❌ ' + p)
    if not probs:
        say('  ✅ Python 包、ffmpeg、磁盘空间')
    b = browser_ok(MV)
    say('  ✅ 浏览器（截图用的 Chromium，已实际打开一次）' if not b else f'  ❌ 浏览器打不开：{b}\n     {browser_fix(b)}')
    say('音色：')
    vp = {k: voice_problems(k) for k in VOICES if not k.startswith('_')}
    for name, pr in vp.items():
        say(f'  {"✅" if not pr else "❌"} {name}{"（默认）" if name == VOICES["_final"] else ""}：{VOICES[name].get("label", "")}')
        for x in pr:
            say(f'       {x}')
    ready = sorted((k for k, pr in vp.items() if not pr), key=lambda k: k != 'supertonic3_M1F5_25')
    bad = probs or b or not ready
    default_ok = not vp[VOICES['_final']]
    if not default_ok:
        say(f'提示：默认音色 {VOICES["_final"]} 还不能用。{fix_hint(VOICES["_final"])}')
    if bad:
        say('自检没有通过，请按上面的提示处理。')
    elif default_ok:
        say('自检通过，可以生成视频。')
    else:
        say(f'自检通过，但默认音色还不能用：现在生成视频要在命令里加 --voice {ready[0]}'
            f'（例如 ./生成视频.sh es01 --voice {ready[0]}；Windows 用 生成视频.bat）。')
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
    ap.add_argument('--tries', type=int, help='音频检查没通过时最多做几次：默认 Qwen3（换种子，每次十几分钟）3 次，Supertonic（重新合成，短文每次不到 1 分钟、es01 约 2 分钟）15 次')
    ap.add_argument('--stills', action='store_true', help='只出截图（不生成音频和视频），写到 西班牙语/截图/<篇目>_<背景>/')
    ap.add_argument('--list', action='store_true', help='列出音色、背景、篇目和生成情况')
    ap.add_argument('--check', action='store_true', help='安装自检')
    a = ap.parse_args()
    if a.check:
        return self_check(MV)
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
    #    所有篇目的所有问题、环境和音色的问题一次全部列出来再停（改完一处再跑才发现下一处，太费时间）
    ids = article_ids(a.articles)
    arts, aprobs = {}, []
    for pid in ids:
        arts[pid], pr = validate(pid, MA, MV)
        aprobs += pr
    need_audio = not a.stills and (a.force or any(arts[pid] is None or not audio_state(arts[pid], voice, MA)[0] for pid in ids))
    vprobs = [f'音色 {voice}：{x}' for x in voice_problems(voice)] if need_audio else []    # 音频都已是最新时不需要配音模型
    probs = aprobs + env_problems(a.stills) + vprobs
    if probs:
        bad = [pid for pid in ids if arts[pid] is None]
        raise SystemExit(f'开工前检查没通过，共 {len(probs)} 处' + (f'（文章有问题的：{"、".join(bad)}）' if bad else '') + '：\n  '
                         + '\n  '.join(probs) + ('\n' + fix_hint(voice) if vprobs else '')
                         + ('\n文章的问题改好后，再运行同一条命令。' if bad else ''))
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

        # 2. 音频 → 3. 视频。视频核查只在“响度 / 电磁音”（对视频音轨重新测量）上没过时，说明这次合成正好在边缘
        #    （音频检查刚好过，视频里 AAC 重新编码后差一点，实测梳状线 0.88 → 1.01 dB）：当作音频没过，
        #    换下一个种子 / 重新合成，音频和视频一起重做（和音频共用 --tries 次数）。别的核查项没过不重试。
        cfg = VOICES[voice]
        tries = max(1, a.tries or (3 if 'seed' in cfg else 15))
        seeds = [None] + ([cfg['seed'] + i for i in range(1, tries)] if 'seed' in cfg else [None] * (tries - 1))
        i = 0
        ok, why = (False, '--force') if a.force else audio_state(p, voice, MA)
        need_audio = not ok
        if ok:
            astat = '已是最新，跳过'
            say(f'\n{head}：音频{why}，跳过')
        else:
            say(f'\n{head}：生成音频（{why}）')
        while True:
            if need_audio:
                while True:
                    seed = seeds[i]
                    args = [tools / 'make_audio.py', pid, '--voice', voice] + (['--seed', seed] if seed is not None else [])
                    rc, tail = run(args)
                    if not rc:
                        break
                    retry = ('检查未通过' in tail or '都不正常' in tail) and '测不了' not in tail      # 太短测不了：重做也一样
                    if not retry or i == len(seeds) - 1:
                        rows.append((pid, '失败', '—', time.time() - t0))
                        what = '朗读音频检查没通过' + (f'（已试 {i + 1} 次）' if retry else '')
                        more = ('' if not retry else
                                '可以加大次数再运行同一条命令（如 --tries 30）；' + ('或换 Qwen3 音色（检查一般一次就过，但慢）。' if 'seed' not in cfg
                                                                             else '或换一个音色。'))
                        return stop(rows, f'{pid} {what}，看上面的输出。{more}{HELP}')
                    i += 1
                    say(f'  检查没通过，{"换种子 " + str(seeds[i]) if seeds[i] is not None else "重新合成"}再做一次（第 {i + 1}/{len(seeds)} 次）')
                astat = '新生成' + (f'（种子 {seed}）' if seed is not None else '') + (f'，第 {i + 1} 次' if i else '')
                need_audio = False
            ok, why, name = (False, '--force', video_name(p, a.style, MV)) if a.force else video_state(p, voice, a.style, scale, MV)
            if ok:
                say(f'  视频{why}，跳过：{name}')
                rows.append((pid, astat, '已是最新，跳过', time.time() - t0))
                break
            say(f'  生成视频（{why}）')
            rc, tail = run([tools / 'make_video.py', pid, '--voice', voice, '--style', a.style, '--scale', scale])
            if not rc:
                remember(name, video_key(p, voice, a.style, scale, MV), voice, a.style, scale)
                rows.append((pid, astat, '新生成，核查通过', time.time() - t0))
                break
            bad = [x for x in tail.splitlines() if '❌' in x]
            if bad and all(re.search(r'❌ (响度一致|无电磁音)', x) for x in bad) and i < len(seeds) - 1:
                i += 1
                need_audio = True
                say(f'  视频音轨复测的响度 / 电磁音没过（这次合成正好在边缘），当作音频没过：'
                    f'{"换种子 " + str(seeds[i]) if seeds[i] is not None else "重新合成"}，音频和视频一起重做（第 {i + 1}/{len(seeds)} 次）')
                continue
            rows.append((pid, astat, '失败', time.time() - t0))
            return stop(rows, f'{pid} 视频生成或核查没通过（没通过的成品已删除），看上面的输出。{HELP}')
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
        p, pr = validate(pid, MA, MV)
        if pr:
            say(f'  {pid}：❌ 文章有 {len(pr)} 处问题：\n      ' + '\n      '.join(pr))
            continue
        n = sum(len(x) for x in p['paras'])
        au = audio_state(p, voice, MA)
        vi = video_state(p, voice, style, scale, MV) if au[0] else (False, '—', '')
        say(f'  {pid} {p["title_es"]} {p["title_zh"]}（{n} 句）：音频 {au[1]}；视频 {vi[1]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
