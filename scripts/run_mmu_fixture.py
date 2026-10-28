#!/usr/bin/env python3
"""Run the bounded native MMU fixture only on an owned ARM diagnostic AVD."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from probe_public_capture import owned_run


def validate_result(output):
    value = json.loads(output)
    for key, expected in {"passed": True, "cpu_count": 2, "remap_rounds": 24,
                          "permission_faults": 2, "arm_code_updates": True,
                          "code_updates": 48}.items():
        if type(value.get(key)) is not type(expected) or value[key] != expected:
            raise ValueError("Incomplete ARM MMU verification: " + key)
    for key in ("pages128_seconds", "pages512_seconds", "pages2048_seconds", "total_seconds"):
        duration = value.get(key)
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
            raise ValueError("Invalid fixture duration: " + key)
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("run-dir", "adb", "fixture", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    os.umask(0o077)
    owned_run(args.run_dir, "emulator-5576")
    if args.output.exists():
        p.error("Use a new receipt file")
    binary = args.fixture.read_bytes()
    # ELF32 little endian, EM_ARM. Do not accidentally validate an x86 host executable.
    if binary[:6] != b"\x7fELF\x01\x01" or int.from_bytes(binary[18:20], "little") != 40:
        p.error("Expected an ARM32 little-endian ELF fixture")
    remote = "/data/local/tmp/android-emu-mmu-" + uuid.uuid4().hex
    result = {"passed": False, "fixture_sha256": hashlib.sha256(binary).hexdigest(),
              "account_input": False, "production_cutover": False, "trials": []}
    def call(arguments, timeout):
        owned_run(args.run_dir, "emulator-5576")
        return subprocess.run([str(args.adb), "-s", "emulator-5576", *arguments],
                              capture_output=True, text=True, timeout=timeout, check=True)
    try:
        call(["push", str(args.fixture), remote], 20)
        call(["shell", "chmod", "700", remote], 10)
        for trial in range(1, 4):
            # The fixture has its own 90-second guest alarm and disables core dumps.
            response = call(["shell", remote], 105)
            value = validate_result(response.stdout)
            result["trials"].append({"trial": trial, "result": value, "stderr": response.stderr})
            print(json.dumps(result["trials"][-1]), flush=True)
        result["passed"] = True
    except Exception as error:
        result["error_type"] = type(error).__name__
        if isinstance(error, subprocess.CalledProcessError):
            result.update(returncode=error.returncode, stdout=error.stdout, stderr=error.stderr)
    finally:
        try:
            call(["shell", "rm", "-f", remote], 10)
            result["cleanup_confirmed"] = True
        except Exception as error:
            result.update(passed=False, cleanup_confirmed=False, cleanup_error_type=type(error).__name__)
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps({k: result[k] for k in ("passed", "cleanup_confirmed")}), flush=True)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
