#!/usr/bin/env bash
if [[ -n "${IELTS_WORK:-}" ]]; then exec > >(tee "$IELTS_WORK/native-package.log") 2>&1; fi
set -euo pipefail
/opt/ttsenv/bin/python -m pip install -q img2pdf==0.6.3 PyMuPDF==1.26.6
out="$RUNNER_TEMP/out"
files=("$TARGET"/最终视频/*.mp4)
/opt/ttsenv/bin/python "$TARGET/tools/reading_notes.py" "${files[0]}" "$out/Reading-notes.pdf" "$out/pdf-proof.json"
/opt/ttsenv/bin/python "$TARGET/tools/series_render.py" package --out "$out"
key=$(jq -r .material_sha256 "$out/$IELTS_LESSON-receipt.json")
version="$IELTS_LESSON-${key:0:16}.zip"
mv "$out/$IELTS_LESSON.zip" "$out/$version"
gh release upload "$STAGING" "$out/$version" "$out/$IELTS_LESSON-receipt.json" --clobber
python "$TARGET/tools/release_assets.py" "$STAGING" "$version" "$RUNNER_TEMP/check"
cmp "$out/$version" "$RUNNER_TEMP/check/$version"
