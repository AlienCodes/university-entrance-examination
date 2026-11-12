"""铁律 26 双向验证：发布任务（含 gh release 的任务）只许拿已做好的成品，不许在发布里重新生成视频。
规则：一个任务里有 gh release create/upload，就不许出现视频引擎的生成命令（make_video / 大字版 --video / 听力视频 video / ffmpeg 编码 libx264）。
用法：python3 tools/防复发/验证/发布不重做.py （现在的工作流 0 处；埋雷：发布里调引擎必须报）"""
import glob, re, sys, yaml

RENDER = re.compile(r'make_video\.py|大字版\.py[^\n]*--video|听力视频\.py[^\n]*\bvideo\b|libx264|mode=video')

def problems(wf):
    out = []
    for name, job in (wf.get('jobs') or {}).items():
        runs = '\n'.join(str(s.get('run', '')) for s in job.get('steps', []) if isinstance(s, dict))
        if re.search(r'gh release (create|upload)', runs) and RENDER.search(runs):
            out.append(f'{name}: 发布任务里重新生成视频（{RENDER.search(runs).group(0)}）——发布问题只改发布这一步')
    return out

def main():
    bad = []
    for f in sorted(glob.glob('.github/workflows/*.yml')):
        bad += [f'{f}: {p}' for p in problems(yaml.safe_load(open(f, encoding='utf-8')))]
    mine = {'jobs': {'publish': {'steps': [{'run': 'python3 专八/听力/tools/听力视频.py 202112-1 video\ngh release upload T x.mp4'}]}}}
    ok_wf = {'jobs': {'publish': {'steps': [{'run': 'gh release upload T up/a.mp4#中文名'}]}}}
    errs = []
    if bad: errs.append('现在 → 0：' + '；'.join(bad))
    if not problems(mine): errs.append('埋雷（发布里重新生成）没报出')
    if problems(ok_wf): errs.append('只上传的发布任务被误报')
    for e in errs: print('❌', e)
    if errs: sys.exit(1)
    print('发布不重做双向验证：全部通过（工作流 0 处，埋雷报出，只上传不误报）')

if __name__ == '__main__':
    main()
