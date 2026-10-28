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
import struct
import subprocess
import time

from owned_process import stop_group


def check_local_overlay(disk):
    """Reject QCOW2 sidecars that can redirect a cloned guest outside its AVD."""
    overlay = disk.with_name(disk.name + ".qcow2")
    if not overlay.exists() and not overlay.is_symlink():
        return
    if not overlay.is_file() or overlay.resolve() != overlay or overlay.stat().st_nlink != 1:
        raise ValueError("QCOW2 overlays must be local files, not links")
    with overlay.open("rb") as stream:
        header = stream.read(104)
        if len(header) < 72 or header[:4] != b"QFI\xfb":
            raise ValueError("Invalid QCOW2 overlay header")
        version = struct.unpack_from(">I", header, 4)[0]
        if version not in (2, 3) or (version == 3 and len(header) < 104):
            raise ValueError("Unsupported QCOW2 overlay version")
        if version == 3 and struct.unpack_from(">Q", header, 72)[0] & ~1:
            raise ValueError("Unsupported or corrupt QCOW2 overlay features")
        offset, size = struct.unpack_from(">QI", header, 8)
        if offset == size == 0:
            return
        if offset < (104 if version == 3 else 72) or not 0 < size <= 4096:
            raise ValueError("Invalid QCOW2 backing file reference")
        stream.seek(offset)
        if stream.read(size) != disk.name.encode("utf-8"):
            raise ValueError("QCOW2 backing must be its own local base disk")


def isolated_avd_paths(avd_home, avd):
    """Pin writable disks to this AVD; never inherit an old absolute data path."""
    if not re.fullmatch(r"android-emu-debug-[a-z0-9-]+", avd):
        raise ValueError("Only isolated android-emu-debug-* AVDs are allowed")
    home = avd_home.resolve()
    avd_dir = home / (avd + ".avd")
    ini = home / (avd + ".ini")
    if not ini.is_file() or not avd_dir.is_dir() or avd_dir.resolve() != avd_dir:
        raise ValueError("AVD must be a real directory under the isolated AVD home")
    settings = dict(line.split("=", 1) for line in ini.read_text().splitlines()
                    if "=" in line and not line.lstrip().startswith("#"))
    if "path" not in settings or Path(settings["path"]).resolve() != avd_dir:
        raise ValueError("AVD registration must point at its own isolated directory")
    disks = [avd_dir / name for name in ("userdata-qemu.img", "cache.img")]
    for disk in disks:
        if not disk.is_file() or disk.resolve() != disk:
            raise ValueError("Writable AVD disks must be existing local files, not symlinks")
        if disk.stat().st_nlink != 1:
            raise ValueError("Writable AVD disks must not be hardlinked to another guest")
        check_local_overlay(disk)
    if any(d.with_name(d.name + ".qcow2").exists() for d in disks):
        # The pinned emulator recreates all overlays if this marker is absent
        # or disagrees with the image. Refuse rather than silently lose Apps.
        version_file = avd_dir / "version_num.cache"
        config_file = avd_dir / "config.ini"
        if not version_file.is_file() or version_file.is_symlink() or not config_file.is_file():
            raise ValueError("Existing QCOW2 layers require their image-version marker and config")
        config = dict(line.split("=", 1) for line in config_file.read_text().splitlines()
                      if "=" in line and not line.lstrip().startswith("#"))
        image_dir = Path(config.get("image.sysdir.1", ""))
        build_prop = image_dir / "build.prop"
        if not image_dir.is_absolute() or not build_prop.is_file():
            raise ValueError("Cannot verify the cloned system-image version")
        properties = dict(line.split("=", 1) for line in build_prop.read_text().splitlines()
                          if "=" in line and not line.lstrip().startswith("#"))
        expected = properties.get("ro.build.version.incremental", "").strip()
        actual = version_file.read_text().strip()
        if not expected.isdecimal() or actual != expected:
            raise ValueError("Image-version mismatch would recreate the existing QCOW2 layers")
    return disks


def guest_command(emulator, avd, port, gpu, disks, *, experimental_arm_smp=False,
                  disable_jni_checks=False, arm_vcpus=2):
    if type(arm_vcpus) is not int or arm_vcpus not in (2, 4):
        raise ValueError("ARM diagnostic supports only two or four verified guest CPUs")
    if not experimental_arm_smp and arm_vcpus != 2:
        raise ValueError("Changing guest CPUs requires the explicit ARM SMP experiment")
    cores = str(arm_vcpus) if experimental_arm_smp else "1"
    command = [str(emulator.resolve()), "-avd", avd, "-port", str(port),
        "-no-window", "-no-audio", "-no-boot-anim", "-no-snapshot", "-gpu", gpu,
        "-cores", cores, "-memory", "1536",
        "-feature", "-Vulkan", "-accel", "off", "-camera-back", "none",
        "-camera-front", "none", "-show-kernel", "-data", str(disks[0]),
        "-cache", str(disks[1])]
    if disable_jni_checks:
        # Upstream runtime diagnostic switch; APK/signature/auth checks are unchanged.
        command += ["-no-jni"]
    if experimental_arm_smp:
        # The pinned emulator wrapper otherwise omits -smp for ARM on x86 hosts.
        # This is opt-in on a cloned AVD; kernel SMP/PSCI must be checked first.
        command += ["-qemu", "-cpu", "cortex-a15", "-smp", cores,
                    "-accel", "tcg,thread=multi"]
    return command


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
    parser.add_argument("--debugger", choices=("gdb", "none"), default="gdb",
                        help="Compare the same symbol-bearing binary without a host ptrace debugger")
    parser.add_argument("--host-cpus", default="14,15")
    parser.add_argument("--experimental-arm-smp", action="store_true",
                        help="Test ARMv7 SMP/MTTCG on a separate cloned AVD")
    parser.add_argument("--arm-vcpus", type=int, choices=(2, 4), default=2,
                        help="Explicit SMP experiment size; verify the guest kernel CPU limit first")
    parser.add_argument("--disable-jni-checks", action="store_true",
                        help="Use upstream -no-jni for a recorded performance comparison")
    args = parser.parse_args()
    if args.arm_vcpus != 2 and not args.experimental_arm_smp:
        parser.error("--arm-vcpus requires --experimental-arm-smp")
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
    try:
        disks = isolated_avd_paths(args.avd_home, args.avd)
    except ValueError as error:
        parser.error(str(error))
    cpus = {int(v) for v in args.host_cpus.split(",")}
    if not cpus or len(cpus) > 4 or not cpus <= os.sched_getaffinity(0):
        parser.error("Choose at most four available host CPUs")
    if args.experimental_arm_smp and len(cpus) < args.arm_vcpus:
        parser.error("Provide at least one allowed host CPU per experimental guest CPU")
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
    command = guest_command(args.emulator, args.avd, args.port, args.gpu, disks,
                            experimental_arm_smp=args.experimental_arm_smp,
                            disable_jni_checks=args.disable_jni_checks, arm_vcpus=args.arm_vcpus)
    prefix = ["taskset", "-c", ",".join(map(str, sorted(cpus))), "nice", "-n", "10"]
    gdb = ["gdb", "-nx", "-q", "--batch", "-x", str(Path(__file__).with_name("crash.gdb")), "--args"]
    launcher = gdb if args.debugger == "gdb" else []
    started = time.monotonic()
    def on_signal(signum, frame):
        raise InterruptedError("Diagnostic interrupted")
    signal.signal(signal.SIGTERM, on_signal)
    receipt = {"command": command, "started_at": datetime.datetime.now().astimezone().isoformat(),
        "serial": "emulator-" + str(args.port), "duration_limit_seconds": args.seconds,
        "debugger": args.debugger,
        "experimental_arm_smp": args.experimental_arm_smp,
        "guest_vcpus": args.arm_vcpus if args.experimental_arm_smp else 1,
        "jni_runtime_checks_requested": not args.disable_jni_checks,
        "production_cutover": False, "physical_device_operated": False, "account_login_attempted": False}
    with (args.output / ("gdb.log" if args.debugger == "gdb" else "emulator.log")).open("wb") as log:
        process = subprocess.Popen(prefix + launcher + command, env=env, stdout=log,
            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        receipt["owned_pgid"] = process.pid
        try:
            receipt["owned_start_ticks"] = Path(f"/proc/{process.pid}/stat").read_text().rsplit(") ", 1)[1].split()[19]
            (args.output / "started.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(json.dumps({"started": process.pid, "serial": receipt["serial"]}), flush=True)
            while process.poll() is None and time.monotonic() - started < args.seconds:
                if (args.output / "stop.request").exists():
                    break
                time.sleep(1)
        finally:
            # Reap only this owned group, including startup/receipt failures.
            stop_group(process)
            receipt.update(exit_code=process.returncode, elapsed_seconds=round(time.monotonic() - started, 2),
                ended_at=datetime.datetime.now().astimezone().isoformat())
            (args.output / "ended.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(json.dumps({"ended": process.returncode, "seconds": receipt["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
