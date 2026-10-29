# ARM guest startup and capture comparison, 2026-10-29

Status: not ready for Stock cutover. The latest TDX public journey passed, and
four Junhong process startups with guest ART JIT disabled passed. The latest
public quote journey also passed with a 90-second diagnostic read budget. These
results do not verify
authenticated funds or complete holdings; the trusted managed account ingress
remains required. No production binding, scheduled job or P30 operation changed.

## Unchanged baseline

- RelWithDebInfo ARM emulator, existing isolated API 24 ARM32 AVD, two guest CPUs;
  foreground/top-app CPU sets both `0-1`, four host cores, 768 MiB TCG cache.
- Existing opt-in CheckJNI-off experiment; unchanged APKs/signatures and App data.
- Junhong 9.9.30 already has normal `speed` AOT output, reported `kOatUpToDate`.
  Repeating package compilation is not a new remedy for this startup failure.
- Every command checks the exact owned emulator process/start ticks and dedicated
  serial. No commands target physical devices. All runs have a finite deadline.

## Fresh enabled-JIT baseline

Run: `two-app-repeat-20261029-1820` in the private experiment store.

Junhong was the only test App launched. At 18:22:33 Android reported the main
process ANR while executing `AppwidgetUpdateService`. A later MainScreen display
event does not convert that failed startup into success. TDX had not been started,
so this failure cannot be attributed to concurrent TDX execution.

The first ANR trace copy was incomplete. A delayed copy contains main
`sysTid=1887` waiting for the `LayoutInflater` monitor held by thread 75
(`InitMarketViewPool`), which was inflating themed views. The same fragment lists
the broker's compiled-code paths and ends with process 1887. **Its initial process
header is missing**: the strict exact-process trace validator correctly rejects
it. Treat the matching-thread fragment as a diagnostic lead, not a complete
process/timestamp-verified stack or proof of a permanent deadlock.

ActivityManager's CPU sampling shows substantial JIT work during the failure;
it does not prove JIT is the sole cause. Prior four-CPU and normal AOT experiments
also failed, so neither should be repeated as an untested fix.

## TDX full public journey

After the failed broker was stopped, TDX started once in 28.990 seconds. The
guarded search for 600999, exact-result selection and navigation to 日K completed
in 158.761 seconds, including native session startup/cleanup. All three strict
observe-then-image captures passed unchanged backend checks:

| Checked image | RPC duration | Capture delay |
| --- | ---: | ---: |
| 1 | 7.359 s | 3061 ms |
| 2 | 5.425 s | 1761 ms |
| 3 | 6.263 s | 2983 ms |

Offline replay accepted all six XML/image observations; native session cleanup
was confirmed. Visual inspection of the third image confirms 招商证券 / 600999,
selected 日K, MA/VOL/MACD panels and chart endpoint 2026/10/29. This is after-hours
public market evidence, not an authenticated account report or a current trade
price. One successful repeat does not establish long-term stability.

## Temporary ART JIT comparison

Run: `junhong-art-compare-20261029-1836` in the private experiment store.

The official [Android 7 JIT configuration guide](https://android.googlesource.com/platform/docs/source.android.com/+/4a5bcd6fa800faafbe7272d39266e21dc26edf39/en/devices/tech/dalvik/jit-compiler.html)
describes volatile `dalvik.vm.usejit` changes with a guest framework restart.
This experiment changed that property only on the owned userdebug AVD, dropped
ADB root before testing, then restored the original `true` value and ordinary
shell afterward. No persistent image change or App check bypass was performed.

The first preparation attempt stopped before any App launch because package
resolution was not ready. `service check activity` alone is insufficient after
restarting the guest framework. The corrected readiness check requires the
zygote, boot-complete state and exact package launcher resolution under the same
bounded deadline; it does not repeat launch or input commands.

The subsequent single Junhong startup passed without a new ANR:

- Launch acknowledged at 31.128 seconds from probe start.
- MainScreen displayed at 67.034 seconds.
- Peer-App absence checked twice; startup probe finished at 70.378 seconds.
- Overall configuration/test/restoration comparison: 147.756 seconds.

This is **startup-only** evidence. The global guest property also affects the
Android framework, and the guest/TCG caches were not identically cold between
configurations. Previous enabled-JIT runs have sometimes started successfully.
Do not claim a causal improvement or production fix from this one comparison.
The next useful test is repeated cold startup plus the full guarded broker quote
journey under the same temporary setting, retaining ANR and capture evidence.
Then complete the real managed funds/all-holdings acceptance before cutover.

Both owned instances were stopped through their runner's stop request. Their
PIDs were absent and dedicated ports 5576/5577 released. The second run separately
read back `dalvik.vm.usejit=true` and `uid=2000(shell)` before stopping. Raw XML,
images, ANR traces and receipts remain private and are not committed.


## Follow-up: startup plus full public route

Three further single-launch runs passed startup in 75.884, 68.415 and 74.678
seconds, with the peer test App stopped. These are process/framework restarts in
the same AVD, not independently cold disk/TCG-cache trials. The first full route
failed at its first quote-entry read after 30.030 seconds. A focused 45-second
quote-entry experiment then failed earlier at the market-home read after 30.029
seconds, so it never exercised the longer quote-entry budget.

The subsequent `junhong-nojit-read90` run used the existing 90-second diagnostic
read budget throughout, preserving the same navigation checks, input deadlines
and no-retry-on-unknown behavior:

| Step | Observed duration |
| --- | ---: |
| Market-home hierarchy | 32.813 s |
| First quote-entry hierarchy | 25.753 s |
| Public quote capture 1 | 36.063 s |
| Public quote capture 2 | 37.390 s |
| Public quote capture 3 | 40.030 s |
| Full public journey including cleanup | 253.944 s |
| Setup, startup, journey and restoration | 393.007 s |

Offline audit confirmed three fresh frame references and image/wire consistency.
Visual review confirms 招商证券 / 600999, selected 分时, chart and order book.
The quote's trading timestamp was not verified, so it is not a fresh-price claim.
Native logs locate the main capture cost in two full 322-node hierarchy traversals:
each took roughly 14–19 seconds, mainly 319 child lookups. A separate host sample
during the failed run showed its two busy threads using about 14.6 CPU seconds
each in 20 seconds with only 0.02 seconds queued; host CPU starvation was not the
main delay in that sample.

Crucial limitation: the quote experiment uses a private read-only bridge with
single-pass traversal, sibling prefetch and a dedicated dynamic-quote contract.
The latter verifies identity/period before and after capture but explicitly marks
XML values as non-atomic and removes input authority. Its rejection of input was
verified. It is **not** the strict Stock account screenshot contract and is not a
production Resource Node deployment. No account, password or trade was entered.
The bridge and raw screenshots remain outside Git.

The temporary JIT setting was restored to `true` and ADB to uid 2000. The original
owned runner was stopped; its PID disappeared and both dedicated ports closed.
No P30 command or production Stock binding change occurred.

## Remaining managed-account acceptance prerequisites

The exact owned ARM guest fingerprint was matched to its live resource inventory
entry. At the check it was unapproved, without a lease or operation claim. The
host Resource Node has no ARM timing profile configured. Its credential-input
policy is resource-specific, and no managed account test has established this
new guest's credential route. Existing heartbeat success does not update a
resource's capabilities or login policy.

The diagnostic runner cannot supply an authenticated Stock request context. The
current Codex tool set has neither `application_describe` nor `application_call`;
this is a separate integration prerequisite, not renewed login-consent demand.
Do not manufacture a principal, read a credential file or give generic production
plans access to an unvalidated guest to bypass it.

Before a real account test, establish a managed test-only route to this exact
resource, preserving the existing account authorization and excluding P30 and
production schedules. Reconcile read deadlines across the Resource Node,
Platform and Stock caller (the latter currently stops ordinary calls at 45 s).
The successful 90-second diagnostic setting alone does not configure those layers.
Then collect real funds plus **all** holdings pages, including scrolling, under
the normal strict account contract. Only repeated complete TDX and broker results
justify switching production Stock tasks.
