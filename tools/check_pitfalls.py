"""踩坑总检查：CLAUDE.md《踩坑记录》里出过的每一个问题，都在这里写成程序检查。

用法（必须用装了依赖的环境：/opt/ttsenv/bin/python）：
    python tools/check_pitfalls.py text  [p25 p26 …]   文字：英文原文、中文译文、生词标注 —— 生成音频前必须通过
    python tools/check_pitfalls.py audio [p25 …]       音频：响度、朗读文本、语音识别回转 —— 生成视频前必须通过
    python tools/check_pitfalls.py video [p25 …]       视频：verify_videos 全部核查 + 解码零错误 + 编码参数 + 内容指纹
    python tools/check_pitfalls.py all                 以上全部 + 仓库级检查，结果写到 踩坑检查报告.md
    python tools/check_pitfalls.py approve p25 …       翻译与释义复核通过后，登记这些篇目的文字指纹

不写篇目时：text/audio 检查全部已完成标注的篇目，video 检查 最终视频/ 里的全部视频。
任何一项不通过，退出码为 1。缺依赖或程序出错同样算不通过，绝不打印“通过”
（踩坑：用错 Python 缺 numpy，核查没跑起来，却读到了旧报告里的“全部通过”）。
"""
import ast
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FINAL = ROOT / '最终视频'
AUDIO = ROOT / 'audio'
APPROVED = HERE / '复核通过.json'            # 篇目 -> 复核通过时的文字指纹
VIDFP = FINAL / '视频指纹.json'              # 视频文件名 -> 生成时的内容指纹（文字 + 音频）
POS_OK = HERE / '词性已核.json'              # 词性自动比对报警、经人工逐条核对确认无误的条目
QA_OK = HERE / 'tts' / '识别差异已核.json'   # 语音识别的关键差异、经人工核对确认读音无误的条目
sys.path[:0] = [str(HERE / 'tts'), str(HERE / 'video')]

# CLAUDE.md 踩坑记录每一条由哪些检查负责。新增踩坑必须在这里登记，否则 repo 检查不通过。
COVER = {
    1: '音频响度（MP3 成品 + 视频音轨各测一次）', 2: '独立测量（ITU-R BS.1770，与处理流程不同的实现）',
    3: '每句至少一个生词', 4: '语音识别回转：漏读、多读', 5: '朗读文本不残留括号/数字/符号/中文',
    6: '切句：人名缩写、U.S. 句末', 7: '英文排版', 8: '画面与声音等长', 9: '逐屏编码 + 无损拼接',
    10: '结尾静音 ≥ 2.0 秒', 11: '文件名不重复', 12: '仓库脚本不得出现 pkill -f',
    13: '逐句朗读修正必须匹配', 14: '复核通过才能做音频视频；视频内容指纹与当前文字、音频一致',
    15: '被否决的意见逐条人工过目（流程项，复核结果存档）', 16: '英文订正全部记录在案',
    17: '原文修正恰好匹配一次；sents.json 与 sent.py 一致', 18: '直撇号', 19: '千分位分数（朗读文本无数字）',
    20: '朗读内容与画面英文逐句一致', 21: '改复核指令后埋雷测试（流程项）', 22: '视频流畅：帧间隔恒定、解码零错误、编码参数',
    23: '否定词、词尾 -ed/-s 的识别差异必须人工核对', 24: '高亮词的词性与释义一致', 25: '中文排版与重复字串',
    26: '核查报告必须是最新的、覆盖全部视频', 27: '词尾辅音被吞（reawakened）：识别差异必须人工核对',
}


class Result:
    def __init__(self):
        self.rows = []

    def add(self, no, where, ok, detail=''):
        self.rows.append((no, where, bool(ok), detail))

    @property
    def fails(self):
        return [r for r in self.rows if not r[2]]


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else json.dumps(b, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def load(path, default):
    return json.loads(Path(path).read_text('utf-8')) if Path(path).exists() else default


def data():
    return json.loads((ROOT / 'data' / 'vocab.json').read_text('utf-8'))


def sents(p):
    return [s for para in p['paras'] for s in para]


def text_fp(p):
    """复核用的文字指纹：标题、体裁、概要、每句英文、中文和全部标注。"""
    return sha({k: p.get(k) for k in ('year', 'paper', 'part', 'title', 'genre', 'summary', 'paras')})


def video_fp(p, tm):
    """视频内容指纹：画面上出现的全部文字 + 音频文件本身。任何一项变了，视频就必须重做。"""
    return sha({'text': {k: p.get(k) for k in ('year', 'paper', 'part', 'words', 'title', 'genre', 'paras')},
                'audio': sha((AUDIO / tm['file']).read_bytes())})


def video_name(p):
    paper = re.sub(r'·[^）]*', '', p['paper'])
    title = (p.get('title') or '').translate(str.maketrans('/\\:*?"<>|', '／＼：＊？＂＜＞｜'))
    return f"{p['year']} {paper} 阅读{p['part']} {title}".strip() + '.mp4'


# ---------------------------------------------------------------- 文字
TYPO = [(r'"', '直引号'), (r"'", '直撇号'), (r'“\s|\s”', '引号内侧空格'), (r'(?<=[A-Za-z])[,;:](?=[A-Za-z“])', '标点后缺空格'),
        (r'(?<=[A-Za-z])\((?=[A-Za-z])', '括号前缺空格'), (r'\s-\s|\w- (?!(?:or|and|to)\b)\w|\w -\w', '连字符多余空格'),
        (r'(?:^|\s)[A-HJ-Z]\.$', '在人名缩写处断句'), (r'\b(\w+) \1\b', '重复单词'),
        (r'\bU\.S\. (?:The|This|It|They|He|She|We|In|But|And|A|An)\b', 'U.S. 句末没断句'), (r'\s[,.;:!?]', '标点前多余空格'),
        (r'\s{2,}', '多余空格')]


def zh_problems(z, whole):
    probs = []
    if re.search(r'[;?!]|(?<!\d),|,(?!\d)|(?<!\d):|:(?!\d)', z): probs.append('半角标点')
    if re.search(r'[一-鿿]\.(?!\d)|(?<![\w.])\.(?=[一-鿿])', z): probs.append('半角句点')
    if whole and z.count('“') != z.count('”'): probs.append('引号不配对')
    if re.search(r'[，。；：！？、]{2,}|，。|。，', z): probs.append('重复标点')
    if re.search(r'[一-鿿] +[一-鿿]', z): probs.append('汉字间空格')
    if '"' in z: probs.append('直引号')
    if re.search(r'([一-鿿，、]{4,})\1', z): probs.append('连续重复字串')
    return probs


def post_corrections():
    """从 sent.py 里读出全部英文订正（POST、POST4…），不执行 sent.py 本身。"""
    tree = ast.parse((HERE / 'sent.py').read_text('utf-8'))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and re.fullmatch(r'POST\d*', node.targets[0].id):
            for k, v in ast.literal_eval(node.value).items():
                out.setdefault(k, []).extend(v)
    return out


def check_sents_json(R):
    """#17：tools/sents.json 必须就是当前 sent.py 跑出来的结果（订正写了却没生效，会在这里暴露）。"""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / 'sents').mkdir()
        for f in ('sent.py', 'passages.json'):
            (td / f).write_bytes((HERE / f).read_bytes())
        r = subprocess.run([sys.executable, 'sent.py'], cwd=td, capture_output=True, text=True)
        if r.returncode:
            R.add(17, 'sent.py', False, '运行出错（修正没匹配到或不唯一）：' + r.stderr.strip()[-300:])
            return
        same = json.loads((td / 'sents.json').read_text('utf-8')) == json.loads((HERE / 'sents.json').read_text('utf-8'))
        R.add(17, 'sents.json', same, '与 sent.py 当前输出一致' if same else 'sents.json 不是最新的：请重新运行 sent.py 并 build.py')


def check_text(R, pids):
    D = data()
    P = {p['id']: p for p in D['passages']}
    approved = load(APPROVED, {})
    posok = set(load(POS_OK, []))
    post = post_corrections()
    log = re.sub(r'\s+', ' ', (ROOT / '原文订正记录.md').read_text('utf-8')).replace('’', "'").replace('“', '"').replace('”', '"')
    try:
        from gaokao_tts import Pronouncer
        pron = Pronouncer()
    except Exception as e:                       # 缺依赖 = 不通过
        R.add(5, '朗读文本', False, f'无法载入朗读程序：{e}')
        pron = None
    try:
        import spacy
        nlp = spacy.load('en_core_web_sm')
    except Exception as e:
        R.add(24, '词性比对', False, f'无法载入 spaCy：{e}')
        nlp = None
    POSMAP = {'n.': {'NOUN', 'PROPN'}, 'v.': {'VERB', 'AUX'}, 'adj.': {'ADJ'}, 'adv.': {'ADV'}}
    for pid in pids:
        p = P[pid]
        S = sents(p)
        # #14 复核通过才能进入音频、视频
        R.add(14, pid, approved.get(pid) == text_fp(p),
              '文字与复核通过时一致' if approved.get(pid) == text_fp(p) else
              ('还没有登记复核通过' if pid not in approved else '复核通过后文字又改过：改动必须重新复核，再 approve'))
        # #3 每句至少一个生词
        empty = [k for k, s in enumerate(S, 1) if not s['w']]
        R.add(3, pid, not empty, f'空句 {empty}' if empty else f'{len(S)} 句都有标注')
        # #6 #7 #18 英文排版、切句、重复
        bad = []
        for k, s in enumerate(S, 1):
            for pat, name in TYPO:
                m = re.search(pat, s['en'])
                if m and not (name == '重复单词' and m.group(1).lower() in ('that', 'had', 'is')):
                    bad.append(f'第{k}句{name}')
        dup = [k for k in range(2, len(S) + 1) if S[k - 1]['en'] in [x['en'] for x in S[:k - 1]]]
        bad += [f'第{k}句与前文重复' for k in dup]
        R.add(7, pid, not bad, '；'.join(bad) if bad else '英文排版、切句全部正常')
        # #25 中文排版
        zh = [('标题', p.get('title') or '', True), ('概要', p.get('summary') or '', True)] + \
             [(f'第{k}句', s['zh'], False) for k, s in enumerate(S, 1)] + \
             [(f'第{k}句 {w["h"]}', w['m'], True) for k, s in enumerate(S, 1) for w in s['w']]
        zbad = [f'{w}{zh_problems(z, whole)}' for w, z, whole in zh if zh_problems(z, whole)]
        allzh = ''.join(s['zh'] for s in S)
        if allzh.count('“') != allzh.count('”'):
            zbad.append('全文中文引号不配对')
        if not (p.get('title') and p.get('summary') and p.get('genre')):
            zbad.append('标题/体裁/概要缺失')
        R.add(25, pid, not zbad, '；'.join(zbad) if zbad else '中文排版正常')
        # #16 英文订正全部记录在 原文订正记录.md
        en = ' '.join(s['en'] for s in S)
        miss = [b for a, b in post.get(pid, []) if b.replace('’', "'").replace('“', '"').replace('”', '"') not in log]
        R.add(16, pid, not miss, f'订正记录里找不到：{miss}' if miss else f'{len(post.get(pid, []))} 处订正都有记录')
        # #5 #13 #19 #23 朗读文本
        if pron:
            rbad = []
            for k, s in enumerate(S, 1):
                try:
                    t = pron.read_text(s['en'], f'{pid}:{k}')
                    if '’' in re.sub(r'’(?![A-Za-z])|(?<![A-Za-z])’', '', t):
                        rbad.append(f'第{k}句残留词内弯撇号')
                except Exception as e:
                    rbad.append(f'第{k}句：{e}')
            R.add(5, pid, not rbad, '；'.join(rbad) if rbad else '朗读文本全部合格')
        # #24 高亮词的词性与释义一致（spaCy 自动比对；报警条目须人工核对后登记到 词性已核.json）
        if nlp:
            pbad = []
            for k, s in enumerate(S, 1):
                doc = nlp(s['en'])
                for w in s['w']:
                    pos = w['m'].split(' ')[0]
                    if w['t'] == 'phr' or len(w['sp']) != 1 or pos not in POSMAP:
                        continue
                    a, b = w['sp'][0]
                    toks = [t for t in doc if a <= t.idx < b]
                    key = f"{pid}:{k}:{w['h']}:{w['m']}"
                    if toks and not any(t.pos_ in POSMAP[pos] for t in toks) and key not in posok:
                        pbad.append(f"第{k}句 {w['h']}（{pos}）高亮“{s['en'][a:b]}”被识别为 {[t.pos_ for t in toks]}")
            R.add(24, pid, not pbad, '；'.join(pbad) if pbad else '高亮词词性与释义一致')


# ---------------------------------------------------------------- 音频
NEG = {'not', 'no', 'never', 'nor', 'cannot', 'none', 'nothing', 'neither'}


def critical_ops(a, b):
    """语音识别差异里会改变意思的几类：否定词、词尾（-ed/-s/-ing/n't）、漏读、多读。"""
    A = [w for w in a.lower().split() if re.search('[a-z]', w)]     # 引号等纯符号不算词
    B = [w for w in b.lower().split() if re.search('[a-z]', w)]
    if not A and not B:
        return []
    why = []
    if {w for w in A if w in NEG or w.endswith("n't")} != {w for w in B if w in NEG or w.endswith("n't")}:
        why.append('否定词')
    if not B: why.append('漏读')
    if not A: why.append('多读')
    strip = lambda w: re.sub(r"(es|s|ed|d|ing|n't)$", '', w)
    why += [f'词尾 {x}/{y}' for x in A for y in B if x != y and len(x) > 2 and strip(x) == strip(y)]
    return why


def apo(t):
    """撇号写法（’ 与 '）不影响朗读内容；早期音频的朗读文本保留了弯撇号。"""
    return t.replace('’', "'")


def check_audio(R, pids, voice='female'):
    from gaokao_tts import verify_loudness, Pronouncer
    D = data()
    P = {p['id']: p for p in D['passages']}
    T = load(AUDIO / 'timings.json', {}).get(voice, {})
    QA = load(AUDIO / 'qa_report.json', {}).get(voice, {})
    qaok = load(QA_OK, {})
    pron = Pronouncer()
    for pid in pids:
        p = P[pid]
        if pid not in T:
            R.add(1, pid, False, '没有音频')
            continue
        tm = T[pid]
        mp3 = (AUDIO / tm['file']).read_bytes()
        # #1 #2 响度：对 MP3 成品独立测量
        rep, errs = verify_loudness(mp3, tm['sentences'], -16.0)
        R.add(1, pid, not errs, f"整体 {rep['integrated_lufs']} LUFS，句间最大偏差 {rep['sentence_max_dev_lu']} LU，"
                                 f"短时波动 {rep['short_term_std_lu']} LU，峰值 {rep['peak_dbfs']} dBFS" + ('；' + '；'.join(errs) if errs else ''))
        # #20 #13 朗读内容与当前英文、当前朗读修正一致（改了英文或修正却没重新生成音频，会在这里暴露）
        S = sents(p)
        stale = [k for k, (s, t) in enumerate(zip(S, tm['sentences']), 1)
                 if s['en'] != t.get('text') or apo(pron.read_text(s['en'], f'{pid}:{k}')) != apo(t.get('read', ''))]
        ok = len(S) == len(tm['sentences']) and not stale
        R.add(20, pid, ok, f'{len(S)} 句全部一致' if ok else f'句数 {len(tm["sentences"])}/{len(S)}，不一致：第 {stale} 句（需重新生成音频）')
        # 铁律 3、4：开头 1.5 秒，句间 0.8 秒，结尾 ≥ 2 秒
        st = [x['start'] for x in tm['sentences']]
        en = [x['end'] for x in tm['sentences']]
        gaps = [st[i + 1] - en[i] for i in range(len(st) - 1)]
        ok = abs(st[0] - 1.5) < 0.01 and all(abs(g - 0.8) <= 0.01 for g in gaps) and tm['duration'] - en[-1] >= 1.95
        R.add(10, pid, ok, f'开头 {st[0]:.2f}s，句间 {min(gaps):.3f}–{max(gaps):.3f}s，结尾 {tm["duration"] - en[-1]:.2f}s')
        # #4 #23 #27 语音识别自检必须针对当前这份 MP3，关键差异必须人工核对过
        q = QA.get(pid)
        fresh = bool(q) and (q.get('mp3_sha256') == sha(mp3) if q.get('mp3_sha256') else q.get('loudness') == rep)
        R.add(4, pid, fresh, '语音识别自检针对的是当前音频' if fresh else '没有针对当前音频的语音识别自检：请运行 gaokao_tts.py qa')
        if fresh:
            crit = []
            for s in q['sentences']:
                ops = s['ops']
                # 同一个词在一处“漏读”、另一处“多读”，是识别结果改了写法或语序（如 £240 million），不是漏读
                moved = {a for a, b in ops if not b.strip()} & {b for a, b in ops if not a.strip()}
                crit += [f"第{s['k']}句 {a!r}→{b!r}（{'、'.join(critical_ops(a, b))}）" for a, b in ops
                         if critical_ops(a, b) and (a or b) not in moved and f"{pid}:{s['k']}:{a}→{b}" not in qaok]
            R.add(23, pid, not crit, '；'.join(crit) + '（逐条听辨/修正读音，确认无误后登记到 识别差异已核.json）' if crit else '无否定词、词尾、漏读、多读差异')
            low = [f"第{s['k']}句 {s['mos']}" for s in q['sentences'] if s['mos'] < 4.0]
            R.add(4, pid, not low, f'自然度低于 4.0：{low}' if low else f"自然度 {q['mos']:.2f}，每句都 ≥ 4.0")


# ---------------------------------------------------------------- 视频
def probe(mp4, args):
    return subprocess.run(['ffprobe', '-v', 'error', *args, '-of', 'json', str(mp4)], capture_output=True, text=True, check=True).stdout


def moov_first(mp4):
    """+faststart：moov 在 mdat 之前，手机/网页边下边播不卡。"""
    with open(mp4, 'rb') as f:
        order = []
        while True:
            h = f.read(8)
            if len(h) < 8:
                break
            size, typ = int.from_bytes(h[:4], 'big'), h[4:].decode('latin1')
            if size == 1:
                size = int.from_bytes(f.read(8), 'big') - 8
            order.append(typ)
            f.seek(size - 8, 1)
    return 'moov' in order and 'mdat' in order and order.index('moov') < order.index('mdat')


def check_video_file(R, mp4, p, tm, fps_rec):
    from verify_videos import check
    name = mp4.name
    for n, c, d in check(mp4, p, tm):            # 铁律与 #1 #3 #8 #10 #11 #20 #22
        no = {'响度一致（第一项检查）': 1, '每句至少标注一个单词': 3, '画面与声音等长': 8, '结尾静音 2 秒': 10,
              '朗读内容与画面英文逐句一致': 20}.get(n, 22)
        R.add(no, f'{name}：{n}', c, d)
    # #22 流畅：完整解码一遍，不允许任何错误；编码参数统一
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-f', 'null', '-'], capture_output=True, text=True)
    R.add(22, f'{name}：完整解码零错误', r.returncode == 0 and not r.stderr.strip(), r.stderr.strip()[:200] or '零错误')
    info = json.loads(probe(mp4, ['-show_entries', 'stream=codec_type,codec_name,pix_fmt,avg_frame_rate,r_frame_rate,start_time,sample_rate']))['streams']
    v = next(s for s in info if s['codec_type'] == 'video')
    a = next(s for s in info if s['codec_type'] == 'audio')
    ok = (v['codec_name'] == 'h264' and v['pix_fmt'] == 'yuv420p' and v['avg_frame_rate'] == v['r_frame_rate'] == '30/1'
          and a['codec_name'] == 'aac' and abs(float(v['start_time'])) < 1e-3 and abs(float(a['start_time'])) < 0.05)
    R.add(22, f'{name}：编码参数', ok, f"{v['codec_name']} {v['pix_fmt']} {v['avg_frame_rate']} fps，{a['codec_name']} {a['sample_rate']} Hz，"
                                    f"起点 画面 {float(v['start_time']):.3f}s / 声音 {float(a['start_time']):.3f}s")
    R.add(22, f'{name}：边下边播（faststart）', moov_first(mp4), 'moov 在前' if moov_first(mp4) else 'moov 在后，手机播放可能卡顿')
    # #14 视频必须是用当前文字和当前音频做的
    rec = fps_rec.get(name)
    cur = video_fp(p, tm)
    R.add(14, f'{name}：内容指纹', rec == cur, '与当前文字、音频一致' if rec == cur else
          ('没有生成记录' if rec is None else '文字或音频在视频生成后改过：视频必须重做'))


def check_video(R, pids=None, voice='female'):
    D = data()
    T = load(AUDIO / 'timings.json', {}).get(voice, {})
    fps_rec = load(VIDFP, {})
    files = sorted(FINAL.glob('*.mp4'))
    keys = [re.sub(r'\s\S+$', '', f.stem) for f in files]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    R.add(11, '最终视频', not dup, f'重复：{dup}' if dup else f'{len(files)} 个文件名互不重复')
    for p in D['passages']:
        if not p.get('done') or (pids and p['id'] not in pids):
            continue
        prefix = f"{p['year']} {re.sub(r'·[^）]*', '', p['paper'])} 阅读{p['part']} "
        mine = [f for f in files if f.name.startswith(prefix)]
        if not mine:
            if pids:
                R.add(14, p['id'], False, '没有视频')
            continue
        for mp4 in mine:
            R.add(14, f'{mp4.name}：文件名与当前标题一致', mp4.name == video_name(p), f'应为 {video_name(p)}')
            check_video_file(R, mp4, p, T[p['id']], fps_rec)
    orphan = [f.name for f in files if not any(f.name.startswith(f"{p['year']} {re.sub(r'·[^）]*', '', p['paper'])} 阅读{p['part']} ")
                                               for p in D['passages'] if p.get('done'))]
    R.add(14, '最终视频', not orphan, f'找不到对应文章：{orphan}' if orphan else '每个视频都有对应文章')


# ---------------------------------------------------------------- 仓库
def check_repo(R):
    tracked = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True).stdout.split('\n')
    pk = [f for f in tracked if f.endswith(('.py', '.sh', '.js')) and f != 'tools/check_pitfalls.py'
          and 'pkill -f' in (ROOT / f).read_text('utf-8', 'ignore')]
    R.add(12, '仓库脚本', not pk, f'含 pkill -f：{pk}' if pk else '没有 pkill -f')
    pyc = [f for f in tracked if '__pycache__' in f or f.endswith('.pyc')]
    R.add(12, '仓库文件', not pyc, f'误提交缓存文件：{pyc}' if pyc else '没有误提交的缓存文件')
    mv = (HERE / 'video' / 'make_video.py').read_text('utf-8')
    R.add(9, 'make_video.py', "'-f', 'concat'" in mv and "'-c', 'copy'" in mv and "'-loop', '1'" in mv and '+faststart' in mv,
          '逐屏单独编码、无损拼接、faststart')
    R.add(22, 'make_video.py', 'check_pitfalls' in mv and 'from verify_videos import check' in mv,
          '生成前做文字/音频踩坑检查，生成后做视频核查，不合格删除成品')
    tts = (HERE / 'tts' / 'gaokao_tts.py').read_text('utf-8')
    R.add(2, 'gaokao_tts.py', 'verify_loudness(' in tts and 'pyloudnorm' in tts, '成品 MP3 用 BS.1770（pyloudnorm）独立测量')
    # 新的踩坑必须有对应检查
    md = (ROOT / 'CLAUDE.md').read_text('utf-8')
    nums = sorted(int(x) for x in re.findall(r'^\| (\d+) \|', md, re.M))
    missing = [n for n in nums if n not in COVER]
    R.add(26, 'CLAUDE.md', not missing, f'踩坑 {missing} 没有登记检查' if missing else f'踩坑 1–{max(nums)} 全部登记了检查')
    check_sents_json(R)
    # #26 核查报告必须是最新的，覆盖文件夹里全部视频
    rep = FINAL / '核查报告.md'
    files = sorted(FINAL.glob('*.mp4'))
    txt = rep.read_text('utf-8') if rep.exists() else ''
    ok = rep.exists() and all(f.stem in txt for f in files) and all(rep.stat().st_mtime >= f.stat().st_mtime for f in files)
    R.add(26, '核查报告.md', ok, f'覆盖全部 {len(files)} 个视频且比视频新' if ok else '报告过期或没覆盖全部视频：请重新运行 verify_videos.py')


# ---------------------------------------------------------------- 入口
def report(R, title):
    by = {}
    for no, where, ok, d in R.rows:
        by.setdefault(no, []).append((where, ok, d))
    lines = [f'# {title}', '', f"**总结：{'全部通过' if not R.fails else f'有 {len(R.fails)} 项不通过'}**（共 {len(R.rows)} 项）", '']
    for no in sorted(by):
        rows = by[no]
        bad = [r for r in rows if not r[1]]
        lines.append(f"## {'❌' if bad else '✅'} 踩坑 {no}：{COVER.get(no, '')}（{len(rows) - len(bad)}/{len(rows)}）")
        lines += [f'- ❌ {w}：{d}' for w, ok, d in bad]
        lines.append('')
    return '\n'.join(lines)


def run(mode, pids, R=None):
    R = R or Result()
    done = [p['id'] for p in data()['passages'] if p.get('done')]
    if mode in ('text', 'all'):
        check_text(R, pids or done)
    if mode in ('audio', 'all'):
        T = load(AUDIO / 'timings.json', {}).get('female', {})
        check_audio(R, pids or [x for x in done if x in T])
    if mode in ('video', 'all'):
        check_video(R, pids)
    if mode == 'all':
        check_repo(R)
    return R


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('text', 'audio', 'video', 'all', 'approve'):
        raise SystemExit(__doc__)
    mode, pids = sys.argv[1], sys.argv[2:]
    if mode == 'approve':
        D = {p['id']: p for p in data()['passages']}
        ap = load(APPROVED, {})
        for pid in pids:
            ap[pid] = text_fp(D[pid])
        APPROVED.write_text(json.dumps(dict(sorted(ap.items())), ensure_ascii=False, indent=1), 'utf-8')
        print('已登记复核通过：', ' '.join(pids))
        return
    try:
        R = run(mode, pids)
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit('❌ 检查程序本身出错，视为不通过')
    for no, where, ok, d in R.fails:
        print(f'❌ 踩坑 {no} {where}：{d}')
    if mode == 'all':
        (ROOT / '踩坑检查报告.md').write_text(report(R, '踩坑总检查报告'), 'utf-8')
    print(f"{'✅ 全部通过' if not R.fails else f'❌ {len(R.fails)} 项不通过'}（{mode}，共 {len(R.rows)} 项）")
    sys.exit(1 if R.fails else 0)


if __name__ == '__main__':
    main()
