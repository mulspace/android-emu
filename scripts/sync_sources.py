#!/usr/bin/env python3
"""Fetch the pinned Linux emulator dependency set, with resumable Git stores."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from owned_process import run

ROOT = Path(__file__).resolve().parents[1]


def validate_project(project):
    path = Path(project["path"])
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Unsafe source path")
    if not re.fullmatch(r"[0-9a-f]{40}", project["revision"]):
        raise ValueError("Source revisions must be immutable Git commits")
    if not project["url"].startswith("https://android.googlesource.com/"):
        raise ValueError("Only official pinned upstreams are allowed")


def sync_one(project, workspace, timeout):
    validate_project(project)
    base = workspace / "aosp"
    dest = base / project["path"]
    dest.mkdir(parents=True, exist_ok=True)
    if not dest.resolve().is_relative_to(base.resolve()):
        raise ValueError("Source path escapes workspace")
    logpath = workspace / "logs" / (project["path"].replace("/", "_") + ".log")
    started = time.monotonic()
    with logpath.open("ab", buffering=0) as log:
        def git(*args):
            return run(["git", *args], cwd=dest, timeout=timeout, log=log)
        if not (dest / ".git").is_dir():
            if list(dest.iterdir()):
                raise ValueError("Refusing to initialize a nonempty source directory")
            git("init", "-q")
            git("remote", "add", "origin", project["url"])
        origin = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=dest, text=True).strip()
        if origin.removesuffix(".git") != project["url"].removesuffix(".git"):
            raise ValueError("Existing checkout has another origin")
        exists = subprocess.run(["git", "cat-file", "-e", project["revision"] + "^{commit}"], cwd=dest, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if not exists:
            if shutil.disk_usage(workspace).free < 20 * 1024**3:
                raise RuntimeError("Less than 20 GiB free: stop before affecting the host")
            git("-c", "http.lowSpeedLimit=1024", "-c", "http.lowSpeedTime=120", "fetch", "--depth=1", "--no-tags", "origin", project["revision"])
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=dest, text=True, capture_output=True)
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=dest, text=True)
        if status and head.returncode == 0:
            raise RuntimeError("Dirty source tree: preserve it and inspect local patches")
        git("checkout", "--detach", project["revision"])
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=dest, text=True).strip()
        if actual != project["revision"]:
            raise RuntimeError("Source revision verification failed")
    return {"path": project["path"], "revision": actual, "seconds": round(time.monotonic() - started, 2), "status": "ready"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--only", nargs="*", help="Exact project paths from sources.lock.json")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    args.workspace.mkdir(parents=True, exist_ok=True)
    (args.workspace / "logs").mkdir(exist_ok=True)
    projects = json.loads((ROOT / "sources.lock.json").read_text())["projects"]
    if args.only:
        known = {p["path"] for p in projects}
        if set(args.only) - known:
            parser.error("Unknown project path")
        projects = [p for p in projects if p["path"] in args.only]
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(sync_one, p, args.workspace, args.timeout): p for p in projects}
        for future in as_completed(futures):
            project = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = {"path": project["path"], "status": "failed", "error": str(error)}
            results.append(result)
            print(json.dumps(result), flush=True)
            temporary = args.workspace / "sync-results.json.tmp"
            temporary.write_text(json.dumps(results, indent=2) + "\n")
            temporary.replace(args.workspace / "sync-results.json")
    return int(any(r["status"] != "ready" for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
