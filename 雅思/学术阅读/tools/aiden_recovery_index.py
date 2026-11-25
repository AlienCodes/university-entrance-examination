"""Share the authorized recording archive listings across a production matrix."""
import json
import os
from functools import lru_cache
from pathlib import Path
import re
import subprocess
import sys

from release_assets import read_github, transient_read_error


ROOT = Path(__file__).resolve().parents[3]
SAVED = ROOT / ".github/ielts-aiden-recovery-index.json"
BRANCH = "codex/ielts-academic-reading"
WORKFLOW = ".github/workflows/ielts-aiden-production.yml"
RECORDING = re.compile(r"aiden-C[1-9]\d*T[1-4]P[1-3]-checks-[1-9]\d*")


def read_index(path, repository):
    data = json.loads(path.read_bytes())
    if data.get("version") != 1 or data.get("repository") != repository:
        raise ValueError("Recording index belongs to a different repository or format")
    return data["runs"]


def check_run(info, number):
    if (info["id"] != number or info["head_branch"] != BRANCH or info["path"] != WORKFLOW
            or not re.fullmatch(r"[0-9a-f]{40}", info["head_sha"])):
        raise ValueError(f"Run {number} is not an authorized recording source")
    return info


def run_info(repository, number):
    if type(number) is not int or number < 1:
        raise ValueError("Invalid recording source run")
    endpoint = f"repos/{repository}/actions/runs/{number}"
    fields = "{id,head_branch,path,head_sha,run_attempt,status,updated_at}"
    return check_run(json.loads(read_github(["gh", "api", endpoint, "--jq", fields])), number)


def list_recordings(repository, info):
    endpoint = f"repos/{repository}/actions/runs/{info['id']}/artifacts?per_page=100"
    fields = ".artifacts[] | select(.expired == false) | {id,name,digest,size_in_bytes,expires_at,workflow_run} | @json"
    results = []
    for line in read_github(["gh", "api", endpoint, "--paginate", "--jq", fields]).splitlines():
        asset = json.loads(line)
        if not RECORDING.fullmatch(asset["name"]):
            continue
        source = asset.pop("workflow_run")
        if source["id"] != info["id"] or source["head_sha"] != info["head_sha"]:
            raise ValueError(f"Recording {asset['id']} belongs to a different run")
        results.append(asset)
    return sorted(results, key=lambda asset: asset["id"], reverse=True)


@lru_cache(maxsize=1)
def indexes(repository):
    shared_path = os.environ.get("IELTS_AIDEN_RECOVERY_INDEX")
    if shared_path:
        return read_index(Path(shared_path), repository), {}
    saved = read_index(SAVED, repository) if SAVED.is_file() else {}
    return {}, saved


@lru_cache(maxsize=32)
def recording_source(repository, number):
    shared, saved = indexes(repository)
    if str(number) in shared:
        entry = shared[str(number)]
        return check_run(entry["run"], number), entry["artifacts"]
    # Older workflow definitions and standalone jobs can reuse the saved listing
    # after checking that GitHub still reports the same completed attempt.
    info = run_info(repository, number)
    entry = saved.get(str(number))
    if entry and info["status"] == "completed" and info == entry["run"]:
        return info, entry["artifacts"]
    return info, None


def build(destination, settled_only=False):
    repository = os.environ["GITHUB_REPOSITORY"]
    config = json.loads((ROOT / ".github/ielts-aiden-batch.json").read_bytes())
    stored = read_index(SAVED, repository) if SAVED.is_file() else {}
    records = {}
    for number in config.get("recover_runs", []):
        try:
            info = run_info(repository, number)
            if settled_only and info["status"] != "completed":
                continue
            old = stored.get(str(number))
            if old and info["status"] == "completed" and old["run"] == info:
                assets = old["artifacts"]
            else:
                assets = list_recordings(repository, info)
        except subprocess.CalledProcessError as exc:
            if not transient_read_error(exc):
                raise
            # An unavailable historical run must not block the other lessons.
            # An omitted run can still be fetched by its consumer.
            print(f"Run {number} temporarily unavailable for the shared index", file=sys.stderr)
            continue
        records[str(number)] = {"run": info, "artifacts": assets}
    destination.write_text(json.dumps({"version": 1, "repository": repository, "runs": records},
                                     ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Indexed {len(records)} runs and {sum(len(r['artifacts']) for r in records.values())} recording archives")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    parser.add_argument("--completed-only", action="store_true")
    args = parser.parse_args()
    build(args.destination, args.completed_only)
