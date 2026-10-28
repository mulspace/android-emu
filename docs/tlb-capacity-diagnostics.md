# ARM32 software TLB capacity experiment

This is an opt-in compatibility experiment on the isolated current-host AVD.
No P30 operations, production service reloads, Stock bindings, Scheduler changes,
account input or trading occurred. App APKs and signatures were unchanged.

## Implementation and reproducibility

The upstream software TLB cap is 256 entries (`CPU_TLB_BITS=8`). The optional
`--arm-tlb-bits 10` build raises it to 1024 entries only for ARM32 executables on
Linux x86-64. Other targets and the default remain unchanged. The original host
displacement bound remains; MMU permissions, invalidation, code-cache flushing,
ARM instructions and guest clocks are not bypassed. This changes a CPU-state
layout, so all target-specific translation units must be rebuilt together.

The symbol-bearing RelWithDebInfo build took 123.42 s with two build jobs.
All 348 ARM headless compilation commands carry the same opt-in definition.
Offline GDB inspection of the actual engine reports 1024 entries per mode.
The renderer binary did not change. An independent complete runtime copy retains
the original baseline for rollback, including libraries and resources.

* Baseline engine SHA-256:
  `fbc831874f717dddcb21eb87899523f49f6fc0ddd7d078c778c9beba877faa11`
* Candidate engine SHA-256:
  `b87614572d5b432257bed6de28b9821a1bdc7067bd2e6470e2eb045ab7ccfcec`
* Native ARM fixture SHA-256:
  `6975098b4b2ad20cc56b590c9c9a0f34d367f02e7ae393b6e8c88e54969f8e33`

Both comparisons use the same isolated ARMv7 AVD, two guest CPUs, 1536 MiB RAM,
host CPUs 14/15, host GLES, 768 MiB translation-code buffer, and disabled Android
CheckJNI diagnostics. Junhong's previously recorded standard AOT compilation
persists in the guest. Sequential tests reuse guest disk/cache state; these are
not randomized cold-state benchmarks.

## Native correctness and timings

The identical NDK-compiled native fixture passed all three trials in each engine:
permission faults, copy-on-write, shared-file aliases, cross-CPU mappings,
24 remapping rounds, discard-to-zero, and 48 executable-code replacements.
The alarm is 90 s, core dumps disabled, and temporary guest files are removed.
Host execution also passed its applicable checks, but cannot validate ARM code
updates and is deliberately not accepted by the guest result validator.

Median of three trials, seconds:

| Test | 256 entries | 1024 entries |
| --- | ---: | ---: |
| 128-page working set | 0.006086 | 0.000270 |
| 512-page working set | 0.023633 | 0.034679 |
| 2048-page working set | 0.097872 | 0.120964 |
| Entire fixture | 0.417682 | 1.004938 |

Small-working-set improvement did not generalize. Guest scheduling, cache state
and host load can affect these short measurements; they do not establish an
application speedup or exhaustive MMU correctness. Do not enable this by default.

## Same-condition public App results

| Observation | 256 entries | 1024 entries |
| --- | ---: | ---: |
| Junhong start helper duration | 77.957 s | 59.633 s |
| Android MainScreen full-display event | 55.621 s | 52.335 s |
| Junhong public market journey | 106.992 s, failed | 102.344 s, failed |
| First checked screenshot | Incomplete hierarchy | Incomplete hierarchy |

The helper includes command overhead and display-event polling. Its larger
reduction must not be reported as the App's startup speedup. Both engines entered
the public market tab, then rejected the first checked capture. The baseline's
saved foreground remained MainScreen and its crash log was empty at that point.
The candidate Tongdaxin start helper took 40.834 s; its initial public read failed
with incomplete hierarchy after 37.040 s, before symbol navigation.

The failure-specific diagnostic now records only missing-root/window type or
child depth/index/count. It does not expose UI text, skip missing children,
relax exact before/after matching, or change production capture code. Follow-up
results belong below. Raw captures and logs remain private and outside Git.

## Readiness and missing-node diagnosis

A later unchanged guarded capture of Tongdaxin's public market page passed in
5.770 s (46.974 s including session startup/cleanup). Visual inspection confirmed
public index/market content, not an authenticated account. The earlier Tongdaxin
failure was in foreground/root acquisition, with three failures only milliseconds
apart. An Activity display event is therefore not sufficient readiness evidence.

The diagnostic public journey now waits for explicitly incomplete read-only
hierarchies within its existing eight-read and whole-request deadlines. It never
replays an input action, retries a generic timeout, accepts a denied foreground,
or skips a sensitivity check. Checked screenshot pairing remains unchanged.

Tongdaxin subsequently completed the full public 600999 search-to-daily-chart
journey in 139.872 s with three accepted checked screenshots: 8.642 s, 3.834 s
and 2.569 s. Visual inspection confirmed 招商证券 / 600999 and the latest displayed
chart date 2026/10/28; the test ran before the 2026/10/29 market session, so this
is prior-session chart data, not a fresh intraday quote. Session cleanup succeeded.
This later success used only the additional numeric diagnostics, with unchanged
capture acceptance rules; it is not a controlled proof that TLB capacity caused
the improvement or that all future cold starts will pass.

## Checked capture retry experiment

Junhong's follow-up failure identified a disappearing child at depth 18, index 2
(after 299/323 visited nodes). The entire App was still accessible. The diagnostic
adapter now refreshes a parent only when its child read fails, records numerical
before/after child counts, and **still rejects that incomplete traversal**.
It never skips a missing child or accepts partial sensitive-input coverage.

A separate opt-in `build_observation_probe.py --retry-incomplete-checked` changes
only incomplete-tree retry eligibility. At most three attempts retain the original
expected observation; every completed tree must still match it exactly. A changed
hierarchy, changed surface or sensitive field still fails. Captured pixels from
a failed attempt are discarded, and the original overall timeout is unchanged.
This is confined to a copied diagnostic JAR; production Resource Node is untouched.

The exact generated SnapshotCapture.java passed 10 compiled Java scenarios in
`tests/guest/CheckedCaptureProbe.java`: missing-before/after recovery, original
expected-frame preservation, changed hierarchy, rotation, sensitive-before/after,
three-attempt exhaustion, unrelated transport error and normal success.
The repository's 46 bounded Python/Java tool tests passed separately.

On the already-open Junhong public market page, three strict image pairs passed
in 5.997 s, 4.571 s and 4.127 s (68.680 s including session start/cleanup).
Visual inspection confirmed the A-share public market tab and indices. This is
not a logged-in account, a verified current-session timestamp, or funds/holdings
acceptance. Warm-state/cache differences mean this pass alone cannot attribute
all improvement to the retry change or prove repeatable cold starts.

The successful Junhong trial still logged one missing node during its initial
read: parent refresh returned false and the child count remained 3. The following
complete read succeeded. No checked-image retry was needed in those three
successful pairs, so this does **not** prove that the new checked-retry branch
caused the live pass; its fail-closed behavior is verified by the compiled tests.

Both baseline and candidate emulator processes were explicitly stopped after
completed probe cleanup. Their runners recorded exit -10 after emulator-console
kill, and their exact PIDs and ports 5576/5577 were verified released. Guest disks
and private evidence are preserved. This is controlled teardown, not a spontaneous
engine crash. Complete authenticated funds/holdings and repeatable cold-start
collection remain outstanding; no Stock cutover has been made.

## Reboot repeat with default 30-second capture deadline

A fresh owned emulator run reused the same candidate binary and latest diagnostic
bridge. Junhong's start helper completed in 64.946 s; Android recorded 51.730 s
for its full MainScreen display. The public journey then failed after 90.116 s
at the first read following the market-tab action, with a transport read timeout.

The numeric log shows why the default budget was exhausted: initial foreground
and geometry checks took about 1.37 s, an absent active root cost 5.03 s, the retry
foreground read took 13.60 s, and its 486-node traversal took 11.27 s. The bridge
completed that traversal only just beyond the host's 30-second request limit.
This was not evidence of a new engine crash or missing market entitlement. The
failed read did not replay the preceding input, and session cleanup succeeded.
Warm capture passes therefore remain insufficient for reliable default-timeout
operation after restart. Production timeout settings remain unchanged.

Tongdaxin's default-timeout repeat did not reach the daily chart either, but for
a different reason. Its start helper took 28.275 s and the journey stopped after
95.457 s while waiting for the chart selector. Saved read-only hierarchies show
the search result briefly existed, the one tap was acknowledged, then the search
WebView rebuilt its list; all eight later reads remained on the search page.
An acknowledged injected tap is not proof that navigation completed. No second
click was sent to compensate for this uncertain outcome.

The isolated journey now requires the exact public stock hit (including bounds)
to match across two consecutive read-only observations, using the latest frame
for its single tap. An incomplete read resets that stability requirement; unknown
pages, transport timeouts and sensitivity/foreground failures are not relaxed.


The stable-result follow-up passed after a fresh emulator boot with the default
30-second per-snapshot deadline. The App display helper took 26.760 s, followed
by a 124.937 s complete public journey including bridge setup/cleanup. Four
read-only result observations were needed before two matched; the one result tap
then reached the daily chart. All three checked image pairs passed in 5.630,
4.056 and 3.875 s. Visual review confirmed 招商证券 / 600999, 日K and latest chart
date 2026/10/28. The test was before the next market session; it does not establish
live intraday freshness, repeated cold-start reliability or account acceptance.

All 47 repository tests passed. The native session acknowledged cleanup. The
owned emulator was explicitly stopped (runner exit -10 after 464.09 s), with its
exact PID absent and ports 5576/5577 released. P30 and production remained untouched.
