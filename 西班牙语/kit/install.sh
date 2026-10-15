#!/usr/bin/env bash
# 西班牙语逐句精读视频工具包：安装（macOS / Linux）。在工具包文件夹里运行：
#   bash install.sh              # 基本安装：Supertonic 配音 + 4K 视频 + 自动核查（约 1 GB）
#   bash install.sh --qwen3      # 另装 Qwen3 真人感配音要的 PyTorch 等（再加约 2 GB）；分卷模型在本文件夹里时顺便解压
#   bash install.sh --mirror     # 在国内：用清华 PyPI 镜像、npmmirror 的浏览器镜像下载（快很多）
#   bash install.sh --python /path/to/python3.12   # 指定 Python（默认自动找 3.12 → 3.11 → 3.13 → 3.10）
# 装好的东西都在本文件夹的 .venv/ 里，不改系统；删掉 .venv/ 就是卸载。可以重复运行（已装好的会跳过）。
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$KIT"
QWEN=0; MIRROR=0; PY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --qwen3) QWEN=1 ;;
    --mirror) MIRROR=1 ;;
    --python) shift; PY="${1:-}" ;;
    --python=*) PY="${1#--python=}" ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "不认识的选项：$1（可用：--qwen3 --mirror --python 路径）"; exit 1 ;;
  esac
  shift
done
step() { printf '\n==== %s ====\n' "$*"; }
die() { printf '\n安装失败：%s\n' "$*" >&2; exit 1; }

step "1/6 找 Python（需要 3.10–3.13，推荐 3.12）"
ok_py() { "$1" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)' 2>/dev/null; }
if [ -n "$PY" ]; then
  ok_py "$PY" || die "$PY 不是 3.10–3.13 的 Python"
else
  for c in python3.12 python3.11 python3.13 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 && ok_py "$c"; then PY="$(command -v "$c")"; break; fi
  done
  [ -n "$PY" ] || die "没找到 Python 3.10–3.13。macOS：到 https://www.python.org/downloads/ 下载 3.12 安装包（或 brew install python@3.12）；Ubuntu：sudo apt install python3.12 python3.12-venv"
fi
echo "用 $PY（$("$PY" -V 2>&1)）"

step "2/6 建虚拟环境 .venv"
VPY="$KIT/.venv/bin/python"
if [ ! -x "$VPY" ]; then
  "$PY" -m venv "$KIT/.venv" || die "建虚拟环境失败。Ubuntu/Debian 请先 sudo apt install python3-venv（或 python3.12-venv）再重试"
fi
PIPX=()
if [ "$MIRROR" = 1 ]; then
  PIPX=(-i https://pypi.tuna.tsinghua.edu.cn/simple)
  export PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
fi
"$VPY" -m pip install --upgrade pip ${PIPX[@]+"${PIPX[@]}"} -q || die "pip 升级失败（网络？在国内可加 --mirror）"

step "3/6 安装 Python 包（西班牙语/kit/requirements.txt）"
"$VPY" -m pip install -r "$KIT/西班牙语/kit/requirements.txt" ${PIPX[@]+"${PIPX[@]}"} || die "安装 Python 包失败（网络？在国内可加 --mirror）"

step "4/6 安装截图用的浏览器（Chromium，约 150 MB）"
"$VPY" -m playwright install chromium || die "浏览器下载失败（网络？在国内可加 --mirror；加了 --mirror 仍失败就去掉它再试）"
if [ "$(uname -s)" = Linux ]; then
  echo "Linux：如果后面自检提示浏览器打不开，运行：sudo $VPY -m playwright install-deps chromium"
fi

if [ "$QWEN" = 1 ]; then
  step "5/6 安装 Qwen3 配音要的 PyTorch 等（约 2 GB）"
  if [ "$(uname -s)" = Darwin ] && [ "$(uname -m)" != arm64 ]; then
    die "这台 Mac 是 Intel 芯片，没有能用的新版 PyTorch，Qwen3 配音装不了；请用 Supertonic 音色（基本安装已经可以用）"
  fi
  if [ "$(uname -s)" = Linux ]; then
    "$VPY" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu || die "PyTorch 安装失败（网络？）"
  else
    "$VPY" -m pip install torch torchaudio ${PIPX[@]+"${PIPX[@]}"} || die "PyTorch 安装失败（网络？在国内可加 --mirror）"
  fi
  "$VPY" -m pip install -r "$KIT/西班牙语/kit/requirements-qwen3.txt" ${PIPX[@]+"${PIPX[@]}"} || die "Qwen3 依赖安装失败"
  "$VPY" -m pip install --no-deps qwen-tts==0.1.1 ${PIPX[@]+"${PIPX[@]}"} || die "qwen-tts 安装失败"
  if [ ! -f "$KIT/西班牙语/models/qwen3-base/model.safetensors" ]; then
    if ls "$KIT"/qwen3-tts-1.7b-base.zip.0* >/dev/null 2>&1; then
      "$VPY" "$KIT/西班牙语/tools/join_parts.py" "$KIT" || die "Qwen3 模型分卷解压失败（看上面的说明）"
    else
      echo "还差 Qwen3 模型：从 Release 下载 qwen3-tts-1.7b-base.zip.001、.002 …（和 SHA256SUMS.txt）放进本文件夹，"
      echo "再运行：$VPY 西班牙语/tools/join_parts.py"
    fi
  fi
else
  step "5/6 Qwen3 配音：没选（要用的话重新运行 bash install.sh --qwen3）"
fi

step "6/6 检查 ffmpeg 并自检"
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "还没有 ffmpeg（生成视频要用）。安装方法："
  echo "  macOS：先装 Homebrew（https://brew.sh），再 brew install ffmpeg"
  echo "  Ubuntu / Debian：sudo apt install ffmpeg"
  echo "装好后重新运行 bash install.sh 自检。"
fi
chmod +x "$KIT/生成视频.sh" 2>/dev/null || true
"$VPY" "$KIT/西班牙语/tools/batch.py" --check || { echo; echo "自检没有全部通过：按上面的提示处理后，重新运行 bash install.sh（已装好的会跳过）。"; exit 1; }
echo
echo "安装完成。生成示例视频：./生成视频.sh es01 --voice supertonic3_M1F5_25"
echo "详细用法见 使用说明.md"
