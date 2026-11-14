"""只读复核冻结两步workflow/control；list使用真实load_control和mock gate/matrix，零网络。"""
from __future__ import annotations
import ast
import copy
from contextlib import redirect_stdout
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import types
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
WORKFLOW = ROOT / '.github/workflows/render-tem8-intensive-two-stage.yml'
CONTROL = ROOT / '.github/tem8-listening-intensive-two-stage.json'
WF_SHA = '455dfd870ecab0560a6b9195d4f89990ea9a9f7cfd288a5d5052609a923967e7'
CONTROL_SHA = '82bfcc868edffff9d9b5cdd81d29e8aef46f1ad22872fc97bac1d2aa50fa39f5'
PUB = ROOT / '专八/听力/批量/tools/发布汇集.py'


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    assert sha(WORKFLOW) == WF_SHA and sha(CONTROL) == CONTROL_SHA, '冻结工作流或控制字节已改变'
    import yaml
    text = WORKFLOW.read_text('utf-8')
    wf = yaml.load(text, Loader=yaml.BaseLoader)
    control = json.loads(CONTROL.read_text('utf-8'))
    assert wf['on']['push'] == {'branches':['codex/tem8-listening-2009-2024'],
                                'paths':['.github/tem8-listening-intensive-two-stage.json']}
    assert wf['concurrency'] == {'group':'tem8-listening-intensive-two-stage-${{ github.run_id }}',
                                 'cancel-in-progress':'false'}
    assert set(wf['jobs']) == {'list','render'}
    assert wf['jobs']['render']['strategy']['max-parallel'] == '20'
    assert wf['jobs']['render']['strategy']['fail-fast'] == 'false'
    assert control['intensive'] == control['render_intensive'] == ['2022-A','2024-A']
    assert control['render_targets'] == {'exam':[],'intensive':['2022-A','2024-A']}
    assert control['cache_only'] is True and control['render'] is True
    assert text.count('精听两步编码.py') == 4
    assert re.findall(r'精听两步编码.py "\$U" (\w+)',text) == ['precheck','approve','video','verify']
    for pin in ['spacy==3.8.7','thinc==8.3.6','preshed==3.0.9','cymem==2.0.11',
                'murmurhash==1.0.12','typer==0.15.4','click==8.1.8','en_core_web_sm-3.8.0-py3-none-any.whl']:
        assert pin in text, pin
    assert '原音准备.py 2022 --out in/audio' in text
    assert '--archive in/default.zip --out in/audio' in text
    assert 'cp in/audio/原音准备.json work/源音频准备.json' in text
    for forbidden in ['考试视频.py', '/tools/精听.py ', '精听45完整审核登记冻结', '精听自动组装激活冻结']:
        assert forbidden not in text, forbidden
    assert "gate 'intensive' '${{ matrix.item.id }}' --work work --record current-review.json" in text
    assert "stage 'intensive' '${{ matrix.item.id }}' --work work --out up" in text
    assert '发布汇集.py store up' in text
    for job in wf['jobs'].values():
        assert job['runs-on'] == 'ubuntu-24.04'
        for step in job['steps']:
            if step.get('uses') == './.github/actions/cet6-chalk-env':
                assert step['with'] == {'asr':'false','browser':'153'}
            if 'run' in step:
                subprocess.run(['bash','-n'], input=step['run'], text=True, check=True)
    listing = next(step for step in wf['jobs']['list']['steps'] if step.get('id') == 'list')
    code = listing['run'].split("python3 - <<'PY'\n",1)[1].rsplit('\nPY',1)[0]
    ast.parse(code)
    spec = importlib.util.spec_from_file_location('real_pub_for_two_stage_test', PUB)
    pub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pub)
    assert pub.INTENSIVE_TWO_STAGE_IDS == frozenset({'2022-A','2024-A'})
    rows = [{'kind':'intensive','id':ident,'year':int(ident[:4])} for ident in control['intensive']]
    positives, negatives = [], []
    with tempfile.TemporaryDirectory(prefix='tem8_two_stage_policy_') as td:
        td = Path(td)
        fixture, output = td / 'control.json', td / 'output'
        def execute(value, matrix_rows, allowed=('2022-A','2024-A')):
            fixture.write_text(json.dumps(value))
            calls = []
            def load(path):
                assert path == Path('.github/tem8-listening-intensive-two-stage.json')
                return pub.load_control(fixture)
            def gate(kind, ident):
                assert kind == 'intensive'
                calls.append(ident)
            fake = types.SimpleNamespace(INTENSIVE_TWO_STAGE_IDS=frozenset(allowed),load_control=load,
                gate=gate,matrix=lambda c:matrix_rows,ensure_release=lambda *args:None,CACHE_TAG=pub.CACHE_TAG)
            fake_spec = types.SimpleNamespace(loader=types.SimpleNamespace(
                exec_module=lambda module:module.__dict__.update(fake.__dict__)))
            with patch('importlib.util.spec_from_file_location',return_value=fake_spec), \
                 patch('importlib.util.module_from_spec',return_value=types.SimpleNamespace()), \
                 patch.dict(os.environ,{'GITHUB_OUTPUT':str(output)}), redirect_stdout(io.StringIO()):
                exec(compile(code,str(WORKFLOW),'exec'),{})
            assert calls == ['2022-A','2024-A']
        for name, selected in [('两项待制作',rows),('已缓存一项，仅一项待制作',rows[:1]),('全部已缓存',[])]:
            execute(copy.deepcopy(control),selected)
            positives.append({'case':name,'passed':True})
        cases = []
        for name, changes in [
            ('禁止cache_only=false',{'cache_only':False}),
            ('禁止render=false',{'render':False}),
            ('禁止混入考试',{'exam':[2019]}),
            ('禁止缺少一个目标',{'intensive':['2024-A']}),
            ('禁止render_intensive与目标不同',{'render_intensive':['2024-A']}),
            ('禁止render_targets与目标不同',{'render_targets':{'exam':[],'intensive':['2024-A']}}),
            ('禁止review阶段',{'stage':'review'})]:
            cases.append((name,{**copy.deepcopy(control),**changes},rows,('2022-A','2024-A')))
        cases += [
            ('禁止额外matrix目标',control,rows+[{'kind':'intensive','id':'2023-A','year':2023}],('2022-A','2024-A')),
            ('禁止matrix重复目标',control,[rows[0],rows[0]],('2022-A','2024-A')),
            ('禁止允许集合扩展到三篇',control,rows,('2022-A','2024-A','2023-A'))]
        for name, value, selected, allowed in cases:
            try:
                execute(copy.deepcopy(value),selected,allowed)
            except AssertionError:
                negatives.append({'case':name,'rejected':True})
            else:
                raise AssertionError('策略负例未拒绝：'+name)
    subprocess.run(['python3','.github/check-release-target.py'],cwd=ROOT,check=True,capture_output=True)
    assert sha(WORKFLOW) == WF_SHA and sha(CONTROL) == CONTROL_SHA
    report = {'schema':1,'status':'pass','checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'workflow':{'path':WORKFLOW.relative_to(ROOT).as_posix(),'sha256':WF_SHA},
              'control':{'path':CONTROL.relative_to(ROOT).as_posix(),'sha256':CONTROL_SHA},
              'test_script_sha256':sha(Path(__file__)),'publisher_at_test_sha256':sha(PUB),
              'yaml_parser':{'package':'PyYAML','version':yaml.__version__},
              'static_checks':['YAML与全部Shell语法','内嵌Python AST','精确分支及control push路径',
                '仅2022-A/2024-A且三个目标字段一致','每run独立concurrency且不取消','max20/fail-fast=false',
                'NLP原固定版本与browser153环境','无exam分支/旧45冻结依赖/原精听编码入口',
                'precheck/approve/video/verify四阶段均新两步入口','原音准备与完整PNG gate、stage/store保留',
                'Release target guard','冻结workflow/control测试前后字节不变'],
              'positive_cases':positives,'negative_cases':negatives,
              'gate_and_matrix':'mock；load_control为当前实际发布器函数；不调用真实gate或GitHub',
              'production_files_modified':False,'network_access':False,'git_commit_or_push':False,
              'reproduce':'python3 专八/听力/批量/核验/精听独立两步编码/独立工作流校验.py'}
    target = HERE / '独立工作流校验.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('PASS: YAML/Shell/策略校验，3正例+10负例，冻结文件字节保持。')
    print('Report SHA256',sha(target))


if __name__ == '__main__':
    main()
