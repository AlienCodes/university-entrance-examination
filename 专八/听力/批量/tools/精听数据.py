"""历年专八精听的数据契约及原声编译；不更改2025、共享引擎或原始录音。"""
from __future__ import annotations
import copy
import difflib
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
ROOT = BATCH.parents[2]
LEAD, TAIL, FPS = 1.5, 2.2, 30
TOKEN = re.compile(r"[A-Za-zÀ-ÿ0-9]+(?:['’][A-Za-z]+)?")


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def dump(path, value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')


def content_sha(d):
    p=copy.deepcopy(d);p.pop('review',None)
    return hashlib.sha256(json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def validate(d, draft=False):
    assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',d['id'])
    assert 2009<=d['year']<=2025 and d['title'].strip() and d['section'].strip()
    assert not re.search(r'[/\\:*?"<>|]',d['section']),'Section名称不可包含文件路径字符'
    assert not d.get('待核') or draft,'仍有待核项，不得制作正式成品'
    assert re.fullmatch('[0-9a-f]{64}',d['audio']['sha256'])
    lo,hi=d['audio']['window'];assert 0<=lo<hi
    assert d['sentences']
    previous=lo
    for i,s in enumerate(d['sentences'],1):
        assert s['en'].strip() and re.search('[一-鿿]',s['zh']),f'第{i}句缺英文/中文'
        assert lo<=s['start']<s['end']<=hi,f'第{i}句不在正文窗口'
        assert previous<=s['start'],f'第{i}句时间不递增'
        previous=s['start']
        assert s['w'],f'第{i}句词汇栏为空'
        occupied=[]
        for w in s['w']:
            assert w['t'] in ('core','word','phr') and w['h'].strip() and w['m'].strip()
            assert w.get('sp'),f'第{i}句词条缺高亮位置：{w["h"]}'
            for a,b in w['sp']:
                assert 0<=a<b<=len(s['en'])
                assert all(b<=x or a>=y for x,y in occupied),f'第{i}句高亮重叠'
                occupied.append((a,b))
    if not draft:
        r=d.get('review',{})
        assert r.get('status')=='approved' and r.get('content_sha256')==content_sha(d),'缺少当前内容的译注审校登记'
    return d


def align_words(s):
    """只接受词时刻的真实对应；不将不明词按整句比例分配时间。"""
    if s.get('word_alignment'):
        out=copy.deepcopy(s['word_alignment'])
    elif s.get('words'):
        tokens=list(TOKEN.finditer(s['en']))
        words=[(m.group(),a,b) for w,a,b in s['words'] for m in TOKEN.finditer(w)]
        norm=lambda x:re.sub(r'[^a-z0-9]','',x.lower().replace('’',"'"))
        sm=difflib.SequenceMatcher(None,[norm(m.group()) for m in tokens],[norm(w) for w,_,_ in words],autojunk=False)
        match={}
        for block in sm.get_matching_blocks():
            for j in range(block.size):match[block.a+j]=block.b+j
        # OCR/拼写订正一对一、词数不变时才准按原词下标对应。
        if len(tokens)==len(words):
            for j in range(len(tokens)):match.setdefault(j,j)
        assert len(match)==len(tokens),'原文与逐词时刻存在无法核定的差异：'+s['en']
        out=[{'char':m.start(),'char_end':m.end(),'start':words[match[j]][1],'end':words[match[j]][2]} for j,m in enumerate(tokens)]
    else:
        return []
    for w in out:
        assert 0<=w['char']<w['char_end']<=len(s['en'])
        assert s['start']-.15<=w['start']<w['end']<=s['end']+.15
    assert all(a['start']<=b['start'] for a,b in zip(out,out[1:]))
    return out


def first_aligned_word(aligned,en,cut):
    """换屏必须绑定这一屏真正的首词；缺词时不可悄悄跳到后面一个词。"""
    token=TOKEN.search(en,cut)
    assert token,'分屏切点后没有英文词：'+en[cut:]
    later=[w for w in aligned if w['char']>=token.start()]
    assert later and later[0]['char']==token.start(),'分屏首词缺少真实对齐：'+token.group()+'；须核准词时刻，不能跳过首词'
    return later[0]


def float_wav(path,x,sr):
    """不带时间相关PEAK块的IEEE FLOAT WAV，原采样率/声道/样本值。"""
    import numpy as np
    x=np.ascontiguousarray(x,dtype='<f4');n,ch=x.shape;size=x.nbytes
    assert 0<ch<=8 and size+48<2**32
    with open(path,'wb') as f:
        f.write(struct.pack('<4sI4s',b'RIFF',size+48,b'WAVE'))
        f.write(struct.pack('<4sIHHIIHH',b'fmt ',16,3,ch,sr,sr*ch*4,ch*4,32))
        f.write(struct.pack('<4sII',b'fact',4,n))
        f.write(struct.pack('<4sI',b'data',size));f.write(memoryview(x).cast('B'))


PROTECTION_2022=BATCH/'核验/2022-停顿边界复核.json'


def audio_protection(d):
    """只采用与2022实际源SHA绑定的已核三段信号；其余14年不套用。"""
    if d['year']!=2022:
        assert not d.get('audio',{}).get('protected_source_intervals'),'非2022不可套用2022信号登记'
        return [],None
    assert PROTECTION_2022.exists(),'2022缺原音等待信号保护登记，不可尝试静音压缩'
    r=json.loads(PROTECTION_2022.read_text('utf-8'))
    source=d['audio']['sha256']
    canonical=r['consumer_contract']['apply_only_if_canonical_sha256_matches']
    encoded=r.get('source_encoded_sha256')
    assert source in [canonical,encoded],'2022原音SHA与低电平信号保护登记不符；须先核定新源'
    assert r['signal_handling']['pure_silence_compression_allowed'] is False
    assert r['signal_handling']['preserve_entire_wait_audio'] is True
    register=r.get('machine_override') or r.get('pauses_override')
    protected=[list(map(float,register[key])) for key in ['previewA','check','previewB']]
    assert all(0<=a<b<=r['canonical']['duration'] for a,b in protected)
    declared=d['audio'].get('protected_source_intervals')
    if declared is not None:assert declared==protected,'2022输入中的保护段与源登记不一致'
    evidence={'registration':str(PROTECTION_2022.relative_to(BATCH)),
              'registration_sha256':sha(PROTECTION_2022),'source_sha256':source,
              'canonical_sha256':canonical,'protected_source_intervals':protected,
              'reason':'2022三段等待内含已核低电平周期性非语音信号，完整保留，不能当作纯静音删减。'}
    return protected,evidence


def compact(x,sr,lo,hi,sentences,protected=()):
    """只删除句间超过2秒的低电平纯静音中段；每句内的语音与停顿全部保留。"""
    import numpy as np
    a,b=round(lo*sr),round(hi*sr)
    assert 0<=a<b<=len(x)
    removed=[];kept_gaps=[]
    for previous,current in zip(sentences,sentences[1:]):
        left,right=previous['end'],current['start']
        if right-left<=2.02:continue
        u,v=round((left+1)*sr),round((right-1)*sr)
        if any(u/sr<b and v/sr>a for a,b in protected):
            kept_gaps.append({'interval':[left,right],'reason':'源SHA绑定的低电平信号保护段，完整保留','protected':True})
            continue
        middle=x[u:v];hop=max(1,round(.01*sr));n=len(middle)//hop
        if n==0:continue
        rms=np.sqrt((middle[:n*hop].astype('float64').reshape(n,hop,x.shape[1])**2).mean(axis=(1,2)))
        # 保守判纯静音：任何10ms帧高于-50dBFS或峰值高于-35dBFS都保留原段。
        if rms.max()<=10**(-50/20) and np.abs(middle).max()<=10**(-35/20):removed.append((u,v))
        else:kept_gaps.append([left,right])
    assert all(a<=u<v<=b for u,v in removed)
    assert all(v<=u2 for (_,v),(u2,_) in zip(removed,removed[1:]))
    intervals=[];cursor=a
    for u,v in removed:
        intervals.append((cursor,u));cursor=v
    intervals.append((cursor,b))
    body=np.concatenate([x[u:v] for u,v in intervals],axis=0)
    def mapping(t):
        sample=round(t*sr)
        assert a<=sample<=b,'字幕词时刻超出正文窗口'
        assert not any(u<sample<v for u,v in removed),'字幕时刻落进删除的静音内'
        return LEAD+(sample-a-sum(v-u for u,v in removed if v<=sample))/sr
    return body,mapping,intervals,removed,kept_gaps


def compile_input(input_file,original,out,draft=False):
    import numpy as np
    import soundfile as sf
    d=validate(json.loads(Path(input_file).read_text('utf-8')),draft)
    assert sha(original)==d['audio']['sha256'],'原声SHA-256不符'
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    source=out/'source.wav'
    subprocess.run(['ffmpeg','-y','-v','error','-i',str(original),'-map','0:a:0','-c:a','pcm_f32le',str(source)],check=True)
    x,sr=sf.read(source,dtype='float32',always_2d=True)
    assert np.isfinite(x).all()
    lo,hi=d['audio']['window']
    protected,protection=audio_protection(d)
    body,warp,intervals,removed,kept=compact(x,sr,lo,hi,d['sentences'],protected)
    assert not any(u/sr<b and v/sr>a for u,v in removed for a,b in protected),'已核低电平信号保护段被静音压缩'
    duration=math.ceil((LEAD+len(body)/sr+TAIL)*FPS)/FPS
    result=np.zeros((round(duration*sr),x.shape[1]),dtype='float32')
    lead=round(LEAD*sr);result[lead:lead+len(body)]=body
    for folder in ['audio','data','阅读','tools/画面核查']:(out/folder).mkdir(parents=True,exist_ok=True)
    audio=out/'audio/原音.wav';float_wav(audio,result,sr)
    assert np.array_equal(result[lead:lead+len(body)],body),'原声样本发生改变'
    flat=[];times=[]
    for i,s in enumerate(d['sentences'],1):
        flat.append({k:copy.deepcopy(s[k]) for k in ['en','zh','w']})
        aa=align_words(s)
        start,end=warp(s['start']),warp(s['end'])
        aligned=[{**w,'start':warp(w['start']),'end':warp(w['end'])} for w in aa]
        # 留存真实句中停顿，用于语义分屏候选；不修改声波。
        segment=result[round(start*sr):round(end*sr)].mean(axis=1)
        hop=max(1,round(.01*sr));n=len(segment)//hop
        energy=10*np.log10((segment[:n*hop].reshape(n,hop).astype('float64')**2).mean(axis=1)+1e-12) if n else np.array([])
        threshold=max(-60,min(-40,float(np.percentile(energy,10))+12)) if n else -50
        parts=[];run=None;cursor=start
        for j,v in enumerate(energy):
            if v<=threshold:
                if run is None:run=j
            elif run is not None:
                if j-run>=15 and start+run/100>cursor:
                    parts.append([cursor,start+run/100]);cursor=start+j/100
                run=None
        parts.append([cursor,end])
        times.append({'k':i,'para':1,'start':start,'end':end,'orig':[s['start'],s['end']],
                      'text':s['en'],'read':s['en'],'parts':parts,'word_alignment':aligned})
    p={'id':d['id'],'year':d['year'],'month':0,'set':1,'part':'L','paper':f"{d['year']}年专八听力",
       'passage':d['section'],'title':d['title'],'genre':d.get('genre','听力原文'),'summary':d.get('summary',''),
       'done':True,'words':sum(len(TOKEN.findall(s['en'])) for s in flat),'nv':sum(len(s['w']) for s in flat),'paras':[flat]}
    tm={'file':'原音.wav','source':'原音','mode':'原音不动','duration':duration,'sample_rate':sr,'channels':x.shape[1],
        'source_sha256':d['audio']['sha256'],'audio_sha256':sha(audio),'window':[lo,hi],'kept_intervals':[[u/sr,v/sr] for u,v in intervals],
        'compressed_gaps':[[u/sr,v/sr] for u,v in removed],'kept_gaps':kept,'sentences':times,
        'protected_source_intervals':protected,'audio_protection':protection}
    dump(out/'data/vocab.json',{'passages':[p]});dump(out/'audio/timings.json',{'cet4_male':{d['id']:tm}})
    dump(out/'tools/人名.json',{'names':d.get('names',[])})
    dump(out/'tools/分屏_水墨.json',{d['id']:d.get('splits',{})})
    dump(out/'prepared.json',{'input_sha256':sha(input_file),'content_sha256':content_sha(d),'draft':draft,
                              'id':d['id'],'source_sha256':tm['source_sha256'],'audio_sha256':tm['audio_sha256'],
                              'source_window':[lo,hi],'compressed_gaps':tm['compressed_gaps'],'kept_gaps':kept,
                              'protected_source_intervals':protected,'audio_protection':protection})
    return d,p,tm
