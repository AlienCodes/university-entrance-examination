"""双向验证：防复发钩子（铁律 13、14、17、18；踩坑 12、54）。喂假的钩子 JSON，违规必须拦（退出 2），正常必须放（退出 0），钩子出错也放。
    python3 tools/防复发/验证/钩子.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

H = Path(__file__).resolve().parents[1] / '钩子' / '钩子.py'
bad = []


def run(mode, data, env=None, raw=None):
    e = dict(os.environ, **(env or {}))
    t0 = time.time()
    p = subprocess.run([sys.executable, str(H), mode], input=raw if raw is not None else json.dumps(data, ensure_ascii=False),
                       capture_output=True, text=True, env=e)
    return p.returncode, p.stdout + p.stderr, time.time() - t0


def case(name, want, mode, data, env=None, raw=None, has=None):
    code, out, dt = run(mode, data, env, raw)
    ok = code == want and (has is None or has in out) and dt < 1.0
    print(f"  {'✅' if ok else '❌'} {name}（退出 {code}，{dt * 1000:.0f} ms）")
    if not ok:
        bad.append(f'{name}: 期望退出 {want}，得到 {code}：{out.strip()[:200]}')


def tool(name, **inp):
    return {'tool_name': name, 'tool_input': inp, 'session_id': SID}


SID = 'selftest-' + uuid.uuid4().hex
# Agent / Workflow
case('Agent 没写预算 → 拦', 2, 'pretool', tool('Agent', prompt='把 50 篇译文复核一遍'))
case('Agent 预算 5 万 → 放', 0, 'pretool', tool('Agent', prompt='查一下函数在哪。token 预算：约 5 万'))
case('Agent 预算 120 万 → 拦', 2, 'pretool', tool('Agent', prompt='全部复核。token 预算：约 120 万'))
case('Agent budget 150k → 放', 0, 'pretool', tool('Agent', prompt='search. token budget: 150k'))
case('Agent 整屏盲审 → 拦', 2, 'pretool', tool('Agent', prompt='把 400 张截图逐屏看一遍。token 预算：约 20 万'))
case('Agent 只看新情况 → 放', 0, 'pretool', tool('Agent', prompt='看 新情况检测.py 列出的 18 屏盲审。token 预算：约 1 万'))
case('Workflow 脚本没预算 → 拦', 2, 'pretool', tool('Workflow', script='export const meta={name:"x"}\nawait agent("a")'))
case('Workflow 脚本注释写预算 → 放', 0, 'pretool', tool('Workflow', script='// token 预算：约 8 万\nexport const meta={name:"x"}'))
case('预算上限可由环境变量调 → 拦', 2, 'pretool', tool('Agent', prompt='token 预算：约 8 万'), env={'FFF_BUDGET_MAX': '50000'})
# Read 图片计数
case('读文本文件 → 放', 0, 'pretool', tool('Read', file_path='/x/a.py'))
for i in range(3):
    case(f'读第 {i + 1} 张图（上限 3）→ 放', 0, 'pretool', tool('Read', file_path=f'/x/{i}.png'), env={'FFF_IMG_LIMIT': '3'})
case('读第 4 张图（上限 3）→ 拦', 2, 'pretool', tool('Read', file_path='/x/9.PNG'), env={'FFF_IMG_LIMIT': '3'})
SID = 'selftest-' + uuid.uuid4().hex
case('另一个会话的第 1 张图 → 放', 0, 'pretool', tool('Read', file_path='/x/0.jpg'), env={'FFF_IMG_LIMIT': '3'})
# Bash
case('pkill -f 无方括号 → 拦（踩坑 12）', 2, 'pretool', tool('Bash', command='pkill -f make_video'))
case('pkill -f 带方括号 → 放', 0, 'pretool', tool('Bash', command='pkill -f "[m]ake_video"'))
case('pgrep 中文模式 → 拦（踩坑 54）', 2, 'pretool', tool('Bash', command='pgrep -f 大字版.py'))
case('pgrep ASCII 模式 → 放', 0, 'pretool', tool('Bash', command='pgrep -f "ttsenv/bin/python .*[-]-stills" | head'))
case('普通命令 → 放', 0, 'pretool', tool('Bash', command='git status && echo 完成'))
case('AskUserQuestion → 拦（铁律 12）', 2, 'pretool', tool('AskUserQuestion', questions=[]))
case('文字里提到 pkill -f 中文 → 放', 0, 'pretool', tool('Bash', command='echo "Bash：pkill -f 大字版 要拦" > a.txt'))
case('分号后 sudo pkill -f 无方括号 → 拦', 2, 'pretool', tool('Bash', command='ls; sudo pkill -f make_video'))
# 对话过长
with tempfile.TemporaryDirectory() as d:
    small, big = Path(d, 's.jsonl'), Path(d, 'b.jsonl')
    small.write_text('x' * 1000)
    big.write_bytes(b'x' * 2_100_000)
    case('短对话 → 不提醒', 0, 'prompt', {'transcript_path': str(small)}, env={'FFF_LONG_MB': '2'})
    code, out, _ = run('prompt', {'transcript_path': str(small)}, {'FFF_LONG_MB': '2'})
    if '铁律 18' in out:
        bad.append('短对话也提醒了')
    case('长对话 → 提醒铁律 18', 0, 'prompt', {'transcript_path': str(big)}, env={'FFF_LONG_MB': '2'}, has='铁律 18')
# 开工清单、容错
code, out, _ = run('session', {})
lines = [x for x in out.splitlines() if x.strip()]
print(f"  {'✅' if code == 0 and 0 < len(lines) <= 10 and '先估 token' in out else '❌'} 开工清单 {len(lines)} 行（≤ 10）")
if not (code == 0 and 0 < len(lines) <= 10 and '先估 token' in out):
    bad.append(f'开工清单不对：{len(lines)} 行')
case('坏 JSON → 放（钩子出错不卡工作）', 0, 'pretool', None, raw='{not json')
case('空输入 → 放', 0, 'pretool', None, raw='')

print('钩子双向验证：' + ('全部通过' if not bad else f'{len(bad)} 处失败\n  ' + '\n  '.join(bad)))
sys.exit(1 if bad else 0)
