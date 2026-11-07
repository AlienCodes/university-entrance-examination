"""踩坑 81 双向验证：作文讲义「题目译文」（tools/作文题目译文.py，四级作文、六级作文 讲义.py check 调用）。
现有 63 篇 0 处；拿掉字段、清空、一条没有中文、删掉 30 / 字数下限、改掉引号里的原句、改图表数字都要报出。"""
import subprocess, sys, pathlib
f = pathlib.Path(__file__).resolve().parents[2] / '作文题目译文.py'
r = subprocess.run([sys.executable, str(f), '--自检'], capture_output=True, text=True)
print(r.stdout.strip() or r.stderr.strip()[-300:])
sys.exit(r.returncode)
