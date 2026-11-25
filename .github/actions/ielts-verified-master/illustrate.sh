#!/usr/bin/env bash
set -euo pipefail
if [[ "${IELTS_AIDEN_BATCH:-}" != "13-6" ]]; then exit 0; fi

# This check uses only the standard library. Reuse the matching, downloaded
# 4K master before setting up video tools on a fresh runner.
complete=$(python "$TARGET/tools/aiden_batch.py" cached 13-6 --lesson "$IELTS_LESSON" --with-illustration)
if [[ "$complete" == true ]]; then
  echo "$IELTS_LESSON already has its checked illustrated 4K video"
  exit 0
fi

python_bin=/opt/ttsenv/bin/python
if [[ ! -x "$python_bin" ]] || ! "$python_bin" -c 'import av,numpy,playwright; assert hasattr(av.container.OutputContainer,"add_stream_from_template")' 2>/dev/null; then
  python -m venv "$RUNNER_TEMP/illustrated-env"
  python_bin="$RUNNER_TEMP/illustrated-env/bin/python"
  "$python_bin" -m pip install -q av==16.0.1 'numpy>=1.26,<3' playwright==1.57.0
fi
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y ffmpeg
fi
if ! command -v google-chrome >/dev/null && ! command -v chromium >/dev/null && [[ ! -x /opt/pw-browsers/chromium ]]; then
  "$python_bin" -m playwright install chromium
  browser=$("$python_bin" -c 'from playwright.sync_api import sync_playwright; p=sync_playwright().start(); print(p.chromium.executable_path); p.stop()')
  mkdir -p "$RUNNER_TEMP/illustrated-bin"
  ln -sf "$browser" "$RUNNER_TEMP/illustrated-bin/chromium"
  export PATH="$RUNNER_TEMP/illustrated-bin:$PATH"
fi
"$python_bin" "$TARGET/tools/illustration_stage.py" "$IELTS_LESSON" "$RUNNER_TEMP/illustrated/$IELTS_LESSON"
if [[ -n "${GITHUB_ENV:-}" && -f "$RUNNER_TEMP/illustrated/$IELTS_LESSON/$IELTS_LESSON-illustrated.json" ]]; then
  echo "IELTS_NEW_ILLUSTRATION=$IELTS_LESSON" >> "$GITHUB_ENV"
fi
