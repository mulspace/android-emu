# Four-CPU and standard compilation follow-up

Date: 2026-10-29, Asia/Shanghai. This follows the
[verified App CPU allocation repair](parallel-read-experiment.md).

The same official Apps, existing isolated ARM32 userdata, host GPU, debug-symbol
emulator, 768 MiB translation cache and sibling-prefetch observation JAR were used.
Only emulator-5576 was operated. Four guest CPUs were assigned to host CPUs
12/13/14/15 at nice 10; RAM remained 1536 MiB. No production service, P30,
Scheduler, Stock binding, credential or account operation was performed.

## Four CPUs correctly available to the App

Guest online and root CPU sets were 0-3. Foreground and top-app initially remained
0; the opt-in repair read back 0-3 and restored ordinary UID 2000 shell before App
launch. Junhong PID 1826 was independently verified in /foreground with allowed
CPUs 0-3. This comparison therefore addresses the previously unverified App CPU
allocation, not merely the QEMU command-line CPU count.

Junhong still failed startup after 65.907 seconds. The exact new ANR event named
AppwidgetUpdateService. The crash buffer was empty. The system ANR file was
interleaved: the App's process header was missing from its eventual main-thread
section, so the nearby media.extractor header must not be used to identify it.
The main thread's sysTid=1826 matched the failed App PID. It was Runnable in
AndroidX WindowInsetsCompat / ViewCompat / dispatchApplyWindowInsets and
ViewRootImpl traversal, with 23.263 seconds cumulative runtime and 4.610 seconds
cumulative runnable wait. Its recorded JIT compilation total was 41.902 seconds.
These cumulative samples do not prove an infinite layout loop or identify one
specific emulator instruction defect. They also do not support the previous
SQLite-sample hypothesis as a fixed deadlock.

**Four correctly allocated CPUs did not eliminate the startup ANR.** Keep the
existing two-CPU diagnostic default; this small comparison is not a universal
claim that four CPUs are slower.

## Tongdaxin before standard compilation

Tongdaxin startup/display/peer-isolation checks passed in 35.910 seconds. The full
public search -> 600999 -> day-K journey then rejected its first bound screenshot
because the hierarchy changed during capture. Both observations had 139 nodes;
only two text values differed, with no geometry, identity, flags or structure
change. Whole journey including confirmed native cleanup: 168.157 seconds.

This proves public navigation reached the chart. It does not pass the three
original-frame screenshot-pair acceptance gate. The separate two-CPU successful
journey from the preceding report remains historical evidence, not a replacement
for this failed repetition.

## Standard Android package compilation

A read-only Package Manager inspection established that Junhong was already
compiled with `speed`, but Tongdaxin used `interpret-only`, both up to date.
Junhong's earlier AOT experiment was not repeated.

For Tongdaxin only, normal ADB shell invoked Android's supported
`cmd package compile -m speed -f com.tdx.AndroidNew` after stopping the two test
Apps. The command is implemented by the upstream
[Android 7 PackageManagerShellCommand](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-7.0.0_r1/services/core/java/com/android/server/pm/PackageManagerShellCommand.java).
No profile clear, permission change, App-data reset, APK modification or App
security bypass was used. Compilation returned Success in 7.260 seconds;
Package Manager then reported speed / kOatUpToDate.

The installed APK was streamed through private temporary files before and after;
both were 191049254 bytes with SHA-256
`29ce31330b2f15f603a78c71fd3f5614b34168c40c0ab0d556d63b5cd96bdbbd`.
Temporary copies were removed. The compilation operation and verification took
53.802 seconds in total. **The isolated userdata now retains this speed
compilation; future comparisons must record this changed baseline.**

Post-compilation startup checks passed in 34.433 seconds, only 1.477 seconds less
than the previous run. The complete journey still failed: the first chart read
took 6.176 seconds but did not expose the expected actionable tab yet; the next
read timed out at 30.030 seconds. Total including confirmed cleanup: 145.971
seconds. The previous journey reached a later stage, so their total times are
not comparable success-path performance. Neither warm-cache effects nor ordinary
run variance were controlled; no causal speedup or stability claim follows.

## Follow-up read-only screenshot and bottleneck

Only after the failed native session confirmed cleanup, a new bounded session
read the existing chart without repeating any page input. That fresh screenshot
succeeded, passed unchanged offline backend validation, and was visually checked:
600999 / 招商证券, 日K, MA/VOL/MACD, chart endpoint 2026/10/29. It is a fresh
read-only image, not the failed journey's original-frame-bound screenshot.

| Component | Duration |
| --- | ---: |
| Native session setup including transport | 25.418 s |
| Before-image hierarchy/safety observation | 3.913 s |
| Image capture | 0.129 s |
| After-image hierarchy/safety observation | 4.295 s |
| Encoding | 0.465 s |
| Whole screenshot RPC | 9.128 s |
| Whole probe including cleanup | 50.213 s |

The two observations dominate this capture. Improving screenshot pixel transfer
alone cannot remove most of this delay. The fresh image's post-image XML must not
be represented as an atomic set of quote values. No expected-frame guard, input
fence, sensitivity scan or timeout was loosened to obtain a passing result.

## End state and remaining acceptance

All three native sessions reported cleanup. The owned emulator was deliberately
stopped after 1098.31 seconds within its original 1200-second bound. Its normal
shell was verified before shutdown; the final event log contained the one Junhong
startup ANR and the crash buffer was empty. Raw images, APKs, ANRs and receipts
remain private outside Git.

Do not switch Stock tasks. Public capture is still intermittent; Junhong
startup is not stable across configurations, and complete authenticated funds,
all holdings and scroll coverage remain unverified. The current terminal still
reports no CLI authentication profile and has no connected managed App adapter.
The user's broker-login authorization remains valid, but account verification
requires the trusted platform ingress; raw credential files or a fabricated
principal are not substitutes.

The [managed acceptance handoff](managed-account-acceptance.md) clarifies the
required authenticated ingress and exact read-only App operations. The older chat
CLI login alone must not be treated as a ready tenant-app Context.
