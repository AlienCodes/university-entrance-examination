"""Claude Code 钩子：在工具层面强制执行省 token 的铁律（13、14、17、18）和两条操作坑（12、54）。

    python3 tools/防复发/钩子/钩子.py <session|prompt|pretool>   （stdin：Claude Code 钩子的 JSON）

- session  （SessionStart）：设置 core.hooksPath，输出十行以内的开工清单。
- prompt   （UserPromptSubmit）：对话记录（transcript_path）超过 FFF_LONG_MB（默认 4）MB → 提醒按铁律 18 写交接、开新会话。
- pretool  （PreToolUse）：
    Agent / Task / Workflow：提示或脚本里必须写“token 预算：约 N 万”（铁律 17：动手前先估 token）；
        超过 FFF_BUDGET_MAX（默认 30 万）拦下；要整屏看截图（盲审、逐屏、整屏）却不走 新情况检测.py / 截图盲审准备.py 的拦下。
    Read 图片：同一会话看图超过 FFF_IMG_LIMIT（默认 30）张拦下，改用 新情况检测.py。
    Bash：pkill -f 的模式不带方括号（会匹配到自己的 shell，踩坑 12）、pgrep/pkill 模式里有中文（ps 里显示成 ?，踩坑 54）拦下。
拦下 = 退出码 2 + stderr 写原因（Claude Code 把原因交给模型）。钩子自己出任何错都放行（退出 0），不卡正常工作。
双向验证：python3 tools/防复发/验证/钩子.py"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

IMG = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')
CHECKLIST = """开工清单（CLAUDE.md 铁律 13—18，钩子强制执行）：
1. 先设计最好的方法：放在哪里跑才能一次启动、自己流到底（长机器活 → GitHub Actions）；能用程序查的不用模型看。
2. 先估 token：开 Agent / Workflow 必须在提示里写“token 预算：约 N 万”，超过 30 万重新设计。
3. 新任务开新会话（铁律 18）；对话变长就写一页交接、换新会话。
4. 看截图只看新情况（新情况检测.py），整屏盲审被禁止；同一会话看图上限 30 张。
5. 改了任何检查程序，先跑 python3 tools/防复发/防复发自检.py --测试。
6. 读日志、读文件只读需要的几行；汇报只说结果。"""


def env_num(k, d):
    try:
        return float(os.environ.get(k, d))
    except ValueError:
        return float(d)


def deny(msg):
    sys.stderr.write('【防复发钩子拦下】' + msg + '\n')
    sys.exit(2)


def budget(text):
    """“token 预算：约 20 万” / “token budget: 150k” → 200000；没写返回 None。"""
    m = re.search(r'token\s*(?:预算|budget)\s*(?:估计|估算)?\s*[:：=]?\s*(?:约|大约|~|≈)?\s*([\d.]+)\s*(万|千|k|K|m|M|百万)?', text, re.I)
    if not m:
        return None
    n = float(m.group(1))
    return n * {'万': 1e4, '千': 1e3, 'k': 1e3, 'K': 1e3, 'm': 1e6, 'M': 1e6, '百万': 1e6}.get(m.group(2) or '', 1)


SCREEN = re.compile(r'整屏|逐屏|每一屏|全部截图|所有截图|盲审|screenshot', re.I)
SAFE = re.compile(r'新情况检测|截图盲审准备')


def check_agent(tool, inp):
    text = ''
    if tool == 'Workflow':
        text = inp.get('script') or ''
        p = inp.get('scriptPath')
        if p and Path(p).is_file():
            text += Path(p).read_text('utf-8', 'ignore')
        if not text and inp.get('name'):
            for c in Path(os.environ.get('CLAUDE_PROJECT_DIR', '.')).glob(f".claude/workflows/{inp['name']}*"):
                text += c.read_text('utf-8', 'ignore')
        text += json.dumps(inp.get('args') or '', ensure_ascii=False)
    else:
        text = (inp.get('prompt') or '') + (inp.get('description') or '')
    b = budget(text)
    if b is None:
        deny(f'{tool} 的提示（或脚本注释）里没写 token 预算。铁律 17：动手前先估 token——写上“token 预算：约 N 万”（N 按 读多少文件/图 × 几个代理 估）再开。')
    mx = env_num('FFF_BUDGET_MAX', 300000)
    if b > mx:
        deny(f'{tool} 的 token 预算 {b:,.0f} 超过上限 {mx:,.0f}。铁律 17：超过几十万的方案一律重新设计（程序兜底、只看新情况、缩小规模）。')
    if SCREEN.search(text) and not SAFE.search(text):
        deny(f'{tool} 要整屏看截图（盲审 / 逐屏）。铁律 17 已淘汰整屏盲审：先用 新情况检测.py 列出新情况，再用 截图盲审准备.py（上限 40 屏）只看那几屏。')


def check_read(inp, sid):
    p = str(inp.get('file_path') or '')
    if not p.lower().endswith(IMG):
        return
    d = Path(tempfile.gettempdir()) / 'fangfufa_hooks'
    d.mkdir(exist_ok=True)
    f = d / (re.sub(r'[^\w-]', '_', sid or 'nosession') + '.img')
    n = int(f.read_text() or 0) if f.exists() else 0
    lim = env_num('FFF_IMG_LIMIT', 30)
    if n >= lim:
        deny(f'本会话已经看了 {n} 张图（上限 {lim:.0f}）。铁律 17：不许一屏一屏看图——用 新情况检测.py 只列新情况、拼成 2×2 看；要再看就开新会话。')
    f.write_text(str(n + 1))


def check_bash(inp):
    cmd = inp.get('command') or ''
    for m in re.finditer(r'\b(pkill|pgrep)\b([^|;&\n]*)', cmd):
        args = m.group(2)
        if re.search(r'[^\x00-\x7f]', args):
            deny(f'{m.group(1)} 的模式里有中文：ps 里中文显示成 ?，匹配不到（踩坑 54）。改用 ASCII 模式，如 pgrep -f "ttsenv/bin/python .*[-]-stills"。')
        if m.group(1) == 'pkill' and re.search(r'(^|\s)-\w*f', args) and '[' not in args:
            deny('pkill -f 的模式会匹配到执行它的 shell 自己（踩坑 12）。按具体 PID 结束进程（kill <PID>），或模式里用方括号防自匹配。')


def session():
    root = os.environ.get('CLAUDE_PROJECT_DIR') or '.'
    subprocess.run(['git', '-C', root, 'config', 'core.hooksPath', '.githooks'], capture_output=True)
    print(CHECKLIST)


def prompt(data):
    p = data.get('transcript_path')
    if not p or not os.path.isfile(p):
        return
    mb = os.path.getsize(p) / 1e6
    lim = env_num('FFF_LONG_MB', 4)
    if mb > lim:
        print(f'【防复发钩子】本对话记录已 {mb:.1f} MB（超过 {lim:g} MB），每一步都在重读很长的上下文。按铁律 18：'
              '做完当前这一小步就写一页交接（现状、按顺序要做的命令、要用户定的事），提交推送，开新会话接着做；不要在本会话开新任务。')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ''
        data = json.loads(raw) if raw.strip() else {}
        if mode == 'session':
            session()
        elif mode == 'prompt':
            prompt(data)
        elif mode == 'pretool':
            tool, inp = data.get('tool_name') or '', data.get('tool_input') or {}
            if tool in ('Agent', 'Task', 'Workflow'):
                check_agent(tool, inp)
            elif tool == 'Read':
                check_read(inp, data.get('session_id') or '')
            elif tool == 'Bash':
                check_bash(inp)
    except SystemExit:
        raise
    except Exception as e:                    # 钩子自己出错一律放行，不卡正常工作
        sys.stderr.write(f'防复发钩子内部错误（已放行）：{e}\n')
    sys.exit(0)


if __name__ == '__main__':
    main()
