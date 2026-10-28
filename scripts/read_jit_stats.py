#!/usr/bin/env python3
"""Read fixed JIT statistics from an owned isolated emulator; never accept commands."""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import stat
import time
from probe_public_capture import owned_run


def parse_stats(text):
    patterns = {
        "code_bytes": r"^gen code size\s+(\d+)/(\d+)\s*$",
        "tb_count": r"^TB count\s+(\d+)\s*$",
        "tb_flushes": r"^TB flush count\s+(\d+)\s*$",
        "tb_invalidations": r"^TB invalidate count\s+(\d+)\s*$",
        "tlb_flushes": r"^TLB flush count\s+(\d+)\s*$",
    }
    result = {}
    for key, pattern in patterns.items():
        matches = re.findall(pattern, text, re.M)
        if len(matches) != 1:
            raise ValueError("Missing or ambiguous JIT metric: " + key)
        if key == "code_bytes":
            used, capacity = map(int, matches[0])
            if not 0 <= used <= capacity or capacity == 0:
                raise ValueError("Invalid translation-buffer capacity")
            result.update(code_bytes=used, capacity_bytes=capacity)
        else:
            result[key] = int(matches[0])
    return result


def query(sock):
    deadline = time.monotonic() + 15
    buffer = bytearray()
    def receive():
        while b"\n" not in buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("JIT monitor deadline")
            sock.settimeout(remaining)
            chunk = sock.recv(8192)
            if not chunk:
                raise ValueError("JIT monitor closed")
            buffer.extend(chunk)
            if len(buffer) > 131072:
                raise ValueError("JIT monitor response too large")
        line, _, rest = buffer.partition(b"\n")
        buffer[:] = rest
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("Invalid QMP object")
        return value
    if "QMP" not in receive():
        raise ValueError("Expected QMP greeting")
    def call(command, ident, arguments=None):
        value = {"execute": command, "id": ident}
        if arguments is not None:
            value["arguments"] = arguments
        sock.sendall(json.dumps(value).encode() + b"\n")
        for _ in range(32):
            response = receive()
            if "event" in response:
                continue
            if response.get("id") != ident or "error" in response or "return" not in response:
                raise ValueError("JIT monitor request failed")
            return response["return"]
        raise ValueError("Too many monitor events")
    call("qmp_capabilities", "capabilities")
    text = call("human-monitor-command", "jit", {"command-line": "info jit"})
    if not isinstance(text, str):
        raise ValueError("Invalid JIT text")
    return text, parse_stats(text)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    os.umask(0o077)
    owned_run(args.run_dir, "emulator-5576")
    receipt = json.loads((args.run_dir / "started.json").read_text())
    path = args.run_dir.resolve() / "jit.sock"
    if receipt.get("jit_monitor") != str(path) or not stat.S_ISSOCK(path.lstat().st_mode):
        raise ValueError("Missing private monitor for this owned run")
    if args.output.exists():
        raise ValueError("Use a new evidence file")
    started = time.monotonic()
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(15)
        sock.connect(str(path))
        raw, metrics = query(sock)
    owned_run(args.run_dir, "emulator-5576")
    result = {"metrics": metrics, "raw": raw, "elapsed_seconds": round(time.monotonic()-started, 3),
              "tcg_cache_mb_requested": receipt.get("tcg_cache_mb_requested")}
    with args.output.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "raw"}))


if __name__ == "__main__":
    main()
