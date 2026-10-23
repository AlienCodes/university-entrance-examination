"""踩坑 53：Release 不许钉在触发运行的那个提交上（GITHUB_SHA / github.sha）。
运行期间分支上改过工作流文件时，在旧提交上建标签等于“恢复旧版工作流文件”，GITHUB_TOKEN 没有 workflows 权限 → 403
（2026-10-17 六级黑板发布两次 403；诊断：同一命令 target=分支最新提交成功、target=旧提交 278c9bc 403）。
一律用分支名（GITHUB_REF_NAME / github.ref_name）：GitHub 在建标签那一刻取分支最新提交。发现违规就报错。"""
import re, sys
from pathlib import Path
# 防复发审计（2026-10-23）实测旧正则漏掉 3 种写法：--target ${{ github.sha }}、--target=$GITHUB_SHA、-f target_commitish=$GITHUB_SHA。
# 现在：target / target_commitish 后面（空格、等号、冒号）跟 GITHUB_SHA 或 github.sha 的任何写法都报
BAD = re.compile(r'(?:--target|target_commitish)["\']?\s*[=:\s]\s*["\']?\$?\{?\{?\s*(?:GITHUB_SHA|github\.sha)\b')
bad = []
for f in sorted(Path('.github/workflows').glob('*.yml')):
    for i, line in enumerate(f.read_text('utf-8').splitlines(), 1):
        if BAD.search(line):
            bad.append(f'{f}:{i}: {line.strip()}')
if bad:
    sys.exit('Release 钉在了触发提交上（踩坑 53，改用分支名）：\n  ' + '\n  '.join(bad))
print('Release 目标检查通过：没有工作流把 Release 钉在触发提交上')
