# Bounded parallel accessibility reads

This opt-in Android 7 diagnostic changes only the private observation JAR in the
owned emulator. It does not edit Kengent source, official Apps, account policy,
production bindings, Scheduler, services or P30.

## Question and retained boundaries

The preceding timing experiment identified remote child retrieval, not attribute
formatting, as the dominant cost. Android's
[AccessibilityInteractionClient](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-7.0.0_r1/core/java/android/view/accessibility/AccessibilityInteractionClient.java)
keeps a client per interrogating thread and forwards requests through the existing
permission-checked connection to the App's UI thread. Parallel callers therefore
can overlap waits but do **not** make the App UI thread parallel. A speedup must
be measured; it cannot be inferred from using two callers.

`--parallel-children` requires `--single-pass --prefetch-siblings` and excludes
`--recover-stable-child`. It is disabled by default.

- At most two sibling reads run: the existing caller and one bounded worker.
- Each read owns a separate sealed parent copy. It invokes the same framework
  sibling lookup and verifies exact returned child ID and window ID.
- Both reads finish before their pair is consumed in the original traversal order.
  The next sibling is retained by its parent wrapper and recycled if not visited.
- A six-second pair wait fails closed; cleanup waits up to six seconds for the
  owned worker. Late results, exceptions, interruption and abandoned jobs release
  their nodes. No retries are added to App input or to a failed native session.
- Every window and hidden descendant is still traversed. Missing nodes fail.
  Password redaction, sensitive-input rejection and the original exact frame,
  foreground, geometry and before/after image checks are unchanged.
- One worker is created per complete hierarchy capture and joined at its end.
  Android's per-thread client registry persists until the bounded native session
  exits. This is a diagnostic, not a proposed long-lived production thread model.
- Tests cover concurrent completion, all ownership exits, deadlines, interruption,
  immutable parent copies, identity rejection and root-buffer cleanup anchors.

The public capture helper now stores both JAR SHA-256 hashes in each private
receipt. Fresh read-only images and exact-frame-bound images are separate modes;
only the latter exercises the current Stock acceptance contract. A fresh read's
post-image XML must never be represented as an atomic snapshot of image values.

## Candidates

- Baseline sibling-prefetch bridge:
  `b32da7955922d24845d3c4df7126f350a72a40c663b40649941133ab6b87a702`.
- Parallel bridge:
  `a5d34d60a37fde3adc6cc07d4921113d62846f6eaa9d831318146b250badd14f`.
- The builder verified identical original Kengent Java source hashes for both.
- Same owned two-vCPU ARM32 guest and debug-symbol emulator, host cores 14/15;
  no snapshot restore or App-data reset during the comparison.

Raw receipts, UI images and logs remain private outside Git. Results below are
public-page compatibility evidence, never proof of authenticated account capture.

## Market-open TDX comparison, 2026-10-29

The baseline navigated to 600999 successfully but its initial chart readiness
read timed out at 30.021 s (whole probe 115.318 s). A new paired-reader session
started from that existing quote, reached day-K, and then correctly rejected its
first checked image because the original observed hierarchy changed. Its entry,
daily readiness, XML observation and rejected image reads took 25.894, 28.678,
10.518 and 17.539 s; whole probe 120.244 s. Both sessions confirmed cleanup.

The following A/B/A comparison used the same open daily chart without further
input. Each group used a new bounded native session and three **fresh read-only**
images, one second apart. No group passes the exact-frame Stock gate by virtue of
these fresh captures.

| Group | Three image RPC durations (s) | Median (s) | Whole probe including startup/cleanup (s) |
| --- | --- | ---: | ---: |
| Sibling baseline A | 28.771 / 10.112 / 9.223 | 10.112 | 92.159 |
| Paired candidate B | 15.454 / 4.696 / 15.285 | 15.285 | 77.114 |
| Sibling baseline A2 | 8.259 / 6.433 / 8.219 | 8.219 | 61.957 |

All nine fresh image receipts passed unchanged offline backend validation. Visual
inspection of A/B retained screenshots showed the same 600999 day-K layout and
2026/10/29 date, with changing volume/market values. Each session reported cleanup.
The candidate reduced the initial group total but had a slower median than both
baseline groups. Warm-up, quote changes and a tiny sample prevent a causal speed
claim. **No consistent performance benefit was demonstrated; keep it opt-in and
do not adopt it as the default.**

## A separate CPU-affinity defect found during this run

Junhong cold startup again ANRed before the candidate bridge had run. The new
system ANR trace actually included the App main thread (previous traces sometimes
omitted it). The reported timed-out component was `AppwidgetUpdateService`; at the
sample, main was in `MainScreen.onResume -> userStatusTrace -> SQLiteOpenHelper`
through an ART native transition. This is a sample, not proof of a persistent
SQLite lock. Main schedstat showed 5.500 s execution and 16.866 s runnable wait.
The App had 17 GCs totaling 9.558 s, with only 0.552 s aggregate mutator pauses and
no blocking GCs; total concurrent GC time is not equivalent to UI pause time.

Live CPU inspection established a concrete configuration mismatch:

- Guest online CPUs and root cpuset were `0-1`.
- `foreground`, `top-app`, `background`, and `system-background` cpusets were `0`.
- The exact Junhong main process belonged to `/foreground` and was allowed only
  CPU 0, despite the two-vCPU emulator launch.

The new opt-in `scripts/configure_guest_smp.py` verifies the owned run, ABI,
existing userdebug image, online/root allocation and both original App CPU sets.
It stops only the two test Apps, briefly uses the image's normal ADB root facility
to change **foreground/top-app only** to `0-1`, then confirms ordinary UID 2000
ADB shell is restored before any App test. It never changes SELinux, APKs,
signatures, App security checks, credentials or the system image. Changes are
volatile and reset at guest boot. Errors roll back modified groups; an
unconfirmed ADB privilege restoration requests this owned emulator's shutdown.

This first allocation repair completed in 15.180 s with both readbacks correct
and ordinary shell restored. Junhong's next startup displayed in 52.388 s from
helper start, completed peer-absence verification at 59.074 s, and produced no new
startup ANR. This single warm-host comparison does not prove a causal speedup or
eliminate cold-start failures; foreground CPU selection must now be accounted for
in future SMP comparisons. Earlier two-/four-vCPU measurements did not establish
that the Apps themselves could use all those CPUs.

Android 7's [upstream init defaults](https://raw.githubusercontent.com/aosp-mirror/platform_system_core/android-7.0.0_r1/rootdir/init.rc)
initialize App CPU sets to CPU 0 and explicitly leave the correct allocation to
the device init configuration. This matches the observed mismatch; launching QEMU
with two online CPUs alone is insufficient. We verified the relaunched Junhong
main process allowed list changed to `0-1` in `/foreground` before proceeding.

The repaired-CPU public search/quote route reached the correct quote in 126.973 s
including cleanup, but its original-frame image was rejected as changed before
capture (XML 9.057 s; rejected image 8.474 s). The CPU allocation fix therefore
has **not** solved the dynamic-quote acceptance problem.

Three subsequent fresh Junhong images passed unchanged offline validation,
at 16.994 / 14.999 / 10.710 s (whole probe 94.315 s including confirmed cleanup).
Visual review showed the correct 600999 public quote and order book. They are
fresh read-only captures, not original-frame-bound or authenticated account
captures. The first owned run ended after 1720.43 s; every native session reported
cleanup, the emulator PID disappeared and ports 5576/5577 were free. Its crash
buffer was empty; one earlier startup ANR remained in the event log.

## Independent guest boot verification

A fresh emulator process, with the same existing private userdata and unchanged
App packages, reset both App CPU sets to `0` as expected. The explicit repair
again verified `0-1` and restored ordinary shell (11.501 s). Junhong startup
passed its display and peer-absence checks in 61.788 s without a new startup ANR.
This is a new guest boot, not an App-data wipe or cold host filesystem cache.

The public search-to-quote route again completed navigation, then rejected the
first bound image because quote/UI values changed between observations. XML and
rejected-image RPCs were 8.534 and 7.618 s; the whole probe was 130.494 s with
confirmed native cleanup. No automatic retry or relaxed image approval was used.

The clean-boot Junhong fresh quote image also passed offline validation (17.114 s,
whole probe 66.191 s, confirmed cleanup). TDX then passed its startup/display and
peer-isolation checks in 41.765 s. Android had restored two Junhong processes
during the switch; the bounded isolation helper detected this and verified their
absence after its one allowed corrective stop.

The first clean-boot TDX journey failed before any page action: its native
initialization did not emit ready within the existing 10-second wait. The original
request expired at 10:52:27.048; the guest emitted ready at 10:52:29.911, too late
to accept. Native service initialization itself took 0.488 s after entering its
instrumented configurator; substantial preceding JVM/class-loading/startup time
remains. The failed session confirmed cleanup (whole probe 63.873 s). Neither the
10-second readiness limit nor production behavior was changed to hide this result.

A subsequent **new** TDX native session (no replay on the failed session) retained
the original readiness/capture limits and passed the entire public search ->
600999 -> day-K -> three exact-frame image pairs route. Whole probe: 108.357 s,
with confirmed cleanup. The three XML reads took 0.945 / 2.412 / 0.698 s; bound
image RPCs took 1.863 / 2.453 / 2.811 s. All six original receipts passed unchanged
offline backend validation, and visual review confirmed the 600999 day-K chart
with 2026/10/29 endpoint. This is stronger than fresh read-only capture, but one
successful route after an initialization failure is not stable device acceptance.

## Current decision

- Keep parallel child reads disabled: no consistent A/B/A improvement.
- Retain the opt-in, verified App CPU allocation repair for future isolated SMP
  tests. It is volatile; the unmodified guest boot resets the groups to CPU 0.
- Do not switch Stock bindings. Junhong still fails the dynamic-quote strict gate;
  complete authenticated funds/holdings and scroll coverage remain unverified.
- This terminal still has no configured Kengent CLI auth profile and no connected
  managed App adapter. Existing broker login permission remains valid, but it
  cannot substitute for a trusted platform ingress. No credentials were read,
  no identity was synthesized, and no account/production operation was attempted.
- 78 host regression tests passed. Diagnostic bridge JARs are not APK releases.
  No raw image/log/ANR/credential artifacts are included in Git.

Final cleanup of the independent guest run: 1090.31 s, intentional stop, owned
emulator PID gone and ports 5576/5577 free. All four native sessions confirmed
cleanup; ordinary ADB shell was verified before shutdown. Its complete event and
crash buffers contained no ANR or crash records. The final TDX main process was
verified in `/foreground` with allowed CPUs `0-1`. P30, live services, Scheduler,
Stock bindings and account credentials were not operated.
