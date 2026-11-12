"""把实际跨组语义复核锁到英文定稿与译注文件；程序硬检查不能代替这项登记。"""
import argparse
import json
from pathlib import Path
from 数据 import C, sha, dump, load_text

REG = C/'ann/复核通过.json'


def current(sid):
    return {'定稿_sha256':sha(C/'定稿'/f'{sid}.json'),
            '译注_sha256':sha(C/'ann'/f'{sid}.txt')}


def check(sid):
    load_text(sid)
    from 覆盖检查 import check as coverage_check
    coverage_check(sid)
    entries=json.loads(REG.read_text()) if REG.exists() else {}
    row=entries.get(sid,{})
    assert row.get('审校人') and row.get('复核依据'),f'{sid} 缺少跨组语义审校登记'
    assert all(row.get(k)==v for k,v in current(sid).items()),f'{sid} 审校后定稿/译注已变'
    for e in row['复核依据']:
        path=C/e['file']
        assert path.is_relative_to(C) and path.exists() and sha(path)==e['sha256'],f'{sid} 复核证据已变'
    return row


def record(sid, reviewer, evidence):
    load_text(sid)
    records=json.loads(REG.read_text()) if REG.exists() else {}
    files=[]
    for f in evidence:
        f=Path(f).resolve()
        files.append({'file':str(f.relative_to(C)),'sha256':sha(f)})
    assert files and reviewer
    records[sid]={**current(sid),'审校人':reviewer,'复核依据':files}
    dump(REG,records);check(sid)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('sid',nargs='+');ap.add_argument('--reviewer');ap.add_argument('--evidence',nargs='+',type=Path)
    a=ap.parse_args()
    for sid in a.sid:
        if a.reviewer:record(sid,a.reviewer,a.evidence)
        else:check(sid)
    print(f'{len(a.sid)}套语义复核登记与当前定稿一致')
