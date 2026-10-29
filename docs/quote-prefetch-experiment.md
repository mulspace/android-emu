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

At the end of this first quote-only run, the complete startup/navigation route
and TDX had not yet been retested with the final candidate. The follow-up
sections below record those tests. Managed authenticated account acceptance
remains outstanding; do not promote the optional candidate to production yet.

All three native sessions confirmed cleanup. The crash buffer was empty. A later
parser audit corrected the initial no-ANR summary: the padded `am_anr  :` tag
recorded one SystemUI TIME_TICK-broadcast ANR during boot, before the quote
probes; no Junhong ANR was found in this run. Successful quote screenshots do
not erase that emulator stability failure. The owned emulator stopped after 1116.31 seconds
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

## Fresh-run TDX regression and Junhong startup failure

The same final candidate was tested in a newly booted isolated AVD. TDX's process
was started once; MainScreen readiness took 45.871 seconds. Public search, exact
600999 result selection, 日K selection and all three bound-image pairs passed in
144.666 seconds including native setup and cleanup. Image RPCs took 12.698,
6.342 and 5.303 seconds; all six original receipts passed offline backend replay.
Visual inspection showed 招商证券 / 600999, 日K and the 2026/10/29 chart date.
The capture was pre-open and showed zero opening price/volume; those fields must
not be described as verified intraday activity.

Starting Junhong after this TDX test failed cold-readiness validation. The App
later emitted its MainScreen display event (104.805-second Activity chain), but
an Android "isn't responding" modal was actually present. The attempted native
journey failed on its first foreground read (`SecurityException`) and cleaned
up after 39.274 seconds, with **zero navigation actions**. No Wait/Close button
was pressed and no late display event was treated as a passing startup receipt.

Retained system logs identify an `AppwidgetUpdateService` execution timeout.
The exact Junhong main-process stack was captured this time: its main thread
waited in Binder `ActivityManagerProxy.registerReceiver` during `MainScreen`
initialization. The contemporaneous system CPU interval reported TDX at 50%,
Junhong at 22% and system_server at 13%. This supports testing background-App
contention, but does not prove it is the sole cause. The previous missing-main-
stack evidence must not be substituted for this current stack.

The runner was explicitly stopped after 795.26 seconds; both native sessions
confirmed cleanup, the owned PID exited and ports 5576/5577 were free.

The public startup helper now uses its original 240-second absolute deadline
instead of ending after twelve polls. It recognizes padded ANR/crash tags,
rejects new App failures even if a MainScreen event is also present, and retains
the exact failure event privately. `--stop-other-test-app` is an explicit
isolation experiment: it can stop only the other of the two named test Apps on
the verified owned emulator before the target App's single launch. It is off by
default and does not change production task/App lifecycle policy. Sixty-six
repository tests passed after these changes.

## Explicit peer-isolation comparison

A new bounded run explicitly stopped only TDX on the isolated emulator before
starting Junhong once. The startup helper passed after 65.316 seconds, including
the peer-stop step, with no new Junhong failure event. The same prefetch candidate
then completed market selection, public symbol entry, two matching exact-result
observations, one result tap and three original-frame-bound quote image pairs.
That complete navigation/capture probe passed in 174.261 seconds including native
initialization and cleanup; its image RPCs were 13.432, 13.533 and 16.394 seconds.
All six original read/image receipts passed unchanged backend validation offline.

This comparison supports further testing of background App contention, but it
is not a randomized speed benchmark. By 09:06 the broker feed had reset to its
pre-open state: the screen showed 600999 with opening values absent, an empty
intraday plot and no active order-book prices. That changed rendering workload
can also affect latency. These images prove guarded public UI capture, **not**
fresh tradable quotes. Do not attribute the entire speed difference to peer
isolation or silently use the empty fields for analysis.

The same current-page check was then repeated with the **original 30-second**
snapshot RPC deadline. All three bound images passed in 15.106, 11.115 and
11.569 seconds; the complete read-only probe, including initialization and
cleanup, took 106.284 seconds. All six original receipts passed offline backend
validation. Thus this last public-page result did not depend on the diagnostic
90-second timeout, although the earlier full navigation run used that setting.

The corrected event parser found zero ANR/crash events in this final isolated
run, and its crash buffer was empty. Both native sessions acknowledged cleanup.
The explicit owned stop ended the emulator after 688.23 seconds with exit -10;
the owned PID was absent and ports 5576/5577 were free. No P30 command, production
binding change, live Scheduler operation, broker login or trade occurred.

These are bounded pre-open engineering results, not a blanket stability claim.
Remaining acceptance work includes changing intraday quotes, managed login,
complete account funds/holdings (including all scrolled rows), and the approved
managed device binding. The desktop's authenticated ingress was rechecked and
still returned HTTP 401; no managed App tool is available here. Broker-login
permission is retained, but it does not supply that missing authenticated
platform Context. Do not switch Stock tasks based only on these public tests.
