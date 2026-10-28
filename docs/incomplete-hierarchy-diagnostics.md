# Incomplete accessibility-tree investigation

This is isolated engineering work on the owned ARM32 diagnostic AVD, not a
production Stock deployment. The public-market probes never open trading,
enter credentials, invoke the Scheduler or operate P30.

## Numeric mismatch diagnostics

`build_observation_probe.py` instruments the copied native bridge to report
counts of changed text/description/bounds/identity/flags and tree topology.
It emits no attribute values, account fields or arbitrary attribute names.
Sensitive observations report only a fixed sensitive flag. These diagnostics
never participate in acceptance: the original exact-frame and before/after
checks still reject every mismatch. The clock classification is diagnostic,
not permission to ignore clock or App changes.

Build SHA-256:
`26fce540cb321e45a4ae75b860b4982b04592a24616e0c0dc8fb1a72760d8db4`.

Two real Junhong probes on 2026-10-29 failed for absent nodes, before a mismatch
classification could be exercised:

| Probe | Successful bound images | Image latency | Outcome |
| --- | ---: | --- | --- |
| Cold public navigation | 1 | 25.255 s | Next checked capture rejected an incomplete tree; 156.160 s total |
| New session on warm public market | 3 | 8.633 / 6.282 / 4.611 s | Fourth checked capture rejected an incomplete tree; 88.905 s total |

Both native sessions acknowledged cleanup. The unchanged backend accepted the
seven successful warm read/image receipts in an offline check, but the whole
probe correctly remained failed. The retained crash buffer was empty. The
emulator was explicitly stopped; its recorded exit was -10 and owned PID and
ports were released. A single warm sequence is not a cold-start benchmark or
proof of authenticated account collection.

Missing nodes occurred around traversal depth 17-19. Some parent refreshes
failed; others succeeded with the same child count. Matching counts alone do
not prove unchanged child identities or safe recovery. The walker still scans
invisible descendants for visible sensitive inputs; none may be skipped to
make this probe pass.

## One-child recovery candidate

`--recover-stable-child` requires `--single-pass` and is off by default. On one
missing child it records the cached parent state, refreshes that parent and
compares every serialized parent attribute, visibility/input type, window and
source node ID, child count, and the ordered IDs of **all** children. Only an
identical state permits one read of the original child index. A failed refresh,
changed identity/order/value or another absent child rejects that traversal.
The recovered child must still undergo the complete traversal and original
frame checks. There are no synthetic nodes, partial scans or input retries.
Cancellation/expiry checks remain in the request. Fixed diagnostic result codes
are: 1 missing state; 2 failed refresh; 3 changed parent; 4 child still missing;
5 child returned. Private raw records stay outside Git.

The candidate copies upstream source into a private build directory and refuses
ambiguous source transformation anchors. It does not edit Kengent source or
publish an APK. Its bridge SHA-256 is:
`9f0bdc8429ada9ac88b5c3810ea36b9e65dcf0ff5c22b5eb1567a7f56b885b20`.

Validation: 51 repository tests passed, including 11 numeric-difference JVM
cases and 11 stable-child recovery cases. The generated capture implementation
also passed 10 original-frame guard scenarios for the final instrumented source.
These tests do not establish live acceptance.

## Candidate live results

On the same isolated AVD on 2026-10-29, boot completed in 45.988 seconds.
A single cold Junhong launch reached MainScreen in 63.798 seconds. The ensuing
public journey failed after 118.147 seconds at its first checked image:

- Two missing-child recoveries returned code 2: the parent itself could no
  longer be refreshed. Neither permitted a child retry or partial scan.
- A later full traversal succeeded, but its XML differed from the original
  observation: 129 versus 135 nodes, 18 changed matched positions, topology
  changed, 8 text fields, 5 descriptions, 18 bounds, 33 identity fields and 13
  flags differed. `clock_value_only=0`. This establishes a real page-structure
  change for this attempt, not a clock-only failure.
- The image request took 28.816 seconds and correctly failed
  `snapshot_changed_before_capture`. The diagnostic proves rejection worked;
  it does not prove exactly which App update or animation caused the change.

A fresh native session on the already displayed public page then timed out
inside initialization; total including cleanup was 46.705 seconds. It never
reached image capture. This receipt does not identify the exact initialization
subphase, and it must not be counted as either a screenshot latency or a
successful stable-child recovery.

Both sessions confirmed cleanup. Retained crash and ANR records contained no
new entries. The emulator console acknowledged the explicit stop; the runner
ended after 497.09 seconds with exit -10, its owned PID was absent and both
5576/5577 ports were free. No P30 or production-service action occurred.

**Result:** the candidate is not proven to improve successful collection. It
remains opt-in, and no production capture checks or bindings were changed.
Further tests should distinguish native-start timeout phases and use actual
collection pages, while authenticated funds/holdings remain a separate gate.

## Upstream basis

The [Android 7 interaction client](https://android.googlesource.com/platform/frameworks/base/+/android-7.0.0_r1/core/java/android/view/accessibility/AccessibilityInteractionClient.java)
caches returned accessibility nodes. The [interaction controller](https://android.googlesource.com/platform/frameworks/base/+/android-7.0.0_r1/core/java/android/view/AccessibilityInteractionController.java)
limits descendant-prefetch batches to 50. An empty text query is not a useful
bulk-prefetch shortcut: [TextView](https://android.googlesource.com/platform/frameworks/base/+/android-7.0.0_r1/core/java/android/widget/TextView.java)
explicitly requires nonempty search text. No framework, APK, signature or app
security checks were modified for this experiment.

## Acceptance remains separate

Require repeatable public navigation and bound screenshots, then complete
funds/holdings through the authenticated managed account adapter and a verified
exclusive **test** device binding. The current desktop has no managed App tool;
its last `/v1/auth/me` check returned 401. Existing login permission does not
supply a missing authenticated request context. No fabricated principal, raw
credential read or production selector fallback is allowed.
