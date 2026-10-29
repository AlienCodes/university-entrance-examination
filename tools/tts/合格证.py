"""音频合格证的规则（踩坑 85、87；只写这一处）：处理链版本、响度上限、旧成品清单、合格证核对。
只用标准库：本机的 gaokao_tts / verify_videos、GitHub 发布前的 .github/check-audio-cert.py、防复发验证都调它，
发布工作流不用装 numpy 也能核。

合格的新音频（2026-10-29 之后生成的）必须同时满足：
  ① timings 条目 clause_check = 当前处理链，合格证 chain = 当前处理链、passed is True；
  ② 合格证的 limits 与这里的标准上限逐项相同，loudness 每一项都在上限以内（整体、句间、短时、峰值、相邻意群、段尾元音），
     timings 条目的 loudness 与合格证里的逐项相同；
  ③ MP3 旁边有合格证文件 *.loudness.json，内容与 timings 里的合格证完全相同；
  ④（有 MP3 时）MP3 的 sha256 与合格证一致（检查之后没被改过）。
旧成品（2026-10-29 前已发布，清单只许减少）与专八听力考试原声（原音音轨.py 写的条目）不追溯。"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHAIN = 'clause-v1'          # 处理链版本：段内电平统一 even + 每段 BS.1770 统一 + 意群级检查
TARGET_LUFS = -16.0
LIMITS = {'integrated': 0.7, 'sentence_dev': 2.0, 'short_term_std': 1.0, 'peak_db': -1.0}
FINE_LIMITS = {'clause_nb': 1.2, 'clause_tail': 4.0}
STD_LIMITS = dict(LIMITS, **FINE_LIMITS)
LEGACY = HERE / '响度旧成品清单.json'
RAW_WRITER = '专八/听力/原文/tools/原音音轨.py'      # 唯一允许写 source='原音' 的程序（踩坑 87）
CORE = ('integrated_lufs', 'sentence_max_dev_lu', 'short_term_std_lu', 'peak_dbfs')
FINE = ('clause_nb_min_lu', 'clause_tail_min_db')


def legacy_key(tm):
    L = tm.get('loudness') or {}
    return f"{tm.get('file')}|{tm.get('duration')}|{L.get('integrated_lufs')}|{L.get('sentence_max_dev_lu')}|{L.get('short_term_std_lu')}"


_KEYS = {}


def legacy_keys(path=LEGACY):
    path = Path(path)
    if path not in _KEYS:
        _KEYS[path] = set(json.loads(path.read_text('utf-8'))['keys']) if path.exists() else set()
    return _KEYS[path]


def is_raw(tm):
    """专八听力考试原声（不是 TTS）：只认 原音音轨.py 写出的样子——file 在 原音/ 下、有 compressed_gaps、每句都有原音对应的 orig，
    没有合格证 / clause_check。别处自己写一个 source='原音' 不算（防复发验证里静态检查只有 RAW_WRITER 能写这个字段）。"""
    S = tm.get('sentences') or []
    return (tm.get('source') == '原音' and str(tm.get('file', '')).startswith('原音/') and 'compressed_gaps' in tm
            and 'clause_check' not in tm and 'certificate' not in tm and bool(S) and all('orig' in s for s in S))


def is_legacy(tm):
    return is_raw(tm) or legacy_key(tm) in legacy_keys()


def sidecar_of(mp3_path):
    return Path(str(mp3_path)[:-4] + '.loudness.json')


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x


def cert_problems(c, tm_loud=None):
    """只看合格证本身（不看文件）：处理链、passed、上限是标准值、各测量值在上限以内、与 timings 的测量值一致。"""
    errs = []
    if not isinstance(c, dict) or c.get('chain') != CHAIN:
        return [f'音频合格证不是当前处理链 {CHAIN} 的']
    if c.get('passed') is not True:
        errs.append('音频合格证显示检查未通过')
    if c.get('limits') != STD_LIMITS:
        errs.append(f"音频合格证的上限 {c.get('limits')} 不是标准值 {STD_LIMITS}")
    sha = c.get('mp3_sha256')
    if not (isinstance(sha, str) and len(sha) == 64 and all(ch in '0123456789abcdef' for ch in sha)):
        errs.append('音频合格证没有 MP3 的 sha256')
    L = c.get('loudness') if isinstance(c.get('loudness'), dict) else {}
    miss = [k for k in CORE + FINE if not _num(L.get(k))]
    if miss:
        errs.append(f'音频合格证缺少测量值 {miss}')
    else:
        bad = []
        if abs(L['integrated_lufs'] - TARGET_LUFS) > LIMITS['integrated']:
            bad.append(f"整体 {L['integrated_lufs']} LUFS")
        if L['sentence_max_dev_lu'] > LIMITS['sentence_dev']:
            bad.append(f"句间 {L['sentence_max_dev_lu']} LU")
        if L['short_term_std_lu'] > LIMITS['short_term_std']:
            bad.append(f"短时 {L['short_term_std_lu']} LU")
        if L['peak_dbfs'] > LIMITS['peak_db']:
            bad.append(f"峰值 {L['peak_dbfs']} dBFS")
        if L['clause_nb_min_lu'] < -FINE_LIMITS['clause_nb']:
            bad.append(f"相邻意群 {L['clause_nb_min_lu']} LU")
        if L['clause_tail_min_db'] < -FINE_LIMITS['clause_tail']:
            bad.append(f"段尾元音 {L['clause_tail_min_db']} dB")
        if bad:
            errs.append('音频合格证里的测量值超标：' + '，'.join(bad))
    if tm_loud is not None and any((tm_loud or {}).get(k) != L.get(k) for k in CORE + FINE):
        errs.append('timings 里的响度测量与合格证不一致')
    return errs


def problems(tm, mp3_path=None, mp3_bytes=None, sidecar=None):
    """核对一条 timings。mp3_path：MP3 文件（旁边必须有 *.loudness.json，sha256 必须一致）；
    或者 sidecar（旁证内容）+ mp3_bytes（可无）：GitHub 上只取得到 JSON 时用。都不给时只核 timings 里的合格证。"""
    if is_legacy(tm):
        return []
    if tm.get('clause_check') != CHAIN or not isinstance(tm.get('certificate'), dict):
        return [f"音频不是当前处理链 {CHAIN} 生成的（没有意群级电平统一与检查 / 没有合格证），不许生成视频、不许发布"]
    c = tm['certificate']
    errs = cert_problems(c, tm.get('loudness'))
    if mp3_path is not None:
        side = sidecar_of(mp3_path)
        if not side.exists():
            return errs + [f'缺少合格证文件 {side.name}']
        sidecar = json.loads(side.read_text('utf-8'))
        if mp3_bytes is None and Path(mp3_path).exists():
            mp3_bytes = Path(mp3_path).read_bytes()
        if mp3_bytes is None:
            errs.append(f'找不到 MP3 {Path(mp3_path).name}，无法核对 sha256')
    if sidecar is not None and sidecar != c:
        errs.append('合格证文件与 timings 里的合格证不一致（chain / passed / 测量值 / sha256 有不同）')
    if mp3_bytes is not None and hashlib.sha256(mp3_bytes).hexdigest() != c.get('mp3_sha256'):
        errs.append('合格证与 MP3 不符（MP3 在检查之后被改过）')
    return errs


def timings_entries(T):
    """timings.json → [(音色, 篇目, 条目)]（跳过不是条目的字段）。"""
    out = []
    for v, d in (T or {}).items():
        if isinstance(d, dict):
            for pid, tm in d.items():
                if isinstance(tm, dict) and 'file' in tm:
                    out.append((v, pid, tm))
    return out
