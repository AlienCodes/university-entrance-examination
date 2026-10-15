"""组装「西班牙语逐句精读视频工具包」（给西班牙语老师下载用：程序、资料、示例、安装脚本、说明，解压就能装、能生成）。

    python3 西班牙语/tools/build_kit.py --out dist --ci                                  # 发布流程用：模型留给工作流下载放进去
    python3 西班牙语/tools/build_kit.py --out 目录 --models-from /opt/es_tts_models       # 本机测试：把本机的 Supertonic 3 模型复制进去
    python3 西班牙语/tools/build_kit.py --out 目录 --models-from /opt/es_tts_models --link-qwen3   # 另把本机 Qwen3 模型做成软链接（只用于本机测试）
    python3 西班牙语/tools/build_kit.py --manifest 工具包目录                            # 只重新写文件清单（工作流放进模型以后用）

只用 Python 标准库（发布流程在干净的机器上直接运行）。工具包保持和仓库相同的相对位置
（工具包根目录/西班牙语/tools/c4.py 的 ROOT = parents[2] = 工具包根目录，四级、高考的共用程序按原路径找得到）：

  工具包根目录/
    使用说明.md、install.sh、install_windows.ps1、install_windows.bat、生成视频.sh、生成视频.bat   （来自 西班牙语/kit/）
    西班牙语/  tools（程序、字体、背景样式 CSS）、文章、图片、配音选型（样音、参考音色）、背景样式（预览图）、kit（依赖清单）、
              audio（示例的朗读音频，只放检查全部通过的）、最终视频（示例视频，只放核查全部通过、不是草稿的）、
              models/（supertonic3 随包；qwen3-base 是 Release 里单独的分卷，用 join_parts.py 解压到这里）
    四级/tools/、tools/tts/、tools/video/   西语程序运行时用到的共用程序和字体（清单在 西班牙语/kit/kit_config.json，用 strace 实测）

工具包里的 voices.json 由仓库的 voices.json 转换：python 一律 "auto"（用安装好的同一个环境），model_dir、ref_audio 改成相对 西班牙语/ 的路径；
模型不在工具包里的音色（Kokoro）去掉。timings.json 里示例音频的 voice_cfg 换成工具包里的设置（batch.py 判断“已是最新”时一致）。

组装完自动检查：所有 .py 能编译；voices.json 里没有绝对路径；程序里没有指向本机仓库（/home/user/…）的路径；
随包模型文件齐全（--ci 时由工作流下载后用 --manifest 再查）。任何一项不合格就报错。
"""
import argparse
import json
import os
import shutil
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ES = HERE.parent
ROOT = ES.parent
CONF = json.loads((ES / 'kit' / 'kit_config.json').read_text('utf-8'))
MANIFEST = '文件清单.txt'
KIT_NOTE = ('西班牙语音色（工具包版，由仓库 voices.json 转换）。python "auto" = 用安装好的同一个 Python 环境；model_dir、ref_audio 是相对 西班牙语/ 的路径。'
            'engine=worker：用 engines/ 里的 script 合成。deline：Supertonic 声码器的帧频梳状线清单（每段原始合成上减掉，见 buzz.py）。'
            'mix：Supertonic 预置音色按权重混合（见 engines/sherpa.py）。seed：Qwen3 的随机种子（检查没通过时 batch.py 自动换下一个）。_final：默认音色。')


def skip(p):
    return p.name in CONF['exclude_names'] or p.suffix in CONF['exclude_suffixes']


ROOT_SRC = set(CONF['root_files'].values()) | set(CONF.get('kit_files', {}).values())   # 放到别处的文件（安装脚本、说明），不在 西班牙语/kit/ 里再放一份（免得运行错的那份）


def copy_tree(src, dst):
    for d, dirs, files in os.walk(src):
        d = Path(d)
        dirs[:] = sorted(x for x in dirs if not skip(d / x))
        for f in sorted(files):
            s = d / f
            rel = s.relative_to(ROOT).as_posix()
            if skip(s) or rel in CONF['exclude_paths'] or rel in ROOT_SRC:
                continue
            t = dst / s.relative_to(src)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, t)


def copy_file(rel, kit):
    s, t = ROOT / rel, kit / rel
    if not s.is_file():
        raise SystemExit(f'找不到 {rel}（kit_config.json 里登记了，仓库里却没有）')
    t.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(s, t)


DEV_PY = ('/opt/ttsenv/bin/python ', '/opt/es_tts_envs/sherpa/bin/python ', '/opt/es_tts_envs/qwen3tts/bin/python ')


def doc_paths(kit):
    """工具包里的说明文档（.md）：开发机的 Python 路径换成 python（工具包里是 .venv 的 Python，见 使用说明.md）。"""
    n = 0
    for f in kit.rglob('*.md'):
        t = f.read_text('utf-8')
        u = t
        for x in DEV_PY:
            u = u.replace(x, 'python ')
        if u != t:
            f.write_text(u, 'utf-8')
            n += 1
    return n


def kit_voices():
    """仓库 voices.json → 工具包 voices.json（相对路径、python auto）。返回 (新 voices, 去掉的音色及原因)。"""
    src = json.loads((HERE / 'voices.json').read_text('utf-8'))
    by_local = {Path(m['local']): m for m in CONF['models'].values()}
    out, dropped = {'_说明': KIT_NOTE, '_final': src['_final']}, {}
    for name, v in src.items():
        if name.startswith('_'):
            continue
        if v.get('engine') != 'worker':
            dropped[name] = f'engine={v.get("engine")}，模型不在工具包里'
            continue
        md = Path(v.get('model_dir', ''))
        m = by_local.get(md) or next((m for m in CONF['models'].values() if md.as_posix() == m['kit']), None)
        if not m:
            dropped[name] = f'model_dir {md} 没有登记在 kit_config.json 的 models 里'
            continue
        nv = dict(v, python='auto', model_dir=m['kit'])
        if v.get('ref_audio'):
            ra = Path(v['ref_audio'])
            if ra.is_absolute():
                try:
                    ra = ra.resolve().relative_to(ES)
                except ValueError:
                    raise SystemExit(f'音色 {name} 的 ref_audio {ra} 不在 西班牙语/ 里，工具包里放不进去')
            if not (ES / ra).is_file():
                raise SystemExit(f'音色 {name} 的参考录音 {ra} 不存在')
            nv['ref_audio'] = ra.as_posix()
        out[name] = nv
    if out['_final'] not in out:
        raise SystemExit(f'默认音色 {out["_final"]} 被去掉了：{dropped.get(out["_final"])}')
    return out, dropped


def example_audio(kit, voices):
    """示例朗读音频：timings.json 里检查全部通过（draft_issues 为空）、文件在、音色在工具包里的，原样复制。"""
    tp = ES / 'audio' / 'timings.json'
    T = json.loads(tp.read_text('utf-8')) if tp.exists() else {}
    out, n = {'_final': voices['_final']}, []
    for name, arts in T.items():
        if name.startswith('_') or name not in voices or not isinstance(arts, dict):
            continue
        for pid, e in arts.items():
            f = ES / 'audio' / e['file']
            if e.get('draft_issues') or not f.is_file():
                continue
            out.setdefault(name, {})[pid] = dict(e, voice_cfg=voices[name])
            for x in (f, f.with_suffix('.srt')):
                if x.is_file():
                    t = kit / '西班牙语' / 'audio' / x.relative_to(ES / 'audio')
                    t.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(x, t)
            n.append(f'{name}/{pid}')
    d = kit / '西班牙语' / 'audio'
    d.mkdir(parents=True, exist_ok=True)
    (d / 'timings.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')
    return n


def example_videos(kit, voices):
    """示例视频：不是草稿、旁边的 _核查.json 每一项都通过、音色在工具包里的。"""
    got, why = [], []
    for v in sorted((ES / '最终视频').glob('*.mp4')):
        chk = v.with_name(v.stem + '_核查.json')
        if v.name.startswith('草稿'):
            why.append(f'{v.name}：草稿')
            continue
        if not chk.is_file():
            why.append(f'{v.name}：没有核查记录')
            continue
        c = json.loads(chk.read_text('utf-8'))
        bad = [x['item'] for x in c.get('checks', []) if not x.get('ok')]
        if bad or not c.get('checks'):
            why.append(f'{v.name}：核查没有全部通过 {bad}')
            continue
        if c.get('voice') not in voices:
            why.append(f'{v.name}：音色 {c.get("voice")} 不在工具包里')
            continue
        for x in (v, chk):
            t = kit / '西班牙语' / '最终视频' / x.name
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(x, t)
        got.append(v.name)
    return got, why


def models(kit, src, link_qwen3):
    for key, m in CONF['models'].items():
        dst = kit / '西班牙语' / m['kit']
        local = Path(src) / Path(m['local']).relative_to('/opt/es_tts_models') if src else None
        if m['in_kit']:
            if not local or not local.is_dir():
                raise SystemExit(f'--models-from 里找不到 {key}（{local}）')
            dst.mkdir(parents=True, exist_ok=True)
            for f in sorted(local.iterdir()):
                if f.is_file():
                    shutil.copy2(f, dst / f.name)
        elif link_qwen3 and key == 'qwen3-base':
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.symlink_to(local.resolve(), target_is_directory=True)


def check_models(kit, require):
    bad = []
    for key, m in CONF['models'].items():
        d = kit / '西班牙语' / m['kit']
        miss = [f for f in m['files'] if not (d / f).is_file()]
        if m['in_kit'] and miss and require:
            bad.append(f'随包模型 {key} 缺文件：{miss}')
    return bad


def sanity(kit, voices):
    bad = []
    for p in kit.rglob('*.py'):
        try:
            compile(p.read_text('utf-8'), str(p), 'exec')
        except SyntaxError as e:
            bad.append(f'{p.relative_to(kit)} 编译不通过：{e}')
    for name, v in voices.items():
        if isinstance(v, dict):
            for k in ('python', 'model_dir', 'ref_audio'):
                if v.get(k) and (Path(v[k]).is_absolute() or v[k].startswith('/')) and not (k == 'python' and v[k] == 'auto'):
                    bad.append(f'voices.json：{name}.{k} 是绝对路径 {v[k]}')
    repos = {str(ROOT), '/home/user/university-entrance-examination'}        # 本机仓库 + 开发机仓库
    for p in list(kit.rglob('*.py')) + list(kit.rglob('*.json')) + list(kit.rglob('*.css')) + list(kit.rglob('*.md')):
        t = p.read_text('utf-8', errors='replace')
        for repo in repos:
            if repo in t:
                bad.append(f'{p.relative_to(kit)} 里有仓库的绝对路径 {repo}')
    return bad


def manifest(kit):
    rows, tops = [], {}
    for p in sorted(kit.rglob('*')):
        if p.is_file() and p.name != MANIFEST:
            rel = p.relative_to(kit).as_posix()
            n = p.stat().st_size
            rows.append(f'{n:>12}  {rel}')
            parts = rel.split('/')
            top = '/'.join(parts[:2]) if parts[0] in ('西班牙语', '四级', 'tools') and len(parts) > 2 else parts[0]
            tops[top] = tops.get(top, 0) + n
    (kit / MANIFEST).write_text(f'# {kit.name}：{len(rows)} 个文件，共 {sum(tops.values()) / 2**20:.1f} MB（字节数  路径）\n'
                                + '\n'.join(rows) + '\n', 'utf-8')
    print(f'文件清单（{len(rows)} 个文件，共 {sum(tops.values()) / 2**20:.1f} MB，明细写在 {MANIFEST}）：')
    for t, n in sorted(tops.items(), key=lambda x: -x[1]):
        print(f'  {n / 2**20:9.2f} MB  {t}')


def main():
    ap = argparse.ArgumentParser(description='组装西班牙语逐句精读视频工具包')
    ap.add_argument('--out', help='输出文件夹（工具包放在 输出文件夹/<工具包名>/）')
    ap.add_argument('--ci', action='store_true', help='发布流程用：不放模型（工作流下载 Supertonic 3 放进 西班牙语/models/supertonic3）')
    ap.add_argument('--models-from', help='本机模型根目录（如 /opt/es_tts_models），把随包模型复制进去')
    ap.add_argument('--link-qwen3', action='store_true', help='本机测试：把 Qwen3 模型做成软链接（不复制 4 GB）')
    ap.add_argument('--allow-no-example', action='store_true', help='没有核查通过的示例视频也继续（本机测试用）')
    ap.add_argument('--force', action='store_true', help='输出位置已有上次组装的工具包时先删掉')
    ap.add_argument('--manifest', metavar='工具包目录', help='只检查随包模型并重写文件清单')
    a = ap.parse_args()

    if a.manifest:
        kit = Path(a.manifest)
        bad = check_models(kit, True)
        if bad:
            raise SystemExit('\n'.join(bad))
        manifest(kit)
        return
    if not a.out or (not a.ci and not a.models_from):
        ap.error('要给 --out，以及 --ci 或 --models-from 二者之一')
    kit = Path(a.out).resolve() / CONF['kit_name']
    if kit.exists():
        if not a.force or not (kit / MANIFEST).is_file():
            raise SystemExit(f'{kit} 已存在（是上次组装的工具包就加 --force 覆盖；不是的话请换个 --out）')
        shutil.rmtree(kit)
    kit.mkdir(parents=True)
    try:
        build(a, kit)
    except BaseException:
        shutil.rmtree(kit, ignore_errors=True)          # 组装失败不留半成品（下次可以直接重来）
        raise


def build(a, kit):
    for d in CONF['spanish_dirs']:
        copy_tree(ES / d, kit / '西班牙语' / d)
    for f in CONF['spanish_files']:
        copy_file(f'西班牙语/{f}', kit)
    for f in CONF['shared_files']:
        copy_file(f, kit)
    for d in CONF['shared_dirs']:
        copy_tree(ROOT / d, kit / d)
    for name, rel in CONF['root_files'].items():
        shutil.copy2(ROOT / rel, kit / name)
    for name, rel in CONF.get('kit_files', {}).items():          # 工具包版的说明（替换仓库里的开发记录）
        (kit / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, kit / name)
    for name in CONF['executable']:
        p = kit / name
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    ndoc = doc_paths(kit)
    voices, dropped = kit_voices()
    (kit / '西班牙语' / 'tools' / 'voices.json').write_text(json.dumps(voices, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    auds = example_audio(kit, voices)
    vids, why = example_videos(kit, voices)
    (kit / '西班牙语' / 'models').mkdir(exist_ok=True)
    if a.models_from:
        models(kit, a.models_from, a.link_qwen3)

    print(f'工具包：{kit}')
    print(f'  音色 {len([k for k in voices if not k.startswith("_")])} 个（默认 {voices["_final"]}）；去掉：' +
          ('；'.join(f'{k}（{v}）' for k, v in dropped.items()) or '无'))
    print(f'  说明文档里开发机的 Python 路径改成 python：{ndoc} 个文件')
    print(f'  示例音频：{", ".join(auds) or "无"}')
    print(f'  示例视频：{", ".join(vids) or "无"}' + (f'；没放进来的：{"；".join(why)}' if why else ''))
    bad = sanity(kit, voices) + check_models(kit, not a.ci)
    if not vids and not a.allow_no_example:
        bad.append('没有核查全部通过的示例视频（西班牙语/最终视频/，非草稿、_核查.json 全部通过）')
    if bad:
        raise SystemExit('工具包检查不通过：\n  ' + '\n  '.join(bad))
    if a.ci:
        print('  模型：--ci，Supertonic 3 由发布工作流下载到 西班牙语/models/supertonic3，之后运行 --manifest 检查并重写清单')
    manifest(kit)


if __name__ == '__main__':
    main()
