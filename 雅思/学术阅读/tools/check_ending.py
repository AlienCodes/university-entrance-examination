"""Inspect final MP4 clocks, decode every tail frame, and play to HTML5 ended."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess
import threading

from playwright.sync_api import sync_playwright
from lesson import PID, PROJECT, save


def atoms(path):
    order=[]
    length=path.stat().st_size
    with path.open('rb') as f:
        while f.tell()<length:
            start=f.tell()
            size,typ=struct.unpack('>I4s',f.read(8))
            if size==1:
                size=struct.unpack('>Q',f.read(8))[0]
            if not size:
                size=length-start
            if size<f.tell()-start or start+size>length:
                raise ValueError('Truncated MP4 box')
            order.append(typ.decode('ascii'))
            f.seek(start+size)
    if order.index('moov')>order.index('mdat'):
        raise ValueError('moov data does not precede media')
    return order


class MovieHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def do_GET(self):
        if self.path!='/movie.mp4':
            body=b'<!doctype html><video muted playsinline width="640" height="360"></video>'
            self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            return
        movie=self.server.movie
        size=movie.stat().st_size
        start,end=0,size-1
        requested=self.headers.get('Range')
        if requested:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
            if match is None or not any(match.groups()):
                self.send_error(416);return
            first,last=match.groups()
            if first:
                start=int(first);end=min(int(last),end) if last else end
            else:
                start=max(0,size-int(last))
            if not 0<=start<=end:
                self.send_error(416);return
        self.send_response(206 if requested else 200)
        self.send_header('Content-Type','video/mp4')
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Length',str(end-start+1))
        if requested:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        try:
            with movie.open('rb') as f:
                f.seek(start);remaining=end-start+1
                while remaining:
                    data=f.read(min(remaining,1<<18));self.wfile.write(data);remaining-=len(data)
        except (BrokenPipeError,ConnectionResetError):
            pass


PLAY_END = """async () => {
 const v=document.querySelector('video');
 const once=(e)=>new Promise((resolve,reject)=>{
   const done=()=>{clearTimeout(timer);resolve();};
   const timer=setTimeout(()=>reject(new Error('Timeout '+e+' time='+v.currentTime+' state='+v.readyState)),40000);
   v.addEventListener(e,done,{once:true});
   v.addEventListener('error',()=>reject(new Error('media error '+v.error?.code)),{once:true});
 });
 let loaded=once('loadedmetadata');v.src='/movie.mp4';await loaded;
 let seek=once('seeked');v.currentTime=v.duration-5.2;await seek;
 let first=v.currentTime,lastFrame=0,callbacks=0;
 const record=(_,data)=>{lastFrame=Math.max(lastFrame,data.mediaTime);callbacks++;if(!v.ended)v.requestVideoFrameCallback(record);};
 v.requestVideoFrameCallback(record);
 let ended=once('ended');await v.play();await ended;
 return {ended:v.ended,duration:v.duration,end:v.currentTime,start:first,last_frame:lastFrame,frame_callbacks:callbacks,error:v.error?.code||0};
}"""


def play_end(video,expected):
    server=ThreadingHTTPServer(('127.0.0.1',0),MovieHandler)
    server.movie=video
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            binary=shutil.which('google-chrome') or shutil.which('chromium') or '/opt/pw-browsers/chromium'
            br=pw.chromium.launch(executable_path=binary,args=['--autoplay-policy=no-user-gesture-required','--disable-background-timer-throttling'])
            try:
                page=br.new_page()
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                result=page.evaluate(PLAY_END)
            finally:
                br.close()
    finally:
        server.shutdown();server.server_close()
    if not (result['ended'] and not result['error'] and abs(result['duration']-expected)<.04
            and abs(result['end']-expected)<.04 and expected-result['last_frame']<.12
            and result['end']-result['start']>5 and result['frame_callbacks']>=3):
        raise ValueError(f'Browser did not play through the tail: {result}')
    return result


def inspect(video,timing):
    read=subprocess.check_output
    p=json.loads(read(['ffprobe','-v','error','-show_format','-show_streams','-show_packets',
                       '-show_entries','format=duration:stream=index,codec_type,codec_name,profile,width,height,pix_fmt,duration,r_frame_rate,nb_frames,sample_rate:packet=stream_index,pts_time,dts_time,duration_time,flags',
                       '-of','json',str(video)]))
    v=next(s for s in p['streams'] if s['codec_type']=='video')
    a=next(s for s in p['streams'] if s['codec_type']=='audio')
    end=math.ceil(timing['sentences'][-1]['end']+4)
    durations=[float(p['format']['duration']),float(v['duration']),float(a['duration'])]
    if (v['codec_name'],v['pix_fmt'],v['r_frame_rate'],a['codec_name'],a['profile'])!=('h264','yuv420p','30/1','aac','LC') or max(abs(x-end) for x in durations)>.002:
        raise ValueError(f'Media clocks/codecs differ: {durations}, {v}, {a}')
    streams=[[p for p in p['packets'] if p['stream_index']==s['index']] for s in (v,a)]
    ends=[]
    for stream in streams:
        dts=[float(p['dts_time']) for p in stream]
        if any(b<=a for a,b in zip(dts,dts[1:])):raise ValueError('Non-monotone decoding timestamps')
        ends.append(max(float(p['pts_time'])+float(p['duration_time']) for p in stream))
    if max(abs(x-end) for x in ends)>.002:raise ValueError(f'Packets end early: {ends}')
    pts=sorted(float(p['pts_time']) for p in streams[0]); frame_count=30*end
    if len(pts)!=frame_count or any(abs(x-i/30)>.001 for i,x in enumerate(pts)):raise ValueError('Missing presentation frames')
    atimes=[float(p['pts_time']) for p in streams[1]]
    if max(b-a for a,b in zip(atimes,atimes[1:]))>.03:raise ValueError('Audio packets contain a gap')
    keys=[float(p['pts_time']) for p in streams[0] if 'K' in p['flags']]
    if not all(any(abs(key-t)<.033 for key in keys) for t in (end-4,end-2)):raise ValueError('Missing tail keyframes')
    frame_size=64*36
    tail=read(['ffmpeg','-v','error','-xerror','-err_detect','explode','-ss',str(end-3),'-i',str(video),'-map','0:v:0','-an',
               '-vf','scale=64:36,format=gray','-fps_mode','passthrough','-f','rawvideo','-'])
    if len(tail)!=90*frame_size:raise ValueError(f'Decoded {len(tail)/frame_size} of final 90 frames')
    subprocess.run(['ffmpeg','-v','error','-xerror','-err_detect','explode','-ss',str(end-5),'-i',str(video),'-map','0:a:0','-f','null','-'],check=True)
    return dict(expected_seconds=end,container_seconds=durations[0],video_seconds=durations[1],audio_seconds=durations[2],
                video_packet_end=ends[0],audio_packet_end=ends[1],actual_video_frames=len(pts),decoded_last_three_seconds_frames=90,
                silence_after_narration_seconds=round(end-timing['sentences'][-1]['end'],3),
                tail_keyframes=[k for k in keys if k>=end-4.01],mp4_boxes=atoms(video),desktop_html5_playback=play_end(video,end))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('video',type=Path);parser.add_argument('proof',type=Path)
    parser.add_argument('--timings',type=Path,default=PROJECT/'audio/timings.json')
    args=parser.parse_args()
    tm=json.loads(args.timings.read_text())['cet4_male'][PID]
    result=inspect(args.video,tm)
    save(args.proof,result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
