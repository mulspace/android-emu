#!/usr/bin/env python3
"""Fetch immutable official Gitiles archives without transferring Git history.

Receipts are local integrity/provenance records, not independent signatures.
Existing extracted trees are never overwritten. Projects can be requested in
separate bounded processes; this script intentionally downloads one at a time.
"""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import signal
import tarfile
import tempfile
import time
import fcntl

from owned_process import run
from sync_sources import ROOT, validate_project


def safe_extract(archive, destination, *, final_destination=None, allowed_root=None):
    final_destination = (final_destination or destination).resolve()
    allowed_root = (allowed_root or final_destination).resolve()
    links = []
    with tarfile.open(archive) as tf:
        for member in tf:
            name = Path(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError("Archive path escapes destination")
            if member.issym():
                # AOSP has legitimate relative cross-project links. Defer all
                # links until files are extracted so none can redirect writes.
                if Path(member.linkname).is_absolute():
                    raise ValueError("Absolute archive link")
                target = (final_destination / name.parent / member.linkname).resolve()
                if not target.is_relative_to(allowed_root):
                    raise ValueError("Archive link escapes source workspace")
                links.append(member)
            else:
                tf.extract(member, destination, filter="data")
    for member in links:
        path = destination / member.name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() or path.is_symlink():
            raise ValueError("Archive link collides with extracted file")
        # Disallow any symlink ancestor even when still within allowed_root.
        if path.parent.resolve() != path.parent.absolute():
            raise ValueError("Nested archive link")
        path.symlink_to(member.linkname)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sync_one(project, workspace, timeout, resolve_ip=None):
    validate_project(project)
    subtree = project.get("subtree", "")
    if subtree and (Path(subtree).is_absolute() or ".." in Path(subtree).parts):
        raise ValueError("Unsafe source subtree")
    relative = Path(project["path"]) / subtree
    base = (workspace / "aosp").resolve()
    dest = base / relative
    if not dest.resolve().is_relative_to(base):
        raise ValueError("Source path escapes workspace")
    key = str(relative).replace("/", "_")
    receipts = workspace / "receipts"
    receipts.mkdir(exist_ok=True)
    receipt = receipts / (key + ".json")
    url = project["url"] + "/+archive/" + project["revision"]
    url += ("/" + subtree if subtree else "") + ".tar.gz"
    with (receipts / (key + ".lock")).open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if receipt.exists() and dest.is_dir():
            previous = json.loads(receipt.read_text())
            if previous["url"] != url:
                raise ValueError("Source receipt mismatch; preserve existing tree")
            print("ready " + str(relative), flush=True)
            return
        if dest.exists() and any(dest.iterdir()):
            raise ValueError("Existing tree has no matching receipt: " + str(dest))
        if shutil.disk_usage(workspace).free < 20 * 1024**3:
            raise RuntimeError("Less than 20 GiB free; preserving host capacity")
        archive = workspace / "downloads" / (key + "-" + project["revision"] + ".tar.gz")
        started = time.monotonic()
        with (workspace / "logs" / (key + "-archive.log")).open("ab", buffering=0) as log:
            if not archive.exists():
                partial = archive.with_suffix(".part")
                print("fetch " + str(relative), flush=True)
                connection = ["--resolve", "android.googlesource.com:443:" + resolve_ip] if resolve_ip else []
                run(["curl", "--http1.1", *connection, "--fail", "--show-error", "--location",
                     "--retry", "2", "--retry-all-errors", "--retry-delay", "2",
                     "--retry-max-time", str(timeout - 20), "--connect-timeout", "20", "--max-time", str(timeout - 10),
                     "--speed-limit", "1024", "--speed-time", "120",
                     url + "?download=1", "--output", str(partial)], timeout=timeout, log=log)
                # Parse the whole gzip stream before accepting a cache entry.
                with tarfile.open(partial) as tf:
                    for _ in tf: pass
                partial.replace(archive)
            dest.parent.mkdir(parents=True, exist_ok=True)
            temp = Path(tempfile.mkdtemp(prefix=".extract-", dir=dest.parent))
            try:
                safe_extract(archive, temp, final_destination=dest, allowed_root=base)
                if dest.exists(): dest.rmdir()
                temp.rename(dest)
            finally:
                if temp.exists(): shutil.rmtree(temp)
        receipt.write_text(json.dumps({"url": url, "revision": project["revision"],
            "path": str(relative), "sha256": sha256(archive),
            "seconds": round(time.monotonic() - started, 2)}, indent=2) + "\n")
        print("ready " + str(relative), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--resolve-ip", help="Optional verified public Google IPv4 for this request only; TLS hostname checks remain enabled")
    args = parser.parse_args()
    if args.resolve_ip:
        address = ipaddress.IPv4Address(args.resolve_ip)
        if not address.is_global: parser.error("resolve-ip must be a public IPv4 address")
    if args.timeout < 30: parser.error("timeout must be at least 30 seconds")
    args.workspace.mkdir(parents=True, exist_ok=True)
    for name in ("downloads", "logs"): (args.workspace / name).mkdir(exist_ok=True)
    projects = json.loads((ROOT / "sources.lock.json").read_text())["projects"]
    if args.only:
        if set(args.only) - {p["path"] for p in projects}: parser.error("Unknown project")
        projects = [p for p in projects if p["path"] in args.only]
    def interrupt(signum, frame): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    failed = []
    for project in projects:
        for subtree in project.get("subtrees", [project.get("subtree", "")]):
            try:
                sync_one(dict(project, subtree=subtree), args.workspace, args.timeout, args.resolve_ip)
            except Exception as error:
                failed.append(project["path"] + "/" + subtree)
                print("failed " + failed[-1] + ": " + str(error), flush=True)
    return int(bool(failed))


if __name__ == "__main__": raise SystemExit(main())
