#!/bin/bash
# v2 开头预览：等 v1 会话推开头预览音频 → v2 4K（截图检查 + 成品核查全部）→ 1080p（< 95 MB）→ 推 高考续写/预览/。出错即停。
# 用法（先搭好环境）：SP=<scratchpad> bash 高考续写/tools/续写预览_v2.sh   （等 高考续写/audio/预览/*.mp3 出现在分支上，最多约 100 分钟）
set -euo pipefail
# 暂停出视频（用户 2026-11-03：“把我的这些所有的建议听完之后再做视频，别那么着急”）：协调会话通知“开始出视频”、
# 并逐条对照 高考续写/用户意见清单.md 之后，才用 RENDER_OK=1 跑
[ -n "${RENDER_OK:-}" ] || { echo "暂停出视频：等协调会话通知“开始出视频”（RENDER_OK=1 才渲染）"; exit 3; }
cd /home/user/university-entrance-examination
SP=${SP:-$(mktemp -d)}
BR=claude/epic-edison-4gkcfb
D=高考续写/讲解/2026_新课标Ⅰ卷
OUTN=${OUTN:-"2026 新课标Ⅰ卷 读后续写 讲解 开头预览 v2（高亮闪烁 + 中文意思）"}
MP3=${MP3:-}                                   # 给了 MP3（v2 逐块屏新音频）就不等
for k in $(seq 50); do
  [ -z "$MP3" ] || break
  git fetch -q origin "$BR" || true
  f=$(git -c core.quotepath=false ls-tree -r --name-only "origin/$BR" 高考续写/audio/预览/ | grep '\.mp3$' | head -1 || true)
  [ -n "$f" ] && MP3=$f && break
  sleep 120
done
[ -n "$MP3" ] || { echo "没等到开头预览音频"; exit 1; }
git pull -q --rebase origin "$BR"
ls tools/tts/models/sherpa-onnx-sense-voice* >/dev/null 2>&1 || { mkdir -p tools/tts/models; curl -fsSL --retry 5 https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17.tar.bz2 | tar xj -C tools/tts/models; }
python3 .github/check-audio-cert.py 高考续写/audio
rm -rf $SP/pv && mkdir -p $SP/pv
env -u LANG -u LC_ALL -u LANGUAGE /opt/ttsenv/bin/python 高考续写/tools/续写视频_v2.py --稿 "$D/稿.json" --音频 "$MP3" --video --out $SP/pv --png $SP/pv/png --name "$OUTN 4K.mp4"
O="高考续写/预览/$OUTN 1080p预览.mp4"
# 转 1080p：转前核对音频合格证，转后核对分辨率、音轨逐包相同、时长、大小（不过就删掉输出、停）
/opt/ttsenv/bin/python 高考续写/tools/转1080预览.py "$SP/pv/$OUTN 4K.mp4" "$MP3" "$O"
sz=$(stat -c %s "$O")
(cd 高考续写/预览 && sha256sum "$OUTN 1080p预览.mp4" > "$OUTN 1080p预览.mp4.sha256")
cp $SP/pv/png/stills.json "$SP/pv/stills.json"
git add "$O" "$O.sha256"
git commit -qm "高考续写：开头预览 v2（高亮闪一下 + 高亮下面中文意思；配音复用开头预览音频，4K 截图检查与成品核查全部通过）1080p

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BA1TPGtns9US2Vd52Dgvkc"
for i in 1 2 3 4; do git pull -q --rebase origin "$BR" && git push -q origin "$BR" && break; sleep $((2**i)); done
echo "PREVIEW_DONE size=$sz sha=$(cut -d' ' -f1 "$O.sha256")"
