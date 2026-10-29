# Native readiness window and current collection limits

Date: 2026-10-29, Asia/Shanghai. Follow-up to the
[host-headroom experiment](host-headroom-experiment.md).

## Scope and reproducible option

The existing `NativeSession.start` gives the native process ten seconds to emit
its authenticated ready message after transport startup. An earlier isolated run
emitted that message too late. This experiment adds `--native-ready-seconds 30`
to the public capture/journey diagnostics only. The default remains ten seconds.

`scripts/native_ready_probe.py` copies only the audited `start` method into a
temporary subclass. It requires the exact dedented source SHA-256
`2cc6ea9da6596a45a797038b2b04379cfa56cc00b4da471d27b561f346b5aeb6`,
and requires one unique readiness timeout anchor. The candidate method SHA-256
is `520139913d4eba30cae6587b20607fca5778941ef5ff6e595df925282427f317`.
Source drift aborts the experiment. No production source file is written.

The extra wait is capped by the original lease's remaining lifetime. It changes
neither native identity/nonce validation, input deadlines, snapshot deadlines,
exact-frame checks nor whole-journey bounds. It adds no operation retry or input
replay. Receipts record the option and both source hashes. A diagnostic helper
is not a production deployment or a performance improvement by itself.

Example, only after verifying the owned emulator and prestarted public App:

```sh
python scripts/probe_public_journey.py \
  --kengent-root /path/to/kengent --adb /path/to/adb \
  --run-dir /private/owned-run --artifacts /private/audited-jars \
  --output /private/new-journey --package com.tdx.AndroidNew \
  --prestarted --seconds 300 --native-ready-seconds 30
```

## Live results

The owned emulator-5576 used the same ARM32 symbol-bearing binary, two guest
CPUs, four allowed host CPUs, nice 10, 768 MiB TCG buffer and sibling-prefetch
bridge as the previous run. The volatile foreground/top-app CPU repair was
explicitly applied and verified; normal UID 2000 shell was restored. Official
Apps, their signatures and account/security behavior were unchanged.

| Measurement | Tongdaxin | Junhong |
| --- | ---: | ---: |
| Prelaunch/display/peer-isolation helper | 33.855 s | 75.055 s |
| Native transport startup | 16.878 s | 10.825 s |
| Native ready wait | 9.046 s | 8.146 s |
| Whole public journey including cleanup | 136.316 s | 143.283 s |
| Final result | Chart readiness read timed out | Bound screenshot rejected changed text |

Junhong's peer-isolation check found one restored TDX process. Its one allowed
corrective stop was followed by two absence checks. These helper durations
include setup and isolation; they are not pure Android launch times.

Both native services became ready within the original ten seconds. Therefore
this run does **not** demonstrate a benefit from the optional thirty-second
window, and does not justify changing the production readiness default.

TDX completed public search, exact 600999 result selection and entry into the
chart. Its first chart-read RPC expired after 30.030 seconds. The guest recorded
an incomplete root read taking 5.082 seconds, and a later complete hierarchy
only after the host deadline: 16.065 seconds for that traversal, including
5.202 seconds root acquisition and 9.784 seconds child retrieval. A late guest
result was not accepted as a successful host operation. This is a slow page
observation problem, separate from native startup.

Junhong completed public market navigation, symbol entry and exact 600999 quote
entry. Quote entry took 28.723 seconds. The following XML observation took
10.112 seconds, then its bound screenshot was rejected after 8.354 seconds.
The numeric difference report shows 225 nodes on both sides, three changed text
nodes, no changed structure, bounds, identities or flags, and no clock-only
change. The actual three text values were not retained in the numeric report;
do not assert which quote fields changed. No pixels from this rejected request
were accepted as collection evidence.

The complete hierarchy before that rejected screenshot took 6.869 seconds,
of which child lookup took 6.339 seconds. This reinforces the prior finding
that accessibility traversal is expensive on the emulated guest. It does not
prove that all App latency has one cause.

## CPU helper microbenchmark, not an emulator patch

The previous profile identified `cpu_get_tb_cpu_state` as a hotspot. A separate
private host experiment deferred its output-PC store until after state flags
were computed, leaving the original expressions intact. The extracted functions
used the audited QEMU headers and actual ARM32 `-O2 -g -DNDEBUG` build options.
Original and candidate results matched on 100,000 varied A-profile fixture
states, and neither modified the input CPU state. M-profile helper calls abort
in the fixture; this is not an all-architecture equivalence proof.

Six alternating-order pairs of five million calls gave median baseline/candidate
durations of 69.822/66.152 milliseconds: approximately 5.26% less time for this
isolated function. Extraction changes compiler inlining context, and this is
not a whole-emulator benchmark. No QEMU source, executable or runtime default
was changed on that basis. It cannot be reported as a 5% App speedup.

## Validation and final state

All 88 host tooling tests passed in 5.543 seconds. Six new readiness tests cover
late/no readiness, the remaining-lease cap, wrong owner, expired lease,
cancellation, unchanged defaults and source-drift rejection. The fixtures do
not call a device, platform API or account endpoint.

Both native sessions confirmed cleanup, and the guest process inventory showed
no remaining bridge process. The ANR/event and crash buffers were empty at the
final check; normal UID 2000 shell was verified. The owned emulator was stopped
after 767.35 seconds within its original 1200-second bound. Its PID disappeared
and ports 5576/5577 were free. No P30, Scheduler, production service, Stock
binding, account credential or trade was operated. Raw traces, screenshots,
userdata and the microbenchmark artifacts remain private outside Git.

## Next decision

Do not repeat the same public route with longer startup timeouts as a supposed
fix. Two separate changes need evaluation:

1. Reduce complete accessibility traversal cost and diagnose root-read stalls.
   All hidden descendants still require sensitivity checks; skipping missing
   nodes or accepting an expired read is not a solution.
2. Design an explicit read-only evidence contract for changing market pages.
   Stock currently requires an image to match an earlier full XML tree, whereas
   live values can change during the several-second observation. A future path
   must validate the *captured image's* stock/period/page, preserve sensitive-page
   rejection and provenance, and must not combine later XML prices with earlier
   pixels as if they were atomic. Guarded physical input must retain its strict
   original-observation checks. Existing fresh-image diagnostic passes do not
   by themselves establish this new Stock contract.

Authenticated complete funds/holdings collection also remains unverified and
requires the [managed acceptance ingress](managed-account-acceptance.md). Keep
Stock on its existing device until both actual collection requirements pass.
