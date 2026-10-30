"""踩坑 80 双向验证：小店商品简介（六级作文/讲义/商品图/标题与描述.py 的 desc_problems）。
1001 字报、1000 字不报（换行不计）；去掉“虚拟商品”或“不支持退”报；放进禁用词报。"""
import subprocess, sys, pathlib
f = pathlib.Path(__file__).resolve().parents[3] / '六级作文/讲义/商品图/标题与描述.py'
r = subprocess.run([sys.executable, str(f), '--自检'], capture_output=True, text=True)
print(r.stdout.strip() or r.stderr.strip()[-300:])
sys.exit(r.returncode)
