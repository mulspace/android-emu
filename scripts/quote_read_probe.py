"""Opt-in private bridge transform and receipt checks; never production routing."""
CONTRACT = 'junhong-time-v1'
PACKAGE = 'com.guotai.dazhihui'
SYMBOL = '600999'
NAME = '招商证券'


def instrument_quote_read(source):
    replacements = [
        ('    private static JSONObject snapshot(JSONObject args) throws Exception {', '''    private static JSONObject snapshot(JSONObject args) throws Exception {
        boolean quoteRead = args.has("read_only_quote");
        if (quoteRead) {
            // Consume all older input authority before inspecting or capturing.
            frame = null; frameAt = 0; frameObservation = null;
            if (args.length() != 6 || !args.getBoolean("include_image") || !args.getBoolean("include_xml")
                    || !"jpeg".equals(args.getString("image_format"))
                    || !"junhong-time-v1".equals(args.getString("read_only_quote"))
                    || args.has("expected_frame_ref") || args.has("retain_history") || args.has("defer_history"))
                throw new IllegalArgumentException();
            args.getString("quote_symbol"); args.getString("quote_name");
        }'''),
        ('JSONObject result = captureSnapshot(args, true);',
         'JSONObject result = captureSnapshot(args, !quoteRead);\n        if (quoteRead) result.remove("history_image_size");'),
        ('        final long snapshotStarted = SystemClock.elapsedRealtime();', '''        final boolean quoteRead = args.has("read_only_quote");
        final String quoteSymbol = quoteRead ? args.getString("quote_symbol") : null;
        final String quoteName = quoteRead ? args.getString("quote_name") : null;
        final long snapshotStarted = SystemClock.elapsedRealtime();'''),
        ('                image = SnapshotCapture.stable(new SnapshotCapture.Port<Bitmap>() {',
         '                SnapshotCapture.Port<Bitmap> capturePort = new SnapshotCapture.Port<Bitmap>() {'),
        ('                }, expected);', '''                };
                if (quoteRead) {
                    image = ReadOnlyQuote.capture(new ReadOnlyQuote.Port<Bitmap>() {
                        public ReadOnlyQuote.State observe() throws Exception {
                            SnapshotCapture.Observation observation = capturePort.observe();
                            return new ReadOnlyQuote.State(observation.surface, observation.hierarchy, observation.sensitive);
                        }
                        public Bitmap capture() throws Exception { return capturePort.capture(); }
                        public void discard(Bitmap image) { capturePort.discard(image); }
                    }, quoteSymbol, quoteName);
                } else image = SnapshotCapture.stable(capturePort, expected);'''),
        ('            if (expectedFrame != null) result.put("based_on_frame_ref", expectedFrame);', '''            if (quoteRead) result.put("read_only_quote_proof", new JSONObject()
                    .put("schema", 1).put("contract", "junhong-time-v1")
                    .put("symbol", quoteSymbol).put("name", quoteName).put("period", "分时")
                    .put("input_authority", false).put("xml_values_atomic", false));
            if (expectedFrame != null) result.put("based_on_frame_ref", expectedFrame);'''),
    ]
    for old,new in replacements:
        if source.count(old) != 1:
            raise ValueError('Read-only quote bridge source changed; inspect before rebuilding')
        source = source.replace(old,new)
    return source


def options():
    return {'include_image': True, 'include_xml': True, 'image_format': 'jpeg',
            'read_only_quote': CONTRACT, 'quote_symbol': SYMBOL, 'quote_name': NAME}


def validate_receipt(receipt):
    proof = receipt.get('read_only_quote_proof')
    expected = {'schema': 1, 'contract': CONTRACT, 'symbol': SYMBOL, 'name': NAME,
                'period': '分时', 'input_authority': False, 'xml_values_atomic': False}
    if (proof != expected or type(proof.get('schema')) is not int
            or proof.get('input_authority') is not False or proof.get('xml_values_atomic') is not False
            or receipt.get('foreground_package') != PACKAGE
            or (receipt.get('width'), receipt.get('height'), receipt.get('rotation')) != (720, 1560, 0)
            or 'based_on_frame_ref' in receipt):
        raise ValueError('Missing or invalid read-only public quote proof')


async def verify_input_denial(call, frame_ref):
    # Negative coordinates independently prohibit a physical tap even if an
    # input-authority regression occurs. Only the EARLIER identity refusal counts.
    try:
        await call("android.tap", {"arguments": {"frame_ref": frame_ref, "x": -1.0, "y": -1.0}})
    except Exception as error:
        diagnostic = getattr(error, "native_diagnostic", None)
        if (isinstance(diagnostic, dict) and diagnostic.get("phase") == "observation_identity"
                and diagnostic.get("exception_type") == "IllegalStateException"):
            return True
        raise ValueError("Read-only input-authority rejection was not verified") from None
    raise ValueError("Read-only image unexpectedly authorized an input request")
