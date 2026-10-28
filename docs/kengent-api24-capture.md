# Kengent capture bridge on the isolated API 24 guest

This is an integration candidate, not a production cutover. The emulator engine
and renderer are unchanged from the dual-CPU experiment. No physical device,
production binding, schedule, account input or App service reload was used.

## Confirmed integration gaps and fixes

- D8 was configured for API 26. The bridge now builds API 24 DEX (037), with the
  minimum API in its cache identity so an older incompatible artifact is not reused.
- API 24/25 obtain the ActivityManager Binder through
  `ActivityManagerNative.getDefault()`. API 26+ retain `ActivityManager.getService()`.
  The exact Binder method, package guard and one-attempt launch/stop remain intact.
- Android 7 toybox lacks `sha256sum`. The fallback reads back the bounded JAR and
  computes SHA-256 on the host. It never trusts SHA-1, a filename or upload success.
  Corrupt bytes and readback timeouts still fail closed.
- The UiAutomator constructor creates Android 7 ClipboardManager, which creates
  a Handler on its calling thread. Initializing it on the stdio worker failed with
  `Can't create handler inside thread that has not called Looper.prepare()`.
  Initialization is now posted once to the existing main Looper, with a five-second
  bound and cancellation of queued work. It does not create an unpumped Looper,
  repeat a physical action or suppress the exception.

The Binder definitions were checked against AOSP Android 7 sources:
[IActivityManager](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-7.0.0_r1/core/java/android/app/IActivityManager.java),
[ActivityManagerNative](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-7.0.0_r1/core/java/android/app/ActivityManagerNative.java).
The ClipboardManager failure was confirmed from a private initialization-only
stack trace. The diagnostic stack logger is excluded from this patch.

## Validation and current limits

298 distinct focused tests passed: launch/stop contracts (195), artifact build,
readback, Android sessions and snapshot guards (99), and main-loop initialization
cancellation/no-replay (4). The real D8 build produced DEX 037.

The first corrected live bridge run returned Tongdaxin's public market screenshot
and hierarchy in 5.685 seconds. Native timings were guard-before 3057 ms, image
capture 153 ms, guard-after 1842 ms, encoding 370 ms. These measurements cover one
sample, not trading-date freshness or stable account capture. Session cleanup
was acknowledged. The next run reached readiness but its first snapshot exceeded
the unchanged eight-second RPC bound; cleanup was again acknowledged. Consequently
repeatable unattended collection has NOT passed.

The test transport explicitly extended only ADB shell deadlines to 30 seconds.
Default identity probing still fails its eight-second bound: secure Android ID
reading took about 7.0 seconds and package listing about 3.7 seconds. Startup with
identity checks, artifact verification and bridge readiness took roughly 26 seconds.
The patch does not silently extend production timeouts. Emulator clone identities
must also be reviewed before registration; the factory serial is not clone-unique.

A final broker public-page probe reached bridge readiness in 24.236 seconds,
but snapshot acquisition failed at `snapshot_foreground` with SecurityException.
An independent local screen capture then showed Junhong's **Application Not
Responding** system dialog over its home screen. This was a correct foreground
boundary rejection, not complete broker collection. No dialog was clicked and
no credentials were entered. The 1770.53-second run was stopped through its owned
stop request; both GDB/emulator PIDs and dedicated ports were verified released.
The next diagnosis should inspect the retained guest ANR trace and startup costs,
rather than relaxing foreground checks or treating a launch command as readiness.

## Patch ownership

[integration/kengent-api24.patch](../integration/kengent-api24.patch) contains only
this integration change and tests, against Kengent commit
`ebe00ea8efa48b375cc836333b9ee76a60c9b96e`. A clean-base apply check passed.
The corresponding Kengent working files are updated locally. Other uncommitted
Kengent work (including newer snapshot/readiness handling used by the live
candidate) is intentionally excluded. Clean-base patch application is not evidence
that those other changes were deployed or that this patch alone passes live acceptance.
Do not automatically deploy this patch or switch device bindings.

Raw logs, APKs, JARs, user data and screenshots remain in private local test storage.

## Offline ANR evidence

A read-only raw copy of the stopped test userdata was inspected with debugfs.
The preserved ANR reason was execution of Junhong AppwidgetUpdateService. Its
main-thread stack was runnable in JSONTokener/JSONArray while loading the home
navigation menu, not blocked in a network read or monitor. Main-thread schedstat
showed about 8.05 seconds running and 31.80 seconds queued since thread creation;
these are cumulative counters, not the duration of this single method.
During the 14.2-second system sampling interval, Junhong used 41% guest CPU,
background Tongdaxin 25%, and system_server 18%. This supports testing background
competition, but does not yet establish a causal speedup. The raw disk, dropbox
report and traces remain private and were not committed.

## Single-App public capture comparison

A subsequent 600.21-second run explicitly stopped both test Apps and launched
Junhong once. A process check found no Tongdaxin process. The public home screen
rendered; retained events showed a System UI boot ANR but no Junhong ANR in that
sample. MainScreen Activity timing was 61.629 seconds (92.610 seconds for the
complete launch chain), so this does not establish faster cold startup.

An early bridge probe and a second probe after the home screen appeared still
returned an absent accessibility root. The system's separate `uiautomator dump`
then returned 71 compressed nodes, all belonging to Junhong, proving that the
public tree was available through the platform path. Two seconds of diagnostic
post-initialization waiting alone did not pass the normal eight-second RPC bound.

With that same two-second wait and a **diagnostic-only 30-second RPC deadline**,
the unchanged validation path returned the actual public home screenshot and
hierarchy in 10.830 seconds. Native timings: guard-before 6630 ms, capture 122 ms,
guard-after 3511 ms, encoding 266 ms, total 10604 ms. The ADB shell timeout was
also extended to 30 seconds only in this private probe, as documented above.
No foreground, sensitive-field, nonce or response check was removed. Cleanup was
acknowledged. This demonstrates one valid response beyond the existing deadline;
it does not prove three repeatable captures, authenticated assets collection,
or a suitable production latency policy. No default timeout has been changed.

Next work: make cold readiness and emulator-specific bounded read timeouts
explicit, profile redundant observation work without weakening guards, then
repeat public captures before an authorized managed funds/holdings test.

## Explicit emulator read profile and repeat-capture experiment

The follow-up candidate adds an opt-in `android_timing_profiles` map to the host
configuration. Only exact `emulator-NNNN[N]` locators accept `arm-emulator`:
identity reads and snapshot RPCs are bounded at 30 seconds, and initialization
settles for two seconds. The default profile retains eight-second reads. Tap,
text, credential and App-launch RPC deadlines remain eight seconds. This profile
does not extend a ResourceNode lease/request or relax foreground, sensitive-input,
frame-age, nonce, response or cleanup guards. No live host configuration was changed.

Slow pre-capture work exposed another protocol mismatch: the guest could return
`capture_delay_ms > 5000`, which the real backend correctly rejects. The candidate
caps that conservative lower bound at 5000, without discounting post-capture work.
Full diagnostic durations remain separate, bounded by the observed call and
30 seconds. Previously successful raw bridge responses alone were therefore not
sufficient evidence of backend acceptance.

The private candidate JAR SHA-256 is
`e7454dc063f6997916d95e904c141953ddc1d061557375910ef01e89ef7ae119`
(DEX 037). One 1500-second isolated dual-CPU run produced:

| Case | Result | Per-snapshot wall seconds |
| --- | --- | --- |
| Initial Junhong connection | First root missing; stopped and cleanup acknowledged | Failed |
| System `uiautomator dump` comparison | Public tree available | Diagnostic only |
| Junhong home, one session | Three captures passed | 9.651, 8.674, 8.651 |
| Junhong home, fresh connection | Three captures passed | 10.005, 8.285, 6.579 |
| TDX public market, broker stopped | Three captures passed | 6.064, 6.066, 4.426 |
| TDX settled search page | Two captures passed | 3.771, 3.731 |
| TDX market to search | Tap acknowledged, immediate next snapshot rejected an incomplete sensitive-field tree | Transition not passed |

The eleven successful home/market/search wire receipts were replayed through the actual
`AndroidBackend.execute` protocol, hierarchy, sensitive-field, image and public
schema checks, with a retained-byte-only transport and synthetic offline context.
All eleven passed. This offline validation performs no ADB operation, network call,
credential access or platform upload; it is not an authenticated end-to-end run.
Live session startup still took about 25–31 seconds. An additional market read
before navigation took 18.126 seconds, so the lower steady-state timings are not
a guaranteed latency bound. The first navigation probe used invalid pixel
coordinates and was rejected before input; the corrected normalized-coordinate
probe used a new observation and sent one tap. No uncertain input was replayed.

125 focused Kengent regression tests passed, including exact-locator policy,
host configuration validation, unchanged physical/credential deadlines, device
discovery, sessions and snapshot guards. The capture probe also tests refusal of
physical, ended, mismatched-port/AVD, absent-process and invalid-PID runs.

The incremental patch is
[`kengent-arm-emulator-timing.patch`](../integration/kengent-arm-emulator-timing.patch).
It applies on the local API24 + snapshot-diagnostics candidate, **not a clean
Kengent HEAD by itself**. Its exact pre/post source hashes are recorded in
[`kengent-arm-emulator-timing.sources.json`](../integration/kengent-arm-emulator-timing.sources.json).
An apply check against the recorded preimage passed. Unrelated Kengent work is
excluded. The candidate remains undeployed.

Reproduction helpers:

- `scripts/probe_public_capture.py`: read-only captures on a live, explicitly owned
  diagnostic GDB/AVD run. It checks the exact port and isolated AVD, saves original
  wire receipts privately, and requires native cleanup acknowledgement.
- `scripts/validate_capture_receipts.py`: offline backend replay using the Kengent
  Python environment. It cannot operate a device or upload an artifact.

These results establish repeatable public-page captures in two warm Junhong
connections and one TDX connection, not stable cold-start collection or authenticated
funds/full holdings. Page-transition readiness, cold latency, clone-unique identity,
and the managed account adapter/current Context remain unresolved. P30, production
bindings, Scheduler and services remain untouched; Stock must not be switched yet.

A subsequent public-symbol text operation returned IllegalStateException after a
valid search-page capture. The operation was not replayed; its outcome remains
unconfirmed pending a focused input-adapter diagnosis. This is another open
end-to-end navigation requirement, separate from the read-only capture successes.

The test runner received SIGTERM at 1364.22 seconds, before its 1500-second cap.
Its finally path stopped the owned GDB/emulator group (GDB exit 0); process and
ports 5576/5577 were verified released. This was an interrupted diagnostic run,
not proof of an emulator crash or a completed full acceptance test. A later public
history-navigation attempt was refused by the ended-run guard before device IO.

## Android 7 input focus and complete-tree capture

The public TDX symbol entry failure was localized without logging input contents:
the global accessibility focus was absent, while the active window returned a
focused editable node. The API 24/25 candidate now falls back to that window's
focus only when global focus is null. Both the root and field must belong to the
package from the current observation. Existing focused/editable/password checks,
single-use observation, deadlines and input confirmation remain unchanged. It
does not choose an arbitrary text field, change focus or replay an uncertain input.

Hint-text methods were added in Android API 26. The candidate isolates these in
an API 26 helper; Android 7 preserves existing text rather than guessing whether
it is a placeholder. Tests run against a legacy stub that lacks those methods.
See the [Android AccessibilityNodeInfo reference](https://developer.android.com/reference/android/view/accessibility/AccessibilityNodeInfo#isShowingHintText()).

During page transitions, missing roots/children now have a distinct incomplete
hierarchy result. Fresh read-only snapshots may re-read at most three times in
the original request. Any captured image is discarded before retrying. Sensitive
fields, denied packages, arbitrary errors and expected-frame input checks do not
retry. Native diagnostics contain fixed operation phases and exception types,
never input values or exception messages. Accepted-attempt timing counters reset
after a discarded attempt; total duration still includes all work.

The incremental candidate is
[`kengent-api24-input-readiness.patch`](../integration/kengent-api24-input-readiness.patch),
with exact pre/post hashes in its `.sources.json` file. It applies on the previous
documented timing candidate and local snapshot implementation, not clean Kengent
HEAD alone. A preimage apply check passed. Private diagnostic logging and unrelated
Kengent edits are excluded; no production service or binding has been changed.

Live results on the isolated ARM32 two-core guest (default JNI checks):

| Case | Result | Snapshot wall seconds |
| --- | --- | --- |
| Window-focus text input | One `600999` operation acknowledged and read back; exact 招商证券 search result | 3.578, 2.736 |
| Search result to quote | One tap acknowledged; immediate snapshot exceeded 30 seconds; tap was not replayed | Transition timeout |
| Settled quote/daily K with final candidate | Three consecutive guarded captures, cleanup acknowledged | 13.694, 9.057, 4.882 |

The retained daily chart shows code 600999, a selected 日K tab, candles through
2026-10-28, volume and MACD. It is overnight historical-market evidence, not a
claim of a new trading-day live price. The five successful search/daily wire
receipts passed the actual AndroidBackend's offline protocol, hierarchy,
sensitive-field and image checks. No device or network access occurs in replay.
The final DEX 037 bridge SHA-256 is
`9141326bf5e0984aaa9ce39a59dc735d680e56e0ef3033ed93d4452ae8b92e4a`.

119 focused regression tests passed. The 1456.48-second diagnostic run ended via
its owned stop request (exit 0); both owned emulator/debugger processes and ports
5576/5577 were verified released. Raw logs, screenshots and JARs stay private.

Cold readiness and immediate page transitions still require validation. This
does not establish authenticated broker assets/complete holdings or authorize
Stock cutover. P30 remains outside the test scope.

## Cold-start timing and cleanup acknowledgement

A separate 621.32-second run used the same final bridge and two-core guest,
stopped both test Apps, and launched Junhong exactly once. Android boot completed
in 74.457 seconds. The broker process started at 02:10:36.550; ActivityManager
reported MainScreen displayed at 02:12:09.867: 65.163 seconds for that Activity,
93.503 seconds for the full launch chain. The initial guarded snapshot ran before
that completion and exhausted the incomplete-tree read attempts. A later system
screen showed the rendered public homepage. The captured ANR event buffer
contained no `am_anr` record; this does not prove long-duration stability.

A subsequent read-only root diagnostic found four valid roots (438, 278, 300,
199 ms). Its null-root/window-query branch did not execute; window flags are not
claimed as a fix. No system `uiautomator dump` was used to prime this run.
With the final non-diagnostic bridge, three new public homepage captures passed
in 13.027, 6.249 and 4.841 seconds, with cleanup acknowledged. All three original
wire receipts also passed offline AndroidBackend validation. No host crash,
account input, physical-device operation or production change was made.

The failed cold probe's normal cleanup exceeded its six-second helper deadline.
Its receipt deliberately remains failed/unconfirmed. A separate diagnostic used
the **same nonce**, extended only cleanup waiting to 30 seconds, and obtained the
exact close acknowledgement; the original generation was not replayed. The
24.465-second total includes identity and artifact verification, not just the
cleanup helper. An opt-in emulator profile now allows that 30-second cleanup
wait. Physical/standard profiles retain six seconds; input/credential RPCs retain
eight seconds. Pending cleanup continues to hold the generation until the exact
nonce acknowledgement; no force-kill fallback or automatic input retry was added.

[`kengent-arm-emulator-cleanup.patch`](../integration/kengent-arm-emulator-cleanup.patch)
and its source hashes record the incremental fix. Its preimage apply check and
87 focused timing/session regression tests passed. The later final-candidate
capture session completed cleanup normally under this profile. Both the debugger
and emulator exited with the owned stop request, and dedicated ports were checked
free. Evidence and bridge artifacts remain private.

Current acceptance: TDX symbol entry and dated daily chart plus repeatable warm
Junhong homepage captures pass. The cold startup observation is a measured
remaining limitation, not a completed cold-start adapter fix. Generic launch
acknowledgement/foreground matching must not be treated as broker homepage or
account readiness. Authenticated funds and complete holdings remain untested:
this terminal has no managed tenant-app adapter/current request Context. Existing
login consent does not supply that missing trusted transport. Do not switch Stock
to this emulator until the real managed account acceptance succeeds.

## Native cold launch, strict capture and remaining broker ANR

The next isolated run exercised `android.start_app` rather than preparing the
screen with a separate launcher. The original bridge submitted one Junhong launch
but failed `foreground_confirmation` at its three-second bound; its generation
was cleaned up and that request was not replayed.

The opt-in emulator candidate now awaits only foreground confirmation for up to
120 seconds after the same one launch, with a 125-second RPC bound. The standard
profile retains three-second confirmation/eight-second RPC limits. Tap, text and
credential RPCs remain at eight seconds. A pure confirmation helper has no launch
or input primitive and checks the original session fence before/after observations.
Its tests cover a 93.5-second synthetic startup, timeout, cancellation, a denied
read, another foreground package and a late response after its deadline.

Stock's typed `DeviceSession` now supplies an explicit 180-second platform budget
only for `android.start_app`, with a 190-second caller bound; otherwise its former
45-second caller bound remains. This prevents the platform's default 60 seconds
or App's default 45 seconds from silently defeating the explicit emulator setting.
The original context deadline, lease, cancellation and single-intent key still
apply. No live App service, configuration, binding or schedule was changed.

215 Python/JVM focused cases and all 20 Rust `device_targets` cases passed. The
incremental patch/source hashes are
[`kengent-arm-emulator-launch.patch`](../integration/kengent-arm-emulator-launch.patch).
Its exact-preimage apply check passed. The live candidate bridge SHA-256 was
`ad1d7100c04aa9365fe824f20b3305d5c1c856b4292cef0743f287a7bd3ab29f`.

The corrected launch acknowledged in 13.316 seconds. The immediately following
snapshot still exceeded 30 seconds. A later strict observe-then-image probe was
correctly rejected because Android's Junhong ANR dialog was in front. Event logs
recorded `AppwidgetUpdateService` ANR at 02:30:53. The retained main-thread stack
was in `BinderProxy.transactNative -> sendAccessibilityEvent` during fragment
layout. Process-cumulative counters showed about 10.88 seconds executing, 24.95
seconds queued and 49.46 seconds aggregate JIT compilation work. Those counters
do not by themselves prove the cause or the duration of the blocked Binder call.

The guest's supported `cmd package compile -m speed -f com.guotai.dazhihui`
returned Success in 14.689 seconds. This is normal Android compilation of caches,
not an APK/signature change or disabled app check; see the
[AOSP Android 7 JIT/compilation guide](https://android.googlesource.com/platform/docs/source.android.com/+/4a5bcd6fa800faafbe7272d39266e21dc26edf39/en/devices/tech/dalvik/jit-compiler.html).
The subsequent separate launch acknowledged in 16.121 seconds, but the snapshot
again timed out and a second service ANR appeared at 02:40:07. Precompilation did
**not** pass acceptance. The final trace copy lacked the broker's own section;
the second ANR is supported by its event and screenshot, not a complete second
broker stack. The isolated AVD now contains this speed-mode cache experiment.

This 1185.42-second run ended via its owned stop request, exit 0. Debugger,
emulator, test processes and dedicated ports were checked released. Private
screens/ANR traces were not committed. No ANR dialog was clicked or bypassed.

Next evidence needed: compare cold startup without an attached UiAutomation
until the public main page is displayed, then use Stock's strict XML-observation
plus `expected_frame_ref` image path. The repeated ANR while accessibility was
attached is a hypothesis to test, not an established causal diagnosis. Warm
unbound screenshots alone remain insufficient. Full managed funds/holdings and
production Stock replacement have still not passed.
