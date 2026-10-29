"""双向验证 + 静态检查 + 按产物查：每个会产出音频 / 视频的入口都接上了意群级电平统一和意群检查，产物都带合格证
（踩坑 85、87，用户 2026-10-29：“一定要生效、彻底杜绝”）。以后新项目复制旧脚本漏接、或者有人想绕过，这里拦下。

① 按产物查（最根本）：仓库里所有 */audio/**/timings.json 的每一条，要么是旧成品（清单冻结，只许减少）/ 专八听力原音，
   要么带 clause-v1 合格证、旁证 *.loudness.json 存在且与之完全相同、测量值在上限内；MP3 在本机时再核 sha256（GitHub 上只看 JSON）。
② 音频入口自动发现（不靠名单，.py 用 AST 认别名，.sh 也查；读不了的文件算错误）：TTS 引擎调用、MP3 / WAV / M4A 写出
   （soundfile 任何别名、from soundfile import write、wavfile、wave、pydub export、torchaudio.save、gTTS、edge-tts、ffmpeg -c:a / -b:a / -q:a 出音频）。
   每个入口必须真的调用（AST，不认注释和字符串）render_passage，或 segment + verify_loudness / final_check / save_checked；
   gaokao_tts.py 逐函数查：写音频文件的函数必须调 final_check / verify_loudness。
③ 视频入口按内容发现（ffmpeg 出 .mp4 且 -c:v / libx264 / -vcodec）：每个必须调用 verify_videos.check 或 certificate_problems，或写明豁免；
   调用 check 的列表推导里，过滤条件不许滤掉“音频合格证”“响度一致”（专八 RAW_SKIP 只在 RAW 模式例外），结果必须被汇总成失败列表、不许清空。
④ verify_loudness / _VERIFY_CORE 的 fine 只能是 True 或 not is_legacy(…)；别处不许重新赋值 _VERIFY_CORE、final_check、certificate、certificate_problems。
⑤ source='原音' 只有 专八/听力/原文/tools/原音音轨.py 能写；别处出现就报错（踩坑 87）。
⑥ 豁免（历史一次性排查工具、诊断脚本、考试原声）写明理由，只许减少。
    python3 tools/防复发/验证/意群响度入口.py              # 全部
    python3 tools/防复发/验证/意群响度入口.py --ci         # GitHub：只看 JSON，不核 MP3 的 sha256"""
import ast
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / 'tools' / 'tts'))
import 合格证 as CERT  # noqa: E402

CI = '--ci' in sys.argv
EXEMPT = {      # 音频入口豁免：路径 → 理由（只许减少）
    'tools/pipeline/audio_debug/tail2.py': '读音诊断：测词尾摩擦段时长，不产出给用户的音频',
    'tools/pipeline/audio_debug/tail3.py': '读音诊断：同上',
    '四级/电磁音排查/生成试听.py': '2026-10-08 电磁音排查的一次性对照（只改一个因素的原始合成），已结束，不再使用',
    '四级/音色试听/生成试听.py': '2026-10-07 选音色的一次性试听，已结束，不再使用',
    '四级/停顿对比/生成对比.py': '2026-10-07 逗号停顿规则的一次性对照样音，已结束，不再使用',
    'tools/tts/download_models.py': '只下载模型文件（提到 kokoro 是下载地址），不合成、不写音频',
    'tools/tts/搭环境.sh': '新容器装环境（装 kokoro 等依赖、下载模型），不合成、不写音频',
    '专八/听力/原文/tools/原音音轨.py': '专八听力考试原声（不是 TTS，用户 2026-10-29 定为不在范围内）；成品另有整体响度与峰值检查',
    '专八/听力/tools/听力视频.py': '专八听力考试原声的视频音轨（不是 TTS），同上',
}
VIDEO_EXEMPT = {   # 视频入口豁免：路径 → 理由（只许减少）
    '专八/听力/tools/听力视频.py': '专八听力考试原声（不是 TTS，没有 timings），用户 2026-10-29 定为不在范围内；有自己的成品核查',
}
GT_WRITE_EXEMPT = {'write_mp3', 'write_wav'}    # gaokao_tts 里只负责写字节的底层函数（调用它们的函数必须检查）
PROTECTED = ('音频合格证（处理链版本、意群响度检查）', '响度一致（第一项检查）')
GUARDED = ('_VERIFY_CORE', 'final_check', 'certificate', 'certificate_problems', 'save_checked', 'cert_check')
SKIP_DIRS = ('tools/防复发/',)
LEGACY_MAX = 438     # 2026-10-29 已发布、不追溯的成品条数（只许减少）
LEGACY_FROZEN = set("""
008f3aeec5ac 00c036225a8b 00e1f755e748 01bebbf65f63 020234b455a5 029575e0c7f5 02e2b8156535 033d1dca201d 03b7ce006cba 03dd1c62c27a
043e79fa04a0 0629561506f3 066df07f9c2c 06f02bdade97 07270d74eafd 079184a9512d 0880b29e2b0a 092d6be46e75 09543c293949 09b0f4f31d3a
09b260fa834a 09dc927dd4e0 0b26b19dad77 0b72414e739f 0bae5c6347da 0bd3da6dac66 0cfd3115245c 0d2ea204f936 0d72a56a483f 0dbea4391218
0ee8b3ed8b79 0f5b5288c4d4 0f97269e36dc 0fa95557bb05 100aa5591da9 10d9deb63d36 1182e71b4daa 11c1484741dd 11d87e23f53c 12148174ede2
127bf7c158d5 12a7ba7b91f8 12b31212e748 12bc791193ab 136a465951d6 15410a70707e 1689e0f143fe 16d784ce2f69 180a43c8a743 1879194701c9
187a9a6a430e 19c7115b85d1 19cd2b4154c2 1a51771a74d6 1b3a5f30cd20 1c33794fe7aa 1cad79f22c17 1d11c3b39368 1d440dad5151 1db074fef1d3
1e4058992ca3 1e9f6b7ec9c2 1eb14029846c 21d99a60ce98 21ee9dc8e4dd 21fa4a21ab8d 2344719d6395 23c582fd5838 23e20b7311eb 24754f404341
24bee5e94901 24c42e437471 24f14cb35434 25372d2dcc26 2551076b311e 278aa589a8c0 279dbe738c2f 27aa6ca8c60c 27bd685d7e83 27ca7106f702
29943d2b5950 29cf280f3cdc 2a0f1d850b92 2a454b1dbf96 2af8c3915bff 2b3f2b1ca277 2b9048c72d74 2c4ecfb9d65e 2c56ef3a0ea3 2ca0b6d6efd3
2d820656d2e7 2da9c353d20c 2dd3acc017ee 2ecead173863 2fa22ad68375 302c9bd75508 303c19648b4d 304f6c883394 31d1975713f9 3247be755394
32cb4560f47d 347c7bf2b133 34ee0380d53a 35047d06a222 35da9f1d1b26 384bf029d9e6 39c678136684 3a3b497c86a7 3a46fd2d694e 3bb033bfaf83
3befd5cd26af 3dac0da261a0 3e4798ce6aba 3ee1bb7429a8 3fdebc4db035 4248204547fe 42704987c1af 4280a978c519 42b5ddad67bf 42b66a305a79
43af84a3422d 442cb70281d0 4441f40d9057 4583c339b29e 46c1d74a995e 46e770a75104 47476871ae0f 4747f9d444f7 488f9c92804b 48c8a797434f
48d0ab245167 492f57f9fed6 494d7a9b5f7a 4a1ecd11b15b 4ae9e05ea59d 4b0083fc8756 4b53687e9dc5 4bfb06e341fc 4c4abe0e568e 4cf2ea7ecedc
4d775dab9bd5 4d77884fa441 4dc63ed2bc2b 4e784ae75d9f 5041b18ec4b7 518226a760f2 51ce049498cf 525a7bad7632 525e5c32768c 53f5768e5529
5422d1b06a28 5440994dfef7 548ec6e2031c 5536d159b91c 55cf38b9fbb4 564175b32f2b 5733ede8cad8 579dbeb8908c 57e4eab936f0 5846b59ae9c3
595a51cbbf82 5a1e41de6fb4 5a5472ffa329 5aa687b3d186 5b074389dd51 5baf6b149aa7 5db6b7651ddb 5e1feccd2252 5e8832ed1b0c 5f398099a45b
5f77e4b36481 603e55f9d84f 60d582b8d433 61223a03502f 61f127eefcfb 61f40e785278 63b28f7e224c 63cb732bc756 63e50538d249 641ec577390f
642959f5c6e7 65277c69f546 6555298656ae 6555bb83e191 65a0b8b2a8a8 68300beabd2f 686c1bef59ae 688221367a78 690297d5a540 69cee607cd05
69d4e9bdf4e6 6a1257861a06 6abc6d80a525 6b6e1b83f0ad 6b9617fbc2dd 6c18893683ad 6c2650da105e 6cfbbf1b9650 6d2638fa9205 6e35cb161c22
6e77de82fff8 700503ce9e66 70410d02321d 70bbd7d54f94 7123353e47f4 716324b6448c 722121403560 72f47d45b314 72fd16b907cd 73e698bac143
7426a48be2f5 74482768029b 74e532a635b9 752d286bb7a0 76604a92e315 7685b7dfd7bc 76c028a4757a 78004bcdad79 78a76e700d37 796a3088bbf6
7a2a8dca0308 7d89b23f5c03 7d90a8eaeff3 7dfb5a321855 7e1696f04558 7e475b82a05d 7e5af35a3dbc 7f4e4a126037 7fd6cab41e04 8063235ade92
80d36e067792 83abe0e9a389 83b3a7fa8b4c 84c72df0187c 84da74fe903b 8566acf1a15a 85b9b11d26f7 85e354bd92a4 8621196a70a5 8706d2546fea
870c5f301240 8a6f086a2179 8acf7f5ddf4b 8ad78293071e 8ba371cc03df 8bbc50b8da25 8bfa0e895865 8da0070eac40 8daeeddbcaf4 8e82471a48c5
8e9c8ae6cb74 8eefc6d328c4 8f7cd4405915 900bb74dd771 90774b7e2e9f 909f99cbe059 91acb948f0a3 927f7f974a9c 92d4d8202db1 93fbcb3612ec
94a34e3e3567 95dd5c8c78c7 95f7c6285d20 97ec9dc62c79 988411d119e6 98f42a346cca 9998230a4980 99c437a87e40 9af6ca36a4c8 9c7fc28bfc74
9e0626012f92 9e1a4b1cbc46 9e39990a9f9e 9e426f139ec6 9e90fc042047 9f3972024e89 9f844f75c558 a001195dad44 a10eec320486 a1b0f578eeec
a3706d2f83c7 a37792ce9d23 a3e964fe4f83 a48bf3cbea07 a543e70ef990 a5447517b979 a56fe5b9bfd6 a6737493160b a6eced715119 a74dab719c29
a7faae2b058c a8b20a2be61c a94c3a41b418 a97c1af09680 a992b2151848 aaca19651624 abbbf5b88a40 ac6dc0fccdfb ad434c18ea43 ad7e4e12c1df
ae3fb13fdcb7 aee3a8927e34 afcce98798b5 b08ae86351f2 b14c47ef7645 b2639a923ee8 b2a1a93decb6 b2d71380ad12 b357f95306e7 b4b3562aae2a
b4d5d8408557 b4e3b86b491e b539bf2cb4d8 b5aeb013fe7f b61b71c86a0e b66a6f98e502 b905248c3646 b97ebaa0f2fd b993f3a4b13e b9fd8f353c4a
bae4b6b34434 bd6aeceb13c7 be772540067a bf45a48f3c1f bf906e277b82 bfe10e3b7d9c bfebf62f52b7 c04cf74c1fe4 c20812b86904 c2e7027c517d
c39580d9f195 c50da6f536e8 c58c6739dcc7 c5c88fc8dd00 c6b110f5004b c77384aebec1 ca39660f48eb ca493e950134 cadc1f62f8b0 cb63e7f3e89b
cb9553e0100b cbc1a05b72f2 cc86f1f7cc13 cf4c250cea47 cffc2de1ad8a d00035300155 d00b17c31986 d0383526853a d0451b632cfd d072a2c2d498
d0975451825f d0d7a5397ac7 d1808274b6ff d184816f3cda d1c28ae36236 d44bb4571b8b d44d1666c996 d487365910a6 d5bfa192280f d5cdd6dc6e95
d5d99abef498 d68532379119 d6cfe3c6628c d7b6926fe321 d7e08cc814b5 d82305ae0233 d87609e59e92 d89e2fcfb7a9 d94415152228 d95f5b3df773
da1bf4ce622d da66f7b59df0 daf34c0d3800 db1bfeebd1ff db4fd0cde7cc dbee3c9eaaaf dd303d78050c dd34e815a554 ddfafb7d456b de10e5af15ae
de85d2459bea df2402ef6ef6 e08de6c9d8a8 e0cf05a1adcb e0e6b0fd961b e28f12bf1639 e2e8ebca8fb6 e2f340530345 e33f11761733 e385b186d5fb
e5707442c621 e5967ff6478a e67e410dc024 e690f07ac52b e6da2740aca3 e793dd650fbf e7b997913f66 e97ae1526e86 e9a42b840946 ea6deda2aea3
eaa0fe09b0b7 eb08e956fb2f eb47c83307e0 eb51f46f8e42 eb538ad2b351 eb8840e06911 ebd64ba08d84 ec304622f424 ed6738abddad ed6bab2b6e6b
ef1d19f08072 ef67a4b7ba16 efccc9e450b0 f0f8f06f5abf f17600224c06 f19142119cc7 f2fb78461e27 f44a1193c649 f45f402b7009 f50bf292cb16
f5c5231bf63c f668b662a621 f7603ef9a0d6 f8271eff489a f87754dd139e f8bb63efed50 f8c7a754c990 fbd46a1a8734 fc0506728bc5 fc1c2c6951af
fc35103d28d0 fdcb9be29b5b fdd4242fa288 fe71ca3af23d fe905b7065b3 fec46ee63fce fef05dbbfbc8 ff76fe12c18b
""".split())   # 2026-10-29 清单 438 条键的 sha256 前 12 位：清单里出现不在这里的键就报错（删 1 加 1 也拦）
RAW_SOURCE_OK = {  # 除 原音音轨.py 外，出现 source='原音' 写法的文件：理由（只许减少）
    '.github/check-audio-cert.py': '自检里造的假条目（临时目录），验证“自己写 source=原音”会被拒绝',
    'tools/tts/合格证.py': '只在说明文字里提到 source=原音 的规则（读这个字段，不写）',
}
if CI is False:
    import os
    CI = os.environ.get('GITHUB_ACTIONS') == 'true'     # GitHub 自检不检出 MP3：只核 JSON

TTS_RE = re.compile(r'\.synth\(|kokoro|supertonic|OfflineTts|\bpiper\b|edge_tts|edge-tts|\bgtts\b|gTTS|pyttsx3|espeak|qwen\w*tts|\bTTS\(|\.tts\(|'
                    r'create_speech|text_to_speech|\.synthesize\(|\.generate_audio\(', re.I)
MP3_RE = re.compile(r'encode_mp3\(|write_mp3\(|write_wav\(|lameenc|libmp3lame|render_passage\(|save_checked\(')
WAV_RE = re.compile(r'(?:\bsf|soundfile|wavfile)\.write\(\s*(?!buf\b|io\.)|wave\.open\([^)]*[\'"]wb?[\'"]')
AEXT = r'\.(?:mp3|m4a|aac|wav|ogg|opus|flac)\b'
FF_AUDIO = re.compile(r'-c:a\b|-acodec\b|-codec:a\b|-b:a\b|-q:a\b|libmp3lame')
AUDIO_MODS = ('soundfile', 'scipy.io.wavfile', 'wave', 'pydub', 'torchaudio', 'gtts', 'edge_tts', 'lameenc', 'pyttsx3', 'piper')


def video_entry(s):
    return 'ffmpeg' in s and re.search(r'\.mp4\b', s) and re.search(r'-c:v\b|libx264|-vcodec\b|libx265', s)


def ffmpeg_audio(s):
    return 'ffmpeg' in s and re.search(AEXT, s) and FF_AUDIO.search(s) and not video_entry(s)


def parse(s):
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            return ast.parse(s)
    except SyntaxError:
        return None


def calls(node):
    """node 里真正调用的函数名（Name 或 属性名；注释、字符串不算）。"""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, (ast.IfExp, ast.BoolOp, ast.Subscript)):      # (write_wav if … else write_mp3)(…)
                out |= {x.id for x in ast.walk(f) if isinstance(x, ast.Name)} | {x.attr for x in ast.walk(f) if isinstance(x, ast.Attribute)}
            out.add(f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else '')
    return out


def ast_audio(tree):
    """AST 认别名：import soundfile as snd → snd.write(…)；from soundfile import write → write(…)；pydub / torchaudio / gTTS / edge_tts 等一导入就算。"""
    alias, fn = {}, set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name in AUDIO_MODS or a.name.split('.')[0] in ('pydub', 'torchaudio', 'gtts', 'edge_tts', 'pyttsx3', 'piper'):
                    if a.name.split('.')[0] in ('pydub', 'torchaudio', 'gtts', 'edge_tts', 'pyttsx3', 'piper', 'lameenc'):
                        return True
                    alias[a.asname or a.name] = a.name
        elif isinstance(n, ast.ImportFrom) and n.module:
            m = n.module
            if m.split('.')[0] in ('pydub', 'torchaudio', 'gtts', 'edge_tts', 'pyttsx3', 'piper', 'lameenc'):
                return True
            for a in n.names:
                if m in ('soundfile', 'scipy.io.wavfile') and a.name == 'write':
                    fn.add(a.asname or a.name)
                if m == 'scipy.io' and a.name == 'wavfile':
                    alias[a.asname or 'wavfile'] = 'scipy.io.wavfile'
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        first = n.args[0] if n.args else None
        to_mem = isinstance(first, ast.Name) and 'buf' in first.id.lower() or (
            isinstance(first, ast.Call) and getattr(first.func, 'attr', getattr(first.func, 'id', '')) == 'BytesIO')
        if isinstance(f, ast.Name) and f.id in fn and not to_mem:
            return True
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in alias:
            m = alias[f.value.id]
            if m in ('soundfile', 'scipy.io.wavfile') and f.attr == 'write' and not to_mem:
                return True
            if m == 'wave' and f.attr == 'open' and any(isinstance(x, ast.Constant) and str(x.value).startswith('w') for x in n.args[1:]):
                return True
        if isinstance(f, ast.Attribute) and f.attr in ('export', 'save') and isinstance(f.value, ast.Name) and f.value.id in ('torchaudio', 'tts', 'sound', 'seg', 'audio'):
            return True
    return False


def is_audio_entry(f, s, tree):
    if TTS_RE.search(s) or MP3_RE.search(s) or WAV_RE.search(s) or ffmpeg_audio(s):
        return True
    return bool(tree is not None and ast_audio(tree))


def wired(tree):
    """真的调用（AST）：共用的 render_passage / save_checked（segment + 检查 + 合格证），或自己同时调 segment 与检查。"""
    if tree is None:
        return False
    c = calls(tree)
    return bool({'render_passage', 'save_checked'} & c or ('segment' in c and {'verify_loudness', 'fine_check', 'final_check', '_VERIFY_CORE'} & c))


def module_consts(tree):
    out = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            v = n.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                out[n.targets[0].id] = [v.value]
            elif isinstance(v, (ast.Tuple, ast.List)) and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in v.elts):
                out[n.targets[0].id] = [e.value for e in v.elts]
    return out


def filter_strings(node, consts):
    """过滤条件里用到的字符串（常量 + 模块级常量名）；RAW and … 里的不算（专八原音模式的例外）。"""
    out = []

    def walk(n):
        if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.And) and isinstance(n.values[0], ast.Name) and n.values[0].id == 'RAW':
            return
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.append(n.value)
        elif isinstance(n, ast.Name) and n.id in consts:
            out.extend(consts[n.id])
        for c in ast.iter_child_nodes(n):
            walk(c)
    walk(node)
    return out


def check_calls(f, tree):
    """视频引擎调用 verify_videos.check 的地方：过滤条件不许滤掉合格证 / 响度；结果必须汇总成失败列表、不许清空。"""
    errs = []
    names = {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == 'verify_videos'
             for a in n.names if a.name == 'check'}
    if not names:
        return errs
    consts = module_consts(tree)
    parent = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    for n in ast.walk(tree):
        if not isinstance(n, (ast.ListComp, ast.GeneratorExp, ast.SetComp)):
            continue
        g = [g for g in n.generators if isinstance(g.iter, ast.Call) and isinstance(g.iter.func, ast.Name) and g.iter.func.id in names]
        if not g:
            continue
        for s in [x for gg in g for c in gg.ifs for x in filter_strings(c, consts)]:
            hit = [P for P in PROTECTED if P.startswith(s) or (s and s in P and len(s) >= 2)]
            if hit:
                errs.append(f'{f}：verify_videos.check 的结果被过滤掉了“{hit[0]}”（过滤串 {s!r}；合格证与响度检查不许滤掉，踩坑 87）')
        a = parent.get(n)
        if not (isinstance(a, ast.Assign) and len(a.targets) == 1 and isinstance(a.targets[0], ast.Name)):
            errs.append(f'{f}：verify_videos.check 的结果没有存进一个变量（无法确认被汇总成失败列表）')
            continue
        res = a.targets[0].id
        fn = a
        while fn in parent and not isinstance(fn, (ast.FunctionDef, ast.Module)):
            fn = parent[fn]
        fails, bad = set(), []
        t = g[0].target
        if isinstance(t, ast.Tuple) and len(t.elts) > 1 and isinstance(t.elts[1], ast.Name) and any(
                isinstance(x, ast.UnaryOp) and isinstance(x.op, ast.Not) and isinstance(x.operand, ast.Name) and x.operand.id == t.elts[1].id
                for c in g[0].ifs for x in ast.walk(c)):
            fails.add(res)                       # 推导式本身就只留不通过的（tools/video/make_video.py）
        for m in ast.walk(fn):
            if isinstance(m, (ast.ListComp, ast.GeneratorExp)) and any(isinstance(x.iter, ast.Name) and x.iter.id == res and x.ifs for x in m.generators):
                p = parent.get(m)
                if isinstance(p, ast.Assign) and len(p.targets) == 1 and isinstance(p.targets[0], ast.Name):
                    fails.add(p.targets[0].id)
            if isinstance(m, ast.Call) and getattr(m.func, 'id', '') == 'all' and res in {x.id for x in ast.walk(m) if isinstance(x, ast.Name)}:
                fails.add('<all>')
        if not fails:
            errs.append(f'{f}：verify_videos.check 的结果（{res}）没有汇总成失败列表（不通过也不会删成品）')
        for m in ast.walk(fn):
            if isinstance(m, ast.Assign) and m is not a:
                tg = {t.id for t in m.targets if isinstance(t, ast.Name)}
                if res in tg:
                    bad.append(f'{res} 被重新赋值')
                if tg & (fails - {res}) and not (isinstance(m.value, (ast.ListComp, ast.GeneratorExp)) and any(
                        isinstance(x.iter, ast.Name) and x.iter.id == res for x in m.value.generators)):
                    bad.append(f'失败列表 {sorted(tg & fails)[0]} 被改成别的（如 []）')
        errs += [f'{f}：{b}（verify_videos.check 的结论被绕过，踩坑 87）' for b in bad]
    return errs


SRC_RE = re.compile(r'''['"]source['"]\s*(?::|\]\s*=)\s*['"]原音|\bsource\s*=\s*['"]原音|['"]source['"]\s*,\s*['"]原音''')


_BASE = None
_PARSED = {}


def files(over):
    global _BASE
    if _BASE is None or over is None:
        _BASE = _read_all()
    out, errs = dict(_BASE[0]), list(_BASE[1])
    out.update(over or {})
    return out, errs


def _read_all():
    out, errs = {}, []
    for p in [*R.rglob('*.py'), *R.rglob('*.sh')]:
        rel = p.relative_to(R).as_posix()
        if any(rel.startswith(d) for d in SKIP_DIRS) or '/.git/' in rel or rel.startswith('.git/'):
            continue
        try:
            out[rel] = p.read_text('utf-8')
        except UnicodeDecodeError:
            errs.append(f'{rel}：不是 UTF-8（读不了就查不了，踩坑 87：GBK 文件曾被跳过），改成 UTF-8')
        except OSError:
            continue
    return out, errs


def load_cac():
    spec = importlib.util.spec_from_file_location('check_audio_cert', R / '.github' / 'check-audio-cert.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def product_check(root=R, ci=None):
    """按产物查：所有 audio 目录下的 timings.json 每一条都合格（check-audio-cert 的同一套），原音条目只许在专八听力原文。"""
    ci = CI if ci is None else ci
    cac = load_cac()
    errs = []
    tps = sorted(p for p in Path(root).rglob('timings.json') if 'audio' in p.relative_to(root).parts[:-1]
                 and not any(p.relative_to(root).as_posix().startswith(d) for d in SKIP_DIRS + ('.git/',)))
    for tp in tps:
        d = tp.parent
        while d.name != 'audio':
            d = d.parent
        errs += cac.check_dir(d, ci)
        rel = d.relative_to(root).as_posix()
        for v, pid, tm in CERT.timings_entries(json.loads(tp.read_text('utf-8'))):
            if tm.get('source') == '原音' and rel != '专八/听力/原文/audio':
                errs.append(f'{rel}/{v}/{pid}：只有专八听力原文的 timings 能有 source=原音')
    return errs, len(tps)


def legacy_problems(leg):
    errs = []
    if leg['count'] > LEGACY_MAX or len(leg['keys']) > LEGACY_MAX:
        errs.append(f"响度旧成品清单 {len(leg['keys'])} 条，超过 2026-10-29 的界线 {LEGACY_MAX} 条（只许减少：新音频必须带合格证）")
    new = [k for k in leg['keys'] if hashlib.sha256(k.encode()).hexdigest()[:12] not in LEGACY_FROZEN]
    if new:
        errs.append(f'响度旧成品清单里有 2026-10-29 冻结时没有的键 {len(new)} 条（只许减少，删一条加一条也不行）：{new[:2]}')
    return errs


_PER = {}


def per_file(f, s, tree):
    """一个文件自己的问题（按 文件名 + 内容 缓存）：返回 (是音频入口, 是视频入口, 问题列表)。"""
    key = (f, hash(s))
    if key in _PER:
        return _PER[key]
    errs = []
    is_a = is_audio_entry(f, s, tree)
    is_v = bool(video_entry(s))
    if is_a and f not in EXEMPT:
        if f.endswith('.py') and tree is None:
            errs.append(f'{f}：Python 语法错误，无法检查')
        elif f == 'tools/tts/gaokao_tts.py':
            for fd in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
                c = calls(fd)
                writes = {'write_mp3', 'write_wav'} & c or ('write_bytes' in c and 'mp3' in ast.unparse(fd))
                if writes and fd.name not in GT_WRITE_EXEMPT and not {'final_check', 'verify_loudness', '_VERIFY_CORE'} & c:
                    errs.append(f'{f}：{fd.name} 写音频文件却没调 final_check / verify_loudness（踩坑 87：say 曾直接写文件）')
        elif not wired(tree):
            errs.append(f'{f}：会合成或写出音频，却没接意群级处理与检查（render_passage / save_checked，或 segment + verify_loudness）')
        if '.synth(' in s and 'segment(' not in s:
            errs.append(f'{f}：直接合成却没经过 segment（意群级电平统一）')
        if re.search(r'fade\((G\.)?level\(', s):
            errs.append(f'{f}：还在用 fade(level(…)) 旁路，没走 segment')
    if tree is not None:
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and getattr(n.func, 'attr', getattr(n.func, 'id', '')) in ('verify_loudness', '_VERIFY_CORE', '_verify'):
                vals = [k.value for k in n.keywords if k.arg == 'fine'] + n.args[4:5]
                for v in vals:
                    okv = (isinstance(v, ast.Constant) and v.value is True) or (
                        isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.Not) and isinstance(v.operand, ast.Call)
                        and getattr(v.operand.func, 'id', getattr(v.operand.func, 'attr', '')) == 'is_legacy')
                    if not okv:
                        errs.append(f'{f}：给 verify_loudness 传了 fine={ast.unparse(v)}（只能是 True 或 not is_legacy(…)，不许关掉意群检查）')
            if f != 'tools/tts/gaokao_tts.py' and isinstance(n, (ast.Assign, ast.AugAssign)):
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    if isinstance(t, ast.Attribute) and t.attr in GUARDED:
                        errs.append(f'{f}：重新赋值了 {ast.unparse(t)}（合格证 / 最终检查不许被替换，踩坑 87）')
    if f != CERT.RAW_WRITER and f not in RAW_SOURCE_OK and SRC_RE.search(s):
        errs.append(f'{f}：写了 source=原音（只有 {CERT.RAW_WRITER} 能写，自己声明原音就能逃过合格证，踩坑 87）')
    if is_v and f not in VIDEO_EXEMPT:
        if f.endswith('.sh') or tree is None:
            errs.append(f'{f}：用 ffmpeg 出视频的脚本必须是 Python 并接上 verify_videos.check / certificate_problems（或登记 VIDEO_EXEMPT）')
        else:
            c = calls(tree)
            vv = {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == 'verify_videos' for a in n.names if a.name == 'check'}
            if not ({'certificate_problems', 'cert_check'} & c or vv & c):
                errs.append(f'{f}：生成视频却既没在生成前核对音频合格证（certificate_problems），也没在生成后跑 verify_videos.check')
            errs += check_calls(f, tree)
    _PER[key] = (is_a, is_v, errs)
    return _PER[key]


def check(over=None, product=True):
    F, errs = files(over or {})
    T = {}
    for f, s in F.items():
        if f.endswith('.py'):
            key = (f, hash(s))
            if key not in _PARSED:
                _PARSED[key] = parse(s)
            T[f] = _PARSED[key]
        else:
            T[f] = None
    audio, engines = [], []
    for f, s in F.items():
        is_a, is_v, e = per_file(f, s, T[f])
        audio += [f] if is_a else []
        engines += [f] if is_v else []
        errs += e
    for f in EXEMPT:
        if f not in F:
            errs.append(f'豁免名单里的 {f} 已不存在：从 EXEMPT 删掉（豁免只许减少）')
    for f in RAW_SOURCE_OK:
        if f not in F or not SRC_RE.search(F[f]):
            errs.append(f'RAW_SOURCE_OK 里的 {f} 已不再写 source=原音：删掉（只许减少）')
    for f in VIDEO_EXEMPT:
        if f not in F:
            errs.append(f'视频豁免名单里的 {f} 已不存在：删掉（只许减少）')
    g = F.get('tools/tts/gaokao_tts.py', '')
    seg = re.search(r'def segment\(x\):(.*?)\n\n\n', g, re.S)
    if not seg or 'even(' not in seg.group(1) or 'level_clause(' not in seg.group(1):
        errs.append('gaokao_tts.segment 没有同时做 even 与 level_clause')
    if not re.search(r'def verify_loudness\([^)]*fine=True', g):
        errs.append('gaokao_tts.verify_loudness 的意群检查不是默认打开')
    if not re.search(r'^_VERIFY_CORE = verify_loudness\b', g, re.M):
        errs.append('gaokao_tts 没在模块加载时存下原始检查 _VERIFY_CORE')
    gt = T.get('tools/tts/gaokao_tts.py')
    rp = next((n for n in (gt.body if gt else []) if isinstance(n, ast.FunctionDef) and n.name == 'render_passage'), None)
    if not rp or not {'certificate', 'final_check'} <= calls(rp) or "'clause_check': CHAIN" not in ast.get_source_segment(g, rp):
        errs.append('gaokao_tts.render_passage 没用 final_check 检查、没写合格证 / clause_check')
    fc = next((n for n in (gt.body if gt else []) if isinstance(n, ast.FunctionDef) and n.name == 'final_check'), None)
    if not fc or '_VERIFY_CORE(' not in ast.get_source_segment(g, fc) or 'fine=True' not in ast.get_source_segment(g, fc):
        errs.append('gaokao_tts.final_check 没用 _VERIFY_CORE(…, fine=True) 再测一遍')
    v = F.get('tools/video/verify_videos.py', '')
    if 'cp = cert_check(mp4, tm, mp3_path)' not in v or 'fine=not is_legacy(tm)' not in v or 'certificate_problems(tm, c)' not in v:
        errs.append('verify_videos 没核对合格证（含旁证、sha256）或没开意群检查')
    leg = json.loads(F.get('tools/tts/响度旧成品清单.json') or (R / 'tools/tts/响度旧成品清单.json').read_text('utf-8'))
    errs += legacy_problems(leg)
    if product:
        errs += product_check()[0]
    return errs, len(audio), len(engines)


def main():
    bad = []

    def case(name, errs, want):
        ok = (not errs) if want is None else any(want in e for e in errs)
        print(f"  {'✅' if ok else '❌'} {name}：{errs[:2] or '0 处'}")
        if not ok:
            bad.append(name)

    def only(key, over):
        return [e for e in check(over, product=False)[0] if key in e]

    errs, na, ne = check()
    print(f'入口：音频 {na} 个（豁免 {len(EXEMPT)}），视频引擎 {ne} 个（豁免 {len(VIDEO_EXEMPT)}）；GitHub 模式：{CI}')
    case('现在 → 0', errs, None)
    rd = lambda k: (R / k).read_text('utf-8')
    k = '考研/tools/make_audio.py'
    case('考研 make_audio 改回 fade(level(…)) → 报出', only('', {k: rd(k).replace(
        'G.segment(engine.synth(pron.phonemes(x, key), style, speed))', 'G.fade(G.level(engine.synth(pron.phonemes(x, key), style, speed)))').replace('G.segment(', 'G.fade(G.level(')}), 'fade(level')
    N = '新项目/tools/'
    case('新项目复制旧脚本、没走 segment → 报出', only(N, {N + 'make_audio.py': 'seg = G.level(engine.synth(ph, style, 1.0))\nG.render_passage(p)\n'}), N)
    new = {
        'piper 写 WAV': 'import piper, soundfile as sf\nv = piper.PiperVoice.load(m)\nsf.write(out / "a.wav", v.synthesize(t), 22050)\n',
        'ffmpeg -c:a libmp3lame 出 MP3': 'import subprocess\nsubprocess.run(["ffmpeg", "-i", w, "-c:a", "libmp3lame", str(out) + ".mp3"])\n',
        'ffmpeg -b:a 出 MP3（不写编码器）': 'import subprocess\nsubprocess.run(["ffmpeg", "-i", w, "-b:a", "128k", "o.mp3"])\n',
        'ffmpeg -q:a 出 MP3': 'import subprocess\nsubprocess.run(["ffmpeg", "-i", w, "-q:a", "2", "o.mp3"])\n',
        'ffmpeg -c:a aac 出 .m4a': 'import subprocess\nsubprocess.run(["ffmpeg", "-i", w, "-c:a", "aac", "o.m4a"])\n',
        'import soundfile as snd': 'import soundfile as snd\nsnd.write(out, x, 24000)\n',
        'from soundfile import write': 'from soundfile import write as w2\nw2(out, x, 24000)\n',
        'from scipy.io import wavfile as wf': 'from scipy.io import wavfile as wf\nwf.write(out, 24000, x)\n',
        'pydub export': 'from pydub import AudioSegment\nAudioSegment.from_wav(a).export("o.mp3", format="mp3")\n',
        'torchaudio.save': 'import torchaudio\ntorchaudio.save("o.wav", x, 24000)\n',
        'gTTS': 'from gtts import gTTS\ngTTS("hi").save("o.mp3")\n',
        'wave.open 写': 'import wave\nw = wave.open(str(out), "wb")\n',
        '只在注释里写 render_passage(': '# 以后接 render_passage(\nimport soundfile as sf\nsf.write(out, x, 24000)\n',
    }
    for nm, src in new.items():
        case(f'新入口（{nm}）不接检查 → 报出', only('朗读.py', {N + '朗读.py': src}), '没接意群级')
    case('edge-tts 写在 .sh 里 → 报出', only('朗读.sh', {N + '朗读.sh': 'edge-tts --text "$t" --write-media o.mp3\n'}), '朗读.sh')
    case('GBK 编码的文件 → 报出（不许跳过）', check_gbk(), '不是 UTF-8')
    files(None)                                   # 删掉临时文件后重读
    case('新入口接上 segment + verify_loudness → 不报', only('朗读2', {N + '朗读2.py':
        'import piper\nx = G.segment(v.synthesize(t))\nrep, errs = G.verify_loudness(mp3, items, -16.0)\nG.write_mp3(o, x)\n'}), None)
    case('只写进内存缓冲区（核查用）→ 不算入口', only('核查.py', {N + '核查.py': 'import io, soundfile as sf\nbuf = io.BytesIO()\nsf.write(buf, x, sr, format="WAV")\n'}), None)
    for nm, fv in (('False', 'False'), ('0', '0'), ('x and False', 'x and False')):
        case(f'有人传 fine={nm} → 报出', only('x.py', {'中考/tools/x.py': f'verify_loudness(mp3, items, -16.0, fine={fv})\n'}), 'fine=')
    case('别处把 G._VERIFY_CORE 换掉 → 报出', only('y.py', {'中考/tools/y.py': 'G._VERIFY_CORE = lambda *a, **k: ({}, [])\n'}), '重新赋值')
    case('别处把 G.final_check 换掉 → 报出', only('y.py', {'中考/tools/y.py': 'G.final_check = lambda *a, **k: ({}, [])\n'}), '重新赋值')
    g = rd('tools/tts/gaokao_tts.py')
    case('segment 去掉 even → 报出', only('even', {'tools/tts/gaokao_tts.py': g.replace('return fade(level_clause(even(x)))', 'return fade(level_clause(x))')}), 'even')
    say_old = g.replace("    save_checked(out, a, items, vcfg.get('lufs', -16.0))\n", "    (write_wav if out.suffix.lower() == '.wav' else write_mp3)(out, a)\n")
    assert say_old != g
    case('gaokao_tts say 改回直接写文件（不检查、不写合格证）→ 报出', only('cmd_say', {'tools/tts/gaokao_tts.py': say_old}), 'cmd_say')
    case('final_check 不再用 _VERIFY_CORE 再测 → 报出', only('final_check', {'tools/tts/gaokao_tts.py': g.replace(
        'core, cerrs = _VERIFY_CORE(mp3_bytes, items, target_lufs, fine=True, **kw)', 'core, cerrs = {}, []')}), 'final_check')
    v = rd('tools/video/verify_videos.py')
    case('verify_videos 去掉合格证核对 → 报出', only('verify_videos', {'tools/video/verify_videos.py': v.replace('cp = cert_check(mp4, tm, mp3_path)', 'cp = []')}), 'verify_videos')
    zk = '中考/tools/make_video.py'
    m = rd(zk)
    case('中考视频引擎去掉生成后核查（verify_videos.check）→ 报出', only(zk, {zk: m.replace('from verify_videos import check', 'check = None')}), zk)
    f0 = "if not r[0].startswith('文件名')"
    assert f0 in m
    case('中考：check 结果里滤掉“音频合格证” → 报出', only(zk, {zk: m.replace(f0, "if not r[0].startswith(('文件名', '音频合格证'))")}), '音频合格证')
    case('中考：check 结果里滤掉“响度” → 报出', only(zk, {zk: m.replace(f0, f0 + " and not r[0].startswith('响度')")}), '过滤掉了')
    case('中考：check 结果里用 in 滤掉合格证 → 报出', only(zk, {zk: m.replace(f0, f0 + " and '合格证' not in r[0]")}), '音频合格证')
    fl = "fails = [f'{n}：{d}' for n, c, d in res if not c]"
    assert fl in m
    case('中考：失败列表改成 [] → 报出', only(zk, {zk: m.replace(fl, 'fails = []')}), zk)
    case('中考：失败列表推导后再清空 → 报出', only(zk, {zk: m.replace(fl, fl + '\n    fails = []')}), '被改成别的')
    z8 = '专八/tools/make_video.py'
    m8 = rd(z8)
    assert 'and not (RAW and r[0].startswith(RAW_SKIP))' in m8
    case('专八：RAW_SKIP 只在 RAW 模式 → 不报（现在）', only(z8, {}), None)
    case('专八：RAW_SKIP 去掉 RAW 条件（任何模式都滤掉响度）→ 报出', only(z8, {z8: m8.replace('and not (RAW and r[0].startswith(RAW_SKIP))', 'and not r[0].startswith(RAW_SKIP)')}), '响度一致')
    case('新视频引擎（大字版2.py）只按内容发现、不接核查 → 报出', only('大字版2', {'专八/tools/大字版2.py':
        'import subprocess\nsubprocess.run(["ffmpeg", "-i", a, "-c:v", "libx264", "o.mp4"])\n'}), '大字版2')
    xv = '六级/tools/宣传视频.py'
    case('六级宣传视频去掉合格证核对 → 报出', only(xv, {xv: rd(xv).replace('certificate_problems(', 'list(')}), xv)
    case('别处自己写 source=原音 → 报出', only('z.py', {'中考/tools/z.py': "tm = {'file': 'a.mp3', 'source': '原音'}\n"}), '原音')
    case('别处 tm["source"] = "原音" → 报出', only('z.py', {'中考/tools/z.py': 'tm["source"] = "原音"\n'}), '原音')
    leg = json.loads(rd('tools/tts/响度旧成品清单.json'))
    leg2 = dict(leg, keys=leg['keys'] + ['新音频.mp3|1|2|3|4'], count=leg['count'] + 1)
    case('往旧成品清单里塞新音频 → 报出', only('旧成品清单', {'tools/tts/响度旧成品清单.json': json.dumps(leg2)}), '旧成品清单')
    leg3 = dict(leg, keys=leg['keys'][1:] + ['新音频.mp3|1|2|3|4'])
    case('旧成品清单删 1 条加 1 条（条数不变）→ 报出', only('旧成品清单', {'tools/tts/响度旧成品清单.json': json.dumps(leg3)}), '冻结')
    case('旧成品清单只删不加 → 不报', only('旧成品清单', {'tools/tts/响度旧成品清单.json': json.dumps(dict(leg, keys=leg['keys'][1:], count=leg['count'] - 1))}), None)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / '新项目' / 'audio').mkdir(parents=True)
        tm = {'file': 'cet4_male/a.mp3', 'duration': 3.0, 'loudness': {}, 'sentences': []}
        (root / '新项目' / 'audio' / 'timings.json').write_text(json.dumps({'cet4_male': {'a01': tm}}), 'utf-8')
        case('按产物查：新音频没有合格证 → 报出', product_check(root, ci=True)[0], '不是当前处理链')
        (root / '新项目' / 'audio' / 'timings.json').write_text(json.dumps({'cet4_male': {'a01': dict(
            tm, file='原音/a.mp3', source='原音', compressed_gaps=[], sentences=[{'orig': [0, 1]}])}}), 'utf-8')
        case('按产物查：别的项目 timings 写 source=原音 → 报出', product_check(root, ci=True)[0], 'source=原音')
    if bad:
        sys.exit(f'意群响度入口双向验证失效：{bad}')
    print('意群响度入口双向验证：全部通过')


def check_gbk():
    """GBK 文件：真的写一个到仓库里的临时目录，跑 files()，再删掉。"""
    d = R / '_入口自检临时'
    d.mkdir(exist_ok=True)
    try:
        (d / 'gbk.py').write_bytes('import soundfile as sf\nsf.write("朗读.wav", x, 24000)\n'.encode('gbk'))
        return files(None)[1]
    finally:
        (d / 'gbk.py').unlink()
        d.rmdir()


if __name__ == '__main__':
    main()
