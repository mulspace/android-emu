#!/usr/bin/env python3
"""Apply reviewed patch sets to exact pinned source, preserving prior fixes."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


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


def reviewed_patches(source, manifest, patch_root=ROOT / "patches"):
    """Check all inputs before any mutation; allow completed earlier patch sets."""
    plan = []
    covered = set()
    for entry in manifest["patches"]:
        path = (patch_root / entry["path"]).resolve()
        if not path.is_relative_to(patch_root.resolve()):
            raise ValueError("Patch path escapes patch root")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Patch checksum does not match reviewed manifest")
        names = entry["files"]
        if not names or covered.intersection(names) or len(set(names)) != len(names):
            raise ValueError("Patch sets must cover distinct source files")
        covered.update(names)
        state = source_state(source, {"files": {name: manifest["files"][name] for name in names}})
        plan.append((path, state))
    if covered != set(manifest["files"]):
        raise ValueError("Patch sets do not cover the full source manifest")
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    source = workspace / "aosp/external/qemu"
    manifest = json.loads((ROOT / "patches/series.json").read_text())
    with (workspace / ".source.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = reviewed_patches(source, manifest)
        commands = [["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-d", str(source), "-i", str(path)]
                    for path, state in plan if state == "unpatched"]
        for command in commands:
            subprocess.run(command + ["--dry-run"], check=True, timeout=30)
        if not args.check:
            # Every source hash and hunk was checked before the first write.
            for command in commands:
                subprocess.run(command, check=True, timeout=30)
            state = source_state(source, manifest)
        else:
            states = {state for _, state in plan}
            state = states.pop() if len(states) == 1 else "partially-patched"
        print(json.dumps({"source_state": state, "check_only": args.check,
                          "pending_patch_sets": len(commands)}))


if __name__ == "__main__":
    main()
