#!/usr/bin/env python3
"""Build an isolated numeric-only observation diagnostic; never access a device."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch


def instrument(source):
    """Strict anchors: refuse source drift instead of changing snapshot checks."""
    start = source.index("    private static final class SnapshotState {")
    end = source.index("    private static JSONObject snapshot(", start)
    block = source[start:end]
    replacements = [
        ('String phase = "snapshot_display_visibility";',
         'String phase = "snapshot_display_visibility";\n            long probeTick = SystemClock.elapsedRealtime();'),
        ('pkg = snapshotForeground();',
         'pkg = snapshotForeground();\n            android.util.Log.i("EmuObservation", "foreground_ms=" + (SystemClock.elapsedRealtime() - probeTick));\n            probeTick = SystemClock.elapsedRealtime();'),
        ('phase = "snapshot_hierarchy";',
         'android.util.Log.i("EmuObservation", "geometry_ms=" + (SystemClock.elapsedRealtime() - probeTick));\n            probeTick = SystemClock.elapsedRealtime();\n            phase = "snapshot_hierarchy";'),
        ('xml = tree();',
         'xml = tree();\n            android.util.Log.i("EmuObservation", "hierarchy_ms=" + (SystemClock.elapsedRealtime() - probeTick));\n            probeTick = SystemClock.elapsedRealtime();'),
        ('try { sensitive(root, 0, new int[]{0}, sensitiveInputs); }',
         'int[] probeNodes = {0};\n            try { sensitive(root, 0, probeNodes, sensitiveInputs); }'),
        ('finally { root.recycle(); }',
         'finally { root.recycle(); }\n            android.util.Log.i("EmuObservation", "sensitive_ms=" + (SystemClock.elapsedRealtime() - probeTick) + " nodes=" + probeNodes[0]);\n            probeTick = SystemClock.elapsedRealtime();'),
        ('observation = new SnapshotCapture.Observation(pkg + ":" + w + ":" + h + ":" + r, xml, sensitiveInputs.length() != 0);',
         'observation = new SnapshotCapture.Observation(pkg + ":" + w + ":" + h + ":" + r, xml, sensitiveInputs.length() != 0);\n            android.util.Log.i("EmuObservation", "stability_ms=" + (SystemClock.elapsedRealtime() - probeTick));'),
        ('} catch (Exception error) {',
         '} catch (Exception error) {\n                android.util.Log.i("EmuObservation", "failed=" + phase + " ms=" + (SystemClock.elapsedRealtime() - probeTick));'),
    ]
    for old, new in replacements:
        if block.count(old) != 1:
            raise ValueError("Diagnostic source anchor changed")
        block = block.replace(old, new)
    return source[:start] + block + source[end:]



def retry_incomplete_checked(source):
    """Keep the exact expected observation while retrying only absent-node reads."""
    old = "if (expected != null || attempt == 2) throw changed;"
    new = "if (attempt == 2 || (expected != null && changed instanceof UnstableSurface)) throw changed;"
    if source.count(old) != 1:
        raise ValueError("Checked retry source anchor changed")
    return source.replace(old, new)


def hierarchy_retry_delay(source, milliseconds):
    """Change only the two intra-request snapshot pauses, never input/lifetime."""
    if milliseconds not in (25, 250, 1000):
        raise ValueError("Unsupported hierarchy retry delay")
    start = source.index("    private static JSONObject captureSnapshot(")
    end = source.index("    private static", start + 1)
    block = source[start:end]
    anchor = "SystemClock.sleep(25L); alive();"
    if block.count(anchor) != 2:
        raise ValueError("Hierarchy pause source anchor changed")
    return source[:start] + block.replace(anchor, f"SystemClock.sleep({milliseconds}L); alive();") + source[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kengent-root", type=Path, required=True)
    parser.add_argument("--sdk-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--single-pass", action="store_true", help="Experimental complete tree/sensitivity traversal; not a production build")
    parser.add_argument("--retry-incomplete-checked", action="store_true", help="Diagnostic: retry missing nodes at most three times without changing the expected frame")
    parser.add_argument("--hierarchy-retry-delay-ms", type=int, choices=(25, 250, 1000), default=25,
                        help="Diagnostic intra-request retry pause; no retries after a native session fails")
    parser.add_argument("--experimental-source", type=Path, default=Path(__file__).resolve().parents[1] / "experimental/native")
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.kengent_root / "src"))
    from kengent.tools.resource_node import android
    original = args.kengent_root / "src/kengent/tools/resource_node/native"
    copied = args.output / "source/native"
    copied.mkdir(parents=True)
    before = {}
    for path in original.glob("*.java"):
        before[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        shutil.copyfile(path, copied / path.name)
    source = copied / "ResourceDeviceBridge.java"
    instrumented = instrument(source.read_text())
    if args.single_pass:
        first = instrumented.index('            xml = tree();', instrumented.index('class SnapshotState'))
        last = instrumented.index('            phase = "snapshot_stability";', first)
        instrumented = instrumented[:first] + '''            AndroidHierarchy.Result captured = AndroidHierarchy.capture(automation, r, w, h, ResourceDeviceBridge::alive);
            xml = captured.xml;
            sensitiveInputs = captured.sensitive;
            android.util.Log.i("EmuObservation", "single_pass_ms=" + (SystemClock.elapsedRealtime() - probeTick) + " nodes=" + captured.nodes);
            probeTick = SystemClock.elapsedRealtime();
''' + instrumented[last:]
        for name in ("SinglePassHierarchy.java", "AndroidHierarchy.java"):
            shutil.copyfile(args.experimental_source / name, copied / name)
    if args.retry_incomplete_checked:
        checks = copied / "SnapshotCapture.java"
        checks.write_text(retry_incomplete_checked(checks.read_text()))
    instrumented = hierarchy_retry_delay(instrumented, args.hierarchy_retry_delay_ms)
    source.write_text(instrumented)
    resource_files = android.resources.files
    def resources(name):
        return copied.parent if name == "kengent.tools.resource_node" else resource_files(name)
    with patch.object(android.resources, "files", resources):
        engine, bridge = android.build_native_artifacts(sdk_root=args.sdk_root, cache_root=args.output / "cache")
    shutil.copyfile(engine, args.output / "u2.jar")
    shutil.copyfile(bridge, args.output / "bridge.jar")
    receipt = {"diagnostic_only": True, "device_operations": False, "experimental_single_pass": args.single_pass,
               "experimental_checked_retry": args.retry_incomplete_checked,
               "hierarchy_retry_delay_ms": args.hierarchy_retry_delay_ms, "source_hashes": before,
               "built_source_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in copied.glob("*.java")},
               "bridge_sha256": hashlib.sha256(bridge.read_bytes()).hexdigest(),
               "instrumented_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    (args.output / "build.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"bridge_sha256": receipt["bridge_sha256"], "diagnostic_only": True}))


if __name__ == "__main__":
    main()
