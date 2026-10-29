# Exact startup ANR evidence and official home-page experiment

Date: 2026-10-29, Asia/Shanghai. Only the owned emulator-5576 is in scope.

## Evidence repair

The optional `prewarm_public_app.py --collect-anr-evidence` saves the original
unprivileged ANR trace, process list and events immediately after a Junhong startup
failure, within the original 240-second deadline. It does not relaunch, grant root,
click an ANR dialog or operate an account. A missing trace or permission failure
is recorded rather than replaced by an unrelated historical stack.

The parser binds the exact main package, process ID and event time to one complete
process block. It identifies the main thread by `sysTid == process PID`, not the
first occurrence of `"main"` (worker threads also contain `group="main"`). Traces
outside the event window (-2 to +120 seconds), incomplete blocks and ambiguous
matches are rejected. Sanitized results expose only scheduling totals and method
names; raw dumps stay outside Git.

Offline replay of the original 08:50:05.631 event matched PID 2389 and its
08:50:30 trace (24.369-second delta). The main thread was in Binder
`registerReceiver` during `MainScreen.starInit`, with cumulative CPU 5.131 seconds
and runnable wait 29.916 seconds. This supports the previously recorded startup
blocking sample; it does not establish a fixed deadlock or one emulator defect.
The suite passed 101 tests in 8.355 seconds, including exact-event, stale-PID,
worker-name collision, missing-permission, incomplete-block and ambiguity cases.

## Current isolated baseline

Installed official Junhong is 9.9.30 / versionCode 23112418 / armeabi-v7a, not
9.30.45. The APK signature and contents are unchanged. Two guest CPUs use host
CPUs 12-15 at nice 10, 768 MiB TCG cache, and verified foreground/top-app CPU sets
0-1. The debug-symbol emulator binary is unchanged. TDX is stopped only inside
this diagnostic AVD; P30, production bindings, services and Scheduler are untouched.

A fresh Junhong start passed: launch acknowledgement at 9.871 seconds, main display
at 73.368 seconds, peer-absence checks at 78.316 seconds. This successful trial
did not exercise the new live failure collector, and does not erase intermittent
ANRs in prior trials. A following guarded home screenshot took 2.663 seconds
(63.053 seconds for session setup, read and confirmed cleanup).

## Official default-home inspection

The screenshot showed a promotional overlay. Only its visually verified close
control was used; no promotional offer or account control was selected. Observed
public controls led through My -> Settings -> Interface settings -> Default home.
The current value was Intelligent (智能); the actual sheet offered Intelligent,
Discover, Quotes, Trade, Wealth and My. Each step used a fresh original frame
reference and retained all native input/sensitivity guards.

The test device's official setting was changed from Intelligent to Quotes (行情),
and a fresh guarded snapshot read back `start_page_tv=行情`. This is an isolated
App preference retained in that test userdata; it is not an APK or production
configuration change. The reverse UI path can restore Intelligent.

All seven native sessions confirmed cleanup. Before stopping the baseline guest,
the shell was UID 2000, no native bridge remained, and the crash buffer was empty.
The event buffer did contain one **SystemUI TIME_TICK ANR during boot** at
16:24:10, before the 16:24:57 foreground CPU repair; there was no Junhong ANR in
this trial. That boot ANR is a remaining system-stability concern, not evidence of
a fully healthy guest. The owned runner stopped at 1141.420 seconds within its
1200-second bound; process absence and both ports released were verified.

## Independent cold comparison

The previous guest was stopped and its ports verified free before a new
600-second bounded cold run with the same binary/settings. Boot completion
polling took 53.495 seconds. The foreground/top-app CPU repair was reapplied and
ordinary UID 2000 restored before the one planned App launch.

The launch acknowledgement arrived at 10.126 seconds, main display at 59.148,
and peer-absence checks at 64.880. No Junhong startup ANR was detected. Compared
with 78.316 seconds in the previous cold start, this trial was 13.436 seconds
(17.2%) shorter. This is one uncontrolled comparison, not a demonstrated causal
or repeatable performance gain. The two runs can differ in cache, network and
background workload. The following three original-observation-bound screenshot requests passed without
relaxing identity, hierarchy, sensitivity or input guards:

| Pair | XML observation | Bound image request |
| --- | ---: | ---: |
| 1 | 8.482 s | 7.872 s |
| 2 | 2.447 s | 4.189 s |
| 3 | 1.795 s | 3.865 s |

Whole native probe including confirmed cleanup was 79.745 seconds. Offline replay
accepted all six original wire records using the unchanged backend. The first
and last images were visually checked: Quotes is the active bottom tab and the
unlogged-in public watchlist/indices page is visible. This is not a broker
holdings screen, nor an independent verification of current market prices.

At final cleanup the event buffer had no ANR/crash events, the crash buffer was
empty, the shell was UID 2000, and no native bridge remained. The second owned
runner stopped deliberately at 321.260 seconds within its 600-second bound;
process absence and both ports released were verified. No diagnostic remains
running. The isolated test userdata retains Quotes as its default home.

The next comparison should repeat cold starts and the complete public quote
journey with this documented setting, not infer stability from a screenshot.
Authenticated complete-account acceptance remains required independently.

## Acceptance remains separate

Successful public navigation is not authenticated account collection. The terminal
still has no CLI auth profile or connected managed App adapter. The existing login
authorization is retained, but complete funds, all holdings and scrolling require
the trusted tenant/workgroup App Context and exact test-device binding. No raw
credential files or substitute identities are used. Do not switch Stock yet.
