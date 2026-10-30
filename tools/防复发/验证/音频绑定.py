"""踩坑 86 双向验证：只换音频时，打包（.github/cet6-chalk-pack.py）不许复用旧音频做的视频。
截图指纹不含音频，旧视频的指纹照样等于审阅登记；打包必须按 timings 里的合格证把视频和所用 MP3 绑在一起。
做法：在临时目录里按发布任务的样子摆好 manifest、审阅登记、timings、artifact，直接调打包程序的 from_artifact / from_repo：
  ① 四级作文 c05 已发布视频的旧核查（指纹 = 登记值、全部通过）+ 现在带合格证的 timings → 必须拒收；
  ② 同一份旧核查、meta 写上正确的 audio_sha256 也必须拒收（核查里没有通过的“音频合格证”）；
  ③ 新核查（音频合格证 合格）+ meta 的 audio_sha256 与合格证不同 → 拒收；
  ④ 新核查 + audio_sha256 与合格证相同 → 收；
  ⑤ 仓库里提交的视频（没有 meta）在有合格证时 → 拒收；
  ⑥ timings 里没有合格证（旧成品，不追溯）→ 旧核查照旧收（其他项目行为不变）；
  ⑦ 发布任务没检出 timings → 报错退出。
用法：python3 tools/防复发/验证/音频绑定.py"""
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

R = Path(__file__).resolve().parents[3]
OLD_REP = R / '四级作文/大字版/成品核查/2025年12月大学英语四级 第2套 写作 Part I 大学生应学习学术写作_核查.json'
PID, FP = 'c05', 'f' * 16
NEED = hashlib.sha256(b'new-audio').hexdigest()


def load(td):
    os.chdir(td)
    os.environ.update(TAG='verify', GITHUB_REPOSITORY='x/y', PROJECT='四级作文')
    spec = importlib.util.spec_from_file_location('pack', R / '.github/cet6-chalk-pack.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def setup(td, cert=True):
    old = json.loads(OLD_REP.read_text('utf-8'))
    name = old['video']
    (td / 'manifest').mkdir()
    (td / 'manifest/manifest.json').write_text(json.dumps({'render': [], 'passages': [{'id': PID, 'name': name}]}, ensure_ascii=False), 'utf-8')
    reg = td / '四级作文/tools/画面核查'
    reg.mkdir(parents=True)
    (reg / '截图审阅通过.json').write_text(json.dumps({f'{PID}@C': {'指纹': FP}}), 'utf-8')
    (td / '四级作文/audio').mkdir(parents=True)
    tm = {'file': 'x.mp3', 'clause_check': 'clause-v1', 'certificate': {'chain': 'clause-v1', 'passed': True, 'mp3_sha256': NEED}} if cert else {'file': 'x.mp3'}
    (td / '四级作文/audio/timings.json').write_text(json.dumps({'cet4_male': {PID: tm}}), 'utf-8')
    return old, name


def art(td, tag, rep, name, audio_sha):
    d = td / 'a' / tag
    d.mkdir(parents=True)
    v = d / name
    v.write_bytes(b'v' * 1000)
    rep = copy.deepcopy(rep)
    rep.update({'指纹': FP, 'size': 1000})
    (d / (Path(name).stem + '_核查.json')).write_text(json.dumps(rep, ensure_ascii=False), 'utf-8')
    meta = {'verify_all': '全部通过', 'sha256': hashlib.sha256(v.read_bytes()).hexdigest()}
    if audio_sha:
        meta['audio_sha256'] = audio_sha
    (d / 'meta.json').write_text(json.dumps(meta), 'utf-8')
    return d


def new_rep(old):
    r = copy.deepcopy(old)
    r['checks'] = r['checks'] + [{'item': '音频合格证（处理链版本、意群响度检查）', 'ok': True, 'detail': '合格'}]
    return r


def main():
    here = os.getcwd()
    res = []
    try:
        td = Path(tempfile.mkdtemp(prefix='bind_'))
        old, name = setup(td)
        m = load(td)
        res.append(('① 旧核查（指纹 = 登记）→ 拒收', bool(m.from_artifact(PID, name, art(td, '1', old, name, None)))))
        res.append(('② 旧核查 + 正确 audio_sha256 → 拒收', bool(m.from_artifact(PID, name, art(td, '2', old, name, NEED)))))
        res.append(('③ 新核查 + 不同 audio_sha256 → 拒收', bool(m.from_artifact(PID, name, art(td, '3', new_rep(old), name, 'a' * 64)))))
        why = m.from_artifact(PID, name, art(td, '4', new_rep(old), name, NEED))
        res.append((f'④ 新核查 + 相同 audio_sha256 → 收（{why or "收"}）', not why))
        d = td / '四级作文/大字版/成品核查'
        d.mkdir(parents=True)
        r = new_rep(old)
        r.update({'指纹': FP, 'size': 1000})
        (d / (Path(name).stem + '_核查.json')).write_text(json.dumps(r, ensure_ascii=False), 'utf-8')
        res.append(('⑤ 仓库视频（无 meta）→ 拒收', bool(m.report_problem(PID, name, d / (Path(name).stem + '_核查.json'), 1000))))
        shutil.rmtree(td)
        td = Path(tempfile.mkdtemp(prefix='bind_'))
        old, name = setup(td, cert=False)
        m = load(td)
        why = m.from_artifact(PID, name, art(td, '6', old, name, None))
        res.append((f'⑥ 旧成品（无合格证）旧核查 → 照旧收（{why or "收"}）', not why))
        (td / '四级作文/audio/timings.json').unlink()
        try:
            m.report_problem(PID, name, td / 'a/6' / (Path(name).stem + '_核查.json'), 1000)
            res.append(('⑦ 缺 timings → 报错', False))
        except SystemExit as e:
            res.append((f'⑦ 缺 timings → 报错（{e}）', True))
        shutil.rmtree(td)
    finally:
        os.chdir(here)
    for t, ok in res:
        print(('✅ ' if ok else '❌ ') + t)
    if not all(ok for _, ok in res):
        sys.exit('音频绑定：不通过')
    print('音频绑定：通过（7/7）')


if __name__ == '__main__':
    main()
