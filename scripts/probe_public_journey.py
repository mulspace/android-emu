#!/usr/bin/env python3
"""Bounded public navigation on an owned diagnostic AVD; never account input."""
import argparse
import hashlib
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

from trace_native_start import traced_session_type
from native_ready_probe import ready_session_type
from quote_read_probe import options as quote_options, validate_receipt as validate_quote_receipt, verify_input_denial

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


def broker_result(items):
    required={
        "et_input_edit":"600999", "tv_stock_market":"沪A",
        "tv_stock_code":"600999", "tv_stock_name":"招商证券",
    }
    for key,value in required.items():
        match=unique(items,lambda n:n.get("resource-id")==JUNHONG+":id/"+key and n.get("text")==value)
        if match is None:return None
        if key != "et_input_edit":
            bounds=re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]",match.get("bounds",""))
            if bounds is None:return None
            left,top,right,bottom=map(int,bounds.groups())
            if not (0 <= left < right <= 720 and 318 <= top < bottom <= 432):return None
    # Exact observed first stock row, not the add-to-watchlist icon or news below it.
    return unique(items,lambda n:n.get("class")=="android.widget.LinearLayout"
                  and n.get("bounds")=="[0,318][720,432]" and n.get("clickable")=="true")


def broker_layout_cancel(items):
    labels={"tv_right":"五档在右边", "tv_below":"五档在下边",
            "tv_five_level_remind":"您还可以到“我的-设置-行情设置”里进行切换"}
    if not any(n.get("text")=="五档/分时位置自由选择" for n in items):return None
    if not all(unique(items,lambda n:n.get("resource-id")==JUNHONG+":id/"+key
                      and n.get("text")==value) is not None for key,value in labels.items()):return None
    return unique(items,lambda n:n.get("resource-id")==JUNHONG+":id/tv_cancel"
        and n.get("text")=="取消" and n.get("bounds")=="[40,977][359,1067]"
        and n.get("clickable")=="true")


def broker_quote_ready(items):
    if not all(any(n.get("text")==value for n in items) for value in ("600999","招商证券","分时")):
        return None
    return unique(items,lambda n:n.get("text")=="600999")


class Journey:
    def __init__(self, package, capture, action, pause=asyncio.sleep, *, junhong_page="market", tdx_page="market", read_only_quote=False, settle_windows=False):
        self.package, self.capture, self.action, self.pause = package, capture, action, pause
        self.junhong_page = junhong_page
        self.tdx_page = tdx_page
        self.read_only_quote = read_only_quote
        self.settle_windows = settle_windows
        if settle_windows and package != TDX:
            raise ValueError("Window settle diagnostic requires TDX")
        if read_only_quote and (package != JUNHONG or junhong_page not in ("quote", "search-quote", "result")):
            raise ValueError("Read-only quote requires a verified Junhong quote route")
        if tdx_page not in ("market", "quote") or (tdx_page != "market" and package != TDX):
            raise ValueError("Invalid TDX public route")
        if junhong_page not in ("market", "search", "result", "quote", "search-quote") or (junhong_page != "market" and package != JUNHONG):
            raise ValueError("Invalid Junhong public route")

    async def wait(self, phase, selector, *, stable=False):
        previous = None
        for attempt in range(8):
            # A native error ends its session. Recovery belongs inside that
            # original native request; never send another RPC after failure.
            options = {"include_image": False, "include_xml": True}
            if self.settle_windows and phase == "chart_ready" and attempt == 0:
                options["wait_window_quiet"] = "tdx-chart-v1"
            frame = await self.capture(f"{phase}_{attempt+1}", options)
            chosen = selector(nodes(frame, self.package))
            if chosen is not None and (not stable or chosen == previous):
                return frame, chosen
            previous = chosen
            if attempt < 7:
                await self.pause(2)
        raise TimeoutError("Public page did not reach the expected state: " + phase)

    async def tap(self, phase, frame, chosen):
        await self.action(phase, "android.tap", center(frame, chosen))

    async def quote_entry(self):
        # A known modal takes priority even if the stock title is visible behind it.
        frame, chosen = await self.wait("broker_quote_entry", lambda ns: broker_layout_cancel(ns) or broker_quote_ready(ns))
        if chosen.get("resource-id") == JUNHONG + ":id/tv_cancel":
            await self.tap("cancel_known_quote_layout_once", frame, chosen)
            await self.wait("broker_quote_ready", broker_quote_ready)

    async def navigate(self):
        if self.junhong_page in ("result", "quote"):
            if self.junhong_page == "result":
                frame, chosen = await self.wait("broker_known_result", broker_result, stable=True)
                await self.tap("open_broker_quote_once", frame, chosen)
            await self.quote_entry()
        elif self.package == JUNHONG:
            def market_tab(ns):
                return unique(ns, lambda n: n.get("resource-id") == JUNHONG + ":id/tv_free_stock_market"
                    and n.get("text") == "行情" and n.get("clickable") == "true")
            frame, chosen = await self.wait("public_home", lambda ns: unique(ns, lambda n:
                n.get("resource-id") == JUNHONG + ":id/bottom_menu_button2"
                and n.get("clickable") == "true") if any(n.get("text") == "行情"
                and n.get("resource-id") == JUNHONG + ":id/btm_text2" for n in ns) else None)
            tab = market_tab(nodes(frame, self.package))
            if tab is None:
                await self.tap("open_market_once", frame, chosen)
                frame, tab = await self.wait("public_market_tab", market_tab)
            if tab.get("selected") != "true":
                await self.tap("open_public_market_once", frame, tab)
                def selected_market(ns):
                    current = market_tab(ns)
                    return current if current and current.get("selected") == "true" else None
                frame, _ = await self.wait("market_ready", selected_market)
            if self.junhong_page in ("search", "search-quote"):
                def search_control(ns):
                    return unique(ns, lambda n: n.get("resource-id") == JUNHONG + ":id/title_search"
                        and n.get("class") == "android.widget.RelativeLayout"
                        and n.get("bounds") == "[640,56][688,128]"
                        and n.get("clickable") == "true")
                # The verified market observation already contains this control.
                # Keep its original frame_ref; the normal native input guard still applies.
                chosen = search_control(nodes(frame, self.package))
                if chosen is None:
                    frame, chosen = await self.wait("broker_search_control", search_control)
                await self.tap("open_broker_public_search_once", frame, chosen)
                def broker_field(ns):
                    return unique(ns, lambda n: n.get("class") == "android.widget.EditText"
                        and n.get("focused") == "true" and n.get("password") == "false"
                        and n.get("enabled") == "true")
                frame, _ = await self.wait("broker_search_field", broker_field)
                await self.action("enter_broker_public_symbol_once", "android.text",
                                  {"frame_ref": frame["frame_ref"], "text": "600999"})
                def symbol_readback(ns):
                    field = broker_field(ns)
                    return field if field and field.get("text") == "600999" else None
                await self.wait("broker_symbol_readback", symbol_readback, stable=True)
                if self.junhong_page == "search-quote":
                    frame, chosen = await self.wait("broker_known_result", broker_result, stable=True)
                    await self.tap("open_broker_quote_once", frame, chosen)
                    await self.quote_entry()
        elif self.package == TDX:
            if self.tdx_page == "market":
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
                    and "600999" in n.get("content-desc", "").splitlines() and n.get("clickable") == "true"), stable=True)
                # Search WebView can briefly expose a hit, then rebuild its results.
                # Require two matching read-only hit observations before the one tap.
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
            if self.read_only_quote:
                current = await self.capture(f"snapshot_{index+1}_quote", quote_options())
                validate_quote_receipt(current)
                nodes(current, self.package)
                continue
            previous = await self.capture(f"snapshot_{index+1}_observe", {"include_image": False, "include_xml": True})
            nodes(previous, self.package)
            current = await self.capture(f"snapshot_{index+1}_checked", {"include_image": True,
                "include_xml": True, "image_format": "jpeg", "expected_frame_ref": previous["frame_ref"]})
            nodes(current, self.package)
            validate_checked_pair(previous, current)
        return current


async def probe(args):
    from kengent.tools.resource_node.android import AdbTransport, NativeSession, _snapshot_hierarchy, _snapshot_image
    owned_run(args.run_dir, args.serial)
    if args.read_only_quote:
        build = json.loads((args.artifacts / "build.json").read_text())
        if build.get("experimental_read_only_quote") is not True or build.get("bridge_sha256") != hashlib.sha256((args.artifacts / "bridge.jar").read_bytes()).hexdigest():
            raise ValueError("Audited read-only quote bridge is required")
    if args.settle_windows:
        build = json.loads((args.artifacts / "build.json").read_text())
        if build.get("experimental_window_quiet") is not True or build.get("bridge_sha256") != hashlib.sha256((args.artifacts / "bridge.jar").read_bytes()).hexdigest():
            raise ValueError("Audited window settle bridge is required")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    events = []
    receipt = {"started_at": datetime.now(UTC).isoformat(),
               "public_only": True, "production_cutover": False, "account_input": False,
               "account_collection_verified": False, "package": args.package,
               "artifact_sha256": {name: hashlib.sha256((args.artifacts / name).read_bytes()).hexdigest()
                                   for name in ("u2.jar", "bridge.jar")},
               "diagnostic_snapshot_timeout_seconds": args.snapshot_seconds,
               "experimental_window_quiet": args.settle_windows,
               "duration_limit_seconds": args.seconds,
               "checked_capture": not args.read_only_quote, "read_only_quote_capture": args.read_only_quote, "events": events, "visual_review_required": True,
               "launch_mode": "prestarted" if args.prestarted else "native",
               "public_page": "broker_" + args.junhong_page if args.package == JUNHONG else "tdx_" + args.tdx_page + "_to_daily_chart"}
    session, passed, phase = None, False, "identify"
    started = time.monotonic()
    deadline = datetime.now(UTC) + timedelta(seconds=args.seconds)
    def event(**value):
        value["observed_at"] = datetime.now(UTC).isoformat()
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
            candidate = ready_session_type(NativeSession, args.native_ready_seconds)
            receipt["native_ready_probe"] = getattr(candidate, "ready_probe_info", {"native_ready_seconds": 10})
            traced = traced_session_type(candidate, lambda value: event(**value))
            session = traced(transport, context, [args.package])
            await session.start(context)
            event(phase=phase, ok=True, seconds=round(time.monotonic()-started, 3))
            last_renewal = time.monotonic()
            attempts = {}
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
                attempts[name] = attempts.get(name, 0) + 1
                try:
                    raw = await session.call(operation, {"arguments": options})
                except Exception as error:
                    event(phase=name, attempt=attempts[name], ok=False,
                          seconds=round(time.monotonic()-tick, 3), type=type(error).__name__,
                          diagnostic=getattr(error, "native_diagnostic", None))
                    raise
                (args.output / f"{name}.wire.json").write_text(json.dumps(raw) + "\n")
                event(phase=name, attempt=attempts[name], ok=True, seconds=round(time.monotonic()-tick, 3))
                return raw
            async def capture(name, options):
                raw = await call(name, "android.snapshot", options)
                if options.get("read_only_quote"):
                    validate_quote_receipt(raw)
                result = dict(raw)
                _snapshot_hierarchy(result, options)
                if options["include_image"]:
                    data, _ = _snapshot_image(result.pop("image_base64"), result, "jpeg")
                    (args.output / f"{name}.jpg").write_bytes(data)
                return raw
            if not args.prestarted:
                await call("launch_app_once", "android.start_app", {"package": args.package})
            last = await Journey(args.package, capture, call, junhong_page=args.junhong_page,
                tdx_page=args.tdx_page, read_only_quote=args.read_only_quote,
                settle_windows=args.settle_windows).navigate()
            if args.read_only_quote:
                phase = "read_only_input_denial"
                owned_run(args.run_dir, args.serial)
                receipt["input_denial_verified"] = await verify_input_denial(session.call, last["frame_ref"])
                event(phase=phase, ok=True, physical_input=False)
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
        receipt["ended_at"] = datetime.now(UTC).isoformat()
        (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({k:receipt[k] for k in ("passed", "elapsed_seconds", "account_collection_verified")}), flush=True)
    return receipt["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kengent-root", "adb", "run-dir", "artifacts", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--serial", choices=("emulator-5576",), default="emulator-5576")
    parser.add_argument("--package", choices=(TDX, JUNHONG), required=True)
    parser.add_argument("--junhong-page", choices=("market", "search", "result", "quote", "search-quote"), default="market", help="Explicit public journey: market, 600999 search, verified result, current quote, or complete search-quote")
    parser.add_argument("--tdx-page", choices=("market", "quote"), default="market", help="Start from the market page or a previously verified open public quote; never repeat uncertain navigation")
    parser.add_argument("--settle-windows", action="store_true", help="Wait for window geometry to settle only before TDX chart entry; unchanged RPC deadline")
    parser.add_argument("--read-only-quote", action="store_true", help="Public Junhong quote evidence with dynamic numeric values; never input authority")
    parser.add_argument("--native-ready-seconds", type=int, choices=(10, 30), default=10,
                        help="Opt-in startup wait comparison, bounded by the original lease; no input/capture changes")
    parser.add_argument("--prestarted", action="store_true", help="Use an explicitly prestarted public App; do not repeat its launch")
    parser.add_argument("--snapshot-seconds", type=int, choices=(30, 90), default=30,
                        help="Diagnostic read-only deadline comparison, never a production setting")
    parser.add_argument("--seconds", type=int, choices=(180, 300, 600), default=600,
                        help="Whole journey deadline, followed by bounded session cleanup")
    args = parser.parse_args()
    if args.settle_windows and args.package != TDX:
        parser.error("Window settle diagnostic requires TDX")
    if args.read_only_quote and (args.package != JUNHONG or args.junhong_page not in ("quote", "search-quote", "result")):
        parser.error("Read-only quote requires a verified Junhong quote route")
    if args.junhong_page != "market" and args.package != JUNHONG:
        parser.error("Junhong public routes require Junhong")
    if args.tdx_page != "market" and args.package != TDX:
        parser.error("TDX public routes require TDX")
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
