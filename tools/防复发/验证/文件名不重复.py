"""踩坑 11：成品文件名不许重复（verify_videos.duplicate_names，各项目 verify_all 调用）。
埋雷：两篇同名必须报出；各项目真实数据（按各自 verify_all 的 video_name）必须 0 处重名。每个项目在单独的进程里跑（各项目 make_video 互不相同）。"""
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / 'tools' / 'video'))
from verify_videos import duplicate_names  # noqa: E402

mine = duplicate_names([{'id': 'a', 'n': '2026 天津卷 阅读C x'}, {'id': 'b', 'n': '2026 天津卷 阅读C x'}, {'id': 'c', 'n': 'y'}], lambda p: p['n'])
ok = mine == {'2026 天津卷 阅读C x': ['a', 'b']}
print(f"埋雷：{'报出' if ok else '没报出'}重名 {mine}")
CHILD = r'''
import json, sys
from pathlib import Path
f = Path(sys.argv[1]); src = f.read_text('utf-8')
ns = {'__file__': str(f), '__name__': 'x'}
exec(compile(src.split('def main')[0], str(f), 'exec'), ns)
C = ns.get('C4') or ns.get('C6') or f.resolve().parent.parent
P = json.loads((Path(C) / 'data' / 'vocab.json').read_text('utf-8'))['passages']
P = [p for p in P if p.get('done', True)]
print('DUP', json.dumps(ns['duplicate_names'](P, ns['video_name']), ensure_ascii=False), len(P))
'''
for proj in ['专八', '考研', '考研作文', '六级', '四级', '中考']:
    r = subprocess.run(['/opt/ttsenv/bin/python', '-c', CHILD, str(R / proj / 'tools' / 'verify_all.py')], cwd=R, capture_output=True, text=True,
                       env={'PATH': '/usr/bin:/bin', 'DZB_VARIANT': '水墨' if proj == '专八' else '', 'HOME': '/root'})
    line = next((x for x in r.stdout.splitlines() if x.startswith('DUP')), None)
    good = bool(line) and line.split()[1] == '{}'
    ok &= good
    print(f"{'✅' if good else '❌'} {proj}：{line or r.stderr.strip()[-300:]}")
print('文件名不重复：双向通过' if ok else '文件名不重复：不通过')
sys.exit(0 if ok else 1)
