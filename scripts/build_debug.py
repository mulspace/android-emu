#!/usr/bin/env python3
"""Configure/build the pinned ARM32 emulator with symbols and bounded resources."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from owned_process import run
from apply_patches import source_state

ROOT = Path(__file__).resolve().parents[1]


def configuration(source, build, cmake, ninja, build_type="Debug", arm_tlb_bits=8):
    if build_type not in ("Debug", "RelWithDebInfo"):
        raise ValueError("Only builds retaining debug information are allowed")
    if type(arm_tlb_bits) is not int or arm_tlb_bits not in (8, 10):
        raise ValueError("ARM TLB bits must be the default 8 or explicit diagnostic 10")
    return [str(cmake), "-H" + str(source), "-B" + str(build), "-G", "Ninja",
        "-DCMAKE_MAKE_PROGRAM=" + str(ninja),
        "-DCMAKE_TOOLCHAIN_FILE=" + str(source / "android/build/cmake/toolchain-linux-x86_64.cmake"),
        "-DCMAKE_BUILD_TYPE=" + build_type, "-DOPTION_ARM_TLB_BITS=" + str(arm_tlb_bits), "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        "-DOPTION_ASAN_IN_DEBUG=OFF", "-DOPTION_COVERAGE_IN_DEBUG=OFF",
        "-DOPTION_CRASHUPLOAD=NONE", "-DOPTION_MINBUILD=OFF", "-DWEBRTC=OFF",
        "-DQTWEBENGINE=OFF", "-DBLUETOOTH_EMULATION=OFF", "-DOPTION_ASTC_TESTS=OFF",
        "-DOPTION_SDK_TOOLS_REVISION=30.7.5", "-DOPTION_SDK_TOOLS_BUILD_NUMBER=local-debug"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--jobs", type=int, choices=(1, 2), default=2)
    p.add_argument("--host-cpus", default="14,15")
    p.add_argument("--timeout", type=int, default=7200)
    p.add_argument("--configure-only", action="store_true")
    p.add_argument("--build-type", choices=("Debug", "RelWithDebInfo"), default="Debug")
    p.add_argument("--arm-tlb-bits", type=int, choices=(8, 10), default=8,
                   help="Keep 256-entry TLBs by default; 1024 entries is an isolated experiment")
    args = p.parse_args()
    if not 30 <= args.timeout <= 14400: p.error("timeout must be 30..14400 seconds")
    cpus = {int(v) for v in args.host_cpus.split(",")}
    if not cpus or len(cpus) > 4 or not cpus <= os.sched_getaffinity(0):
        p.error("Choose at most four available host CPUs")
    workspace = args.workspace.resolve()
    aosp = workspace / "aosp"
    source = aosp / "external/qemu"
    cmake = aosp / "prebuilts/cmake/linux-x86/bin/cmake"
    ninja = aosp / "prebuilts/ninja/linux-x86/ninja"
    compiler = aosp / "prebuilts/clang/host/linux-x86/clang-r416183b/bin/clang"
    for path in (source / "CMakeLists.txt", cmake, ninja, compiler):
        if not path.is_file(): p.error("Missing pinned build input: " + str(path))
    if shutil.disk_usage(workspace).free < 20 * 1024**3:
        p.error("Less than 20 GiB free; preserve host capacity")
    build = workspace / "out" / ("arm32-debug" if args.build_type == "Debug" else "arm32-relwithdebinfo")
    build.mkdir(parents=True, exist_ok=True)
    (workspace / "logs").mkdir(exist_ok=True)
    # Supply the upstream's `python` command locally without changing /usr/bin.
    shim = workspace / "tools/bin"
    shim.mkdir(parents=True, exist_ok=True)
    python = shim / "python"
    if not python.exists(): python.symlink_to(sys.executable)
    env = os.environ.copy()
    env["PATH"] = str(shim) + os.pathsep + env["PATH"]
    env["CMAKE_BUILD_PARALLEL_LEVEL"] = str(args.jobs)
    prefix = ["taskset", "-c", ",".join(map(str, sorted(cpus))), "nice", "-n", "10"]
    cmds = [configuration(source, build, cmake, ninja, args.build_type, args.arm_tlb_bits)]
    if not args.configure_only:
        cmds.append([str(ninja), "-C", str(build), "-j", str(args.jobs),
                     "emulator", "qemu-system-armel-headless"])
    def interrupted(signum, frame): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    record = {"started_at": datetime.datetime.now().astimezone().isoformat(),
        "commands": cmds, "build_type": args.build_type, "arm_tlb_bits": args.arm_tlb_bits, "status": "running", "production_cutover": False,
        "lock_sha256": hashlib.sha256((ROOT / "sources.lock.json").read_bytes()).hexdigest()}
    receipt = workspace / "logs" / ("build-" + stamp + ".json")
    started = time.monotonic()
    with (workspace / ".source.lock").open("a+") as source_lock, (build / ".build.lock").open("w") as lock:
        fcntl.flock(source_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        record["source_patch_state"] = source_state(source)
        record["patch_manifest_sha256"] = hashlib.sha256((ROOT / "patches/series.json").read_bytes()).hexdigest()
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt.write_text(json.dumps(record, indent=2) + "\n")
        try:
            with (workspace / "logs" / ("build-" + stamp + ".log")).open("wb") as log:
                for command in cmds:
                    remaining = args.timeout - (time.monotonic() - started)
                    if remaining <= 0: raise TimeoutError("Overall build timeout")
                    run(prefix + command, timeout=remaining, cwd=source, env=env, log=log)
            if not args.configure_only:
                binaries = list(build.rglob("qemu-system-armel-headless"))
                if len(binaries) != 1: raise RuntimeError("Expected exactly one ARM32 binary")
                binary = binaries[0]
                sections = subprocess.check_output(["readelf", "-SW", str(binary)], text=True, timeout=30)
                if ".debug_info" not in sections or ".debug_line" not in sections:
                    raise RuntimeError("Output binary has no required DWARF sections")
                record["binary"] = str(binary)
                record["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
                record["symbols_verified"] = True
                renderer = build / "lib64/libOpenglRender.so"
                if not renderer.is_file():
                    raise RuntimeError("Missing renderer library")
                record["renderer"] = str(renderer)
                record["renderer_sha256"] = hashlib.sha256(renderer.read_bytes()).hexdigest()
            record["status"] = "configured" if args.configure_only else "built"
        except BaseException as error:
            record.update(status="failed", error=type(error).__name__ + ": " + str(error))
            raise
        finally:
            record["seconds"] = round(time.monotonic() - started, 2)
            receipt.write_text(json.dumps(record, indent=2) + "\n")
            print(json.dumps({"status": record["status"], "receipt": str(receipt)}), flush=True)


if __name__ == "__main__": main()
