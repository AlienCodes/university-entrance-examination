#!/bin/bash
# 按给定顺序逐篇生成专八音频，每篇做完立刻自检 + 识别分诊（及时做、及时查，铁律 15）；每篇完成即提交推送（铁律 9）。
# 用法：bash 专八/tools/batch_audio.sh t11 t12 …
# 任何一篇没通过（响度 / 电磁音等检查、或识别分诊有待核的读错）就停在这一篇：改读音（读音修正.json）、试合成确认
# （tools/tts/识别复核.py 专八 试合成 …），再从这一篇重跑。以前 17 篇全配完才看识别报告，查出 4 篇读错整篇重做（踩坑 72、73）。
cd "$(dirname "$0")/../.." || exit 1
PY=/opt/ttsenv/bin/python
$PY 专八/tools/pron_check.py > /dev/null 2>&1 || { echo "停止：专名 / 词形歧义读音还有没核对的词（先跑 pron_check.py，核对后 --approve）"; exit 1; }
for id in "$@"; do
  $PY 专八/tools/make_audio.py "$id" || { echo "停止：音频未通过 $id"; exit 1; }
  $PY 专八/tools/qa_audio.py "$id" || { echo "停止：自检出错 $id"; exit 1; }
  $PY tools/tts/识别分诊.py 专八 "$id"; tri=$?
  git add 专八/audio && git commit -q -m "专八音频：$id 及自检（识别分诊$([ $tri = 0 ] && echo 通过 || echo 有待核)）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Bo2nvX3EdvyJhDdDqVayNH" && git push -q -u origin claude/epic-edison-4gkcfb
  [ $tri = 0 ] || { echo "停止：$id 识别分诊有待核（见上面），改读音、试合成确认后从 $id 重跑"; exit 1; }
done
echo 全部完成
