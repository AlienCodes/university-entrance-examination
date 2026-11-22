#!/usr/bin/env bash
# Keep both model servers local to this runner. Their native libraries are independent.
set -euo pipefail
LD_LIBRARY_PATH="$(dirname "$IELTS_MT_BIN")" "$IELTS_MT_BIN" -m "$IELTS_MT_MODEL" -t 4 -c 2200 --parallel 1 -ngl 0 --host 127.0.0.1 --port 8124 > "$RUNNER_TEMP/translation.log" 2>&1 &
translator=$!
LD_LIBRARY_PATH="$(dirname "$IELTS_EDITOR_BIN")" "$IELTS_EDITOR_BIN" -m "$IELTS_EDITOR_MODEL" -t 4 -c 10000 -np 1 -ngl 0 --host 127.0.0.1 --port 8123 --log-disable > "$RUNNER_TEMP/llama.log" 2>&1 &
editor=$!
trap 'kill "$translator" "$editor" 2>/dev/null || true' EXIT
for port in 8124 8123; do
  for retry in {1..60}; do
    if curl -fsS "http://127.0.0.1:$port/health" > /dev/null 2>&1; then break; fi
    sleep 2
  done
  curl -fsS "http://127.0.0.1:$port/health" > /dev/null
done
"$@"
