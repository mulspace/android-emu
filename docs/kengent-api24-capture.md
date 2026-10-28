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
