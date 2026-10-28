#!/usr/bin/env python3
"""Resume large pinned toolchains by Gitiles tree/blob, verifying Git object IDs.

Prefer directory archives. With --files, download each direct blob separately;
subdirectories still try a bounded archive first. No Git history is required.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
import urllib.parse

from owned_process import run
from source_contract import ROOT, validate_project
from sync_archives import sync_one


FAILED = []

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def fetch(url, path, resolve_ip, timeout=90):
    connection = ["--resolve", "android.googlesource.com:443:" + resolve_ip] if resolve_ip else []
    run(["curl", "--http1.1", "--compressed", *connection, "--fail", "--silent", "--show-error",
        "--location", "--connect-timeout", "15", "--max-time", str(timeout - 5),
        "--retry", "2", "--retry-all-errors", "--retry-delay", "1",
        "--output", str(path), url], timeout=timeout)


def sync_tree(project, subtree, workspace, resolve_ip, direct_files=False):
    base = (workspace / "aosp").resolve()
    dest = base / project["path"] / subtree
    if not dest.resolve().is_relative_to(base): raise ValueError("Source path escape")
    if not direct_files and not dest.exists():
        try:
            sync_one(dict(project, subtree=subtree), workspace, 180, resolve_ip)
            return
        except Exception as error:
            print("split " + str(dest.relative_to(base)) + ": " + type(error).__name__, flush=True)
    url = project["url"] + "/+/" + project["revision"] + "/" + subtree.strip("/")
    with tempfile.TemporaryDirectory(dir=workspace / "downloads") as scratch:
        treefile = Path(scratch) / "tree.json"
        fetch(url.rstrip("/") + "/?format=JSON", treefile, resolve_ip)
        tree = json.loads(treefile.read_text()[4:])
        entries = tree["entries"]
        dest.mkdir(parents=True, exist_ok=True)
        for entry in sorted(entries, key=lambda e: (e["type"] == "tree", not e["name"].startswith(("libc++", "clang", "ld.")), e["name"])):
            name = entry["name"]
            if Path(name).name != name or name in (".", ".."): raise ValueError("Invalid tree entry")
            child = "/".join(filter(None, (subtree.strip("/"), name)))
            if entry["type"] == "tree":
                try:
                    sync_tree(project, child, workspace, resolve_ip)
                except Exception as error:
                    FAILED.append(project["path"] + "/" + child)
                    print("failed " + FAILED[-1] + ": " + str(error), flush=True)
                continue
            if entry["type"] != "blob": raise ValueError("Unsupported gitlink")
            path = dest / name
            symlink = entry["mode"] == 0o120000
            if path.is_symlink():
                data = os.readlink(path).encode()
            elif path.is_file():
                data = path.read_bytes()
            elif path.exists(): raise ValueError("Existing non-file source")
            else: data = None
            if data is not None:
                if git_blob(data) != entry["id"]: raise ValueError("Preserving modified file: " + str(path))
                continue
            body = Path(scratch) / "blob.base64"
            try:
                fetch(project["url"] + "/+/" + project["revision"] + "/" + urllib.parse.quote(child, safe="/") + "?format=TEXT", body, resolve_ip, 180)
            except Exception as error:
                FAILED.append(project["path"] + "/" + child)
                print("failed " + FAILED[-1] + ": " + type(error).__name__, flush=True)
                continue
            data = base64.b64decode(body.read_bytes(), validate=True)
            if git_blob(data) != entry["id"]: raise ValueError("Official Git blob hash mismatch")
            if symlink:
                link = data.decode()
                if Path(link).is_absolute() or not (dest / link).resolve().is_relative_to(base):
                    raise ValueError("Link escapes source workspace")
                path.symlink_to(link)
            else:
                temporary = path.with_name("." + name + ".download")
                temporary.write_bytes(data)
                temporary.chmod(0o755 if entry["mode"] == 0o100755 else 0o644)
                temporary.replace(path)
            print("blob " + project["path"] + "/" + child, flush=True)
        record = {"project": project["path"], "revision": project["revision"], "subtree": subtree,
                  "tree_id": tree["id"], "entries": entries, "incomplete_paths": list(FAILED)}
        receipts = workspace / "tree-receipts"
        receipts.mkdir(exist_ok=True)
        (receipts / ((project["path"] + "/" + subtree).replace("/", "_") + ".json")).write_text(json.dumps(record, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--subtree", default="")
    parser.add_argument("--resolve-ip")
    parser.add_argument("--files", action="store_true")
    args = parser.parse_args()
    if args.resolve_ip:
        import ipaddress
        if not ipaddress.IPv4Address(args.resolve_ip).is_global: parser.error("Only a public IPv4 is allowed")
    if Path(args.subtree).is_absolute() or ".." in Path(args.subtree).parts: parser.error("Unsafe subtree")
    projects = json.loads((ROOT / "sources.lock.json").read_text())["projects"]
    project = next((p for p in projects if p["path"] == args.project), None)
    if project is None: parser.error("Project not in lockfile")
    validate_project(project)
    for directory in ("downloads", "logs"): (args.workspace / directory).mkdir(parents=True, exist_ok=True)
    def interrupted(signum, frame): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    sync_tree(project, args.subtree, args.workspace, args.resolve_ip, args.files)
    return int(bool(FAILED))


if __name__ == "__main__": raise SystemExit(main())
