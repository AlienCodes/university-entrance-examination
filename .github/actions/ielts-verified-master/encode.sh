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
  /opt/ttsenv/bin/python "$TARGET/tools/aiden_boundaries.py" "${files[0]}" "$RUNNER_TEMP/out/phrase-playback.json"
fi
