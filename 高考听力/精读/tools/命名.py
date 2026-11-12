"""精读视频中文标题与ASCII资产名；年份、卷别及场次置前。"""
import json
import re
from pathlib import Path

SETS=json.loads((Path(__file__).resolve().parents[2]/'套.json').read_text())
NAME_RE=r'^20\d\d年 \S+ 高考英语真题 原文精读\.mp4$'


def label(sid,kind='text'):
    y,paper=SETS[sid]['名'].split(' ',1)
    return f'{y}年 {paper} 高考英语真题 原文精读.mp4'


def asset(sid,kind='text'):
    return f'gaokao-text-{sid}.mp4'


def rank(sid):
    p=SETS[sid]['名']
    return (int(p[:4]),3 if '上海' in p else 2 if '江苏' in p else 1 if '浙江' in p else 0,p)


def order(items):
    return sorted(items,key=lambda x:rank(x[0]))


def problems(labels):
    bad=[f'中文文件名不符：{x}' for x in labels if not re.fullmatch(NAME_RE,x)]
    if len(set(labels))!=len(labels):bad.append('中文文件名重复')
    return bad
