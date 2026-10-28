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
