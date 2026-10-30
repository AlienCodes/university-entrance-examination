#!/bin/bash
# 新容器一次搭好 /opt/ttsenv（配音、识别分诊、分屏、截图预检都用它）。专八 2026（2026-10-24）踩到：
#   pip 默认装最新 torch 2.14，没有配套的 torchaudio（PyPI 最高 2.11），qa.py 的自然度模型（SpeechMOS）要 torchaudio → 识别自检出错；
#   download.pytorch.org 被代理拦，只能从 PyPI 装成对的 torch==2.11.0 torchaudio==2.11.0。
set -e
cd "$(dirname "$0")/../.."
[ -x /opt/ttsenv/bin/python ] || python3.11 -m venv /opt/ttsenv
P="/opt/ttsenv/bin/pip --timeout 60 --retries 5"
$P install -q -r .github/cet6-render-requirements.txt
$P install -q "kokoro-onnx>=0.6.1" "misaki[en]>=0.9.4" num2words soundfile soxr pyloudnorm lameenc pypdf pyyaml \
  "torch==2.11.0" "torchaudio==2.11.0" \
  en_core_web_sm@https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
# 2026-10-25：新装的 spacy 3.8.16 + preshed 3.0.14 / cymem 2.0.16 一加载 en_core_web_sm 就 OverflowError（分屏建议.py 跑不起来）；钉在能用的版本，并当场试加载
$P install -q "spacy==3.8.7" "thinc==8.3.6" "preshed==3.0.9" "cymem==2.0.11" "murmurhash==1.0.12"
/opt/ttsenv/bin/python -c "import spacy; spacy.load('en_core_web_sm')('It is ok.'); print('spacy 正常')"
/opt/ttsenv/bin/python -c "import torch, torchaudio, kokoro_onnx, misaki, playwright; assert torch.__version__.split('+')[0] == torchaudio.__version__.split('+')[0], (torch.__version__, torchaudio.__version__); print('环境就绪：torch', torch.__version__)"
/opt/ttsenv/bin/python tools/tts/download_models.py --qa
git config core.hooksPath .githooks
