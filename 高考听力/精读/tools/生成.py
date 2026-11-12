"""高考原声精读：原文译注检查→原音→共用分屏与排版→逐屏核查→4K→原音/画面独立核查。"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

from 数据 import C, ROOT, HERE, LEAD, TAIL, FPS, dump, prepare, sha
from 项目 import engine


def call(argv):
    subprocess.run([str(x) for x in argv], check=True)


def workflow_script(path, args):
    previous = sys.argv
    sys.argv = [str(path), *args]
    try:
        runpy.run_path(str(path), run_name='__main__')
    finally:
        sys.argv = previous


def fingerprint(m, p, tm, generator_bytes=None):
    import re
    h = hashlib.sha256()
    files = [Path(__file__), HERE/'数据.py', HERE/'片头检查.py', HERE/'审校登记.py', HERE/'覆盖检查.py',
             Path(m.__file__), m.QA/'layoutcheck.py', m.QA/'zh_bind.py',
             m.QA/'分词补充.txt', ROOT/'专八/tools/字号.json', ROOT/'四级/tools/fonts/fonts.css',
             *m.look_files('6')]
    if generator_bytes is None:
        css=ROOT/'四级/tools/fonts/fonts.css'
        files+=sorted({(css.parent/name).resolve() for name in
            re.findall(r'url\([\'\"]?([^\'\"\)]+)',css.read_text())
            if name.endswith(('.woff2','.woff','.ttf'))})
    for f in files:
        h.update(str(f.relative_to(ROOT)).encode())
        h.update(generator_bytes if f==Path(__file__) and generator_bytes is not None else f.read_bytes())
    h.update(json.dumps([p, tm, m.SPLIT.get(p['id'], {})], ensure_ascii=False, sort_keys=True).encode())
    return h.hexdigest()


def screens_fingerprint_ok(m,p,tm,value):
    if value==fingerprint(m,p,tm):return True
    # 音频预检误报修复不改变截图。兼容仅限这个已通过版本；任何视觉函数或其他输入改变都拒绝。
    import ast
    path=C/'审校/截图指纹兼容_e2e9918.json'
    if not path.exists():return False
    old=json.loads(path.read_text());source=old['source'].encode()
    assert hashlib.sha256(source).hexdigest()==old['生成_sha256']
    before=ast.parse(source);after=ast.parse(Path(__file__).read_text())
    qa={'fingerprint','screens_fingerprint_ok','audio_check','cached_check','verify','encode','main'}
    approved=old.get('新检查函数_AST_sha256',{})
    if set(approved)!=qa:return False
    for name in qa:
        matches=[n for n in after.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
        if len(matches)!=1 or not isinstance(matches[0],ast.FunctionDef):return False
        fn=matches[0]
        # 本机3.12比Actions3.11多出type_params字段；统一规范后再锁定函数。
        for node in ast.walk(fn):
            if hasattr(node,'type_params'):delattr(node,'type_params')
        if hashlib.sha256(ast.dump(fn,include_attributes=False).encode()).hexdigest()!=approved[name]:return False
    raster=lambda tree:ast.Module(body=[n for n in tree.body if not
        (isinstance(n,ast.FunctionDef) and n.name in qa)],type_ignores=[])
    if ast.dump(raster(before),include_attributes=False)!=ast.dump(raster(after),include_attributes=False):return False
    fonts=old.get('字体旧基线',{})
    if hashlib.sha256(json.dumps(fonts,sort_keys=True).encode()).hexdigest()!='4e3631435202f0bab77299e8883d25828242ed5ebfa4ef809e77c9cd9362bb7d':return False
    if any(not (ROOT/name).is_file() or sha(ROOT/name)!=value for name,value in fonts.items()):return False
    return value==fingerprint(m,p,tm,source)


def input_snapshot(m, p, tm):
    return {'passage': p, 'timings': tm, 'split': m.SPLIT.get(p['id'], {})}


def hint(m, p):
    return m.page('<div class="top"><b>GAOKAO ENGLISH</b><span>'+m.esc(p['paper'])+'</span></div>'
                  '<div class="gk-hint"><strong>原声提示</strong><p>请听录音中的考试提示</p>'
                  '<small>随后继续逐句精读</small></div><style>.gk-hint{position:absolute;inset:0;display:flex;'
                  'flex-direction:column;align-items:center;justify-content:center;color:#4b3b6b;gap:28px;'
                  'font-family:"Noto Sans SC"}.gk-hint strong{font-size:78px}.gk-hint p{font-size:46px;margin:0}'
                  '.gk-hint small{font-size:28px;color:#88779c}</style>')


def closing(m, p):
    return m.page('<div class="top"><b>GAOKAO ENGLISH</b><span>'+m.esc(p['paper'])+'</span></div>'
                  '<div class="gk-end"><strong>本套精读结束</strong><p>'+m.esc(p['paper_title'])+'</p></div>'
                  '<style>.gk-end{position:absolute;inset:0;display:flex;flex-direction:column;gap:36px;'
                  'align-items:center;justify-content:center;color:#4b3b6b;font-family:"Noto Sans SC"}'
                  '.gk-end strong{font-size:76px}.gk-end p{font-size:42px}</style>')


def build_states(m, p, d, tm, labels):
    flat = [s for para in p['paras'] for s in para]
    states = [(0, 'screen001'), (round(LEAD*FPS), 'hint')]
    shot = 1
    for k, s in enumerate(flat, 1):
        parts = m.split_parts(p['id'], k, s)
        it = tm['sentences'][k-1]
        for n, (lo, hi, zh, tag) in enumerate(parts):
            t = it['start'] if not n else m.switch_time(C/'audio'/tm['file'], it, s['en'], lo)
            assert it['start']-.02 <= t <= it['end']+.02, f'{k} 分屏换屏超出本句'
            states.append((round(t*FPS), f'screen{shot+1:03d}'))
            shot += 1
    assert shot == len(labels), f'画面映射{shot}≠排版{len(labels)}'
    papers = json.loads((C.parent/'套.json').read_text())
    blocks = json.loads((C.parent/'识别'/papers[p['id']]['识别']/'分块.json').read_text())
    for a,b,lang,text in blocks:
        if lang != 'zh' or not any(w in text for w in ['听','题','节','秒','回答','阅读','分钟']):
            continue
        if b <= d['cut'] or a >= tm['window'][1]:
            continue
        # 只有与英文句子不重叠的中文说明才插提示屏，避免语言误判覆盖实际英文。
        overlaps = any(max(a,s['start']) < min(b,s['end'])-.10 for s in d['sentences'])
        if not overlaps:
            states.append((round((max(a,d['cut'])-d['cut']+LEAD)*FPS), 'hint'))
    speech_end = min(tm['duration']-2.0, tm['sentences'][-1]['end']+.20)
    states.append((round(speech_end*FPS), 'end'))
    unique = {}
    for frame, key in sorted(states, key=lambda x:(x[0], x[1].startswith('screen'))):
        if 0 <= frame < round(tm['duration']*FPS):
            unique[frame] = key
    out = []
    for f,k in sorted(unique.items()):
        if not out or out[-1][1] != k:
            out.append([f,k])
    required={f'screen{i+1:03d}' for i in range(len(labels))}
    assert required<={k for _,k in out},f'换屏量化吞掉正文画面：{required-{k for _,k in out}}'
    assert out[0] == [0, 'screen001'] and all(a[0]<b[0] for a,b in zip(out,out[1:]))
    assert (round(tm['duration']*FPS)-out[-1][0])/FPS >= 2
    return out


def stills(m, p, d, tm, out):
    from playwright.sync_api import sync_playwright
    frozen=fingerprint(m,p,tm)
    shots = out/'shots'; shots.mkdir(exist_ok=True)
    labels = m.screens(p)
    f = out/'page.html'
    rows = []
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=os.environ.get('GK_BROWSER','/opt/pw-browsers/chromium'))
        pg = br.new_page(viewport={'width':1920,'height':1080}, device_scale_factor=2)
        m.P_CUR = p
        for i, label, fit, r in m.layout(pg,p,f):
            if not fit: pg.evaluate(m.GK_COVER_FIT)
            if label=='片头':
                from 片头检查 import problems as cover_problems
                problems = cover_problems(pg,m,p['paper_title'])
            else:
                problems = m.screen_checks(pg,label,fit,r)
            if problems:
                pg.screenshot(path=str(shots/f'screen{i+1:03d}.bad.png'))
                raise ValueError('\n'.join(problems))
            target=shots/f'screen{i+1:03d}.png'; pg.screenshot(path=str(target))
            rows.append({'index':i,'label':label,'file':target.name,'sha256':sha(target),'sizes':r})
        for key, body in [('hint',hint(m,p)),('end',closing(m,p))]:
            f.write_text(body,'utf-8');pg.goto(f.as_uri());pg.evaluate('document.fonts.ready')
            bad = pg.evaluate(m.TH.GLYPH)
            if bad: raise ValueError(f'{key} 缺字：{bad}')
            target=shots/(key+'.png');pg.screenshot(path=str(target))
            rows.append({'label':key,'file':target.name,'sha256':sha(target)})
        br.close()
    states=build_states(m,p,d,tm,labels)
    assert frozen==fingerprint(m,p,tm),'截图期间程序或输入改变，需按固定版本重跑'
    dump(out/'states.json',states)
    dump(out/'screens-input.json',input_snapshot(m,p,tm))
    dump(out/'screens.json',{'id':p['id'],'fingerprint':fingerprint(m,p,tm),'problems':[],
                             'frames':round(tm['duration']*FPS),'shots':rows})
    print(f'{p["id"]}：{len(rows)}张4K截图，{len(states)}个画面状态，全部排版检查0处',flush=True)
    return states


def base_engine():
    spec=importlib.util.spec_from_file_location('gk_audio_check',ROOT/'专八/听力/tools/听力视频.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def audio_check(tm, out):
    """编码前用相同AAC参数完整往返，先拦截原音变速、音量或声道改变。"""
    import numpy as np
    import soundfile as sf
    encoded, decoded = out/'audio-precheck.m4a', out/'audio-precheck.wav'
    call(['ffmpeg','-y','-v','error','-i',C/'audio'/tm['file'],
          '-c:a','aac','-b:a','192k',encoded])
    call(['ffmpeg','-y','-v','error','-i',encoded,'-c:a','pcm_f32le',decoded])
    y,sr=sf.read(decoded,dtype='float32',always_2d=True)
    ref,sr2=sf.read(out/'source.wav',dtype='float32',always_2d=True)
    lo,hi=(round(t*sr2) for t in tm['window']);ref=ref[lo:hi]
    offset=round(LEAD*sr)
    bad=[]
    if sr!=tm['sample_rate'] or y.shape[1]!=tm['channels']:
        bad.append('AAC改变原采样率/声道')
    bad+=base_engine().orig_match(ref,y[offset:offset+len(ref)],sr)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(encoded)]))
    stream=next(s for s in info['streams'] if s['codec_type']=='audio')
    if abs(float(stream['duration'])-tm['duration'])>.05:bad.append('AAC容器时长偏差超过50毫秒')
    # 原生16kHz的AAC一帧为64ms。解码末尾可补齐到一整帧；这不是音轨漂移，须逐样本为静音。
    expected=round(tm['duration']*sr);padding=len(y)-expected
    if not 0<=padding<=1024 or (padding and np.abs(y[expected:]).max()>=.001):
        bad.append(f'AAC末帧补齐不符：{padding}样本，须≤1024且全为静音')
    if np.abs(y[:offset-480]).max()>=.001:bad.append('片头静音不符')
    if len(y)-offset-len(ref)<2*sr or np.abs(y[offset+len(ref)+round(.05*sr):]).max()>=.001:
        bad.append('片尾静音不符')
    dump(out/'audio-precheck.json',{'ok':not bad,'problems':bad,
        'source_sha256':tm['source_sha256'],'audio_sha256':tm['audio_sha256'],
        'container_duration':float(stream['duration']),'decoded_padding_samples':padding})
    encoded.unlink(missing_ok=True);decoded.unlink(missing_ok=True)
    assert not bad, f'音频预检失败：{bad}'
    print('原声AAC完整往返预检通过',flush=True)


def verify(m, original, p, tm, out, mp4, states, fast=False):
    import numpy as np
    import soundfile as sf
    from fractions import Fraction
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(mp4)]))
    v=next(s for s in info['streams'] if s['codec_type']=='video')
    a=next(s for s in info['streams'] if s['codec_type']=='audio')
    frames=round(tm['duration']*FPS)
    checks=[]
    def check(name,ok,detail):
        checks.append({'name':name,'ok':bool(ok),'detail':detail})
    expected=(480,270) if fast else (3840,2160)
    check('预演分辨率' if fast else '4K分辨率', (v['width'],v['height'])==expected,f'{v["width"]}×{v["height"]}')
    check('恒定30帧与完整帧数',Fraction(v['r_frame_rate'])==FPS and Fraction(v['avg_frame_rate'])==FPS and int(v['nb_read_frames'])==frames,str(v['nb_read_frames']))
    check('声画时长',abs(float(a['duration'])-frames/FPS)<=.05,f'{a["duration"]}/{frames/FPS}')
    check('原采样率与声道',int(a['sample_rate'])==tm['sample_rate'] and int(a['channels'])==tm['channels'],f'{a["sample_rate"]}Hz {a["channels"]}声道')
    decoded=out/'verify.wav'
    call(['ffmpeg','-y','-v','error','-i',mp4,'-map','0:a:0','-c:a','pcm_f32le',decoded])
    y,sr=sf.read(decoded,dtype='float32',always_2d=True)
    ref,sr2=sf.read(out/'source.wav',dtype='float32',always_2d=True)
    lo,hi=(round(t*sr2) for t in tm['window']);ref=ref[lo:hi]
    base=base_engine();offset=round(LEAD*sr)
    probs=base.orig_match(ref,y[offset:offset+len(ref)],sr)
    check('原声逐样本核对',not probs,probs or '音量差≤0.05dB、SNR≥30dB、逐秒差≤1dB')
    check('片头1.5秒静音',np.abs(y[:offset-480]).max()<.001,'1.5秒')
    check('片尾至少2秒静音',np.abs(y[offset+len(ref)+round(.05*sr):]).max()<.001 and len(y)-offset-len(ref)>=2*sr,'至少2秒')
    boundaries=[s[0] for s in states]+[frames]
    shotpaths=[out/'shots'/(s[1]+'.png') for s in states]
    if fast:
        from PIL import Image
        tiny=out/'fast-shots';tiny.mkdir(exist_ok=True)
        for path in set(shotpaths):
            # 使用与ffmpeg预演相同的scale滤镜，仅用于试跑画面核查。
            call(['ffmpeg','-y','-v','error','-i',path,'-vf','scale=480:270',tiny/path.name])
        shotpaths=[tiny/path.name for path in shotpaths]
    name,ok,detail=m.frame_check(mp4,boundaries,shotpaths)
    check(name,ok,detail)
    check('成品体积',0<mp4.stat().st_size<1900*2**20,str(mp4.stat().st_size))
    rep={'id':p['id'],'ok':all(c['ok'] for c in checks),'checks':checks,'sha256':sha(mp4),
         'bytes':mp4.stat().st_size,'fingerprint':fingerprint(m,p,tm),'states':len(states),
         'screens_fingerprint':json.loads((out/'screens.json').read_text())['fingerprint']}
    dump(out/('fast-verification.json' if fast else 'verification.json'),rep)
    decoded.unlink(missing_ok=True)
    if not rep['ok']:
        failed=mp4.with_suffix('.未通过.mp4');mp4.replace(failed)
        raise ValueError(f'成品核查失败，保留未通过成品：{[c for c in checks if not c["ok"]]}')
    print(f'{p["id"]}：成品全部核查通过，{mp4.stat().st_size/2**20:.1f}MiB',flush=True)
    return rep


def encode(m, original, p, tm, out, fast=False):
    if not fast:
        from 审校登记 import check as check_review
        check_review(p['id'])
    cached_check(m,p,tm,out)
    states=json.loads((out/'states.json').read_text());frames=round(tm['duration']*FPS)
    rows=[]
    for (a,key),b in zip(states,[s[0] for s in states[1:]]+[frames]):
        assert b>a
        rows.append(f"file '{out/'shots'/(key+'.png')}'\nduration {(b-a)/FPS:.9f}")
    rows.extend([f"file '{out/'shots'/(states[-1][1]+'.png')}'\nduration 1",f"file '{out/'shots'/(states[-1][1]+'.png')}'"])
    listing=out/'concat.txt';listing.write_text('\n'.join(rows)+'\n')
    mp4=out/(p['paper_title']+' 高考英语真题 原文精读.mp4')
    cmd=['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',listing,'-i',C/'audio'/tm['file'],
         '-fps_mode','cfr','-r',FPS,'-frames:v',frames,'-c:v','libx264','-preset','veryfast','-tune','stillimage',
         '-crf','18','-threads',os.environ.get('GK_THREADS','2'),'-pix_fmt','yuv420p','-g','300',
         '-c:a','aac','-b:a','192k','-movflags','+faststart',mp4]
    if fast:
        i=cmd.index('-c:v');cmd[i:i]=['-vf','scale=480:270'];cmd[cmd.index('-preset')+1]='ultrafast';cmd[-1]=out/'预演.mp4'
    call(cmd)
    rep=verify(m,original,p,tm,out,Path(cmd[-1]),states,fast)
    if not fast:
        dump(out/'meta.json',{'id':p['id'],'套':p['id'],'kind':'text','mp4':mp4.name,'label':mp4.name,
                             'mp4_sha256':rep['sha256'],'mp4_bytes':rep['bytes'],'原音_sha256':tm['source_sha256'],
                             '定稿_sha256':sha(C/'定稿'/f'{p["id"]}.json'),
                             '译注_sha256':sha(C/'ann'/f'{p["id"]}.txt'),
                             'fingerprint':rep['fingerprint'],'screens_fingerprint':rep['screens_fingerprint'],
                             '成品核查':'全部通过'})


def cached_check(m,p,tm,out):
    from 审校登记 import check as review_check
    review_check(p['id'])
    report=json.loads((out/'screens.json').read_text())
    assert report['id']==p['id'] and not report['problems']
    assert screens_fingerprint_ok(m,p,tm,report['fingerprint']), '截图后视觉代码或输入已变'
    assert report['frames']==round(tm['duration']*FPS)
    assert json.dumps(json.loads((out/'screens-input.json').read_text()),sort_keys=True)==json.dumps(input_snapshot(m,p,tm),sort_keys=True), '截图输入内容已变'
    audio_report=json.loads((out/'audio-precheck.json').read_text())
    assert audio_report['ok'] and audio_report['audio_sha256']==tm['audio_sha256'] and audio_report['source_sha256']==tm['source_sha256'], '缺少当前音轨的AAC预检'
    labels=m.screens(p)
    expected={f'screen{i+1:03d}.png' for i in range(len(labels))}|{'hint.png','end.png'}
    actual=[s['file'] for s in report['shots']]
    assert len(actual)==len(expected) and set(actual)==expected,'截图登记数量/文件集合不符'
    for s in report['shots']:
        assert sha(out/'shots'/s['file'])==s['sha256'],'截图内容已变'
    d=json.loads((C/'定稿'/f'{p["id"]}.json').read_text())
    assert build_states(m,p,d,tm,labels)==json.loads((out/'states.json').read_text()), '换屏状态不符'
    print(f'{p["id"]}：已通过预检的全部PNG、代码、数据、原声、时间与状态再次核对一致',flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('sid');ap.add_argument('action',choices=['prepare','audio','precheck','stills','cached','video','fast','all'])
    ap.add_argument('--original',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--draft',action='store_true',help='只用于未审预览，不准发布')
    args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if os.environ.get('GK_HTTP'):
        from 本机预览 import enable
        enable([ROOT,out,Path(tempfile.gettempdir())],os.environ.get('GK_BROWSER','/usr/bin/chromium'))
    d,p,tm=prepare(args.sid,args.original,out,args.draft)
    if args.action=='prepare':return
    if args.action in ('audio','precheck','all'):
        audio_check(tm,out)
    if args.action=='audio':return
    m=engine();m.NAMES=d.get('names',[])
    m.check_names(p)
    if args.action=='cached':
        cached_check(m,p,tm,out);return
    os.environ['DZB_PROJECT']='高考原文精读'
    suggestion=out/'split-suggestions.json'
    if args.action in ('precheck','all'):
        workflow_script(ROOT/'专八/tools/分屏建议.py',[args.sid,'--styles','6','--out',str(suggestion)])
        workflow_script(ROOT/'专八/tools/分屏定稿.py',[str(suggestion),args.sid])
        m.set_project('高考原文精读');m.NAMES=d.get('names',[])
    if args.action in ('precheck','stills','all'):
        stills(m,p,d,tm,out)
    if args.action in ('video','fast','all'):
        encode(m,args.original,p,tm,out,args.action=='fast')


if __name__=='__main__':
    main()
