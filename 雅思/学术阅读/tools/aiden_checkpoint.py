"""Recover completed phrase recordings from an earlier run of this production workflow."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from aiden_profile import PAUSE_POLICY
from lesson import PID


def gh_json(endpoint):
    return json.loads(subprocess.check_output(["gh", "api", endpoint]))


def restore_archive(archive, folder):
    folder.mkdir(parents=True, exist_ok=True)
    restored = 0
    with zipfile.ZipFile(archive) as z:
        for note in z.namelist():
            if not re.fullmatch(r"aiden-takes/[0-9a-f]{64}\.json", note):
                continue
            details = z.read(note)
            data = json.loads(details)
            if data.get("policy") != PAUSE_POLICY:
                continue
            wavename = note[:-5] + ".flac"
            wav = z.read(wavename)
            if (not data.get("transcript") or not data.get("timed") or not wav.startswith(b"fLaC")
                    or hashlib.sha256(wav).hexdigest() != data.get("sha256")):
                raise ValueError("An archived recording differs from its recognition evidence")
            target = folder / Path(wavename).name
            meta = folder / Path(note).name
            if target.exists() and meta.exists():
                previous = json.loads(meta.read_bytes())
                if hashlib.sha256(target.read_bytes()).hexdigest() != previous.get("sha256"):
                    raise ValueError("A restored recording has inconsistent metadata")
                continue
            target.write_bytes(wav)
            meta.write_bytes(details)
            restored += 1
    return restored


def recover():
    config = json.loads(Path(".github/ielts-aiden-batch.json").read_text())
    runs = config.get("recover_runs", [])
    if not runs:
        return
    base = "repos/" + os.environ["GITHUB_REPOSITORY"]
    work = Path(os.environ["IELTS_WORK"])
    for run_id in runs:
        if type(run_id) is not int or run_id < 1:
            raise ValueError("Invalid source run")
        run = gh_json(f"{base}/actions/runs/{run_id}")
        if (run["head_branch"] != "codex/ielts-academic-reading"
                or run["path"] != ".github/workflows/ielts-aiden-production.yml"):
            raise ValueError("The recordings are from a different production workflow")
        run_artifacts = subprocess.check_output([
            "gh", "api", "--paginate", "--jq", ".artifacts[] | @json",
            f"{base}/actions/runs/{run_id}/artifacts?per_page=100"
        ], text=True)
        prefix = "aiden-" + PID + "-checks-"
        artifacts = [json.loads(line) for line in run_artifacts.splitlines() if line]
        for asset in sorted(artifacts, key=lambda x: x["id"], reverse=True):
            if (asset["expired"] or not asset["name"].startswith(prefix)
                    or not asset["name"][len(prefix):].isdigit()):
                continue
            with tempfile.TemporaryDirectory(dir=work) as temp:
                path = Path(temp) / "recordings.zip"
                with path.open("wb") as out:
                    subprocess.run(["gh","api",f"{base}/actions/artifacts/{asset['id']}/zip"],
                                   stdout=out,check=True)
                with path.open("rb") as fetched:
                    digest = hashlib.file_digest(fetched, "sha256").hexdigest()
                if path.stat().st_size != asset["size_in_bytes"] or "sha256:" + digest != asset["digest"]:
                    raise ValueError("Incomplete or altered recording archive")
                count = restore_archive(path, work / "aiden-takes")
            print(f"{PID} recovered {count} complete recordings from job artifact {asset['id']}", flush=True)


if __name__ == "__main__":
    recover()
