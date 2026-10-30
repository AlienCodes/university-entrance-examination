#!/bin/bash
# 推送触发 Actions 前在本机预演：按工作流同样的命令（plan 的 --list + 每个 shard 的合成），用假 qwen_tts（返回真实音频），处理链照真的走。
# 用法：bash tools/防复发/预演_qwen/预演.sh 任务_xxx.json [shard…]   （默认 shard 0；任何一步出错即停）
# 第一步：防复发自检（与 GitHub fangfufa-check 同一条命令），不过不往下走——推送前在本机先过，CI 不再红。
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${CI_PY:-python3}
$PY tools/防复发/防复发自检.py --不查复盘 --测试 --ci | tail -1
T="高考语法填空/tts/$1"; shift
N=$(python3 高考语法填空/tools/qwen_synth.py --task "$T" --list)
echo "作业：$N"
OUT=$(mktemp -d)
for s in "${@:-0}"; do
  PYTHONPATH=tools/防复发/预演_qwen /opt/ttsenv/bin/python 高考语法填空/tools/qwen_synth.py --task "$T" --shard "$s" --out "$OUT"
done
python3 - "$OUT" <<'PY'
import json, sys
from pathlib import Path
ms = sorted(Path(sys.argv[1]).rglob('meta_part*.json'))
assert ms, '没有产出 meta'
for p in ms:
    m = json.loads(p.read_text('utf-8'))
    ch = m.get('chain')
    print(p.parts[-3:], '段数', len(m['segments']), '处理链', ch if ch is None else ch.get('passed'))
    assert ch is None or ch['passed'], ch
PY
rm -rf "$OUT"
echo 预演通过
