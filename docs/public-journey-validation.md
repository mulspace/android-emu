# Public navigation acceptance gate

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
