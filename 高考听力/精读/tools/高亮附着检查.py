"""编号不能插入英语缩约词或所有格中间；截图前先按实际高亮位置全查。"""
import argparse
import re
from 数据 import C,load_text


def problems(sentence):
    en=sentence['en'];out=[]
    for w in sentence['w']:
        for a,b in w['sp']:
            tail=en[b:]
            contraction=re.match(r"['’](?:t|m|re|ve|ll|d)(?![A-Za-z])",tail)
            ascii_s=re.match(r"'s(?![A-Za-z])",tail)
            plural=(tail.startswith("'") and en[a:b].endswith('s') and
                    (len(tail)==1 or not tail[1].isalpha()) and '‘' not in en[:a])
            if contraction or ascii_s or plural:
                out.append(f"{w['h']}的编号会把附着撇号/缩约词隔开：{en[a:min(len(en),b+5)]}")
    return out


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('sid',nargs='*');args=ap.parse_args()
    ids=args.sid or [p.stem for p in sorted((C/'定稿').glob('*.json'))]
    errors=[]
    for sid in ids:
        _,p,_=load_text(sid)
        for k,s in enumerate(p['paras'][0],1):errors.extend(f'{sid}:{k} {e}' for e in problems(s))
    assert not errors,'\n'.join(errors)
    print(f'{len(ids)}套：缩约词/所有格高亮与编号附着位置全部通过')
