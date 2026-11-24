#!/usr/bin/env bash
set -euo pipefail
speech_packages=(espeak-ng)
if [[ "${IELTS_NARRATOR:-}" == Aiden ]]; then speech_packages+=(sox); fi
python .github/actions/cet6-chalk-env/prepare_packages.py 141 --decoder-only --extra-packages "${speech_packages[@]}"
python -m venv "$RUNNER_TEMP/speech"
sp="$RUNNER_TEMP/speech/bin/python"
if [[ "${IELTS_NARRATOR:-}" == Aiden ]]; then
  "$sp" -m pip install -q torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
  "$sp" -m pip install -q qwen-tts==0.1.1 sherpa-onnx==1.13.8
  case "${IELTS_LESSON:-}" in
    C6T1P3|C8T1P1|C11T4P2|C12T1P1|C13T2P1|C13T2P2) "$sp" -m pip install -q pocketsphinx==5.0.4 ;;
  esac
else
  "$sp" -m pip install -q torch --index-url https://download.pytorch.org/whl/cpu
fi
"$sp" -m pip install -q 'click==8.1.8' 'typer==0.16.0' 'numpy<2.3' 'spacy==3.8.7' 'thinc==8.3.6' 'preshed==3.0.9' 'cymem==2.0.13' 'murmurhash==1.0.12' 'kokoro-onnx==0.6.1' 'misaki[en]==0.9.4' num2words soxr pyloudnorm soundfile lameenc scipy
"$sp" -m pip install -q --no-deps https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
if [[ "${IELTS_NARRATOR:-}" != Aiden ]]; then "$sp" tools/tts/download_models.py; fi
