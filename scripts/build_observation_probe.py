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


def mismatch_diagnostics(source):
    """Attach a numeric explanation without changing matching or rejection."""
    anchor = "        public final String phase;\n        Mismatch("
    value = '            phase = "snapshot_" + (clockOnly ? "clock_changed_" : "changed_")\n                    + (during ? "during_capture" : "before_capture");'
    if source.count(anchor) != 1 or source.count(value) != 1:
        raise ValueError("Mismatch diagnostic source anchor changed")
    source = source.replace(anchor, "        public final String phase;\n        public final String diagnostic;\n        Mismatch(")
    return source.replace(value, value + '\n            diagnostic = left.sensitive || right.sensitive ? "sensitive=1"\n                    : HierarchyDifference.describe(left.hierarchy, right.hierarchy);')

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



def startup_diagnostics(source):
    """Timestamp fixed startup phases; preserve all deadlines and failure paths."""
    first = source.index("    private static void serve(PrintStream wire) {")
    end = source.index("    public static void main(String[] args)", first)
    block = source[first:end]
    anchor = '        String phase = "service_configurator";'
    if block.count(anchor) != 1:
        raise ValueError("Startup diagnostic source anchor changed")
    block = block.replace(anchor, anchor + '\n        long startupTick=SystemClock.elapsedRealtime();\n        android.util.Log.i("EmuStartup", "phase=configurator elapsed_ms=0");')
    for phase in ("service_automation", "service", "ready"):
        anchor = f'            phase = "{phase}";'
        if block.count(anchor) != 1:
            raise ValueError("Startup diagnostic source anchor changed")
        block = block.replace(anchor, anchor + f'\n            android.util.Log.i("EmuStartup", "phase={phase} elapsed_ms=" + (SystemClock.elapsedRealtime()-startupTick));')
    return source[:first] + block + source[end:]


def recover_stable_child(source):
    """Retry an absent child only if all cached parent/child identities survive refresh."""
    anchor = """                int before=node.getChildCount();
                boolean refreshed=node.refresh();
                android.util.Log.i("EmuObservation", "missing_child_refresh refreshed=" + refreshed
                    + " before=" + before + " after=" + node.getChildCount() + " index=" + index);
                // This traversal still fails. Never skip an absent child or accept
                // a partial sensitivity scan; a later complete traversal is required.
                return null;"""
    replacement = """                long recoveryTick=android.os.SystemClock.elapsedRealtime();
                child=StableChildRecovery.recover(new StableChildRecovery.Port<AccessibilityNodeInfo>() {
                    public void check() { checkAlive(); }
                    public Object state() { return parentState(); }
                    public boolean refresh() { return node.refresh(); }
                    public AccessibilityNodeInfo read() { return node.getChild(index); }
                    public void trace(int result) { android.util.Log.i("EmuObservation", "child_recovery_result=" + result); }
                });
                android.util.Log.i("EmuObservation", "stable_child_recovery found=" + (child!=null)
                    + " ms=" + (android.os.SystemClock.elapsedRealtime()-recoveryTick));
                if(child==null)return null;"""
    state = """        private Object parentState() {
            try {
                List<Object> state=new ArrayList<>();
                state.add(attributes()); state.add(visible()); state.add(inputType());
                java.lang.reflect.Method source=AccessibilityNodeInfo.class.getMethod("getSourceNodeId");
                java.lang.reflect.Method child=AccessibilityNodeInfo.class.getMethod("getChildId",int.class);
                state.add(source.invoke(node)); state.add(node.getWindowId());
                int count=node.getChildCount();
                if(count<0 || count>10000)throw new IllegalStateException();
                state.add(count);
                for(int i=0;i<count;i++)state.add(child.invoke(node,i));
                return state;
            } catch(Exception error) { throw new IllegalStateException(); }
        }
        private void checkAlive() {
            try { check.alive(); } catch(Exception error) { throw new IllegalStateException(); }
        }
"""
    replacements = [
        (anchor,replacement),
        ("final AccessibilityNodeInfo node; final int width,height;", "final AccessibilityNodeInfo node; final int width,height; final SinglePassHierarchy.Check check;"),
        ("Node(AccessibilityNodeInfo node,int w,int h){this.node=node;width=w;height=h;}", "Node(AccessibilityNodeInfo node,int w,int h,SinglePassHierarchy.Check check){this.node=node;width=w;height=h;this.check=check;}"),
        ("return new Node(child,width,height);", "return new Node(child,width,height,check);"),
        ("new Node(root,width,height)","new Node(root,width,height,check)"),
        ("        public void recycle(){node.recycle();}",state+"        public void recycle(){node.recycle();}"),
    ]
    for old,new in replacements:
        if source.count(old)!=1:
            raise ValueError("Stable child recovery source anchor changed")
        source=source.replace(old,new)
    return source

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kengent-root", type=Path, required=True)
    parser.add_argument("--sdk-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--single-pass", action="store_true", help="Experimental complete tree/sensitivity traversal; not a production build")
    parser.add_argument("--prefetch-siblings", action="store_true", help="API-24 diagnostic: framework sibling prefetch, preserving complete traversal")
    parser.add_argument("--recover-stable-child", action="store_true", help="Diagnostic: one missing-child read after an identical parent refresh; requires single-pass")
    parser.add_argument("--retry-incomplete-checked", action="store_true", help="Diagnostic: retry missing nodes at most three times without changing the expected frame")
    parser.add_argument("--hierarchy-retry-delay-ms", type=int, choices=(25, 250, 1000), default=25,
                        help="Diagnostic intra-request retry pause; no retries after a native session fails")
    parser.add_argument("--experimental-source", type=Path, default=Path(__file__).resolve().parents[1] / "experimental/native")
    args = parser.parse_args()
    if args.recover_stable_child and not args.single_pass:
        parser.error("--recover-stable-child requires --single-pass")
    if args.prefetch_siblings and not args.single_pass:
        parser.error("--prefetch-siblings requires --single-pass")
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
    instrumented = startup_diagnostics(instrument(source.read_text()))
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
    if args.recover_stable_child:
        hierarchy = copied / "AndroidHierarchy.java"
        hierarchy.write_text(recover_stable_child(hierarchy.read_text()))
        shutil.copyfile(args.experimental_source / "StableChildRecovery.java", copied / "StableChildRecovery.java")
    if args.prefetch_siblings:
        hierarchy=copied / "AndroidHierarchy.java"
        body=hierarchy.read_text()
        if body.count("node.getChild(index)") != (2 if args.recover_stable_child else 1):
            raise ValueError("Sibling prefetch source anchor changed")
        hierarchy.write_text(body.replace("node.getChild(index)","SiblingPrefetch.child(node,index)"))
        shutil.copyfile(args.experimental_source / "SiblingPrefetch.java",copied / "SiblingPrefetch.java")
    if args.retry_incomplete_checked:
        checks = copied / "SnapshotCapture.java"
        checks.write_text(retry_incomplete_checked(checks.read_text()))
    checks = copied / "SnapshotCapture.java"
    checks.write_text(mismatch_diagnostics(checks.read_text()))
    shutil.copyfile(args.experimental_source / "HierarchyDifference.java", copied / "HierarchyDifference.java")
    anchor = "        } catch (SnapshotCapture.Mismatch error) {\n"
    if instrumented.count(anchor) != 1:
        raise ValueError("Mismatch logger source anchor changed")
    instrumented = instrumented.replace(anchor, anchor + '            android.util.Log.i("EmuObservation", "mismatch " + error.diagnostic);\n')
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
               "numeric_hierarchy_timing": args.single_pass,
               "experimental_sibling_prefetch": args.prefetch_siblings,
               "experimental_stable_child_recovery": args.recover_stable_child,
               "hierarchy_retry_delay_ms": args.hierarchy_retry_delay_ms, "numeric_mismatch_diagnostics": True, "numeric_startup_diagnostics": True, "source_hashes": before,
               "built_source_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in copied.glob("*.java")},
               "bridge_sha256": hashlib.sha256(bridge.read_bytes()).hexdigest(),
               "instrumented_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    (args.output / "build.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"bridge_sha256": receipt["bridge_sha256"], "diagnostic_only": True}))

if __name__ == "__main__":
    main()
