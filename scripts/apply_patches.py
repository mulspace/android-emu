#!/usr/bin/env python3
"""Apply the reviewed patch only to the exact pinned source, with a build lock."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/0001-tcg-bound-translation-blocks.patch"


def source_state(source, manifest=None):
    if manifest is None:
        manifest = json.loads((ROOT / "patches/series.json").read_text())
    states = set()
    for name, hashes in manifest["files"].items():
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()):
            raise ValueError("Source manifest path escapes source root")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest == hashes["before_sha256"]:
            states.add("unpatched")
        elif digest == hashes["after_sha256"]:
            states.add("patched")
        else:
            raise ValueError("Source differs from both reviewed versions: " + name)
    if len(states) != 1:
        raise ValueError("Mixed/empty patch state; preserve files and inspect manually")
    return states.pop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    source = workspace / "aosp/external/qemu"
    manifest = json.loads((ROOT / "patches/series.json").read_text())
    if hashlib.sha256(PATCH.read_bytes()).hexdigest() != manifest["patch_sha256"]:
        raise ValueError("Patch checksum does not match reviewed manifest")
    with (workspace / ".source.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = source_state(source, manifest)
        command = ["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-d", str(source), "-i", str(PATCH)]
        if state == "unpatched":
            subprocess.run(command + ["--dry-run"], check=True, timeout=30)
            if not args.check:
                # Every source hash and hunk was checked before the first write.
                subprocess.run(command, check=True, timeout=30)
                state = source_state(source, manifest)
        print(json.dumps({"source_state": state, "check_only": args.check,
                          "patch_sha256": manifest["patch_sha256"]}))


if __name__ == "__main__":
    main()
