# TDX chart window-transition experiment

Date: 2026-10-29, Asia/Shanghai.

The previous TDX search-to-chart route failed its first chart observation at
30.030 seconds. Guest timing retained an obsolete window root, a later missing
active root, and then a complete 16.065-second traversal that arrived after the
host deadline. Retrying the same full-tree reads during the transition wastes
the observation budget; a late result must remain rejected.

Android 7's [AccessibilityInteractionClient](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-7.0.0_r1/core/java/android/view/accessibility/AccessibilityInteractionClient.java)
posts hierarchy requests to the App's UI thread and waits up to five seconds
for a response. [UiAutomation](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-7.0.0_r1/core/java/android/app/UiAutomation.java)
provides window enumeration without retrieving each window's view tree.
These source facts motivate a scheduling experiment; they do not prove that
all observed delays have the same cause.

## Candidate

`WindowQuiet` polls structural window descriptors at at most ten reads per
second, requiring one active and one focused window, with IDs, types, layers,
focus flags and bounds unchanged for one second. Empty/incomplete window lists
reset the quiet interval. The wait is capped at eight seconds and the original
RPC/lease deadline still applies. Cancellation, clock regression and a read
returning beyond its deadline fail. Every acquired window is recycled.

This is only a scheduling hint: it neither says the App is loaded nor authorizes
input/capture. Following the wait, the unchanged full-tree/foreground/geometry/
sensitivity and original-frame checks still run. No hidden child is omitted,
no missing root is accepted and no picture is approved by window geometry alone.
The observation consumes old input authority before waiting.

Build with the opt-in `--settle-windows` flag on
`scripts/build_observation_probe.py`, then opt into `--settle-windows` on the
public TDX journey. The first `chart_ready` observation alone requests it;
subsequent reads and strict image pairs use the original contract. The native
bridge accepts this diagnostic only with the single TDX package and XML-only
snapshot arguments. The probe requires the exact audited candidate JAR hash.
Default behavior and production Kengent source are unchanged.

Candidate bridge SHA-256:
`d8234144ecce29d60ae4263035a5ced2fbc3fc870a6878694cc75aacfd663ad4`.

The 95-test suite passed, including ten Java policy scenarios and route tests
for default behavior, one-time scheduling, cancellation/deadlines and source
anchor drift. No official APK, signature, authentication or production binding
was changed; only diagnostic JARs were built. Live evidence follows below.


## Live baseline / candidate / baseline result

All three routes used the same emulator process, official App, two guest CPUs,
four allowed host CPUs, native-ready option, candidate JAR and 30-second snapshot
RPC deadline. Each route explicitly stopped/relaunched only TDX and verified
Junhong remained stopped. The middle route alone enabled the scheduling option.
This is a sequential A/B/A comparison with warm caches, not a randomized study.

| Measurement | Baseline A1 | Candidate B | Baseline A2 |
| --- | ---: | ---: | ---: |
| Launch/display/peer-isolation helper | 32.187 s | 31.984 s | 32.728 s |
| First chart observation | 26.195 s | 23.323 s | 24.106 s |
| Bound image 1 | 6.954 s | 6.610 s | 6.380 s |
| Bound image 2 | 6.306 s | 4.146 s | 4.698 s |
| Bound image 3 | 3.826 s | 4.549 s | 5.725 s |
| Complete public journey and cleanup | 150.111 s | 147.962 s | 143.533 s |
| Original receipt replay | 6/6 | 6/6 | 6/6 |

All three public search -> exact 600999 result -> day-K routes passed. All nine
images and their nine original observations passed the unchanged backend replay.
Visual review of the final image in each route confirmed 招商证券 / 600999, the
selected 日K chart, volume/MACD and the 2026/10/29 endpoint. The displayed data
are after-close chart evidence, not authenticated assets or executable prices.

The candidate's window wait consumed 1.337 seconds. It avoided the retained
obsolete-window-root failure seen at the start of A1, but then spent 13.990 seconds
obtaining the foreground and 7.703 seconds on a complete hierarchy. A1's
foreground retry path took 18.162 seconds. Avoiding one obsolete-root query did
not remove the slow App/UI-thread response.

The middle route's whole time was slower than the following unmodified route.
Therefore the sample does **not** establish a repeatable speedup or justify a new
runtime default. Keep `--settle-windows` optional and disabled. Further work
should isolate App/UI-thread loading and accessibility response time; a stable
window outline is insufficient evidence that its contents have finished loading.
The candidate is retained to make this result reproducible, not as a claimed
production performance fix.

A read-only guest allocation check found system_server, SystemUI and the TDX
main process all in `/foreground`, each allowed CPUs `0-1`. Do not pursue a
hypothetical one-core system-server restriction contradicted by this run.

## Cleanup and acceptance limits

The first CPU-allocation helper exited before mutation because boot had not yet
completed. The original emulator remained alive. After `sys.boot_completed=1`
was observed, the next explicitly applied helper verified both App CPU sets and
ordinary UID 2000 shell restoration. No boot was restarted on that observation
timeout, and no failure receipt was overwritten.

All three native sessions confirmed cleanup. The final ANR/event and crash
buffers were empty; the guest inventory contained no bridge process, and normal
shell identity was verified. The owned emulator stopped after 1002.39 seconds
inside its original 1200-second limit. Its PID was absent and ports 5576/5577
were free. No P30, live Scheduler, production service, credential, order or Stock
binding was operated. Private screenshots, wire data, logs, JARs and userdata
remain outside Git.

This strengthens repeatable public TDX collection evidence for one stock on one
guest boot. It does not establish multi-stock throughput, Junhong cold-start
stability, or complete authenticated funds/holdings/scroll coverage. The latter
still requires the [trusted managed ingress](managed-account-acceptance.md).
Production Stock cutover remains unapproved by these diagnostic results.
