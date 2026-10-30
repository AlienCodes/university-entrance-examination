"""双向验证：六级作文讲义三份 PDF 的目录链接检查（踩坑 79）。
现在的 PDF 必须 0 处；去掉目录链接、一个链接改跳下一页、去掉书签、没有提示文字，都必须报出来（讲义.py toc-selftest）。"""
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
sys.exit(subprocess.run([sys.executable, str(R / '六级作文' / 'tools' / '讲义.py'), 'toc-selftest'], cwd=R).returncode)
