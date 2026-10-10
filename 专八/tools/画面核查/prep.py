"""For each finished TEM-8 video: extract screens, write reference file, check screen count = 1 + sentences + extra screens of splits.
/opt/ttsenv/bin/python 专八/tools/画面核查/prep.py <frames dir> t01 t02 ..."""
import json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
S = Path(sys.argv[1])
sys.path.insert(0, str(R / '专八' / 'tools'))
import make_video as M
P = {p['id']: p for p in json.loads((R / '专八' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
REF = S / 'ref'
REF.mkdir(parents=True, exist_ok=True)
subprocess.run(['/opt/ttsenv/bin/python', str(R / '专八' / 'tools' / 'gen_review.py'), str(REF)], check=True, capture_output=True)
bad = []
for pid in sys.argv[2:]:
    p = P[pid]
    mp4 = R / '专八' / '最终视频' / M.video_name(p)
    sents = [s for pa in p['paras'] for s in pa]
    splits = M.SPLIT.get(pid, {})
    ats = {k: (c['at'] if isinstance(c['at'], list) else [c['at']]) for k, c in splits.items()}
    want = 1 + len(sents) + sum(len(a) for a in ats.values())
    got = int(subprocess.run(['/opt/ttsenv/bin/python', str(HERE / 'extract.py'), str(mp4), str(S / pid)], check=True, capture_output=True, text=True).stdout)
    ref = REF / f'{pid}.txt'
    extra = [f'\n# 视频画面结构：第 1 屏是片头（标题、试卷、篇目、体裁、词数），之后每句一屏，共 {len(sents)} 句；长句拆成多屏；预期屏数 {want}。']
    for k, a in sorted(ats.items(), key=lambda x: int(x[0])):
        zh = splits[k]['zh']
        extra.append(f'# 第 {k} 句分成 {len(zh)} 屏（页脚 PART 1/{len(zh)} …）：' + '；'.join(f'第 {i + 2} 屏英文从 “{x}” 开始' for i, x in enumerate(a))
                     + '；各屏中文依次是：' + ''.join(f'「{z}」' for z in zh))
    ref.write_text(ref.read_text('utf-8') + '\n'.join(extra) + '\n', 'utf-8')
    print(pid, 'screens', got, 'expected', want, 'OK' if got == want else 'MISMATCH', flush=True)
    if got != want:
        bad.append(pid)
print('mismatch:', bad)
