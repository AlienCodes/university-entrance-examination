#!/bin/bash
# 用户本人声音：一条命令从录音到触发合成（出错即停）。录音在 Release user-voice（用户自己上传；本人同意声音公开使用）。
#   ① 下载 Release user-voice 的全部音频到临时目录（录音不进仓库，Release 里已有）；
#   ② 挑参考.py 程序挑参考片段 → tts/音色/用户本人.{json,挑选.md}；
#   ③ 当前任务.txt ← 任务_用户声音.json；预演（CI 同款自检 + 假模型走真处理链）；
#   ④ 提交推送 → 触发 Actions 合成；⑤ 等 gram-tts-out 出现 runs/任务_用户声音-*（每 2 分钟看一次，最多 2 小时），
#      取回后 选段.py → 样音/D_用户本人.mp3（完整处理链 + 合格证），提交推送。
# 用法：bash 高考语法填空/tools/用户声音.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=/opt/ttsenv/bin/python
REPO=aliencodes/university-entrance-examination
BR=claude/epic-edison-4gkcfb
T=$(mktemp -d)
curl -sSf "https://api.github.com/repos/$REPO/releases/tags/user-voice" > "$T/rel.json"
python3 - "$T" <<'PY'
import json, sys, subprocess
d = sys.argv[1]
assets = json.load(open(f'{d}/rel.json'))['assets']
aud = [a for a in assets if a['name'].lower().rsplit('.', 1)[-1] in ('wav', 'mp3', 'm4a', 'aac', 'flac', 'ogg', 'opus', 'webm', 'mp4', 'mov', 'amr', 'wma')]
assert aud, f'Release user-voice 里没有音频：{[a["name"] for a in assets]}'
for a in aud:
    subprocess.run(['curl', '-sSfL', '-o', f"{d}/{a['name']}", a['browser_download_url']], check=True)
    print('下载', a['name'], a['size'])
PY
mapfile -t FILES < <(find "$T" -type f ! -name rel.json)
$PY 高考语法填空/tools/挑参考.py --录音 "${FILES[@]}" --名 用户本人
$PY -c "import json; print(json.load(open('高考语法填空/tts/音色/用户本人.json'))['ref_text'])"
echo "任务_用户声音.json" > 高考语法填空/tts/当前任务.txt
echo "# $(date -u +%FT%TZ) 用户本人声音第 56 题样音" >> 高考语法填空/tts/当前任务.txt
CI_PY=${CI_PY:-python3} bash tools/防复发/预演_qwen/预演.sh 任务_用户声音.json
git add 高考语法填空/tts/音色/用户本人.json 高考语法填空/tts/音色/用户本人.挑选.md 高考语法填空/tts/当前任务.txt
git commit -qm "高考语法填空：用户本人声音参考片段（程序挑选、去呼吸），触发第 56 题样音合成"
for i in 1 2 3 4; do git push -q origin "$BR" && break; sleep $((2**i)); done
echo "已触发；等 Actions 合成" 
for k in $(seq 60); do
  git fetch -q origin gram-tts-out || true
  R=$(git ls-tree --name-only origin/gram-tts-out runs/ 2>/dev/null | grep '任务_用户声音-' | sort -V | tail -1 || true)
  if [ -n "$R" ] && git ls-tree -r --name-only origin/gram-tts-out "$R" | grep -q 'take3/meta_part0.json'; then break; fi
  R=""; sleep 120
done
[ -n "$R" ] || { echo "2 小时内没等到合成结果"; exit 1; }
rm -rf "$T/out"; mkdir -p "$T/out"
git archive origin/gram-tts-out "$R" | tar -x -C "$T/out"
$PY 高考语法填空/tools/选段.py --稿 高考语法填空/tts/样稿_56.json --run "$T/out/$R/user" --out 高考语法填空/样音/D_用户本人.mp3
$PY tools/tts/去呼吸.py 高考语法填空/样音/D_用户本人.mp3
git add 高考语法填空/样音/D_用户本人.*
git commit -qm "高考语法填空：用户本人声音第 56 题样音（完整处理链、去呼吸、合格证）"
for i in 1 2 3 4; do git push -q origin "$BR" && break; sleep $((2**i)); done
rm -rf "$T"
echo 用户声音样音完成
