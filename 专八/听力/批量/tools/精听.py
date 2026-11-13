"""专八历年精听：原声编译→既有书卷水墨排版检查→4K编码→原声和逐屏独立核验。

python 精听.py 单元.json prepare|audio|precheck|stills|video|all --original 原声 --out 工作目录
首次调用precheck可加--autosplit；输入待核时只允许--draft预览，不准编码正式成品。
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tempfile

from 精听数据 import ROOT,HERE,LEAD,TAIL,FPS,sha,dump,compile_input,validate,first_aligned_word,audio_protection,PROTECTION_2022

PROJECT='专八批量精听'


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


def engine(out):
    # 与高考精读入口相同：新项目仅注册到本进程，不改共享PROJECTS或旧2025数据。
    old={k:os.environ.pop(k,None) for k in ['DZB_PROJECT','DZB_VARIANT']}
    try:m=load_module('make_video',ROOT/'专八/tools/make_video.py')
    finally:
        for k,v in old.items():
            if v is not None:os.environ[k]=v
    config=copy.deepcopy(m.PROJECTS['专八听力'])
    config.update(dir=str(out),tag='TEM-8 · LISTENING · ORIGINAL TEXT',max_mb=1900,
                  name_re=r'20\d\d年专八听力 .+\.mp4')
    m.PROJECTS[PROJECT]=config
    os.environ['DZB_PROJECT']=PROJECT;os.environ['DZB_VARIANT']='水墨'
    m.set_project(PROJECT);m.EXAM_WORDS[PROJECT]=['专八','TEM-8','TEM8']
    original=m.look_files
    m.look_files=lambda look=None:[*original(look),Path(__file__),HERE/'精听数据.py']
    original_page=m.page
    def page(body):
        # 与既有高考精读适配相同，只排版转义后的正文引号；不改来源、字符范围或词时刻。
        rendered=original_page(body).replace('&#x27;','’')
        return re.sub(r'&quot;(?=\w)','“',rendered).replace('&quot;','”')
    m.page=page
    fallback=m.switch_time
    def switch_time(audio,it,en,cut):
        aligned=it.get('word_alignment') or []
        if not aligned:return fallback(audio,it,en,cut)
        t=first_aligned_word(aligned,en,cut)['start']
        gaps=list(zip([p[1] for p in it['parts']],[p[0] for p in it['parts'][1:]]))
        near=[(a+b)/2 for a,b in gaps if abs((a+b)/2-t)<=.35]
        return min(near,key=lambda x:abs(x-t)) if near else t
    m.switch_time=switch_time
    return m


def fingerprint(m,p,tm):
    h=hashlib.sha256()
    files=[Path(__file__),HERE/'精听数据.py',Path(m.__file__),m.QA/'layoutcheck.py',m.QA/'zh_bind.py',
           m.QA/'分词补充.txt',ROOT/'专八/tools/字号.json',ROOT/'四级/tools/fonts/fonts.css',*m.look_files('C')]
    for base in [ROOT/'专八/tools/fonts',ROOT/'四级/tools/fonts']:
        files+=sorted(f for f in base.rglob('*') if f.is_file() and f.suffix.lower() in ['.woff2','.woff','.ttf','.otf'])
    if p['year']==2022:files.append(PROTECTION_2022)
    for f in dict.fromkeys(files):
        h.update(str(f.relative_to(ROOT)).encode());h.update(f.read_bytes())
    h.update(json.dumps([p,tm,m.SPLIT.get(p['id'],{}),m.NAMES],ensure_ascii=False,sort_keys=True).encode())
    return h.hexdigest()


def read_prepared(out,input_file,draft=False):
    d=validate(json.loads(Path(input_file).read_text('utf-8')),draft)
    p=json.loads((out/'data/vocab.json').read_text())['passages'][0]
    tm=json.loads((out/'audio/timings.json').read_text())['cet4_male'][p['id']]
    report=json.loads((out/'prepared.json').read_text())
    assert report['input_sha256']==sha(input_file),'输入更改，须重新prepare'
    assert sha(out/'audio'/tm['file'])==tm['audio_sha256']
    protected,protection=audio_protection(d)
    assert tm.get('protected_source_intervals',[])==protected and tm.get('audio_protection')==protection,'原音保护登记改变，须重新prepare'
    return d,p,tm


def compare_audio(a,b,sr):
    """独立复用原音精听逐样本守门，不适用TTS的-16 LUFS要求。"""
    raw=load_module('tem8_raw_audio_check',ROOT/'专八/听力/原文/tools/原音音轨.py')
    return raw.seg_match([(a,b)],sr)


def audio_check(out,tm):
    import numpy as np
    import soundfile as sf
    original,sr=sf.read(out/'source.wav',dtype='float32',always_2d=True)
    ref,sr2=sf.read(out/'audio'/tm['file'],dtype='float32',always_2d=True)
    assert sr==sr2==tm['sample_rate'] and original.shape[1]==ref.shape[1]==tm['channels']
    body=np.concatenate([original[round(a*sr):round(b*sr)] for a,b in tm['kept_intervals']],axis=0)
    assert np.linalg.norm(body)>1e-6,'正文窗口完全无声，不能凭文本生成伪听力'
    offset=round(LEAD*sr)
    assert np.array_equal(body,ref[offset:offset+len(body)]),'原音编译样本改变'
    encoded=out/'audio-precheck.m4a';decoded=out/'audio-precheck.wav'
    subprocess.run(['ffmpeg','-y','-v','error','-i',str(out/'audio'/tm['file']),'-c:a','aac','-b:a','192k',str(encoded)],check=True)
    subprocess.run(['ffmpeg','-y','-v','error','-i',str(encoded),'-c:a','pcm_f32le',str(decoded)],check=True)
    got,sr3=sf.read(decoded,dtype='float32',always_2d=True)
    assert sr3==sr and got.shape[1]==ref.shape[1]
    bad,measure=compare_audio(body,got[offset:offset+len(body)],sr)
    assert not bad,'AAC完整往返原音核对未通过：'+str(bad)
    dump(out/'audio-precheck.json',{'ok':True,'audio_sha256':tm['audio_sha256'],'source_sha256':tm['source_sha256'],
                                  'raw_exact_before_encoding':True,'raw_match':measure,'sample_rate':sr,'channels':got.shape[1]})
    encoded.unlink();decoded.unlink()


def script(path,args):
    old=sys.argv;sys.argv=[str(path),*args]
    try:runpy.run_path(str(path),run_name='__main__')
    finally:sys.argv=old


def autosplit(m,p,out):
    suggestion=out/'split-suggestions.json'
    script(ROOT/'专八/tools/分屏建议.py',[p['id'],'--project',PROJECT,'--styles','C','--out',str(suggestion)])
    script(ROOT/'专八/tools/分屏定稿.py',[str(suggestion),p['id']])
    m.set_project(PROJECT)


def states(m,p,tm,out):
    flat=[s for para in p['paras'] for s in para]
    result=[[0,'screen001']];i=1
    for k,s in enumerate(flat,1):
        it=tm['sentences'][k-1]
        for j,(lo,hi,zh,tag) in enumerate(m.split_parts(p['id'],k,s)):
            when=it['start'] if j==0 else m.switch_time(out/'audio'/tm['file'],it,s['en'],lo)
            assert it['start']-.02<=when<=it['end']+.02
            if j:
                gaps=list(zip([p[1] for p in it['parts']],[p[0] for p in it['parts'][1:]]))
                declaration=m.SPLIT.get(p['id'],{}).get(str(k),{}).get('无停顿')
                assert any(a-.02<=when<=b+.02 for a,b in gaps) or declaration in ['句中没有停顿','停顿处切不开'],'分屏换屏缺少真实停顿或无停顿说明'
            i+=1;result.append([round(when*FPS),f'screen{i:03d}'])
    assert all(a[0]<b[0] for a,b in zip(result,result[1:])), '两个画面量化到同一帧，须核对句界/分屏'
    assert len(result)==len(m.screens(p))
    assert round(tm['duration']*FPS)-result[-1][0]>1
    return result


def stills(m,p,tm,out,browser):
    from playwright.sync_api import sync_playwright
    frozen=fingerprint(m,p,tm);shots=out/'shots';shots.mkdir(exist_ok=True)
    rows=[];page=out/'page.html';m.P_CUR=p;m.check_names(p)
    with sync_playwright() as pw:
        br=pw.chromium.launch(executable_path=browser,args=['--no-sandbox'])
        pg=br.new_page(viewport={'width':1920,'height':1080},device_scale_factor=2)
        for i,label,fit,r in m.layout(pg,p,page):
            bad=m.screen_checks(pg,label,fit,r)
            if bad:
                pg.screenshot(path=str(shots/f'screen{i+1:03d}.bad.png'))
                dump(out/'layout-problems.json',{'id':p['id'],'problems':bad})
                raise ValueError('\n'.join(bad))
            target=shots/f'screen{i+1:03d}.png';pg.screenshot(path=str(target))
            rows.append({'file':target.name,'label':label,'sha256':sha(target),'sizes':r})
        br.close()
    assert frozen==fingerprint(m,p,tm),'截图期间输入或代码改变'
    s=states(m,p,tm,out);dump(out/'states.json',s)
    dump(out/'screens.json',{'id':p['id'],'fingerprint':frozen,'problems':[],'shots':rows})
    print(f'{p["id"]}: {len(rows)}张4K水墨截图，排版检查0处',flush=True)


def cached_check(m,p,tm,out):
    report=json.loads((out/'screens.json').read_text())
    assert report['fingerprint']==fingerprint(m,p,tm),'代码/数据/原音改变，截图失效'
    assert not report['problems']
    assert len(report['shots'])==len(m.screens(p))
    assert all(sha(out/'shots'/r['file'])==r['sha256'] for r in report['shots'])
    a=json.loads((out/'audio-precheck.json').read_text())
    assert a['ok'] and a['audio_sha256']==tm['audio_sha256'] and a['source_sha256']==tm['source_sha256']
    assert states(m,p,tm,out)==json.loads((out/'states.json').read_text())


def approve(m,p,tm,out,note):
    assert note and len(note.strip())>=10,'请记录实际截图核对依据或抽样/例外复核记录，不能空登记'
    cached_check(m,p,tm,out)
    dump(out/'approved-screens.json',{'id':p['id'],'fingerprint':fingerprint(m,p,tm),
                                     'screens_sha256':sha(out/'screens.json'),'review_note':note})


def verify(m,p,tm,out,mp4,draft=False):
    import numpy as np
    import soundfile as sf
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(mp4)]))
    v=next(s for s in info['streams'] if s['codec_type']=='video');a=next(s for s in info['streams'] if s['codec_type']=='audio')
    checks=[]
    def check(item,ok,detail):checks.append({'item':item,'ok':bool(ok),'detail':detail})
    frames=round(tm['duration']*FPS)
    check('4K 16:9',v['width']==3840 and v['height']==2160,[v['width'],v['height']])
    check('30帧恒定/帧数',v['r_frame_rate']=='30/1' and int(v['nb_frames'])==frames,[v['r_frame_rate'],v['nb_frames']])
    check('声画等长',abs(float(v['duration'])-float(a['duration']))<.05,[v['duration'],a['duration']])
    check('原采样率与声道',int(a['sample_rate'])==tm['sample_rate'] and a['channels']==tm['channels'],[a['sample_rate'],a['channels']])
    if tm.get('protected_source_intervals'):
        intact=not any(u<b and v>a for u,v in tm['compressed_gaps'] for a,b in tm['protected_source_intervals'])
        check('2022低电平信号保护段完整保留',intact,tm['protected_source_intervals'])
    decoded=out/'decoded.wav';subprocess.run(['ffmpeg','-y','-v','error','-i',str(mp4),'-vn','-c:a','pcm_f32le',str(decoded)],check=True)
    y,sr=sf.read(decoded,dtype='float32',always_2d=True)
    ref,sr2=sf.read(out/'audio'/tm['file'],dtype='float32',always_2d=True)
    if sr==sr2 and y.shape[1]==ref.shape[1]:
        offset=round(LEAD*sr);end=round(tm['sentences'][-1]['end']*sr)
        bad,measure=compare_audio(ref[offset:end],y[offset:end],sr)
        check('原声逐样本核对',not bad,bad or measure)
        check('片头1.5秒静音',np.abs(y[:max(1,offset-round(.03*sr))]).max()<.001,'1.5秒')
        # 源窗口可含末句后的呼吸声；只要求真正追加的2.2秒数字静音。
        source=json.loads((out/'prepared.json').read_text())
        body_samples=sum(round(b*sr)-round(a*sr) for a,b in tm['kept_intervals'])
        tail=offset+body_samples+round(.05*sr)
        check('片尾至少2秒静音',len(y)-offset-body_samples>=2*sr and np.abs(y[tail:]).max()<.001,'至少2秒')
    s=json.loads((out/'states.json').read_text());bound=[x[0] for x in s]+[frames]
    item,ok,detail=m.frame_check(mp4,bound,[out/'shots'/(x[1]+'.png') for x in s]);check(item,ok,detail)
    check('成品附件大小',0<mp4.stat().st_size<1900*2**20,mp4.stat().st_size)
    result={'id':p['id'],'ok':all(r['ok'] for r in checks),'draft':draft,'checks':checks,'sha256':sha(mp4),'bytes':mp4.stat().st_size,
            'fingerprint':fingerprint(m,p,tm),'source_sha256':tm['source_sha256'],'duration':tm['duration'],'mode':'原音不动',
            'protected_source_intervals':tm.get('protected_source_intervals',[]),'audio_protection':tm.get('audio_protection')}
    dump(out/('preview-verification.json' if draft else 'verification.json'),result);decoded.unlink()
    assert result['ok'],'成品独立核验未通过：'+str([r for r in checks if not r['ok']])
    return result


def encode(m,p,tm,out,input_file,draft=False):
    validate(json.loads(Path(input_file).read_text('utf-8')),draft)
    assert draft or not json.loads((out/'prepared.json').read_text())['draft'],'未审预览不得生成正式成品'
    cached_check(m,p,tm,out)
    if not draft:
        approval=json.loads((out/'approved-screens.json').read_text())
        assert approval['fingerprint']==fingerprint(m,p,tm) and approval['screens_sha256']==sha(out/'screens.json'),'缺少当前截图核对登记'
    s=json.loads((out/'states.json').read_text());frames=round(tm['duration']*FPS)
    # concat解析器使用引号；拒绝无法无歧义表示的工作路径。
    assert "'" not in str(out)
    rows=[]
    for (a,key),b in zip(s,[x[0] for x in s[1:]]+[frames]):
        assert b>a;rows.append(f"file '{out/'shots'/(key+'.png')}'\nduration {(b-a)/FPS:.9f}")
    rows += [f"file '{out/'shots'/(s[-1][1]+'.png')}'\nduration 1",f"file '{out/'shots'/(s[-1][1]+'.png')}'"]
    listing=out/'concat.txt';listing.write_text('\n'.join(rows)+'\n')
    mp4=out/(('技术预览_译注未定稿_' if draft else '')+m.video_name(p))
    subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-i',str(out/'audio'/tm['file']),
                    '-fps_mode','cfr','-r',str(FPS),'-frames:v',str(frames),'-c:v','libx264','-preset','veryfast','-tune','stillimage',
                    '-crf','18','-threads',os.environ.get('TEM8_THREADS','2'),'-pix_fmt','yuv420p','-g','900','-x264-params','scenecut=0',
                    '-c:a','aac','-b:a','192k','-movflags','+faststart',str(mp4)],check=True)
    r=verify(m,p,tm,out,mp4,draft)
    if draft:
        print(f'{p["id"]}: 仅技术预览（未定稿，不得发布） {mp4}',flush=True)
        return
    dump(out/'meta.json',{'id':p['id'],'year':p['year'],'kind':'text','mp4':mp4.name,'label':mp4.name,
                         'mp4_bytes':r['bytes'],'mp4_sha256':r['sha256'],'原音_sha256':tm['source_sha256'],
                         'input_sha256':sha(input_file),'fingerprint':r['fingerprint'],'成品核查':'全部通过',
                         '原音保护登记_sha256':(tm.get('audio_protection') or {}).get('registration_sha256')})
    print(f'{p["id"]}: 正式成品核验通过 {mp4}',flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path);ap.add_argument('action',choices=['prepare','audio','precheck','stills','approve','video','preview','verify','all'])
    ap.add_argument('--original',type=Path);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--draft',action='store_true');ap.add_argument('--autosplit',action='store_true')
    ap.add_argument('--review-note',help='approve或all的实际截图核对依据，不能留空')
    ap.add_argument('--browser',default=os.environ.get('TEM8_BROWSER') or shutil.which('chromium') or '/opt/pw-browsers/chromium')
    args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if args.action=='preview':assert args.draft,'技术预览必须显式--draft'
    if args.action in ['prepare','audio','precheck','all']:
        assert args.original,'本阶段必须指定--original'
        d,p,tm=compile_input(args.input,args.original,out,args.draft)
    else:d,p,tm=read_prepared(out,args.input,args.draft)
    if args.action=='prepare':return
    if args.action in ['audio','precheck','all']:audio_check(out,tm)
    if args.action=='audio':return
    # 本机与Actions共用HTTP预览，浏览器不必开放file://访问。
    helper=load_module('tem8_http_preview',ROOT/'高考听力/精读/tools/本机预览.py')
    helper.enable([ROOT,out,Path(tempfile.gettempdir())],args.browser)
    m=engine(out)
    if args.autosplit and args.action in ['precheck','all']:autosplit(m,p,out)
    if args.action in ['precheck','stills','all']:stills(m,p,tm,out,args.browser)
    if args.action in ['approve','all']:approve(m,p,tm,out,args.review_note)
    if args.action in ['video','all']:encode(m,p,tm,out,args.input)
    if args.action=='preview':encode(m,p,tm,out,args.input,True)
    if args.action=='verify':verify(m,p,tm,out,out/m.video_name(p))


if __name__=='__main__':main()
