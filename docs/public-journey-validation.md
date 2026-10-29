# Public navigation acceptance gate

Latest follow-up results and corrections are in
[the quote traversal and startup experiment](quote-prefetch-experiment.md).
The dated failed runs below remain historical evidence, not the current summary.

This is isolated engineering validation, not Stock production acceptance. No
account login, credential access, trading, production device binding, Scheduler
operation, or P30 command is part of this probe.

`scripts/probe_public_journey.py` runs against an already-owned `run_debug.py`
instance on `emulator-5576`. It uses the existing guarded native bridge with one
App launch, deterministic public controls, and three XML-to-bound-image pairs.
It preserves the original request and response of each step in private storage.
A timeout, ambiguous control, changed layout or failed guard stops the journey;
an uncertain input is never replayed. Readiness polling reads only, with eight
observations per expected page and a 600-second whole-probe bound. Cleanup is
required for a passing receipt.

The TDX journey enters public symbol `600999`, explicitly presses Search, selects
the exact matching result, opens 日K and closes only the previously verified
inline announcement if that exact layout is present. TDX draws its header in a
canvas: the resulting stock identity and chart date still require visual review.
The Junhong journey opens only the public 行情 tab. It does not navigate to 交易.
Neither journey can establish authenticated account-assets acceptance.

Example, using the local Kengent Python environment:

```sh
python scripts/probe_public_journey.py \
  --kengent-root /path/to/kengent \
  --adb /path/to/android-sdk/platform-tools/adb \
  --run-dir /private/current-owned-run \
  --artifacts /private/current-bridge-artifacts \
  --output /private/new-public-probe \
  --package com.tdx.AndroidNew
```

`--snapshot-seconds 90` is an explicit diagnostic comparison. The default is 30.
It changes only this probe's read-only snapshot RPC deadline. It does not change
input deadlines, frame freshness, sensitive-field checks, foreground checks,
production policy, or the original whole-test deadline. A longer RPC timeout is
not a bypass for a rejected snapshot. Session renewal is capped by that original
whole-test deadline.

## 2026-10-29 results

The same two-core ARM32 debug-symbol emulator, host GPU, unmodified APKs and
CheckJNI-enabled guest were used throughout. The private native bridge SHA-256
was `ad1d7100c04aa9365fe824f20b3305d5c1c856b4292cef0743f287a7bd3ab29f`.
The runner started at 03:38:35 and ended at 03:56:43, Asia/Shanghai. An App cold
start below means its process had been force-stopped; the later comparison did
not reboot Android or reset persistent App caches.

| Test | Outcome | Total including setup and cleanup |
| --- | --- | --- |
| TDX cold process, 30-second reads | Four successful loading-page observations; the next read timed out before search | 100.149 s |
| TDX warm homepage, 30-second reads | Search, code readback and exact result selection succeeded; first quote-tree read timed out | 129.238 s |
| TDX cold process, diagnostic 90-second reads | Home-tree read took 50.556 s; quote-tree read took 56.115 s; navigation reached 日K, but the first expected-frame image failed `snapshot_guard` | 247.819 s |
| Junhong cold process, diagnostic 90-second reads | Launch acknowledged; first public-home observation failed `snapshot_stability` | 94.203 s |

All four native sessions acknowledged cleanup. None passed the complete public
journey. The longer deadline demonstrated that two slow TDX reads eventually
return; it did not solve screenshot consistency and is **not** a deployed fix.
Successful manual/warm captures recorded earlier must not be represented as a
successful unattended cold-start journey.

Junhong's retained event log recorded an ANR at 03:54:48 while executing
`com.gtja.market.appwidget.AppwidgetUpdateService`. Its ActivityManager launch
record reported 79.945 seconds for the full chain and 63.804 seconds for
MainScreen. The retained crash buffer was empty; this is a guest App ANR, not
evidence of a new host-emulator crash. The stopped guest's retained `traces.txt`
contained the pushservice process but no exact main-process section, so it does
not establish the broker main-thread stack for this ANR. Do not substitute the
pushservice stack or an older JSON-parser trace as its current root cause.

The runner ended through its owned stop request after 1087.4 seconds. GDB and
emulator processes were absent, and ports 5576/5577 were free. The temporary raw
disk used for read-only ANR extraction was removed; raw evidence remains private.

31 repository tooling tests passed, including 10 new navigation tests. These
check exact layouts, ambiguous controls, wrong foreground/sensitive fields,
bounded loading reads, one-shot input, checked-frame failures and public-only
Junhong navigation. Unit-test success is not a substitute for the failed live
acceptance gate.

## Remaining work

1. Distinguish incomplete hierarchy, foreground transition, and before/after
   observation differences in the native failure diagnostics without returning
   private UI contents. The existing generic stability/guard codes do not prove
   which observation changed. In particular, a clock/layout change is a hypothesis,
   not the established cause of this failed image.
2. Address cold readiness and guest startup ANRs without disabling checks or
   reissuing uncertain physical actions, then repeat this same full journey.
3. Run complete funds and holdings collection through managed `tenant-app` with
   the trusted account Context and a separately verified test-device binding.
   This desktop session currently has neither that adapter nor a trusted request
   Context. Do not emulate either through shell account calls or credential files.

Production Stock tasks must remain on their existing binding until both public
navigation and managed complete-account capture pass.

## Explicit Junhong public-page probes

The default Junhong route remains the public market page. The optional
`--junhong-page` values are narrowly scoped:

- `search`: open the verified search control and enter public symbol 600999 once.
- `result`: require two identical observations of the exact 600999 / 招商证券 /
  沪A stock row and open it once; never press the adjacent add-watchlist icon.
- `search-quote`: perform the market, public search, verified stock-row and quote
  steps in one native session, then check three image pairs on the quote page.
- `quote`: inspect the already-open 600999 quote page. Only the fully matched
  first-use 五档/分时位置 layout prompt may be cancelled; unknown dialogs stop.

The quote-page gate requires the actual symbol, company name and 分时 label.
All successful routes still require three original-frame-bound image pairs;
none opens 交易, reads credentials, submits an order or verifies account assets.
A successful `search` receipt is search-page evidence, not a quote/account pass.

Navigation reuses its most recent verified market observation when the search
control is already present. It retains that original `frame_ref` for the usual
native action guard. If the public market is already selected, it does not
retap the bottom navigation or select the same market tab again. A missing
selector still requires bounded read-only readiness observations; native errors
terminate the session without replaying actions.

`trace_native_start.py` reports transport preparation, native-ready wait and
configuration reply durations without logging request/response bodies, identity
values or exceptions. It restores the wrapped transport on failure and
cancellation. The private bridge also timestamps fixed initialization phases.
These diagnostics do not change input, startup or lease deadlines.

### Startup and public-search results, 2026-10-29

Bridge SHA-256:
`bda4aadbd1f40469bd28879b8e8ba3810c22d06dde03460d7a7039fcb5b1804d`.
This build adds numeric startup tracing to the prior single-pass / 1000 ms
intra-request pause experiment. The unproven stable-child-recovery option was
not enabled. No emulator, App, signature or screenshot acceptance rule changed.

Five native starts completed in this run. Transport preparation took
8.910-13.416 seconds; native-ready waits took 4.737-5.965 seconds; configuration
replies took 49-64 ms. The previous intermittent initialization timeout did not
recur, so these measurements do **not** prove its cause or resolution. The fixed
native phase logs make a future recurrence distinguishable from page capture.

| Probe | Outcome | Total including cleanup |
| --- | --- | ---: |
| Search route before eliminating redundant market reads | Missing child on extra search-control observation; no search action attempted | 92.168 s |
| Reuse current selected market frame, then public 600999 search | Passed all three bound-image pairs | 66.557 s |
| Open verified stock result | Result tapped once; stopped at first-use layout prompt | 77.725 s |
| Read-only inspection of that exact layout prompt | One bound-image pair passed | 44.819 s |
| Cancel only that known prompt, then capture the stock quote | Quote identity/readiness passed; first image RPC hit 30-second deadline | 111.962 s |

The successful search images took 2.268, 2.716 and 2.421 seconds. Visual review
confirmed the official 600999 / 招商证券 / 沪A result, and the unchanged backend
accepted all six read/image receipts offline. This is a warm search-page result,
not a cold-start timing comparison, complete quote capture or account acceptance.
The test did not add the stock to a watchlist.

The layout prompt was separately inspected before any dismissal. It offered
五档在右边 / 五档在下边 with an explicit 取消 button. Only that full known layout
is permitted; the diagnostic cancelled it once and did not press confirmation,
buy, sell or cancel-order controls.

After dismissal, the actual quote tree contained 327 nodes. Its consecutive
single-pass walks took 18.745, 14.933 and 25.078 seconds. The stock identity and
分时 view were found, but the first checked-image request timed out at 30.030
seconds. No image from that timed-out request is accepted. A longer read-only
comparison remains unverified; do not describe the quote page as stable merely
because the simpler search page passed.

All five native sessions confirmed cleanup. The retained crash buffer was
empty and the event log had no crash or ANR events. The explicit emulator stop
ended the runner after 1195.22 seconds with exit -10; its owned PID was absent
and ports 5576/5577 were free. P30, production bindings, Apps and Scheduler were
untouched. Sixty repository tests passed.

Authenticated account acceptance remains blocked by the missing trusted
managed entry: the host's `/v1/auth/me` still returns 401 and this desktop
provides no managed App tool. Existing broker-login permission is preserved,
but cannot replace authenticated tenant/workgroup context. Complete funds and
holdings must be validated through that entry before any Stock cutover.
