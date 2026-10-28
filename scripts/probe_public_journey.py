#!/usr/bin/env python3
"""Bounded public navigation on an owned diagnostic AVD; never account input."""
import argparse
import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import re
import signal
import sys
import time
import uuid
import xml.etree.ElementTree as ET

from probe_public_capture import owned_run, validate_checked_pair

TDX = "com.tdx.AndroidNew"
JUNHONG = "com.guotai.dazhihui"


def nodes(frame, package):
    if frame.get("foreground_package") != package or frame.get("sensitive_inputs"):
        raise ValueError("Unexpected or sensitive foreground")
    if (frame.get("width"), frame.get("height"), frame.get("rotation")) != (720, 1560, 0):
        raise ValueError("Unverified public layout")
    return [n.attrib for n in ET.fromstring(frame["hierarchy_xml"]).iter("node")
            if n.attrib.get("package") == package]


def unique(items, predicate):
    found = [n for n in items if predicate(n)]
    if len(found) > 1:
        raise ValueError("Ambiguous public control")
    return found[0] if found else None


def center(frame, node):
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
    if not match or node.get("clickable") != "true" or node.get("enabled") == "false":
        raise ValueError("Public control is not actionable")
    left, top, right, bottom = map(int, match.groups())
    if not (0 <= left < right <= frame["width"] and 0 <= top < bottom <= frame["height"]):
        raise ValueError("Invalid public control bounds")
    return {"frame_ref": frame["frame_ref"], "x": (left + right) / 2 / (frame["width"] - 1),
            "y": (top + bottom) / 2 / (frame["height"] - 1)}


def tdx_search(items):
    if not any(n.get("text") == "市场" and n.get("resource-id") == TDX + ":id/tvContent"
               and n.get("selected") == "true" for n in items):
        return None
    return unique(items, lambda n: n.get("bounds") == "[648,71][693,116]"
                  and n.get("class") == "android.widget.ImageView" and n.get("clickable") == "true")


def search_field(items):
    return unique(items, lambda n: n.get("class") == "android.widget.EditText"
                  and n.get("focused") == "true" and n.get("password") != "true"
                  and n.get("bounds") == "[120,68][586,128]")


def daily(items):
    if not all(any(n.get("text") == label for n in items) for label in ("分时", "周K", "月K")):
        return None
    return unique(items, lambda n: n.get("text") == "日K" and n.get("clickable") == "true")


def inline_notice(items):
    # Exact previously observed public announcement, not a generic close-dialog rule.
    label = unique(items, lambda n: n.get("bounds") == "[49,387][671,446]" and bool(n.get("text")))
    close = unique(items, lambda n: n.get("bounds") == "[671,387][701,446]"
                   and n.get("class") == "android.widget.LinearLayout" and n.get("clickable") == "true")
    if bool(label) != bool(close):
        raise ValueError("Unrecognized announcement layout")
    return close


class Journey:
    def __init__(self, package, capture, action, pause=asyncio.sleep):
        self.package, self.capture, self.action, self.pause = package, capture, action, pause

    async def wait(self, phase, selector):
        for attempt in range(8):
            frame = await self.capture(f"{phase}_{attempt+1}", {"include_image": False, "include_xml": True})
            chosen = selector(nodes(frame, self.package))
            if chosen is not None:
                return frame, chosen
            if attempt < 7:
                await self.pause(2)
        raise TimeoutError("Public page did not reach the expected state: " + phase)

    async def tap(self, phase, frame, chosen):
        await self.action(phase, "android.tap", center(frame, chosen))

    async def navigate(self):
        if self.package == JUNHONG:
            frame, chosen = await self.wait("public_home", lambda ns: unique(ns, lambda n:
                n.get("resource-id") == JUNHONG + ":id/bottom_menu_button2"
                and n.get("clickable") == "true") if any(n.get("text") == "行情"
                and n.get("resource-id") == JUNHONG + ":id/btm_text2" for n in ns) else None)
            await self.tap("open_market_once", frame, chosen)
            def market_tab(ns):
                return unique(ns, lambda n: n.get("resource-id") == JUNHONG + ":id/tv_free_stock_market"
                    and n.get("text") == "行情" and n.get("clickable") == "true")
            frame, chosen = await self.wait("public_market_tab", market_tab)
            if chosen.get("selected") != "true":
                await self.tap("open_public_market_once", frame, chosen)
            def selected_market(ns):
                tab = market_tab(ns)
                return tab if tab and tab.get("selected") == "true" else None
            await self.wait("market_ready", selected_market)
        elif self.package == TDX:
            frame, chosen = await self.wait("market_ready", tdx_search)
            await self.tap("open_search_once", frame, chosen)
            frame, _ = await self.wait("search_ready", search_field)
            await self.action("enter_public_symbol_once", "android.text",
                              {"frame_ref": frame["frame_ref"], "text": "600999"})
            def submit(ns):
                field = search_field(ns)
                if field is None or field.get("text") != "600999":
                    return None
                return unique(ns, lambda n: n.get("text") == "搜索" and n.get("clickable") == "true")
            frame, chosen = await self.wait("symbol_readback", submit)
            await self.tap("submit_public_search_once", frame, chosen)
            frame, chosen = await self.wait("exact_result", lambda ns: unique(ns, lambda n:
                n.get("content-desc", "").startswith("招商证券\n")
                and "600999" in n.get("content-desc", "").splitlines() and n.get("clickable") == "true"))
            await self.tap("open_exact_result_once", frame, chosen)
            frame, chosen = await self.wait("chart_ready", daily)
            await self.tap("select_daily_once", frame, chosen)
            frame, _ = await self.wait("daily_ready", daily)
            close = inline_notice(nodes(frame, self.package))
            if close is not None:
                await self.tap("close_verified_announcement_once", frame, close)
                await self.wait("daily_after_notice", daily)
        else:
            raise ValueError("Unsupported diagnostic package")
        # Capture identity/date must be visually checked: TDX draws the header in a canvas.
        # Do not fabricate an XML stock code or report account/market acceptance here.
        for index in range(3):
            previous = await self.capture(f"snapshot_{index+1}_observe", {"include_image": False, "include_xml": True})
            nodes(previous, self.package)
            current = await self.capture(f"snapshot_{index+1}_checked", {"include_image": True,
                "include_xml": True, "image_format": "jpeg", "expected_frame_ref": previous["frame_ref"]})
            nodes(current, self.package)
            validate_checked_pair(previous, current)


async def probe(args):
    from kengent.tools.resource_node.android import AdbTransport, NativeSession, _snapshot_hierarchy, _snapshot_image
    owned_run(args.run_dir, args.serial)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    events = []
    receipt = {"public_only": True, "production_cutover": False, "account_input": False,
               "account_collection_verified": False, "package": args.package,
               "diagnostic_snapshot_timeout_seconds": args.snapshot_seconds,
               "duration_limit_seconds": args.seconds,
               "checked_capture": True, "events": events, "visual_review_required": True,
               "launch_mode": "prestarted" if args.prestarted else "native"}
    session, passed, phase = None, False, "identify"
    started = time.monotonic()
    deadline = datetime.now(UTC) + timedelta(seconds=args.seconds)
    def event(**value):
        events.append(value)
        print(json.dumps(value), flush=True)
    try:
        async with asyncio.timeout(args.seconds):
            transport = AdbTransport(adb_path=str(args.adb), serial=args.serial,
                artifacts=(args.artifacts / "u2.jar", args.artifacts / "bridge.jar"), timing_profile="arm-emulator")
            # Isolated diagnostic experiment only. All input and identity bounds stay intact.
            transport.timing = replace(transport.timing, snapshot_seconds=args.snapshot_seconds)
            identity = await transport.identify()
            if args.package not in identity["packages"]:
                raise ValueError("Public App is not installed")
            transport.fingerprint = identity["fingerprint"]
            context = {"nonce": uuid.uuid4().hex,
                       "expires_at": min(deadline, datetime.now(UTC) + timedelta(seconds=280)).isoformat()}
            receipt["nonce"] = context["nonce"]
            phase = "native_start"
            session = NativeSession(transport, context, [args.package])
            await session.start(context)
            event(phase=phase, ok=True, seconds=round(time.monotonic()-started, 3))
            last_renewal = time.monotonic()
            async def call(name, operation, options):
                nonlocal phase, last_renewal
                phase = name
                owned_run(args.run_dir, args.serial)
                if time.monotonic() - last_renewal > 60:
                    # Diagnostic session only, capped by this test's original absolute deadline.
                    context["expires_at"] = min(deadline, datetime.now(UTC) + timedelta(seconds=280)).isoformat()
                    await session.renew(context)
                    last_renewal = time.monotonic()
                tick = time.monotonic()
                (args.output / f"{name}.request.json").write_text(json.dumps(options) + "\n")
                raw = await session.call(operation, {"arguments": options})
                (args.output / f"{name}.wire.json").write_text(json.dumps(raw) + "\n")
                event(phase=name, ok=True, seconds=round(time.monotonic()-tick, 3))
                return raw
            async def capture(name, options):
                raw = await call(name, "android.snapshot", options)
                result = dict(raw)
                _snapshot_hierarchy(result, options)
                if options["include_image"]:
                    data, _ = _snapshot_image(result.pop("image_base64"), result, "jpeg")
                    (args.output / f"{name}.jpg").write_bytes(data)
                return raw
            if not args.prestarted:
                await call("launch_app_once", "android.start_app", {"package": args.package})
            await Journey(args.package, capture, call).navigate()
            passed = True
    except BaseException as error:
        event(phase=phase, ok=False, type=type(error).__name__,
              diagnostic=getattr(error, "native_diagnostic", None))
    finally:
        if session is not None:
            try:
                await asyncio.wait_for(session.close(), 45)
                receipt["cleanup_confirmed"] = True
            except BaseException as error:
                receipt["cleanup_confirmed"] = False
                receipt["cleanup_error_type"] = type(error).__name__
        receipt["passed"] = passed and receipt.get("cleanup_confirmed") is True
        receipt["elapsed_seconds"] = round(time.monotonic()-started, 3)
        (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({k:receipt[k] for k in ("passed", "elapsed_seconds", "account_collection_verified")}), flush=True)
    return receipt["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kengent-root", "adb", "run-dir", "artifacts", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--serial", choices=("emulator-5576",), default="emulator-5576")
    parser.add_argument("--package", choices=(TDX, JUNHONG), required=True)
    parser.add_argument("--prestarted", action="store_true", help="Use an explicitly prestarted public App; do not repeat its launch")
    parser.add_argument("--snapshot-seconds", type=int, choices=(30, 90), default=30,
                        help="Diagnostic read-only deadline comparison, never a production setting")
    parser.add_argument("--seconds", type=int, choices=(180, 300, 600), default=600,
                        help="Whole journey deadline, followed by bounded session cleanup")
    args = parser.parse_args()
    sys.path.insert(0, str(args.kengent_root.resolve() / "src"))
    os.umask(0o077)
    async def run():
        task = asyncio.current_task()
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().add_signal_handler(sig, task.cancel)
        return await probe(args)
    raise SystemExit(0 if asyncio.run(run()) else 1)


if __name__ == "__main__":
    main()
