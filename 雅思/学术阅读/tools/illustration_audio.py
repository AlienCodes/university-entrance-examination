"""Add one sample-exact second before a verified AAC track using its original packets."""
from fractions import Fraction
from itertools import chain
from pathlib import Path
import subprocess
import tempfile

import av

RATE = 48000
BLOCK = 1024
TIME_BASE = Fraction(1,RATE)


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
                put(clip,sound,bytes(p),p.pts+RATE,duration)
                end=p.pts+duration
            if end!=source_samples:
                raise ValueError('Original audio does not cover the rendered picture')
