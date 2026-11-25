"""Recover completed phrase recordings from an earlier run of this production workflow."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import zipfile

from aiden_profile import IDENTITY, PAUSE_POLICY, rejected_sources
from lesson import PID, PROJECT
from release_assets import fetch, inventory, read_github


def gh_json(endpoint):
    return json.loads(read_github(["gh", "api", endpoint]))


REVIEW_TAKES = 5


def reviewed_master_failures():
    return rejected_sources(PID)


def diagnostic_reports(report):
    """Keep the latest attempt at its original path and four prior attempts in bounded slots."""
    latest = report.parent / 'rejected' / report.name
    yield latest
    for slot in range(1, REVIEW_TAKES):
        stem = hashlib.sha256(f'{report.stem}:rereading:{slot}'.encode()).hexdigest()
        yield latest.with_name(stem + '.json')


def rejected_seed(report, key, printed):
    if (not isinstance(key,str) or not re.fullmatch(re.escape(PID) + r":[1-9]\d*",key)
            or not isinstance(printed,str) or not printed.strip() or not report.is_file()):
        return None
    entry = json.loads(report.read_bytes())
    if (entry.get("accepted") is not False or entry.get("key") != key or entry.get("printed") != printed
            or type(entry.get("seed")) is not int or not entry.get("issue")):
        return None
    raw = report.with_suffix(".flac")
    if raw.is_file() and hashlib.sha256(raw.read_bytes()).hexdigest() == entry.get("sha256"):
        return entry["seed"]
    return None


def restore_archive(archive, folder):
    folder.mkdir(parents=True, exist_ok=True)
    restored = 0
    with zipfile.ZipFile(archive) as z:
        for note in z.namelist():
            if re.fullmatch(r"aiden-takes/rejected/[0-9a-f]{64}\.json", note):
                details = z.read(note)
                data = json.loads(details)
                key, printed, seed = (data.get(k) for k in ("key", "printed", "seed"))
                if (data.get("accepted") is not False or not isinstance(key, str)
                        or not re.fullmatch(re.escape(PID) + r":[1-9]\d*", key)
                        or not printed or not data.get("issue") or type(seed) is not int
                        or data.get("stage") == "mastered-mp3"):
                    continue
                rejected = folder / "rejected" / Path(note).name
                previous = rejected_seed(rejected, key, printed)
                if previous is not None and previous >= seed:
                    continue
                wav = z.read(note[:-5] + ".flac")
                if not wav.startswith(b"fLaC") or hashlib.sha256(wav).hexdigest() != data.get("sha256"):
                    raise ValueError("Rejected recording does not match its diagnostic evidence")
                rejected.parent.mkdir(exist_ok=True)
                rejected.with_suffix(".flac").write_bytes(wav)
                rejected.write_bytes(details)
                continue
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


def snapshot_names():
    return (PID + "-takes-a.zip", PID + "-takes-b.zip")


def pack_snapshot(folder, archive):
    recordings = {}
    with zipfile.ZipFile(archive, "w") as result:
        for note in sorted(folder.glob("*.json")):
            if not re.fullmatch(r"[0-9a-f]{64}", note.stem):
                continue
            data = json.loads(note.read_bytes())
            if data.get("policy") != PAUSE_POLICY or not data.get("transcript") or not data.get("timed"):
                continue
            wav = note.with_suffix(".flac")
            with wav.open("rb") as src:
                digest = hashlib.file_digest(src, "sha256").hexdigest()
            if digest != data["sha256"]:
                raise ValueError("Recording no longer matches its recognition evidence: " + note.stem)
            recordings[note.stem] = digest
            result.write(wav, "aiden-takes/" + wav.name)
            result.write(note, "aiden-takes/" + note.name, compress_type=zipfile.ZIP_DEFLATED)
        for note in sorted((folder / "rejected").glob("*.json")):
            if not re.fullmatch(r"[0-9a-f]{64}", note.stem):
                continue
            data = json.loads(note.read_bytes())
            if data.get("stage") == "mastered-mp3" or rejected_seed(note,data.get("key"),data.get("printed")) is None:
                continue
            wav = note.with_suffix(".flac")
            result.write(wav, "aiden-takes/rejected/" + wav.name)
            result.write(note, "aiden-takes/rejected/" + note.name, compress_type=zipfile.ZIP_DEFLATED)
        manifest = dict(lesson=PID, narrator=IDENTITY, policy=PAUSE_POLICY, takes=recordings)
        result.writestr("snapshot.json", json.dumps(manifest, sort_keys=True))
    return len(recordings)


def restore_snapshot(stage, folder):
    names = snapshot_names()
    try:
        candidates = [a for name, a in inventory(stage).items() if name in names]
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"{PID}: snapshot inventory unavailable ({type(exc).__name__}), checking saved job artifacts", flush=True)
        return
    if not candidates:
        return
    for asset in sorted(candidates, key=lambda a: a["id"], reverse=True):
        try:
            with tempfile.TemporaryDirectory(dir=folder.parent) as temp:
                path = fetch(asset, temp)
                with zipfile.ZipFile(path) as z:
                    info = json.loads(z.read("snapshot.json"))
                    if (info["lesson"], info["narrator"], info["policy"]) != (PID, IDENTITY, PAUSE_POLICY):
                        raise ValueError("Snapshot belongs to a different lesson or narrator")
                    notes = {Path(n).stem for n in z.namelist() if re.fullmatch(r"aiden-takes/[a-f0-9]{64}\.json", n)}
                    if not notes or notes != set(info["takes"]):
                        raise ValueError("Incomplete snapshot")
                    for name in notes:
                        note = json.loads(z.read("aiden-takes/" + name + ".json"))
                        if note["sha256"] != info["takes"][name] or note.get("policy") != PAUSE_POLICY:
                            raise ValueError("Snapshot and recognition report disagree")
                count = restore_archive(path, folder)
            print(f"{PID}: recovered {count} accepted takes from {asset['name']}", flush=True)
            return
        except (KeyError, OSError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
            print(f"{PID}: unable to restore {asset['name']} ({type(exc).__name__}), checking the preceding copy", flush=True)


class PeriodicSnapshot:
    def __init__(self, folder):
        self.folder = folder
        group = os.environ.get("IELTS_AIDEN_BATCH", "")
        self.stage = os.environ.get("STAGING") if group in ("13-6", "5-1") else None
        if (self.stage != "ielts-academic-aiden-cache-" + group
                or ".github/workflows/ielts-aiden-production.yml@" not in os.environ.get("GITHUB_WORKFLOW_REF", "")):
            self.stage = None
        self.next_check = time.monotonic() + 600
        self.saved_files = set()

    def after_sentence(self, *, force=False):
        now = time.monotonic()
        if not self.stage or (not force and now < self.next_check):
            return
        self.next_check = now + 600
        try:
            files = {(str(note.relative_to(self.folder)),hashlib.sha256(note.read_bytes()).digest())
                     for pattern in ("*.json","rejected/*.json") for note in self.folder.glob(pattern)}
            if not files or files == self.saved_files:
                return
            inventory.cache_clear()
            remote = inventory(self.stage)
            names = snapshot_names()
            # Keep the newest verified generation while replacing the earlier one.
            target = min(names, key=lambda name: remote.get(name, {}).get("id", 0))
            with tempfile.TemporaryDirectory(dir=self.folder.parent) as temp:
                archive = Path(temp) / target
                count = pack_snapshot(self.folder, archive)
                if not count:
                    return
                with archive.open("rb") as src:
                    digest = "sha256:" + hashlib.file_digest(src, "sha256").hexdigest()
                subprocess.run(["gh", "release", "upload", self.stage, str(archive), "--clobber"], check=True, timeout=120)
                inventory.cache_clear()
                asset = inventory(self.stage).get(target, {})
                if (asset.get("digest"), asset.get("size")) != (digest, archive.stat().st_size):
                    raise ValueError("Uploaded snapshot does not match local bytes")
            self.saved_files = files
            print(f"{PID}: saved {count} complete takes in {target}", flush=True)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self.next_check = time.monotonic() + 120
            print(f"{PID}: snapshot pending after {type(exc).__name__}; retrying during this recording", flush=True)


def download_historical_artifact(base, asset, path):
    endpoint = f"{base}/actions/artifacts/{asset['id']}/zip"
    for attempt, delay in enumerate((0, 2, 8)):
        if delay:
            time.sleep(delay)
        # A new redirect avoids reusing an expired signed storage URL.
        url = endpoint if not attempt else f"{endpoint}?retry={time.time_ns()}"
        with path.open("wb") as output:
            result = subprocess.run(["gh", "api", url], stdout=output, stderr=subprocess.PIPE)
        if result.returncode == 0:
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            if path.stat().st_size != asset["size_in_bytes"] or "sha256:" + digest != asset["digest"]:
                raise ValueError(f"Incomplete or altered recording archive {asset['id']}")
            return True
        reason = result.stderr.decode(errors="replace").lower()
        if "http 404" in reason or "http 410" in reason:
            break
        if not any(error in reason for error in ("http 500", "http 502", "http 503", "http 504",
                                                 "timed out", "timeout", "unexpected eof", "connection reset",
                                                 "tls handshake", "blob.core.windows.net")):
            raise RuntimeError(f"Cannot retrieve job artifact {asset['id']} (gh exit {result.returncode})")
    print(f"{PID}: historical artifact {asset['id']} unavailable; using the other saved recordings", flush=True)
    return False


def recover():
    config = json.loads(Path(".github/ielts-aiden-batch.json").read_text())
    runs = config.get("recover_runs", [])
    work = Path(os.environ["IELTS_WORK"])
    stage = os.environ.get("STAGING", "")
    if stage == "ielts-academic-aiden-cache-13-6":
        # A later rejected take can supersede an intact earlier recording in a
        # runner snapshot. Restore independently checked originals first. Their
        # filenames still bind them to the text, reading profile and phrase.
        reviewed = Path(__file__).resolve().parents[1] / "审校/Aiden/13-6/复验原声" / (PID + ".zip")
        if reviewed.is_file():
            count = restore_archive(reviewed, work / "aiden-takes")
            print(f"{PID}: restored {count} independently reviewed original recordings", flush=True)
    if stage in ("ielts-academic-aiden-cache-13-6", "ielts-academic-aiden-cache-5-1"):
        restore_snapshot(stage, work / "aiden-takes")
    if not runs:
        return
    base = "repos/" + os.environ["GITHUB_REPOSITORY"]
    for run_id in runs:
        if type(run_id) is not int or run_id < 1:
            raise ValueError("Invalid source run")
        run = gh_json(f"{base}/actions/runs/{run_id}")
        if (run["head_branch"] != "codex/ielts-academic-reading"
                or run["path"] != ".github/workflows/ielts-aiden-production.yml"):
            raise ValueError("The recordings are from a different production workflow")
        run_artifacts = read_github([
            "gh", "api", "--paginate", "--jq", ".artifacts[] | @json",
            f"{base}/actions/runs/{run_id}/artifacts?per_page=100"
        ])
        prefix = "aiden-" + PID + "-checks-"
        artifacts = [json.loads(line) for line in run_artifacts.splitlines() if line]
        for asset in sorted(artifacts, key=lambda x: x["id"], reverse=True):
            if (asset["expired"] or not asset["name"].startswith(prefix)
                    or not asset["name"][len(prefix):].isdigit()):
                continue
            with tempfile.TemporaryDirectory(dir=work) as temp:
                path = Path(temp) / "recordings.zip"
                if not download_historical_artifact(base, asset, path):
                    continue
                count = restore_archive(path, work / "aiden-takes")
            print(f"{PID} recovered {count} complete recordings from job artifact {asset['id']}", flush=True)


if __name__ == "__main__":
    recover()
