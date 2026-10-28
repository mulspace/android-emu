# Snapshot diagnostics and single-pass experiment

This work is isolated engineering validation on the existing ARM32 AVD. It does
not approve a production Stock device or establish authenticated funds/holdings
capture. Official APKs, CheckJNI, debug symbols, two guest CPUs, host GPU and the
original screenshot/input checks were retained.

## Precise failure diagnostics

The incremental Kengent patch `integration/kengent-snapshot-diagnostics.patch`
distinguishes an incomplete hierarchy, an unstable foreground/rotation, and
before/after screenshot differences. It can identify one narrowly defined
SystemUI clock-text difference for diagnosis. **All mismatches still fail.**
No clock normalization is used for acceptance, no failed input is replayed,
and no UI text or exception message is included in the failure diagnostic.

The patch has exact preimage and result SHA-256 hashes. It was applied in a
temporary copy of those preimages and compared byte-for-byte with its source.
The Kengent worktree contains unrelated work; this patch is deliberately not a
diff of that entire worktree. 109 focused Python/JVM cases passed through the
bounded host test wrapper. No production service was reloaded.

## Debugger comparison

`run_debug.py --debugger none` runs the same symbol-bearing emulator without host
GDB. GDB remains the default. The direct-mode probe verifies the exact engine
path, original process start ticks, process group, isolated AVD and dedicated
port. It refuses PID reuse, a different executable or an ended run.

On 2026-10-29 the no-GDB comparison used the existing two-core, CheckJNI-enabled
guest and host CPUs 14/15. `TracerPid=0` was verified. These are sequential live
samples, **not** a controlled statistical benchmark or proof that the debugger
caused the failures.

| Probe | Result |
| --- | --- |
| TDX cold process | Incomplete hierarchy on the fifth homepage read; 133.869 s including setup/cleanup |
| Junhong cold process | Public home read 64.100 s, market read 31.876 s; first checked image passed, second failed because content changed during capture; 195.996 s total |
| TDX with component timing | Complete search and daily-chart navigation, first checked image passed; second failed during capture; 306.239 s total |

The component-timing TDX run recorded a 49.287 s homepage read and a 64.723 s
quote-page read. Its retained later timing log showed a separate sensitive-node
scan of 203 nodes taking **22.751 s**, after a 3.328 s XML dump. Thus a second
traversal is a measured cost, although that sample does not explain every slow
startup or prove the complete cause of the earlier missing nodes.

Two sampled busy emulator threads each executed about 1.8 seconds during a
two-second host sample, with only 0.010/0.026 seconds queued. That sample does
not support host scheduling contention as the dominant cause. Three tiny native
CPU fixtures passed with the same checksum; their guest durations were
0.010800, 0.026580 and 0.009081 seconds. CPU-fixture speed is not App throughput.

No guest crash was recorded in the retained crash buffer. The runner ended
after an explicit stop request at 1282.44 seconds, with process return code -10;
this is recorded as a stop outcome, not a clean emulator exit or a spontaneous
test crash. Its PID and dedicated ports were verified released.

## Experimental single traversal

`scripts/build_observation_probe.py` copies Kengent's native sources to a private
build directory and adds numeric-only timing logs. It never modifies the source
tree, operates ADB or accesses an account. Every source and output hash is
recorded. The default diagnostic build retains both original traversals.

With `--single-pass`, the experimental classes in `experimental/native/` gather
XML and sensitive-control metadata in one complete traversal. They preserve
all accessible window roots, visit invisible descendants for sensitivity,
reject missing children, bound depth/node/output size, check cancellation and
recycle owned nodes. API 26 hint access is isolated from the API 24 path.

This does not relax the existing screenshot checks: allowed foreground,
geometry, sensitive fields, session lifetime, exact expected-frame content and
post-capture content checks remain in the original bridge. The experiment is
not wired into production and does not change Kengent's normal builder.

35 repository tests passed, including JVM checks for escaped XML, sensitive
input types, invisible subtrees, missing children, cancellation, resource cleanup
and bounds. Those tests do not establish real App acceptance.

Example (private output directory must not already exist):

```sh
python scripts/build_observation_probe.py \
  --kengent-root /path/to/kengent --sdk-root /path/to/android-sdk \
  --output /private/new-single-pass-build --single-pass
```

## Display-before-attachment comparison

`prewarm_public_app.py` verifies the installed launcher Activity, stops only the
selected isolated test App, launches it once and requires a new main-Activity
displayed event. It never attaches UiAutomation, clicks a dialog or logs in.
Unknown or timed-out launch results are not replayed. Its 240-second overall
deadline and subprocess limits bound the experiment.

After a successful receipt, `probe_public_journey.py --prestarted` attaches the
same guarded native bridge and performs the complete public navigation without
issuing a second launch. Both launch modes are recorded. Activity display alone
is not successful capture; the original three checked image pairs are still
required.


## Single-pass and startup results

The final experimental bridge was
`d39c7d99f11f4a7607bafb3b4a2a3c2f9e3b1286da0eff7373e64eca447574fa`.
An early probe overlapped boot preparation and was explicitly cancelled; it
acknowledged cleanup and is excluded from the comparison. Subsequent probes
were started only after preparation and prior-session cleanup had completed.

- TDX cold process failed before traversal: three foreground-root reads took
  20.230, 20.238 and 23.602 seconds, then reported incomplete hierarchy. Total
  including setup and cleanup was 138.238 seconds. Earlier loading-page walks
  completed in 1.146, 0.462 and 0.377 seconds for 38 nodes; these are not a
  complex-market-page speedup benchmark.
- Junhong cold process likewise failed in foreground-root acquisition before
  the new walker ran. Total was 88.411 seconds.
- The display-before-attachment helper observed a new MainScreen display after
  81.625 seconds. The subsequent guarded journey failed because Android owned
  the foreground. Window metadata confirmed an Application Not Responding
  dialog for Junhong. Its AppwidgetUpdateService ANR event preceded bridge
  attachment. Thus UiAutomation attachment is not required for this ANR to
  occur. No dialog was clicked or bypassed.

The single-pass implementation remains experimental. Its tests demonstrate
bounded traversal behavior, not successful App capture or a measured speedup.

## Native CPU profile and exact broker ANR

A separate single cold launch, without UiAutomation, was sampled for 75 seconds
at 99 Hz using user-mode cycles against the owned emulator process only. Perf
retained 10,092 samples with no lost samples. Self-costs included:

| Symbol | User-mode CPU sample share |
| --- | ---: |
| cpu_get_tb_cpu_state | 10.39% |
| helper_lookup_tb_ptr | 10.34% |
| qht_lookup | 4.51% |
| tlb_set_page_with_attrs | 3.43% |
| regime_el | 3.36% |
| get_phys_addr | 3.22% |

These measure emulator CPU hotspots, not percentages of end-to-end App waiting.
The effective ARM compile command ended in `-O2 -g -DNDEBUG`; there is no evidence
that an accidental `-O0` build caused this sample. Future optimization should
measure translation-block dispatch and address translation, preserving CPU/MMU
semantics and the existing correctness fixtures.

The latest trace contains the **exact main broker process**, not its pushservice.
At the 04:53:15 ANR it was in ART ConditionVariable waiting via
RenderNode.nCreate, called from ImageView construction and XBanner.addPoints.
The process reported about 13.307 seconds running and 24.476 seconds queued;
JIT compilation accumulated 48.368 seconds for 116 compilations. GC total was
11.058 seconds, but total mutator pause was only 267.257 milliseconds and blocking
GC count was zero. These cumulative counters and a single sampled stack do not
prove that JIT or GC alone caused the service ANR.

Raw screenshots, wire receipts, traces and the 42 MB perf recording stay private.
The test Apps were stopped and the isolated console acknowledged shutdown. The
runner recorded return code -10 after shutdown, ended after 1136.21 seconds, and
its PID plus ports 5576/5577 were verified released. No production App, P30,
credential, account binding or Scheduler operation was performed.

## Acceptance

Public navigation and repeated screenshot success must be demonstrated on the
same actual build before considering this experiment for adoption. Full Stock
acceptance additionally requires the managed account adapter, a trusted Context
and a verified test-device binding for complete assets and holdings capture.
No shell credential/account workaround, production binding switch, Scheduler
operation or P30 action is part of this work.
