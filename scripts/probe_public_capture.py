#!/usr/bin/env python3
"""Public-page capture only, on an explicitly owned android-emu diagnostic run."""
import argparse
import asyncio
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import signal
import sys
import time
import uuid


def owned_run(path, serial, proc_root=Path('/proc')):
    receipt = json.loads((path / "started.json").read_text())
    if receipt["serial"] != serial or not serial.startswith("emulator-"):
        raise ValueError("Only this owned diagnostic emulator may be probed")
    if (path / "ended.json").exists():
        raise ValueError("Diagnostic emulator has ended")
    pid = receipt["owned_pgid"]
    if type(pid) is not int or pid < 1:
        raise ValueError("Invalid diagnostic process")
    command = (proc_root / str(pid) / 'cmdline').read_bytes().split(b"\0")
    if b"--args" not in command or b"-port" not in command:
        raise ValueError("Owned diagnostic process is not the expected GDB run")
    if command[command.index(b"-port") + 1] != serial.removeprefix("emulator-").encode():
        raise ValueError("Owned diagnostic port changed")
    if b"-avd" not in command or not command[command.index(b"-avd") + 1].startswith(b"android-emu-debug-"):
        raise ValueError("Not an isolated diagnostic AVD")


async def probe(args):
    from kengent.tools.resource_node.android import AdbTransport, NativeSession, _snapshot_hierarchy, _snapshot_image
    owned_run(args.run_dir, args.serial)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    events = []
    receipt = {"public_only": True, "production_cutover": False, "account_input": False,
               "package": args.package, "timing_profile": "arm-emulator", "events": events}
    session = None
    started = time.monotonic()
    phase = "identify"
    def event(value):
        events.append(value)
        print(json.dumps(value), flush=True)
    try:
        async with asyncio.timeout(240):
            transport = AdbTransport(adb_path=str(args.adb), serial=args.serial,
                artifacts=(args.artifacts / "u2.jar", args.artifacts / "bridge.jar"),
                timing_profile="arm-emulator")
            identity = await transport.identify()
            if args.package not in identity["packages"]:
                raise ValueError("Requested public App is not installed")
            transport.fingerprint = identity["fingerprint"]
            context = {"nonce": uuid.uuid4().hex,
                "expires_at": (datetime.now(UTC) + timedelta(seconds=280)).isoformat()}
            receipt["nonce"] = context["nonce"]
            phase = "native_start"
            session = NativeSession(transport, context, [args.package])
            await session.start(context)
            event({"phase": phase, "ok": True, "seconds": round(time.monotonic() - started, 3)})
            for index in range(args.count):
                owned_run(args.run_dir, args.serial)
                phase = f"snapshot_{index + 1}"
                tick = time.monotonic()
                options = {"include_image": True, "include_xml": True, "image_format": "jpeg"}
                raw = await session.call("android.snapshot", {"arguments": options})
                # Keep the ORIGINAL wire receipt privately for offline backend validation.
                (args.output / f"{phase}.wire.json").write_text(json.dumps(raw) + "\n")
                result = dict(raw)
                _snapshot_hierarchy(result, options)
                data, _ = _snapshot_image(result.pop("image_base64"), result, "jpeg")
                if result["foreground_package"] != args.package:
                    raise ValueError("Captured foreground is not the intended public App")
                (args.output / f"{phase}.jpg").write_bytes(data)
                event({"phase": phase, "ok": True, "seconds": round(time.monotonic() - tick, 3),
                       "capture_delay_ms": result.get("capture_delay_ms"),
                       "timings": result.get("snapshot_timings")})
                if index + 1 < args.count:
                    await asyncio.sleep(1)
    except BaseException as error:
        value = {"phase": phase, "ok": False, "type": type(error).__name__}
        if hasattr(error, "problem"):
            value["problem"] = error.problem()
        if hasattr(error, "native_diagnostic"):
            value["diagnostic"] = error.native_diagnostic
        event(value)
    finally:
        if session is not None:
            try:
                await asyncio.wait_for(session.close(), 45)
                receipt["cleanup_confirmed"] = True
            except BaseException as error:
                receipt["cleanup_confirmed"] = False
                receipt["cleanup_error_type"] = type(error).__name__
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        receipt["passed"] = (len([e for e in events if e["phase"].startswith("snapshot_") and e["ok"]]) == args.count
                             and receipt.get("cleanup_confirmed") is True)
        (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({"passed": receipt["passed"], "cleanup_confirmed": receipt.get("cleanup_confirmed"),
                          "elapsed_seconds": receipt["elapsed_seconds"]}), flush=True)
    return receipt["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kengent-root", type=Path, required=True)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--serial", default="emulator-5576")
    parser.add_argument("--package", choices=("com.tdx.AndroidNew", "com.guotai.dazhihui"), required=True)
    parser.add_argument("--count", type=int, choices=range(1, 7), default=3)
    args = parser.parse_args()
    sys.path.insert(0, str(args.kengent_root.resolve() / "src"))
    os.umask(0o077)
    async def run():
        task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(signum, task.cancel)
        return await probe(args)
    raise SystemExit(0 if asyncio.run(run()) else 1)


if __name__ == "__main__":
    main()
