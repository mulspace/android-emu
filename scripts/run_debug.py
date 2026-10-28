#!/usr/bin/env python3
"""Run only an explicitly named isolated AVD; collect bounded GDB diagnostics."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time

from owned_process import stop_group


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--avd-home", type=Path, required=True)
    parser.add_argument("--android-home", type=Path, required=True)
    parser.add_argument("--avd", required=True)
    parser.add_argument("--port", type=int, default=5576)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=1200)
    parser.add_argument("--gpu", choices=("host", "swiftshader_indirect"), default="host")
    parser.add_argument("--host-cpus", default="14,15")
    args = parser.parse_args()
    if not re.fullmatch(r"android-emu-debug-[a-z0-9-]+", args.avd):
        parser.error("Only isolated android-emu-debug-* AVDs are allowed")
    if args.port < 5554 or args.port > 5682 or args.port % 2 or args.port in (5554, 5556, 5558, 5566):
        parser.error("Use a dedicated even emulator port, excluding existing test ports")
    if not 30 <= args.seconds <= 3600:
        parser.error("Diagnostic duration must be 30..3600 seconds")
    if not args.emulator.is_file() or not (args.avd_home / (args.avd + ".ini")).is_file():
        parser.error("Emulator or explicitly named AVD does not exist")
    if args.output.exists():
        parser.error("Use a new output directory to preserve earlier evidence")
    cpus = {int(v) for v in args.host_cpus.split(",")}
    if not cpus or len(cpus) > 4 or not cpus <= os.sched_getaffinity(0):
        parser.error("Choose at most four available host CPUs")
    for port in (args.port, args.port + 1):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                parser.error("Isolated test port already occupied")
    args.output.mkdir(parents=True, mode=0o700)
    args.android_home.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    engine = args.emulator.resolve().parent
    env.update({
        "ANDROID_AVD_HOME": str(args.avd_home.resolve()),
        "ANDROID_USER_HOME": str(args.android_home.resolve()),
        "ANDROID_EMULATOR_HOME": str(args.android_home.resolve()),
        "LD_LIBRARY_PATH": ":".join(str(engine / p) for p in ("lib64", "lib64/gles_swiftshader", "lib64/qt/lib")),
    })
    if args.gpu == "host" and not env.get("DISPLAY"):
        parser.error("host graphics requires the operator's explicit DISPLAY/XAUTHORITY environment")
    command = [str(args.emulator.resolve()), "-avd", args.avd, "-port", str(args.port),
        "-no-window", "-no-audio", "-no-boot-anim", "-no-snapshot", "-gpu", args.gpu,
        "-cores", "1", "-memory", "1536", "-feature", "-Vulkan", "-accel", "off",
        "-camera-back", "none", "-camera-front", "none", "-show-kernel"]
    prefix = ["taskset", "-c", ",".join(map(str, sorted(cpus))), "nice", "-n", "10"]
    gdb = ["gdb", "-nx", "-q", "--batch", "-x", str(Path(__file__).with_name("crash.gdb")), "--args"]
    started = time.monotonic()
    def on_signal(signum, frame):
        raise InterruptedError("Diagnostic interrupted")
    signal.signal(signal.SIGTERM, on_signal)
    receipt = {"command": command, "started_at": datetime.datetime.now().astimezone().isoformat(),
        "serial": "emulator-" + str(args.port), "duration_limit_seconds": args.seconds,
        "production_cutover": False, "physical_device_operated": False, "account_login_attempted": False}
    with (args.output / "gdb.log").open("wb") as log:
        process = subprocess.Popen(prefix + gdb + command, env=env, stdout=log,
            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        receipt["owned_pgid"] = process.pid
        (args.output / "started.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({"started": process.pid, "serial": receipt["serial"]}), flush=True)
        try:
            while process.poll() is None and time.monotonic() - started < args.seconds:
                if (args.output / "stop.request").exists():
                    break
                time.sleep(1)
        finally:
            # Reap the owned group even if GDB has already exited with an inferior left.
            stop_group(process)
            receipt.update(exit_code=process.returncode, elapsed_seconds=round(time.monotonic() - started, 2),
                ended_at=datetime.datetime.now().astimezone().isoformat())
            (args.output / "ended.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(json.dumps({"ended": process.returncode, "seconds": receipt["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
