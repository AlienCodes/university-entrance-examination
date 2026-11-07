#!/bin/bash
# 整批重做：音频（含自检）→ 视频 → 本批总核查。每篇完成即提交推送；中途中断后重跑会从头再做（已提交的不会丢）。
# 用法：bash 四级/tools/redo_batch.sh c40 c39 …
cd "$(dirname "$0")/../.." || exit 1
bash 四级/tools/batch_audio.sh "$@"
bash 四级/tools/batch_video.sh "$@"
/opt/ttsenv/bin/python 四级/tools/verify_all.py "$@"
echo "verify exit $?"
