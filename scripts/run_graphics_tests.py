#!/usr/bin/env python3
"""Build/run only the detached-vertex-buffer regression in an owned process."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
import signal
from pathlib import Path
import time

from apply_patches import source_state
from owned_process import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--host-cpus", default="14,15")
    parser.add_argument("--gpu", choices=("host", "swiftshader"), default="swiftshader")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    cpus = {int(v) for v in args.host_cpus.split(",")}
    if not cpus or len(cpus) > 4 or not cpus <= os.sched_getaffinity(0):
        parser.error("Choose at most four available host CPUs")
    if not 30 <= args.timeout <= 600:
        parser.error("timeout must be 30..600 seconds")
    if args.gpu == "host" and not os.environ.get("DISPLAY"):
        parser.error("host rendering requires the explicit DISPLAY/XAUTHORITY environment")
    root = args.workspace.resolve()
    source = root / "aosp/external/qemu"
    build = root / "out/arm32-relwithdebinfo"
    ninja = root / "aosp/prebuilts/ninja/linux-x86/ninja"
    if not (build / "build.ninja").is_file():
        parser.error("Configure/build RelWithDebInfo first")
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    output = root / "logs" / ("graphics-test-" + stamp)
    output.parent.mkdir(parents=True, exist_ok=True)
    record = {"gpu": args.gpu, "status": "running", "production_cutover": False}
    started = time.monotonic()
    prefix = ["taskset", "-c", ",".join(map(str, sorted(cpus))), "nice", "-n", "10"]
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(build / "lib64") + ":" + str(build / "lib64/gles_swiftshader")
    env["ANDROID_EMU_TEST_WITH_HOST_GPU"] = "1" if args.gpu == "host" else "0"
    with (root / ".source.lock").open("a+") as source_lock, (build / ".build.lock").open("a+") as build_lock:
        fcntl.flock(source_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        fcntl.flock(build_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        record["source_patch_state"] = source_state(source)
        if record["source_patch_state"] != "patched":
            raise ValueError("Apply the reviewed fixes and regression test first")
        try:
            with output.with_suffix(".log").open("wb") as log:
                run(prefix + [str(ninja), "-C", str(build), "-j", "2", "OpenglRender_unittests"],
                    timeout=args.timeout, env=env, log=log)
                binary = build / "OpenglRender_unittests"
                record["test_binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
                remaining = args.timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError("Overall graphics test timeout")
                run(prefix + [str(binary), "--gtest_filter=DeletedVertexBufferTest.*"],
                    timeout=min(60, remaining), env=env, log=log)
            if b"[       OK ] DeletedVertexBufferTest.ClientDrawAfterDeletingUnusedBuffer" not in output.with_suffix(".log").read_bytes():
                raise RuntimeError("Expected graphics regression did not execute")
            record["status"] = "passed"
        except BaseException as error:
            record.update(status="failed", error=type(error).__name__ + ": " + str(error))
            raise
        finally:
            record["seconds"] = round(time.monotonic() - started, 3)
            output.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
            print(json.dumps({"status": record["status"], "receipt": str(output.with_suffix(".json"))}), flush=True)


if __name__ == "__main__":
    main()
