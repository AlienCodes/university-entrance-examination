#!/bin/bash
# 新容器一次搭好 /opt/ttsenv（配音、识别分诊、分屏、截图预检都用它）。专八 2026（2026-10-24）踩到：
#   pip 默认装最新 torch 2.14，没有配套的 torchaudio（PyPI 最高 2.11），qa.py 的自然度模型（SpeechMOS）要 torchaudio → 识别自检出错；
#   download.pytorch.org 被代理拦，只能从 PyPI 装成对的 torch==2.11.0 torchaudio==2.11.0。
set -e
cd "$(dirname "$0")/../.."
[ -x /opt/ttsenv/bin/python ] || python3.11 -m venv /opt/ttsenv
P=/opt/ttsenv/bin/pip
$P install -q -r .github/cet6-render-requirements.txt
$P install -q "kokoro-onnx>=0.6.1" "misaki[en]>=0.9.4" num2words soundfile soxr pyloudnorm lameenc \
  "torch==2.11.0" "torchaudio==2.11.0" \
  en_core_web_sm@https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
/opt/ttsenv/bin/python -c "import torch, torchaudio, kokoro_onnx, misaki, playwright; assert torch.__version__.split('+')[0] == torchaudio.__version__.split('+')[0], (torch.__version__, torchaudio.__version__); print('环境就绪：torch', torch.__version__)"
/opt/ttsenv/bin/python tools/tts/download_models.py --qa
git config core.hooksPath .githooks
