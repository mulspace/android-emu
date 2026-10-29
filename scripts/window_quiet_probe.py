"""Optional read-only transition scheduling; does not relax capture checks."""
def instrument_window_quiet(source):
    anchor = '        JSONObject result = captureSnapshot(args, true);'
    replacement = '        if (args.has("wait_window_quiet")) {\n            if (!"tdx-chart-v1".equals(args.getString("wait_window_quiet"))\n                    || args.length() != 3 || args.getBoolean("include_image")\n                    || !args.getBoolean("include_xml") || packages.size()!=1\n                    || !packages.contains("com.tdx.AndroidNew")) throw new IllegalArgumentException();\n            frame=null; frameAt=0; frameObservation=null;\n            long quietElapsed=AndroidWindowQuiet.await(automation, ResourceDeviceBridge::alive);\n            android.util.Log.i("EmuWindowQuiet", "elapsed_ms="+quietElapsed);\n        }\n        JSONObject result = captureSnapshot(args, true);'
    if source.count(anchor)!=1:
        raise ValueError('Window quiet bridge source changed')
    return source.replace(anchor,replacement)
