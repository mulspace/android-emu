# ARM32 translation-cache diagnostics

## Scope and reproducibility

These are isolated current-host engineering tests, not a Stock cutover. They use
an unchanged symbol-bearing ARM32 engine, two guest CPUs, host CPUs 14/15, host
GLES, 1536 MiB guest RAM and official App packages. No account, trade, P30,
production binding, service reload or Scheduler operation is part of this work.

Engine SHA-256:
`fbc831874f717dddcb21eb87899523f49f6fc0ddd7d078c778c9beba877faa11`.

The source contains a 32 MiB static-buffer constant, but its system-mode dynamic
allocator uses `ram_size / 4` when no size is supplied. Read-only `info jit`
confirmed 402,571,219 usable bytes with the original command and 805,224,403 bytes
with `-tb-size 768`. Do not report the source constant as the actual default.

The new runner options are opt-in. The default command and JNI checks remain
unchanged. The monitor is a Unix socket in the private run directory, not a TCP
listener. Its reader checks the owned process identity and allows only fixed JIT
statistics, with a deadline and bounded response. Neither option changes ARM
instruction, MMU, guest-clock, APK or App authentication semantics.

## 2026-10-29: initial cache comparison

| Observation | Original dynamic cache | Explicit 768 MiB |
| --- | ---: | ---: |
| Usable code capacity | 402,571,219 bytes | 805,224,403 bytes |
| Flushes at recorded boot checkpoint | 4 | 2 |
| First Junhong public-start receipt | 89.447 s | 72.667 s |
| Guest MainScreen full display event | 70.743 s | 62.867 s |
| Flushes at first homepage checkpoint | 9 | 3 |
| First strict navigation attempt | Foreground rejected due to ANR | Entered page, then read exceeded 30 s |

Each column is a single process-start comparison, not a statistically controlled
benchmark. Sequential runs reuse the isolated guest disk and have different
Android/App/network/cache state. The boot wait helpers were started at different
offsets and their durations must not be compared as full boot times. Guest
`boot_progress_enable_screen` was 54.739 s versus 55.035 s. The extra JIT reads
also take a small lock briefly. Lower flush counts do not alone prove better
collection performance or explain all ANRs.

With 768 MiB and a diagnostic-only 90 s read deadline:

* Junhong's initial public page produced one accepted checked screenshot. The
  second pair failed `snapshot_changed_before_capture`. Total diagnostic time
  was 65.141 s. The real quote date/account state was not verified by this page.
* Tongdaxin reached the exact 600999 search result and daily chart. Two checked
  captures succeeded in 23.291 s and 16.954 s; the third failed the same strict
  mismatch check. The first chart readiness read took 42.594 s; total journey
  time was 230.871 s. Visual review identified 招商证券 / 600999 and the chart's
  latest displayed date 2026/10/28. At the 2026/10/29 early-morning test time this
  is prior-session data, not a live intraday quote.
* A later Junhong process restart again showed an Android ANR window. Its public
  prewarm timed out; the subsequent diagnostic read rejected that foreground.
  Larger cache therefore does not resolve App stability.

The 90 s allowance exists only in the diagnostic script. Input freshness,
foreground boundaries, sensitive-input checks and exact before/after hierarchy
matching were unchanged. There is no production timeout increase or automatic
retry of an uncertain input action.

## Public market navigation correction

The bottom Junhong 行情 tab initially opens 自选 with recommendation cards.
The test now also selects the exact observed `tv_free_stock_market` top tab,
then checks that tab is selected. It does not enter 开户/交易 or change self-selected
stocks. A selected top tab is not clicked again. The initial live attempt with
this corrected journey was blocked by the startup ANR before reaching the tab;
unit coverage is not a successful live-market acceptance result.

## Remaining observation questions

Numerical single-pass diagnostics still show expensive hierarchy reads: 227 nodes
needed 10.582 s during the first Junhong read, and 486 nodes needed 16.214 s while
the market page was loading; a later warm read of those 486 nodes took 4.494 s.
The emulator/cache state and App readiness both matter.

Offline adjacent accepted/observed receipts also reveal UI volatility:

* Junhong changed the `scrollable` attribute of `rv_market_index` between two
  recorded observations.
* Tongdaxin's second accepted hierarchy and third observation were byte-identical.
  The later rejected pre-capture tree was not retained, so its exact difference
  is still unknown. The captured system clock has both text `5:24` and an
  accessibility description `5:24 AM`. The existing clock-only diagnostic
  normalizes only the text, so it cannot classify a simultaneous description
  change as clock-only. This is a diagnostic limitation, not proof that the
  actual rejection was solely the clock.

Do not remove hierarchy or sensitivity checks to hide these failures. A future
change needs explicit, privacy-preserving difference evidence and tests that
continue rejecting meaningful UI changes. No account-assets or complete holdings
capture has passed, and Stock tasks remain on their prior devices.

Raw logs, screenshots, monitor receipts and App state remain in the private local
workspace and are excluded from Git. The first two owned emulator instances were
stopped; their runners recorded exit -10 after an emulator-console kill request,
with PID disappearance and both test ports released. This is verified cleanup,
not a claim of a normal guest exit or a spontaneous engine crash.

## JNI diagnostic and standard Android compilation

A third isolated run combined the same 768 MiB cache with upstream `-no-jni`.
Kernel logs show `android.checkjni=1` in the first two runs and no forced check
flag in the third; the two related guest properties were empty in the third run.
This concerns Android runtime debug checks, not an App security/authentication
check. The runner default is unchanged.

The initial Junhong startup receipt was 73.342 s, with a 62.099 s full MainScreen
Android event. The subsequent strict public read rejected the foreground after
40.710 s; this setting therefore did not establish usable collection.

The isolated package then underwent the standard command
`cmd package compile -m speed -f com.guotai.dazhihui`. It completed in 9.425 s.
Package Manager reported `compilation_filter=speed, status=kOatUpToDate`.
The 113,501,807-byte installed APK was streamed to a private temporary file for
SHA-256 verification before and after, because this API24 image lacks a
`sha256sum` shell command. Both hashes were
`2c7e087cdc2ea006e36d9ba5bd60db2485eb6e185d311f17b17b2016c32bf9ac`.
The temporary copies were removed. No profile clear, App-data reset, APK patch,
signature change or account operation occurred. The earlier missing-hash-tool
attempt stopped before issuing any compilation command.

The journey helper now supports a shorter whole-test deadline (`--seconds 180`
or `300`, default `600`), with its existing bounded session cleanup. Session TTL
renewals are capped by that same deadline, and input/capture checks are unchanged.

After compilation, Junhong's public-start receipt was 76.326 s, followed by a
44.193 s strict-read failure. The foreground was positively identified as
`Application Not Responding: com.guotai.dazhihui`. Thus standard package AOT did
not fix the observed condition either. No unknown dialog was dismissed.

The fresh main-process ANR dump at 05:41:13 confirms **CheckJNI is off**. The main
thread was Runnable in `NativeAllocationRegistry` / `Paint` / `EdgeEffect`,
then `GridView` construction and repeated `LayoutInflater` calls inside
`NewsInfoFlowFragment.onCreateView`. Its cumulative guest scheduler statistics
show about 6.038 s running and 17.305 s queued. These are cumulative guest-thread
measurements, not a timed proof of one lock deadlock or the entire startup cost.
The guest logcat crash buffer was empty. This directs the next investigation toward
execution throughput and guest scheduling during UI construction, rather than
assuming APK compilation or JNI checks alone solve the ANR.

Repository verification: 40 bounded unit tests pass, including fixed QMP commands,
cache option placement/bounds, complete metrics, exact public-page selection,
no repeated selected-tab action, and unchanged strict screenshot-pair checks.
No new emulator binary or production Resource Node build was deployed in this
comparison. The existing debug engine and private single-pass capture candidate
were reused; the compiled App cache persists only inside the isolated AVD.

The third owned instance was also stopped and its PID/ports were verified released.
