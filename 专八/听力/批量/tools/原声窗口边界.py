"""用真实PCM低能量间隙确定单位窗口，避免ASR最后词尾估计截音。"""
import hashlib
from pathlib import Path
import subprocess
import numpy as np

VERIFIED = set()


def pcm(prep, root, lo, hi):
    pieces = []
    sr, channels = prep['canonical']['sample_rate'], prep['canonical']['channels']
    for entry in prep['source_entries']:
        origin = entry.get('canonical_start', 0.)
        a, z = max(lo, origin), min(hi, entry.get('canonical_end', prep['canonical']['duration']))
        if a >= z: continue
        path = Path(root) / entry['file']
        key = (str(path), entry['sha256'])
        if key not in VERIFIED:
            with path.open('rb') as f: assert hashlib.file_digest(f, 'sha256').hexdigest() == entry['sha256']
            VERIFIED.add(key)
        info = entry.get('audio', {})
        assert info.get('sample_rate', sr) == sr and info.get('channels', channels) == channels
        # 分析仍用源采样率、源声道；不用单声道相消后的波形找低能量谷。
        data = subprocess.check_output(['ffmpeg','-v','error','-ss',str(a-origin),'-t',str(z-a),'-i',str(path),'-map','0:a:0','-f','f32le','-'])
        pieces.append(np.frombuffer(data, dtype='<f4').reshape(-1, channels))
    assert pieces
    samples = np.concatenate(pieces)
    assert abs(len(samples)/sr-(hi-lo)) < .15
    # 仅分析副本去直流；原声文件/声道样本从不回写。
    dc = samples.astype('float64').mean(0)
    analysis = samples.astype('float64') - dc
    hop = max(1, round(.01 * sr)); n = len(samples)//hop
    frames = analysis[:n*hop].reshape(n,hop,channels)
    # 任一声道存在语音都视为有声，避免左右声道抵消误裁。
    db = 10*np.log10((frames**2).mean(1).max(1)+1e-12)
    peaks = np.max(np.abs(frames), axis=(1,2))
    threshold = max(-58., min(-38., float(np.percentile(db,10))+8))
    quiet = (db < threshold) & (20*np.log10(peaks+1e-12) < threshold+13)
    changes = np.flatnonzero(np.diff(np.r_[False,quiet,False].astype('int8')))
    runs = [[round(lo+int(a)*hop/sr,6), round(lo+int(z)*hop/sr,6)] for a,z in zip(changes[::2],changes[1::2]) if (z-a)*hop/sr >= .16]
    return {'decoded_window':[lo,hi],'sample_rate':sr,'channels':channels,'frame_seconds':hop/sr,
            'threshold_dBFS':threshold,'quiet_runs':runs,'analysis_DC_removed_per_channel':dc.tolist(),
            'frames_dBFS':[round(float(v),2) for v in db]}


def find(prep, source_root, sentences, effective_asr):
    first = min(s['start'] for s in sentences); last = max(s['end'] for s in sentences)
    duration = prep['canonical']['duration']
    following = [w[1] for w in effective_asr if w[1] > last+.01]
    next_start = min(following) if following else duration
    # 只是读取锚周围小窗；实际裁点必须落在测得的低能量间隙或物理文件边界。
    pre = pcm(prep,source_root,max(0.,first-1.6),min(duration,first+.2))
    starts = [r for r in pre['quiet_runs'] if r[0]+.08 <= min(r[1],first-.025)]
    if starts:
        run = starts[-1]; lo = (run[0]+min(run[1],first-.025))/2; start_kind='measured_quiet_before_first_ASR_anchor'
        assert run[0] <= lo <= run[1] and lo < first
    elif first <= 1.6:
        lo=0.;run=None;start_kind='complete_file_start'
    else:
        return None, {'status':'blocked_no_safe_leading_quiet','first_anchor':first,'analysis':pre}
    if duration-last <= 1.5:
        hi=duration;tail=None;end_kind='complete_file_end'
    else:
        limit=min(duration,last+2.8,next_start-.04)
        if limit <= last+.16:
            return None, {'status':'blocked_no_safe_trailing_room','last_anchor':last,'next_ASR_start':next_start}
        tail=pcm(prep,source_root,max(0.,last-.2),limit)
        # ASR词尾估计可能本身已落在静段内，允许quiet run覆盖anchor；
        # 切点必须确实位于已测得的低能量区，而非靠原词长推算。
        ends=[r for r in tail['quiet_runs'] if max(r[0],last)+.2 <= min(r[1],next_start-.025)]
        if not ends:
            return None, {'status':'blocked_no_safe_trailing_quiet','last_anchor':last,'analysis':tail}
        end_run=ends[0];hi=max(end_run[0],last)+.2;end_kind='measured_quiet_after_last_ASR_anchor'
        assert end_run[0] <= hi <= end_run[1] and hi < next_start
    return [round(lo,6),round(hi,6)], {'status':'measured_PCM_boundaries_or_complete_file_edge','canonical_sha256':prep['canonical']['sha256'],
        'source_entries':[{'file':e['file'],'sha256':e['sha256']} for e in prep['source_entries']],
        'first_ASR_anchor':first,'last_ASR_anchor':last,'next_ASR_start':next_start,
        'window':[round(lo,6),round(hi,6)],'start_kind':start_kind,'end_kind':end_kind,
        'leading_PCM':pre,'trailing_PCM':tail,
        'note':'原采样率/声道PCM逐10ms实测低能量间隙；词尾仍是ASR候选，窗口未按词长估计；正式原音未修改。'}
