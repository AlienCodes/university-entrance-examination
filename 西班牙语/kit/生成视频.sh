#!/usr/bin/env bash
# 生成西班牙语逐句精读视频（macOS / Linux）：用工具包 .venv 里的 Python 运行 西班牙语/tools/batch.py，参数原样传过去。
#   ./生成视频.sh es01                              # 一篇（默认音色、默认背景 C）
#   ./生成视频.sh all --voice supertonic3_M1F5_25 --style 5
#   ./生成视频.sh --list        ./生成视频.sh --check        ./生成视频.sh --help
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VPY="$KIT/.venv/bin/python"
if [ ! -x "$VPY" ]; then
  echo "还没安装：请先在工具包文件夹里运行 bash install.sh" >&2
  exit 1
fi
exec "$VPY" -X utf8 "$KIT/西班牙语/tools/batch.py" "$@"
