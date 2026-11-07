#!/bin/bash
# 逐篇生成视频并提交推送（铁律 9）；中考、四级、专八、六级的 batch_video.sh 都转到这里（踩坑 87）。
#   bash tools/video/batch_commit.sh <项目> <篇目>...
#   BATCH_VIDEOS=最终视频_校园 bash …   成品目录（默认 最终视频；要与 <项目>/tools/verify_all.py 核查的目录相同，专八 最终视频_校园、六级 最终视频_黑板）
# 以前：引擎先把成品写进 <项目>/最终视频 再核查，提前 SystemExit、核查抛异常、进程被杀都会留下没核查的 MP4，
#       下一篇成功后 git add <项目>/最终视频 把它一起提交了。现在：
#   ① 每篇开始前、失败后，都把 <项目>/最终视频 里没提交的改动还原、没登记的文件删掉；
#   ② 引擎成功后再跑 <项目>/tools/verify_all.py <篇目>（独立重测），通过才提交；
#   ③ 只提交这一篇：最终视频 里有改动的必须恰好是这一篇的一个 MP4，否则不提交。
# 测试用环境变量：BATCH_PY（Python，默认 /opt/ttsenv/bin/python）、BATCH_NO_PUSH=1（不推送）。
cd "$(dirname "$0")/../.." || exit 1
P="$1"; shift
[ -n "$P" ] && [ -f "$P/tools/make_video.py" ] && [ -f "$P/tools/verify_all.py" ] || { echo "用法：batch_commit.sh <项目> <篇目>..."; exit 2; }
PY="${BATCH_PY:-/opt/ttsenv/bin/python}"
V="$P/${BATCH_VIDEOS:-最终视频}"
clean() {   # 还原 最终视频 里没提交的改动（只动有改动的已登记文件，不碰稀疏检出移出的），删掉没登记的文件
  git diff --name-only -z -- "$V" | xargs -0 -r git checkout -q --
  git clean -fq -- "$V"
}
changed() { { git -c core.quotepath=off diff --name-only -- "$V"; git -c core.quotepath=off ls-files --others --exclude-standard -- "$V"; } | sort -u; }
fail=0
for id in "$@"; do
  clean
  if ! "$PY" "$P/tools/make_video.py" "$id" --out "$V"; then echo "视频未通过：$id"; clean; fail=1; continue; fi
  if ! "$PY" "$P/tools/verify_all.py" "$id"; then echo "独立核查未通过：$id"; clean; fail=1; continue; fi
  mapfile -t ch < <(changed)
  if [ "${#ch[@]}" -ne 1 ] || [[ "${ch[0]}" != *.mp4 ]]; then
    echo "最终视频里的改动不是恰好这一篇的一个 MP4，不提交：${ch[*]}"; clean; fail=1; continue
  fi
  git add -- "${ch[0]}" && git commit -q -m "${P}视频：$id

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || { echo "提交失败：$id"; fail=1; continue; }
  [ -n "$BATCH_NO_PUSH" ] || git push -q -u origin "$(git rev-parse --abbrev-ref HEAD)" || { echo "推送失败，停止：$id"; exit 1; }
done
clean
echo 全部完成
exit $fail
