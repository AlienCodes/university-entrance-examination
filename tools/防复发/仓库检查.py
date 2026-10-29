"""仓库级检查（防复发自检每次提交前自动调用，约 0.1 秒）。

    python3 tools/防复发/仓库检查.py            # 单独跑
工作流（.github/workflows/*.yml）：
  踩坑 68：YAML 解析不了、步骤不是 {name/uses/run} 字典、或者某个字符串值里藏着“- name: / - uses: / - run:”这样的行
          （删行只删了文字、留下缩进，下一步骤被并进了上一个多行字符串：YAML 照样能解析，GitHub 判工作流无效）；
  踩坑 42、43、52：发布用第三方 softprops/action-gh-release（403）、Info-ZIP 打包（zip -0 / zip -q，中文名不打 UTF-8 标记）、
          unzip -l 判断包内容（中文名显示不出来）——新工作流一律不许用；旧的几个已完结项目登记在 LEGACY，只许减少。
  踩坑 87：发布音频 / 视频的工作流（AUDIO_RELEASE）必须在打包之前跑 .github/check-audio-cert.py <音频目录>，稀疏检出要带上
          tools/tts 与音频目录；每个 release-*.yml 都必须登记在 AUDIO_RELEASE 或 NO_AUDIO（写明理由）里，新发布流程不许漏。
软链接（踩坑 47）：仓库里的软链接不许指向仓库外（临时目录一删，模型就没了），也不许是断的。
双向验证：python3 tools/防复发/验证/仓库检查.py"""
import os
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
BAN = [(r'softprops/action-gh-release', '踩坑 42：发布改用 gh release create/upload'),
       (r'(?<![\w-])zip\s+-(?:0|q)', '踩坑 52：打包一律用 Python zipfile（Info-ZIP 不给中文文件名打 UTF-8 标记）'),
       (r'unzip\s+-l', '踩坑 43：查看包内容一律用 Python zipfile（unzip -l 显示不出中文名）')]
# 已完结项目的旧发布流程（下次再用时改掉，并从这里删去；只许减少）
LEGACY = {'release-cet4-videos.yml', 'release-cet6-videos.yml', 'release-papers.yml', 'release-tem8-videos.yml',
          'release-videos.yml', 'release-zk-materials.yml', 'release-zk-videos.yml'}

# 踩坑 87：发布的包里有音频（MP3，或视频音轨）的工作流 → 要核对合格证的音频目录
AUDIO_RELEASE = {
    'release-cet4-dictation.yml': ['四级/audio'], 'release-cet6-materials.yml': ['六级/audio'], 'release-dictation.yml': ['audio'],
    'release-kaoyan-materials.yml': ['考研/audio'], 'release-tem8-materials.yml': ['专八/audio'], 'release-zk-materials.yml': ['中考/audio'],
    'release-cet4-videos.yml': ['四级/audio'], 'release-cet6-videos.yml': ['六级/audio'], 'release-tem8-videos.yml': ['专八/audio'],
    'release-videos.yml': ['audio'], 'release-zk-videos.yml': ['中考/audio'], 'release-tem8-listening-text.yml': ['专八/听力/原文/audio'],
}
NO_AUDIO = {     # 发布的东西里没有本仓库 TTS 音频：理由
    'release-papers.yml': '原卷 PDF', 'release-cet4-writing-handout.yml': '讲义 PDF', 'release-cet6-writing-handout.yml': '讲义 PDF',
    'release-kaoyan-writing-handout.yml': '讲义 PDF',
    'release-tem8-listening.yml': '专八听力考试原声视频（听力视频.py，不是 TTS，没有 timings；用户 2026-10-29 定为不在范围内）',
}


def audio_release_problems(name, y):
    if not name.startswith('release-'):
        return []
    if name not in AUDIO_RELEASE:
        return [] if name in NO_AUDIO else [f'{name}：新的发布流程没登记在 仓库检查.py 的 AUDIO_RELEASE / NO_AUDIO（踩坑 87：发音频 / 视频的必须核对合格证）']
    errs = []
    for jn, j in ((y or {}).get('jobs') or {}).items():
        steps = (j or {}).get('steps') or []
        runs = [str(st.get('run') or '') for st in steps if isinstance(st, dict)]
        k = next((i for i, r in enumerate(runs) if '.github/check-audio-cert.py' in r), None)
        if k is None:
            errs.append(f'{name}：任务 {jn} 没跑 .github/check-audio-cert.py（踩坑 87：不核合格证就发布）')
            continue
        args = runs[k].split('.github/check-audio-cert.py', 1)[1].split('\n')[0].split()
        miss = [d for d in AUDIO_RELEASE[name] if d not in args]
        if miss:
            errs.append(f'{name}：check-audio-cert.py 没核 {miss}')
        late = [i for i, r in enumerate(runs) if re.search(r'gh release (create|upload)|zipfile|shutil\.copy|zip ', r) and i < k]
        if late:
            errs.append(f'{name}：合格证核对排在打包 / 发布之后（第 {late[0] + 1} 步就开始打包了）')
        for st in steps:
            sp = isinstance(st, dict) and 'actions/checkout' in str(st.get('uses', '')) and (st.get('with') or {}).get('sparse-checkout')
            if sp:
                pats = [x.strip().strip('/') for x in sp.splitlines() if x.strip() and not x.strip().startswith('!')]
                for need in ['.github', 'tools/tts', *AUDIO_RELEASE[name]]:
                    if not any(need == q or need.startswith(q + '/') for q in pats):
                        errs.append(f'{name}：稀疏检出没带 {need}（合格证核对要用）')
    return errs


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


def check_workflow(name, text):
    import yaml
    errs = []
    try:
        y = yaml.safe_load(text)
    except Exception as e:
        return [f'{name}：YAML 解析失败（{str(e).splitlines()[0]}）']
    jobs = (y or {}).get('jobs') or {}
    if not jobs:
        errs.append(f'{name}：没有 jobs')
    for jn, j in jobs.items():
        for i, st in enumerate((j or {}).get('steps') or []):
            if not isinstance(st, dict) or not ({'uses', 'run'} & set(st)):
                errs.append(f'{name}：任务 {jn} 第 {i + 1} 步不是带 uses / run 的步骤')
                continue
            for s in strings(st):
                if any(re.match(r'\s*-\s+(name|uses):', ln) for ln in s.splitlines()):
                    errs.append(f'{name}：任务 {jn} 第 {i + 1} 步的字符串里藏着“- name: / - uses:”行，像是下一步骤被并进来了（踩坑 68：删行留下了缩进）')
                    break
    errs += audio_release_problems(name, y)
    hits = [(pat, why) for pat, why in BAN if re.search(pat, text)]
    if name not in LEGACY:
        errs += [f'{name}：用了 {pat}（{why}）' for pat, why in hits]
    elif not hits:
        errs.append(f'{name} 已经不用旧打包 / 发布方式了，把它从 仓库检查.py 的 LEGACY 删去（只许减少）')
    return errs


def check_workflows(root=R):
    errs = []
    d = root / '.github' / 'workflows'
    for f in sorted(d.glob('*.y*ml')):
        errs += check_workflow(f.name, f.read_text('utf-8'))
    return errs


def check_symlinks(root=R):
    errs = []
    root = root.resolve()
    for dp, dns, fns in os.walk(root):
        if '.git' in dns:
            dns.remove('.git')
        for n in fns + dns:
            p = Path(dp) / n
            if p.is_symlink():
                t = Path(os.path.realpath(p))
                rel = p.relative_to(root)
                if not t.exists():
                    errs.append(f'{rel}：断掉的软链接（指向 {os.readlink(p)}；踩坑 47：模型一律放真实文件）')
                elif root not in t.parents and t != root:
                    errs.append(f'{rel}：软链接指向仓库外 {t}（踩坑 47：临时目录一删就没了，改放真实文件）')
    return errs


def main():
    errs = check_workflows() + check_symlinks()
    for e in errs:
        print('❌ ' + e)
    print('仓库检查：' + ('通过' if not errs else f'{len(errs)} 处不通过'))
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
