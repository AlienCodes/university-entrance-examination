"""只为ASR漏掉的短应声找孤立声学岛；不产生该词的伪词时刻。"""
from pathlib import Path
import hashlib
import subprocess

FILLERS = {'ah', 'oh', 'eh', 'mm', 'mmm', 'hmm', 'um', 'umm', 'urmm', 'uh', 'er', 'yeah', 'yes', 'no', 'okay', 'ok', 'right', 'well', 'emm'}
VERIFIED = set()


def clip(prep, root, lo, hi):
    import numpy as np
    pieces = []
    for part in prep['source_entries']:
        a = max(lo, part.get('canonical_start', 0.))
        z = min(hi, part.get('canonical_end', prep['canonical']['duration']))
        if a >= z:
            continue
        path = Path(root) / part['file']
        key = (str(path), part['sha256'])
        if key not in VERIFIED:
            with path.open('rb') as f:
                assert hashlib.file_digest(f, 'sha256').hexdigest() == part['sha256']
            VERIFIED.add(key)
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(a - part.get('canonical_start', 0.)),
            '-t', str(z - a), '-i', str(path), '-f', 'f32le', '-ac', '1', '-ar', '16000', '-'])
        pieces.append(np.frombuffer(raw, dtype='<f4'))
    if not pieces:
        return None
    audio = np.concatenate(pieces)
    assert abs(len(audio) / 16000 - (hi - lo)) < .15
    return audio


def isolated_island(prep, root, left, right):
    import numpy as np
    # 整段太长时不能凭一个响声猜是哪一个应声；太短则缺少两侧静段证据。
    if not .22 <= right - left <= 4.:
        return None
    audio = clip(prep, root, left, right)
    if audio is None:
        return None
    hop = 160
    n = len(audio) // hop
    energy = 10 * np.log10((audio[:n * hop].reshape(n, hop).astype('float64') ** 2).mean(1) + 1e-12)
    noise = float(np.percentile(energy, 15))
    threshold = max(-50., min(-25., noise + 12.))
    active = energy > threshold
    # 最多填30ms的岛内短间隔，不能跨越真实词间停顿。
    changes = np.flatnonzero(np.diff(np.r_[True, active, True].astype('int8')))
    for a, z in zip(changes[::2], changes[1::2]):
        if a > 0 and z < n and z - a <= 3:
            active[a:z] = True
    changes = np.flatnonzero(np.diff(np.r_[False, active, False].astype('int8')))
    candidates = [(int(a), int(z)) for a, z in zip(changes[::2], changes[1::2])
                  if .06 <= (z - a) / 100 <= 1.2 and a >= 8 and n - z >= 8]
    if len(candidates) != 1:
        return None
    a, z = candidates[0]
    # 两边均须有至少80ms低电平帧；相邻词的尾音不能冒充孤立应声。
    if active[a-8:a].any() or active[z:z+8].any():
        return None
    return {'speech_island': [round(left + a / 100, 6), round(left + z / 100, 6)],
            'sentence_boundary': [round(left + max(0, a - 2) / 100, 6), round(left + min(n, z + 2) / 100, 6)],
            'ASR_bracket': [left, right], 'frame_seconds': .01, 'threshold_dBFS': round(threshold, 3),
            'noise_percentile_15_dBFS': round(noise, 3), 'proof': '唯一60—1200ms声学岛，两边各至少80ms低电平；源文件SHA已复核。',
            'status': 'machine_acoustic_candidate; not_word_timestamps; human_review_required'}


def resolve(result, prep, source_root):
    rows, src = result['rows'], result['source']
    proofs = []
    for i, row in enumerate(rows):
        if row['boundary_anchored'] or not row['missing']:
            continue
        missing = row['missing']
        if not all(src[j].text.lower() in FILLERS for j in missing):
            continue
        # 只有紧邻的句子可作为两侧锚；不跨别的缺句寻找方便的空隙。
        previous = rows[i-1] if i and rows[i-1]['unit'] == row['unit'] else None
        following = rows[i+1] if i+1 < len(rows) and rows[i+1]['unit'] == row['unit'] else None
        matched = row['word_alignment']
        first, last = row['lexemes'][0], row['lexemes'][-1]
        need_start, need_end = first in missing, last in missing
        if not matched:
            if not previous or not following or not previous['anchor_window'] or not following['anchor_window']:
                continue
            left, right = previous['anchor_window'][1], following['anchor_window'][0]
        elif need_start and not need_end:
            if not previous or not previous['anchor_window']:
                continue
            left, right = previous['anchor_window'][1], matched[0]['start']
        elif need_end and not need_start:
            if not following or not following['anchor_window']:
                continue
            left, right = matched[-1]['end'], following['anchor_window'][0]
        else:
            continue
        proof = isolated_island(prep, source_root, left, right)
        if not proof:
            continue
        lo, hi = proof['sentence_boundary']
        if matched:
            lo = lo if need_start else matched[0]['start']
            hi = hi if need_end else matched[-1]['end']
        row['acoustic_boundary'] = [lo, hi]
        row['acoustic_evidence'] = {'unit': row['unit'], 'sentence': row['n'], 'source_text': row['sentence']['en'],
                                    'unanchored_filler': [src[j].text for j in missing], **proof}
        proofs.append(row['acoustic_evidence'])
    return proofs
