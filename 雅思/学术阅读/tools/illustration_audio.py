"""Add one sample-exact second before a verified AAC track using its original packets."""
from fractions import Fraction
from itertools import chain
from pathlib import Path
import subprocess
import tempfile

import av
import numpy as np

RATE = 48000
BLOCK = 1024
TIME_BASE = Fraction(1,RATE)


def silent_rounded_end(core, end, target, packet_start):
    # The core muxer stores its edit length in whole milliseconds. At 30 fps
    # this can trim 16 samples from the declared length of a silent AAC block.
    if end % (RATE // 1000) or not 0 < target-end <= RATE // 2000 or target > packet_start+BLOCK:
        raise ValueError(f'Original audio ends at sample {end}, picture at {target}')
    tail = subprocess.check_output([
        'ffmpeg','-nostdin','-v','error','-xerror','-sseof','-0.15','-i',str(core),
        '-map','0:a:0','-ac','1','-ar',str(RATE),'-f','f32le','-'
    ])
    samples = np.frombuffer(tail,dtype='<f4')
    if len(samples) < RATE//10 or not np.all(np.abs(samples) < .001):
        raise ValueError('The final AAC block is not part of the verified silent hold')


def put(output, stream, payload, pts, duration):
    packet = av.Packet(payload)
    packet.stream = stream
    packet.time_base = TIME_BASE
    packet.pts = packet.dts = pts
    packet.duration = duration
    output.mux(packet)


def pad(core, target, source_samples):
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        silence = Path(tmp)/'silence.m4a'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','anullsrc=r=48000:cl=mono',
                        '-t','0.2','-c:a','aac','-b:a','128k',str(silence)],check=True)
        with av.open(silence) as blank:
            silent_packet = next(bytes(p) for p in blank.demux(audio=0) if p.pts is not None and p.pts>0)
        with av.open(str(core)) as original, av.open(str(target),'w',format='mp4',
                options={'movflags':'+faststart','movie_timescale':str(RATE),'use_editlist':'1'}) as clip:
            track = original.streams.audio[0]
            if (track.codec_context.name,track.codec_context.channels,track.time_base)!=('aac',1,TIME_BASE):
                raise ValueError('Expected native mono AAC at 48 kHz')
            sound = clip.add_stream_from_template(track)
            track_end = track.start_time + track.duration
            packets = (p for p in original.demux(track) if p.pts is not None)
            first = next(packets)
            # 47 AAC packets cover 48,128 samples. The container edit removes the
            # extra 128 samples at the start, leaving every original access unit intact.
            prefix = (RATE+BLOCK-1)//BLOCK
            beginning = first.pts+RATE-prefix*BLOCK
            for i in range(prefix):
                put(clip,sound,silent_packet,beginning+i*BLOCK,BLOCK)
            end = first.pts
            for p in chain([first],packets):
                if p.pts>=source_samples:
                    break
                if p.pts!=end or p.dts!=p.pts:
                    raise ValueError('The original AAC timeline has a discontinuity')
                duration=min(p.duration or BLOCK,source_samples-p.pts)
                if p.pts+duration == track_end < source_samples:
                    silent_rounded_end(core,track_end,source_samples,p.pts)
                    duration=source_samples-p.pts
                put(clip,sound,bytes(p),p.pts+RATE,duration)
                end=p.pts+duration
            if end!=source_samples:
                raise ValueError('Original audio does not cover the rendered picture')


def check_packets(core, movie, source_samples):
    """Match every original compressed AAC access unit on the 48 kHz timeline."""
    import hashlib
    with av.open(str(core)) as original, av.open(str(movie)) as rendered:
        old=(p for p in original.demux(audio=0) if p.pts is not None and p.pts<source_samples)
        new=(p for p in rendered.demux(audio=0) if p.pts is not None)
        first=next(old)
        pkt=next(new)
        while pkt.pts<first.pts+RATE:
            pkt=next(new)
        count=0
        fingerprint=hashlib.sha256()
        for left,right in zip(chain([first],old),chain([pkt],new),strict=True):
            if right.pts-left.pts!=RATE or bytes(left)!=bytes(right):
                raise ValueError(f'Original AAC access unit differs at {left.pts}/{RATE}')
            fingerprint.update(bytes(right))
            count+=1
        if right.pts+right.duration != source_samples+RATE:
            raise ValueError('Final AAC packet does not end on the final picture boundary')
        return dict(original_aac_packets=count, original_aac_payload_sha256=fingerprint.hexdigest(),
                    final_packet_duration_adjustment_samples=right.duration-left.duration, sample_rate=RATE)
