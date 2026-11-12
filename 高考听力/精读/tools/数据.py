"""把人工定稿与译注编译成共用排版数据和原音时间，不自动清空待核。"""
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import struct
import sys
import unicodedata

HERE = Path(__file__).resolve().parent
C = HERE.parent
P = C.parent
ROOT = P.parent
LEAD, TAIL, FPS = 1.5, 2.2, 30
TOKEN = re.compile(r"[A-Za-zÀ-ÿ0-9]+(?:['’][A-Za-z]+)?")


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def dump(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    temp.replace(path)


def write_float_wav(path, samples, sample_rate):
    """标准IEEE-float WAV；不写libsndfile带当前时间的PEAK块，跨进程字节可复现。"""
    import numpy as np
    data=np.ascontiguousarray(samples,dtype='<f4')
    assert data.ndim==2 and 0<data.shape[1]<=8
    n,channels=data.shape;size=data.nbytes
    assert size+48<2**32,'WAV超过RIFF上限'
    with open(path,'wb') as f:
        f.write(struct.pack('<4sI4s',b'RIFF',size+48,b'WAVE'))
        f.write(struct.pack('<4sIHHIIHH',b'fmt ',16,3,channels,sample_rate,
                            sample_rate*channels*4,channels*4,32))
        f.write(struct.pack('<4sII',b'fact',4,n))
        f.write(struct.pack('<4sI',b'data',size))
        f.write(memoryview(data).cast('B'))


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower().replace('’', "'"))
                   if not unicodedata.combining(c))


def sentence_asr(sid, sentence, primary, source_hash):
    name = sentence.get('asr_source')
    if not name:
        return primary
    folder = C/'准备'/sid
    path = (folder/name).resolve()
    assert path.is_relative_to(folder.resolve()) and path.suffix=='.json', '补识别路径不合法'
    extra = json.loads(path.read_text('utf-8'))
    assert extra['原音_sha256']==source_hash and extra['模型']=='sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8', '补识别来源不符'
    assert extra.get('encoder_sha256') and extra.get('窗口'), '补识别缺少模型和窗口证据'
    return extra['words']


def load_text(sid, draft=False):
    os.environ['ZB_ROOT'] = str(C)
    sys.path.insert(0, str(ROOT / '专八/tools'))
    import ann_lib as A
    d = json.loads((C / '定稿' / f'{sid}.json').read_text('utf-8'))
    papers = json.loads((P / '套.json').read_text('utf-8'))
    assert d['id'] == sid and sid in papers
    raw_sha = (P / '识别' / papers[sid]['识别'] / '原音.sha256').read_text().split()[0]
    assert raw_sha == d['source_hash'], f'{sid} 原音来源不符'
    if d.get('待核') and not draft:
        raise ValueError(f'{sid} 还有{len(d["待核"])}项待核，禁止生成正式成品')
    sents = d['sentences']
    assert sents, f'{sid} 空原文'
    R = {sid: {'id': sid, 'sents': [[s['en'] for s in sents]]}}
    annfile = C / 'ann' / f'{sid}.txt'
    e, t, n = A.check(sid, annfile, R)
    if e or t:
        raise ValueError(f'{sid} 标注硬检查：' + '；'.join(e+t))
    meta, ann = A.parse(str(annfile))
    assert sorted(ann) == list(range(1, len(sents)+1)), '句号与原文不一致'
    aw = json.loads((C / '准备' / sid / '识别.json').read_text())
    result = []
    last_indices, last_start = {}, -1.0
    for k, s in enumerate(sents, 1):
        a, b = s['asr_range']
        key=s.get('asr_source','识别.json')
        current=sentence_asr(sid,s,aw,d['source_hash'])
        assert 0 <= a < b <= len(current) and a >= last_indices.get(key,-1), f'{sid}:{k} ASR范围倒序/重叠'
        assert abs(s['start']-current[a][1]) < .011 and abs(s['end']-current[b-1][2]) < .011, f'{sid}:{k} 秒数不来自真实ASR'
        assert s['start'] >= last_start and s['end'] > s['start'], f'{sid}:{k} 时间倒序'
        last_indices[key], last_start = b, s['start']
        taken, words = [], []
        for w in sorted(ann[k]['w'], key=lambda w: -len(w['h'])):
            sp = A.find(w, s['en'], taken)
            assert sp, f'{sid}:{k} 词条不能高亮：{w}'
            taken += sp
            words.append({'t': w['t'], 'h': w['h'], 'm': w['m'], 'sp': sp})
        result.append({'en': s['en'], 'zh': ann[k]['zh'], 'w': words})
    y, paper = papers[sid]['名'].split(' ', 1)
    p = {'id': sid, 'year': int(y), 'month': 0, 'set': 1, 'part': 'L',
         'paper_title': f'{y}年 {paper}', 'paper': f'{y}年 {paper} 高考英语真题',
         'passage': 'Original Text', 'title': '原文精读', 'genre': meta.get('G', ''),
         'summary': meta.get('S', ''), 'done': True, 'nv': n,
         'names': d.get('names', []),
         'words': sum(len(TOKEN.findall(s['en'])) for s in sents), 'paras': [result]}
    return d, p, aw


def word_alignment(s, raw, cut):
    en = [(m.group(), m.start(), m.end()) for m in TOKEN.finditer(s['en'])]
    ar = [(m.group(), a, b) for w, a, b in raw for m in TOKEN.finditer(w)]
    sm = difflib.SequenceMatcher(None, [norm(x[0]) for x in en], [norm(x[0]) for x in ar], autojunk=False)
    matched = {}
    for block in sm.get_matching_blocks():
        for j in range(block.size):
            matched[block.a+j] = block.b+j
    out = []
    for i, (_, char0, char1) in enumerate(en):
        if i in matched:
            at = matched[i]
        elif len(en) == len(ar):
            at = i  # 同音/拼写订正，词序及词数相同；仍使用原始词的时间。
        else:
            near = min(matched, key=lambda j: abs(j-i)) if matched else None
            if near is None or abs(near-i) > 3:
                raise ValueError(f'无法给字幕词定位：{s["en"]} / {en[i][0]}')
            at = max(0, min(len(ar)-1, matched[near]+i-near))
        out.append({'char': char0, 'char_end': char1,
                    'start': max(LEAD, ar[at][1]-cut+LEAD), 'end': max(LEAD, ar[at][2]-cut+LEAD)})
    return out


def prepare(sid, original, out, draft=False):
    import numpy as np
    import soundfile as sf
    d, p, aw = load_text(sid, draft)
    if sha(original) != d['source_hash']:
        raise ValueError('原声文件SHA-256不符')
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    wav = out / 'source.wav'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(original), '-map', '0:a:0', '-c:a', 'pcm_f32le', str(wav)], check=True)
    x, sr = sf.read(wav, dtype='float32', always_2d=True)
    cut = float(d['cut'])
    # 沿用精读原音音轨的内容窗口：完整保留正文范围的原声，尾部原声水印不属于原文。
    content_end = min(len(x)/sr, d['sentences'][-1]['end']+.30)
    first = max(0, round(cut*sr)); last = min(len(x), round(content_end*sr))
    ref = x[first:last]
    assert len(ref) > sr and np.abs(ref).max() <= 1
    duration = math.ceil((LEAD+len(ref)/sr+TAIL)*FPS)/FPS
    audio = np.zeros((round(duration*sr), x.shape[1]), np.float32)
    k0 = round(LEAD*sr); audio[k0:k0+len(ref)] = ref
    target = C / 'audio' / f'{sid}.wav'
    target.parent.mkdir(exist_ok=True)
    write_float_wav(target,audio,sr)
    hop = max(1, round(sr*.01)); mono = audio.mean(axis=1)
    n = len(mono)//hop
    db = 10*np.log10((mono[:n*hop].reshape(n, hop)**2).mean(axis=1)+1e-12)
    floor = float(np.percentile(db[round(LEAD*100):round((duration-TAIL)*100)], 10))
    threshold = max(floor+12, -50)
    times = []
    for i, s in enumerate(d['sentences']):
        start, end = max(LEAD, s['start']-cut+LEAD), s['end']-cut+LEAD
        # 只细化显示边界，原音样本不改；补回ASR几十毫秒的起止误差。
        lo = max(LEAD, start-.12)
        hi = min(duration-TAIL, end+.15)
        before = d['sentences'][i-1]['end']-cut+LEAD if i else LEAD
        after = d['sentences'][i+1]['start']-cut+LEAD if i+1<len(d['sentences']) else duration-TAIL
        a = max(lo, min(start, before)); b = min(hi, max(end, after))
        a0, b0 = max(0, int(a*100)), min(len(db), int(b*100))
        parts, run, seg = [], None, a0
        for q in range(a0, b0):
            if db[q] <= threshold:
                if run is None: run = q
            else:
                if run is not None and q-run >= 15 and run > seg:
                    parts.append([seg/100, run/100]); seg = q
                run = None
        parts.append([seg/100, b0/100])
        times.append({'k': i+1, 'para': 1, 'start': a, 'end': b, 'orig': [a-LEAD+cut, b-LEAD+cut],
                      'text': s['en'], 'read': s['en'], 'parts': parts,
                      'word_alignment': word_alignment(s, sentence_asr(sid,s,aw,d['source_hash'])[s['asr_range'][0]:s['asr_range'][1]], cut)})
    tm = {'file': f'{sid}.wav', 'source': '原音', 'mode': '原音不动', 'duration': duration,
          'sample_rate': sr, 'channels': x.shape[1], 'source_sha256': d['source_hash'],
          'window': [cut, last/sr], 'audio_sha256': sha(target), 'sentences': times}
    for f, key, value in [(C/'data/vocab.json', 'passages', p), (C/'阅读/sents.json', None, {
        **{k:p[k] for k in ['id','year','month','set','passage','paper','part']}, 'sents': [[s['en'] for s in d['sentences']]]})]:
        if key:
            old = json.loads(f.read_text()) if f.exists() else {key: []}
            rows = {r['id']:r for r in old[key]}; rows[sid] = value; old[key] = list(rows.values()); dump(f, old)
        else:
            old = json.loads(f.read_text()) if f.exists() else []
            rows = {r['id']:r for r in old}; rows[sid] = value; dump(f, list(rows.values()))
    tf = C/'audio/timings.json'
    old = json.loads(tf.read_text()) if tf.exists() else {'cet4_male': {}}
    old['cet4_male'][sid] = tm; dump(tf, old)
    nf = HERE/'人名.json'; names = json.loads(nf.read_text())['names'] if nf.exists() else []
    dump(nf, {'names': sorted(set(names)|set(d.get('names', [])))})
    dump(out/'prepared.json', {'id':sid,'sentences':len(times),'entries':p['nv'],'duration':duration,
                              'source_sha256':d['source_hash'],'audio_sha256':tm['audio_sha256'],
                              'draft':bool(d.get('待核')),'window':tm['window']})
    print(f'{sid}: {len(times)}句 / {p["nv"]}词条 / {duration:.2f}秒，原声{sr}Hz {x.shape[1]}声道')
    return d, p, tm
