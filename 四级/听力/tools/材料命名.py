"""给原始音频起 ASCII 名（发布 / Actions 用），写 原始材料/音频清单.json 和 SHA256SUMS。
顶层 30 个（老师给的“四级听力视频/audio files”）：t<年月>-<套>.mp3，按文件名标签；
内层合集（“解析 听力原文对照.zip”）里与顶层任何一个都不是同一段录音的：s<年月>-<套>.mp3。
文件名标签只是标签：哪段录音对应哪份试卷，由识别文字与试卷比对决定（对照表.py）。
用法：python3 材料命名.py 指纹.json 同录音.json 输出目录"""
import json, re, sys, os, shutil
from pathlib import Path
fp = {x['file']: x for x in json.load(open(sys.argv[1]))}
groups = json.load(open(sys.argv[2]))['groups']
out = Path(sys.argv[3]); out.mkdir(exist_ok=True)
def label(f):
    n = f.split('/')[-1]
    m = re.search(r'(20)?(\d\d)[年.](\d{1,2})月?', n)
    y, mo = '20' + m.group(2), int(m.group(3))
    k = re.search(r'第\s*(\d)\s*套', n)
    return f'{y}{mo:02d}-{k.group(1) if k else 1}'
items = []
for g in groups:
    tops = [f for f in g if '/audio files/' in f]
    inner = [f for f in g if '/audio files/' not in f]
    for f in tops:
        items.append({'id': 't' + label(f), 'file': f, 'same_as': [label(x) for x in inner]})
    if not tops:
        f = inner[0]
        items.append({'id': 's' + label(f), 'file': f, 'same_as': []})
ids = [x['id'] for x in items]
assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
assert sum(1 for i in ids if i[0] == 't') == 30, len(ids)
lines = []
for x in sorted(items, key=lambda x: x['id']):
    f = fp[x['file']]
    x.update({k: f[k] for k in ('sha256', 'bytes', 'sr', 'channels', 'bitrate', 'header_dur', 'decoded_dur', 'peak_db')})
    x['原名'] = x.pop('file').split('/', 1)[1]
    x['asset'] = f"cet4-{x['id']}.mp3"
    lines.append(f"{x['sha256']}  {x['asset']}")
    if len(sys.argv) > 4:
        shutil.copyfile(fp[[k for k in fp if k.endswith(x['原名'])][0]]['file'], Path(sys.argv[4]) / x['asset'])
items.sort(key=lambda x: x['id'])
(out / '音频清单.json').write_text(json.dumps(items, ensure_ascii=False, indent=1), 'utf-8')
(out / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
print(len(items), 'recordings')
