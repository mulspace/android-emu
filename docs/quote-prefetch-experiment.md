# Junhong quote traversal latency experiment

This is an opt-in, API-24-only diagnostic candidate. It does not change Kengent
production code, App signatures, login policy, Stock bindings, Scheduler or P30.
All raw receipts, images and jars remain in private storage outside Git.

## Evidence and mechanism

The 2026-10-29 two-vCPU ARM32 run reached the official 600999 / 招商证券 quote
page through public controls. A 90-second read-only deadline did not fix the
initial entry read: the complete search-to-quote run stopped after 206.967 seconds,
with the entry RPC timing out at 90.089 seconds. Its native session cleaned up.
An unguarded screenshot used only for diagnosis showed the public quote page;
that screenshot was **not** accepted as a managed collection result.

A second, current-page diagnostic retained a complete tree with these timings:

| Component | Time / count |
| --- | ---: |
| Complete traversal | 48.153 s |
| Child retrieval, including missing-child refresh when applicable | 46.630 s |
| Child calls / calls at least 100 ms | 290 / 38 |
| Slowest child retrieval | 5.850 s |
| Attribute collection | 0.155 s / 198 calls |
| Root acquisition | 0.807 s |
| Window enumeration | 0.005 s |

The outer quote-entry RPC took 49.233 seconds. The next XML observation timed out
at 90.090 seconds, so this run also failed its three-image gate (183.525 seconds
including confirmed cleanup). These measurements identify child acquisition as
the dominant cost in this retained traversal; they do not establish why every
slow framework call waits, or prove a general emulator throughput improvement.

Android 7's [AccessibilityNodeInfo source](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-7.0.0_r1/core/java/android/view/accessibility/AccessibilityNodeInfo.java)
uses descendant-only prefetch for `getChild`. Its existing internal related-node
lookup additionally requests predecessor and sibling prefetch through the same
[AccessibilityInteractionClient](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-7.0.0_r1/core/java/android/view/accessibility/AccessibilityInteractionClient.java)
connection and cache. The experiment invokes that existing framework path for
the exact indexed child; it does not replace the framework permission check.

`SiblingPrefetch` requires SDK 24, a sealed parent and a valid child index. It
checks the returned source-node ID and window ID, recycles rejected results and
fails closed on unsupported reflection or lookup errors. No exception payload or
UI content is logged. Normal cache invalidation still happens before each full
observation. The traversal still visits every child, including hidden descendants
for sensitive-input detection, and fails on missing nodes. Original-frame,
foreground, geometry, sensitivity and before/after-image checks are unchanged.

Enable only in the private diagnostic builder:

```sh
python scripts/build_observation_probe.py \
  --kengent-root /path/to/kengent --sdk-root /path/to/android-sdk \
  --output /private/new-prefetch-candidate \
  --single-pass --retry-incomplete-checked --hierarchy-retry-delay-ms 1000 \
  --prefetch-siblings
```

The default is disabled. Build receipts record the flag, source hashes and jar
hash. `EmuHierarchyTiming` emits numeric root/window/child/attribute durations and
counts once per completed or failed traversal, with no stock/account/UI text.
A process killed during a blocked framework call cannot emit its final counter;
do not treat a missing timing line as a zero-duration traversal.

## Observed candidate result, 2026-10-29

The final candidate jar SHA-256 was
`b32da7955922d24845d3c4df7126f350a72a40c663b40649941133ab6b87a702`.
The preceding timing-only jar was
`0f4783afd8a0c82a7b3eef68ad09149d915ea148eb9d1555f6e427e61cd71e06`.
Both used the same emulator process, App version, open quote page, host CPU
allocation, 90-second read-only deadline and unchanged snapshot acceptance rules.
The final candidate was tested after the baseline, with the App already warm;
this is not a randomized benchmark or proof of the speedup's causal magnitude.

| Final candidate operation | Time |
| --- | ---: |
| Quote identity/readiness | 31.534 s |
| First XML observation / bound image | 25.766 / 49.256 s |
| Second XML observation / bound image | 26.800 / 41.618 s |
| Third XML observation / bound image | 20.937 / 37.466 s |
| Whole current-page probe including initialization and cleanup | 277.653 s |

All three original-frame-bound image pairs passed. Ten complete traversals each
visited 291 nodes, with durations 16.005-29.858 seconds (median 19.951 seconds).
The previously retained timing-only traversals took 48.153 and 93.890 seconds;
the latter completed in the guest only after its 90-second host RPC had expired
and was therefore **not** an accepted observation. Missing-child recovery beyond
the existing bounded whole-traversal retries was not enabled for either build.

Visual inspection confirmed the public 招商证券 / 600999 分时 page and order-book
layout. Its screen did not establish the quote's trading date; this pre-open
image is not proof of that day's live quote freshness or account access. The
unchanged backend accepted all six original read/image receipts offline. The
backend discarded optional diagnostic timing fields over its 30-second cap;
the durations above come from the retained host RPC events, not that capped
product telemetry. No production timeout or telemetry contract was changed.

The complete cold navigation route still has not passed with the final candidate;
its successful run began on the already-open quote. TDX was not retested with
sibling prefetch. Remaining work is a cold-navigation/repeat comparison, TDX
regression on the same candidate, and managed authenticated account acceptance.
Do not promote this optional candidate to a production default yet.

All three native sessions confirmed cleanup. The crash buffer was empty and no
ANR/crash events were found. The owned emulator stopped after 1116.31 seconds
(explicit stop, exit -10); its process was absent and ports 5576/5577 were free.
P30 and production services were untouched. Sixty-three repository tests passed,
including one-shot complete navigation, known-dialog priority, wrong child/window
identity, unsupported SDK, unsealed parents and rejected-result recycling.

## Acceptance limits

Public quote screenshots do not establish authenticated funds and holdings
collection. The current desktop still lacks an authenticated Kengent managed
entry for that account test. Existing broker-login authorization remains valid,
but no credential values, borrowed session or synthetic tenant Context may be
used to replace the missing managed entry. Stock tasks must remain on their
existing device until both Apps pass the actual collection requirements.
