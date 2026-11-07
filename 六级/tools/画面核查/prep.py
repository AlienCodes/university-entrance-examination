"""For each finished video: extract screens, write reference file, check screen count = 1 + sentences + splits.
python prep.py s01 s02 ..."""
import json, subprocess, sys
from pathlib import Path
R = Path('/home/user/university-entrance-examination')
S = Path('/tmp/claude-0/-home-user/8ecea899-aaa9-5a52-878f-ec29bb403c87/scratchpad/cet6/frames')
sys.path.insert(0, str(R / '六级' / 'tools'))
import make_video as M
P = {p['id']: p for p in json.loads((R / '六级' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
REF = S / 'ref'
REF.mkdir(exist_ok=True)
subprocess.run(['/opt/ttsenv/bin/python', str(R / '六级' / 'tools' / 'gen_review.py'), str(REF)], check=True, capture_output=True)
bad = []
for pid in sys.argv[1:]:
    p = P[pid]
    mp4 = R / '六级' / '最终视频' / M.video_name(p)
    sents = [s for pa in p['paras'] for s in pa]
    splits = M.SPLIT.get(pid, {})
    want = 1 + len(sents) + len(splits)
    got = int(subprocess.run(['/opt/ttsenv/bin/python', str(S / 'extract.py'), str(mp4), str(S / pid)], check=True, capture_output=True, text=True).stdout)
    ref = REF / f'{pid}.txt'
    extra = [f'\n# 视频画面结构：第 1 屏是片头（标题、试卷、篇目、体裁、词数），之后每句一屏，共 {len(sents)} 句；预期屏数 {want}。']
    for k, sp in sorted(splits.items(), key=lambda x: int(x[0])):
        extra.append(f'# 第 {k} 句分成两屏：第二屏英文从 “{sp["at"]}” 开始；两屏中文分别是：「{sp["zh"][0]}」「{sp["zh"][1]}」')
    ref.write_text(ref.read_text('utf-8') + '\n'.join(extra) + '\n', 'utf-8')
    print(pid, 'screens', got, 'expected', want, 'OK' if got == want else 'MISMATCH', flush=True)
    if got != want:
        bad.append(pid)
print('mismatch:', bad)
