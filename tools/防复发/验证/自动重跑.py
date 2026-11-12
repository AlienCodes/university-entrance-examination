"""双向验证：合成机被收回时自动重跑一次（踩坑 100）。CI 能跑（pyyaml）。
  ① 工作流能解析（yaml.safe_load），监听的名字 = 语法填空配音工作流的 name，权限 actions: write，只有一个步骤、命令是 gh run rerun <id> --failed；
  ② 触发条件：第 1 次失败 → 重跑；第 2 次失败 → 不重跑；成功、被取消 → 不重跑（把 if 表达式代入四种情况求值）；
  ③ 下游等待（候选第3轮.sh）合成结果不完整时继续等（重跑会补齐），不拿残缺的结果选段。
    python3 tools/防复发/验证/自动重跑.py"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
W = ROOT / '.github/workflows'
bad = []
main = yaml.safe_load((W / 'tts-grammar-qwen.yml').read_text('utf-8'))
rr = yaml.safe_load((W / 'tts-grammar-qwen-rerun.yml').read_text('utf-8'))
on = rr.get('on') or rr.get(True)
job = rr['jobs']['rerun']
steps = job['steps']
ok1 = (on['workflow_run']['workflows'] == [main['name']] and on['workflow_run']['types'] == ['completed']
       and rr['permissions'] == {'actions': 'write'} and len(steps) == 1 and re.search(r'gh run rerun \S.*workflow_run\.id.* --failed', steps[0]['run']))
print(f'① 解析、监听名字、权限、步骤：{"对" if ok1 else "错"}')
if not ok1:
    bad.append('①')


def fire(conclusion, attempt):
    expr = job['if'].replace('github.event.workflow_run.conclusion', repr(conclusion)).replace('github.event.workflow_run.run_attempt', str(attempt))
    expr = expr.replace('&&', ' and ').replace('||', ' or ')
    return bool(eval(expr, {}))


cases = {('failure', 1): True, ('failure', 2): False, ('success', 1): False, ('cancelled', 1): False}
got = {k: fire(*k) for k in cases}
print(f'② 触发：{got}')
if got != cases:
    bad.append('②')
sh = (ROOT / '高考语法填空/tools/候选第3轮.sh').read_text('utf-8')
if '合成完整性.py' not in sh:
    bad.append('③ 候选第3轮.sh 等待时没查完整性')
print('自动重跑双向验证', '通过' if not bad else '失败：' + '、'.join(bad))
sys.exit(1 if bad else 0)
