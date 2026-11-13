"""仓库级检查（防复发自检每次提交前自动调用，约 0.1 秒）。

    python3 tools/防复发/仓库检查.py            # 单独跑
工作流（.github/workflows/*.yml）：
  踩坑 68：YAML 解析不了、步骤不是 {name/uses/run} 字典、或者某个字符串值里藏着“- name: / - uses: / - run:”这样的行
          （删行只删了文字、留下缩进，下一步骤被并进了上一个多行字符串：YAML 照样能解析，GitHub 判工作流无效）；
  踩坑 42、43、52：发布用第三方 softprops/action-gh-release（403）、Info-ZIP 打包（zip -0 / zip -q，中文名不打 UTF-8 标记）、
          unzip -l 判断包内容（中文名显示不出来）——新工作流一律不许用；旧的几个已完结项目登记在 LEGACY，只许减少。
  踩坑 87：发布音频 / 视频的工作流（AUDIO_RELEASE）必须在打包之前跑 .github/check-audio-cert.py <音频目录>，稀疏检出要带上
          tools/tts 与音频目录；每个 release-*.yml 都必须登记在 AUDIO_RELEASE 或 NO_AUDIO（写明理由）里，新发布流程不许漏。
  踩坑 114：工作流调用的脚本读系统文件（如 /usr/share/dict/american-english），工作流必须 apt 装对应的包（SYSDEP）。
  踩坑 117：用 .github/actions/cet6-chalk-env（环境里核 ffmpeg 6.1.1 等固定版本）的任务必须 runs-on: ubuntu-24.04，
          ubuntu-latest 正在逐步换新镜像（apt 的 ffmpeg 8.0.1），抽到新镜像的机器整批失败。
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

# 踩坑 109：用 cet6-chalk-pack.py 打包的生成工作流，render 写 meta 时必须带 audio_sha256（踩坑 86 视频与音频绑定；漏了，带合格证的篇目一律打包不收）。
# 这几个旧工作流的项目音频还没有合格证（2026-10-29 前的成品），下次重做时补上并从这里删去（只许减少）
NO_AUDIO_SHA = {'render-cet6-chalk.yml', 'render-cet6-writing.yml', 'render-kaoyan-campus.yml', 'render-kaoyan-writing.yml',
                'render-tem8-campus.yml', 'render-tem8-ink.yml'}


def pack_meta_problems(name, text):
    if 'cet6-chalk-pack.py' not in text:
        return []
    has = "'audio_sha256'" in text
    if name in NO_AUDIO_SHA:
        return [f'{name} 已经写 audio_sha256 了，把它从 仓库检查.py 的 NO_AUDIO_SHA 删去（只许减少）'] if has else []
    return [] if has else [f'{name}：用 cet6-chalk-pack.py 打包，但 render 的 meta 没写 audio_sha256（踩坑 109 / 86：打包会拒收带合格证的篇目）']


def gram_out_problems(name, text):
    """踩坑 113：推到 gram-tts-out 的合成工作流，结果目录名必须是 runs/<任务>-<运行号>（合成完整性.task_of 靠它找任务清单）。"""
    if 'gram-tts-out' not in text:
        return []
    ds = re.findall(r'\bD="runs/([^"]*)"', text)
    if not ds:
        return [f'{name}：推 gram-tts-out，但没找到 D="runs/<任务>-<运行号>" 的结果目录写法（踩坑 113）']
    errs = [f'{name}：结果目录 runs/{d} 不是“任务-运行号”（应为 runs/${{T}}-${{{{ github.run_number }}}}；'
            f'别的写法让 合成完整性.task_of 认不出任务清单，补合成的次数被当成缺片，踩坑 113）'
            for d in ds if d != '${T}-${{ github.run_number }}']
    if not re.search(r'\bT=\$\(basename "[^"]+" \.json\)', text):
        errs.append(f'{name}：结果目录的任务名 T 不是 $(basename "<任务清单>" .json)（踩坑 113）')
    return errs


# 踩坑 87：发布的包里有音频（MP3，或视频音轨）的工作流 → 要核对合格证的音频目录
AUDIO_RELEASE = {
    'release-cet4-dictation.yml': ['四级/audio'], 'release-cet6-materials.yml': ['六级/audio'], 'release-dictation.yml': ['audio'],
    'release-kaoyan-materials.yml': ['考研/audio'], 'release-tem8-materials.yml': ['专八/audio'], 'release-zk-materials.yml': ['中考/audio'],
    'release-cet4-videos.yml': ['四级/audio'], 'release-cet6-videos.yml': ['六级/audio'], 'release-tem8-videos.yml': ['专八/audio'],
    'release-videos.yml': ['audio'], 'release-zk-videos.yml': ['中考/audio'], 'release-tem8-listening-text.yml': ['专八/听力/原文/audio'],
}
NO_AUDIO = {     # 发布的东西里没有本仓库 TTS 音频：理由
    'release-papers.yml': '原卷 PDF', 'release-cet4-writing-handout.yml': '讲义 PDF', 'release-cet6-writing-handout.yml': '讲义 PDF',
    'release-kaoyan-writing-handout.yml': '讲义 PDF', 'release-cet6-listening-handout.yml': '讲义 PDF + 商品图', 'release-cet4-listening-handout.yml': '讲义 PDF + 商品图',
    'release-gaokao-listening-materials.yml': '八份讲义 PDF、商品图与文字说明；包内没有MP3或MP4',
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


# 踩坑 114：GitHub 机器上没有的系统文件 → 工作流必须 apt 装的包（脚本里写了这个路径、工作流又调用了这个脚本）
SYSDEP = {'/usr/share/dict/': 'wamerican'}


def sysdep_problems(name, text, root=R):
    errs = []
    for sc in sorted(set(re.findall(r'[^\s\'"`;|&()]+\.py\b', text))):
        f = root / sc
        if not f.is_file():
            continue
        src = f.read_text('utf-8', errors='ignore')
        for path, pkg in SYSDEP.items():
            if path in src and not re.search(r'apt(-get)?\s+install[^\n]*\b' + re.escape(pkg) + r'\b', text):
                errs.append(f'{name}：调用的 {sc} 读 {path}，工作流没有 apt install {pkg}（踩坑 114：GitHub 机器上没有）')
    return errs


def runner_problems(name, y):
    errs = []
    for jn, j in ((y or {}).get('jobs') or {}).items():
        uses = [st.get('uses', '') for st in (j or {}).get('steps') or [] if isinstance(st, dict)]
        if any('cet6-chalk-env' in u for u in uses) and (j or {}).get('runs-on') != 'ubuntu-24.04':
            errs.append(f'{name}：任务 {jn} 用 cet6-chalk-env，runs-on 是 {j.get("runs-on")}，必须 ubuntu-24.04（踩坑 117）')
    return errs


def duration_problems(name, text):
    """踩坑 118 再犯（四级精读 201806-2，运行 42172057319）：拿 ffprobe format=duration（按帧头估算，比解码长 30—66 ms）去 assert 核对 timings。"""
    for ln in text.splitlines():
        if 'format=duration' in ln and ('subprocess' in ln or 'float(' in ln):
            return [f'{name}：用 ffprobe format=duration 量音频时长去核对（踩坑 118：时长一律按解码长度，soundfile frames / samplerate）']
    return []


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
    errs += pack_meta_problems(name, text)
    errs += gram_out_problems(name, text)
    errs += sysdep_problems(name, text)
    errs += runner_problems(name, y)
    errs += duration_problems(name, text)
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
