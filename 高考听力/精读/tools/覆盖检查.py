"""逐词覆盖所有保留起点后的源ASR，尾部也检查；未收录的中文误识别须逐段有核定理由。"""
import json
from pathlib import Path
from 数据 import C, sha


def gaps(d, words):
    used=set()
    for s in d['sentences']:
        a,b=s['asr_range']
        if not s.get('asr_source'):
            used.update(range(a,b))
        else:
            used.update(i for i,(_,x,y) in enumerate(words)
                        if x>=s['start']-.30 and y<=s['end']+.30)
    groups=[]
    for i,(_,a,b) in enumerate(words):
        if a<d['cut']-.02 or i in used:continue
        if not groups or i>groups[-1][-1]+1:groups.append([i])
        else:groups[-1].append(i)
    return [{'range':[g[0],g[-1]+1],'start':words[g[0]][1],'end':words[g[-1]][2],
             'text':' '.join(words[i][0] for i in g)} for g in groups]


def check(sid, d=None):
    folder=C/'准备'/sid;source=folder/'识别.json'
    if d is None:d=json.loads((C/'定稿'/f'{sid}.json').read_text())
    words=json.loads(source.read_text());missing=gaps(d,words)
    if not missing:return []
    decision=folder/'未收录核定.json'
    assert decision.exists(),f'{sid} 有{len(missing)}段源词未收录且未核定，包含录音尾部'
    data=json.loads(decision.read_text())
    assert data['逐词_sha256']==sha(source) and data['原音_sha256']==d['source_hash'],f'{sid} 覆盖核定来源已变'
    assert data.get('审阅人') and data.get('完整检查至源ASR末尾') is True
    ignored=set()
    for row in data['例外']:
        a,b=row['range']
        assert row.get('理由') and 0<=a<b<=len(words)
        assert row['text']==' '.join(words[i][0] for i in range(a,b)),f'{sid} 核定词段内容不符'
        ignored.update(range(a,b))
    unresolved=[r for r in missing if not set(range(*r['range']))<=ignored]
    assert not unresolved,f'{sid} 仍有未解释词段：{unresolved}'
    return missing
