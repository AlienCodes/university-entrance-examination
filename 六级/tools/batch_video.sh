#!/bin/bash
# 按给定顺序逐篇生成六级 4K 视频，每篇通过 make_video.py 的成品核查和 verify_all.py 独立核查才提交推送（铁律 9）。
# 逐篇清理、只提交这一篇的做法在 tools/video/batch_commit.sh（踩坑 87：以前没核查的 MP4 会被下一篇一起提交）。
BATCH_VIDEOS="${BATCH_VIDEOS:-最终视频_黑板}" exec bash "$(dirname "$0")/../../tools/video/batch_commit.sh" 六级 "$@"
