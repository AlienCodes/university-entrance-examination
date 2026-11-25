#!/usr/bin/env bash
# A worker also has generated files in its checkout. Use a separate Git index
# and preserve receipts saved by other workers finishing at the same time.
set -euo pipefail
lesson=${1:?lesson}
[[ "$lesson" =~ ^C(1[0-3]|[6-9])T[1-4]P[1-3]$ ]]
branch=codex/ielts-academic-reading
base='雅思/学术阅读/审校/Aiden/13-6'
files=("$base/逐词核音/$lesson.json" "$base/复验原声/$lesson.退回.json")
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
export GIT_INDEX_FILE="$tmp/index"
for delay in 0 2 5 10 20 40; do
  sleep "$delay"
  git fetch -q --no-tags origin "refs/heads/$branch"
  tip=$(git rev-parse FETCH_HEAD)
  git -c core.sparseCheckout=false read-tree "$tip"
  for path in "${files[@]}"; do
    [[ -f "$path" ]] || continue
    new=$(git hash-object -w -- "$path")
    original=$(git rev-parse --verify -q "HEAD:$path" || true)
    current=$(git rev-parse --verify -q "$tip:$path" || true)
    [[ "$new" != "$original" && "$new" != "$current" ]] || continue
    if [[ "$original" != "$current" ]]; then
      echo "$lesson already has a different remote review; preserving it" >&2
      exit 1
    fi
    git update-index --add --cacheinfo "100644,$new,$path"
  done
  tree=$(git write-tree)
  [[ "$tree" != "$(git rev-parse "$tip^{tree}")" ]] || exit 0
  commit=$(git -c user.name='github-actions[bot]' -c user.email='41898282+github-actions[bot]@users.noreply.github.com' commit-tree "$tree" -p "$tip" -m "Save final-film word check for $lesson")
  if git push -q origin "$commit:refs/heads/$branch"; then exit 0; fi
done
exit 1
