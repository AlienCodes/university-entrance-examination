"""真实首套原文回归；漏句/漏尾、错时间/来源、失效核定必须拦截；原声WAV可复现。"""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'高考听力/精读/tools'))
import 数据 as D
import 覆盖检查 as V


def rejects(fn):
    try:fn()
    except (AssertionError,ValueError):return
    raise AssertionError('错误输入未被门禁拦截')


with tempfile.TemporaryDirectory() as td:
    import numpy as np
    import soundfile as sf
    td=Path(td)
    x=(np.sin(np.arange(44100,dtype=np.float32)*.013)*.1)[:,None]
    x=np.concatenate((x,-x),axis=1)
    a,b=td/'a.wav',td/'b.wav'
    D.write_float_wav(a,x,44100);D.write_float_wav(b,x,44100)
    assert a.read_bytes()==b.read_bytes() and b'PEAK' not in a.read_bytes()[:100]
    y,sr=sf.read(a,dtype='float32',always_2d=True)
    assert sr==44100 and np.array_equal(x,y),'原采样率、声道或任何样本改变'
    sid='2023-shq';C=D.C;P=D.P
    case=td/'高考听力/精读';case.mkdir(parents=True)
    for rel in ['定稿/2023-shq.json','ann/2023-shq.txt','准备/2023-shq/识别.json',
                '准备/2023-shq/未收录核定.json']:
        dest=case/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(C/rel,dest)
    shutil.copyfile(P/'套.json',case.parent/'套.json')
    sets=json.loads((P/'套.json').read_text());raw=Path('识别')/sets[sid]['识别']/'原音.sha256'
    dest=case.parent/raw;dest.parent.mkdir(parents=True);shutil.copyfile(P/raw,dest)
    D.C=V.C=case;D.P=case.parent
    d,_,_=D.load_text(sid);assert len(d['sentences'])==175
    V.check(sid,d)
    for position in [0,57,-1]:
        bad=copy.deepcopy(d);bad['sentences'].pop(position)
        rejects(lambda:V.check(sid,bad))
    path=case/'定稿/2023-shq.json'
    bad=copy.deepcopy(d);bad['sentences'][30]['end']+=.1
    path.write_text(json.dumps(bad));rejects(lambda:D.load_text(sid))
    bad=copy.deepcopy(d);bad['source_hash']='0'*64
    path.write_text(json.dumps(bad));rejects(lambda:D.load_text(sid))
    path.write_text(json.dumps(d))
    decision=case/'准备/2023-shq/未收录核定.json'
    approved=json.loads(decision.read_text());approved['逐词_sha256']='0'*64
    decision.write_text(json.dumps(approved));rejects(lambda:V.check(sid,d))
    D.C=C;D.P=P;V.C=C
print('精读门禁通过：WAV字节稳定且样本无损；真实175句正常；漏首/中/尾句、改时间/原音/核定来源6类错误均拦截')
