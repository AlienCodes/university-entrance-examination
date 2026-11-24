#!/usr/bin/env bash
if [[ -n "${IELTS_WORK:-}" ]]; then exec > >(tee "$IELTS_WORK/native-video.log") 2>&1; fi
set -euo pipefail
/opt/ttsenv/bin/python "$TARGET/tools/series_render.py" align
export IELTS_SYSTEM_FFMPEG="$(command -v ffmpeg)"
export PATH="$PWD/$TARGET/tools/静帧编码:$PATH"
/opt/ttsenv/bin/python "$TARGET/tools/pilot_video.py" video
mkdir -p "$RUNNER_TEMP/out"
files=("$TARGET"/最终视频/*.mp4)
test "${#files[@]}" -eq 1
/opt/ttsenv/bin/python "$TARGET/tools/check_ending.py" "${files[0]}" "$RUNNER_TEMP/out/ending.json"
if [[ "${IELTS_NARRATOR:-}" == Aiden ]]; then
  case "$IELTS_LESSON" in
    C6T1P3|C8T1P1|C11T1P2|C11T1P3|C11T2P2|C11T4P2|C12T1P1|C13T2P1|C13T2P2|C13T4P1) /opt/ttsenv/bin/python -m pip install -q pocketsphinx==5.0.4 ;;
    C11T4P3) /opt/ttsenv/bin/python -m pip install -q onnxruntime==1.32.0 ;;
  esac
  /opt/ttsenv/bin/python "$TARGET/tools/aiden_encoded_audio.py" "${files[0]}" "$RUNNER_TEMP/out/phrase-playback.json"
fi
