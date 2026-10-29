# Read-only public quote evidence experiment

Date: 2026-10-29, Asia/Shanghai. This follows the
[readiness-window investigation](native-ready-window.md).

## Problem and scope

The existing Stock image path compares the complete current hierarchy against
an earlier observation. On Junhong, live numbers, the rotating bottom index or
the clock can change during the multi-second read. This rejects a legitimate
public quote image even when its stock and page have not changed. Increasing a
startup timeout does not solve that mismatch.

This opt-in diagnostic adds a distinct **read-only public quote** contract to
the private bridge. It does not change the default screenshot contract, official
APKs, App authentication, production Kengent source, deployed APIs, resource
bindings, Scheduler or P30. It is not authenticated account collection and has
not been integrated into production Stock.

The initial diagnostic is deliberately explicit: Junhong, 600999 / 招商证券,
the selected 分时 page and the verified 720 x 1560 portrait layout. The policy
class accepts a six-digit symbol/name, but the diagnostic launcher pins this
public test stock. TDX is not admitted by this contract: its canvas-based stock
identity needs separate image-based validation.

## Checks and permitted changes

`experimental/native/ReadOnlyQuote.java` performs one complete observation,
one screenshot and one complete post-image observation. It retains the existing
native foreground, geometry, complete-hierarchy and sensitive-input checks.
The full projected trees must match, including structure, node identity,
coordinates, flags and all unrecognized text.

Both observations require unique matching stock-code/name nodes, the selected
分时 control, one current-price node and one 五档 node. Foreign packages,
editable fields, password/sensitive observations, incomplete trees, ambiguous
identity and changed layout fail. XML size, depth and node counts are bounded;
DTD/entity declarations and external-resource resolution are refused.

Only these verified fields may vary:

- Known numeric quote fields, with bounded numeric/unit formatting: current
  price, change, summary/detail values, the displayed H-share comparison and
  bottom-index price/change.
- The known bottom-index name, restricted to the explicit public-index list.
- The exact SystemUI clock's time text/description, with time-format checks.

Arbitrary text, stock names/codes, account fields and transaction controls do
not become volatile just because they contain numbers. Any unexpected change
ends the request. No automatic read retry or input replay is added to this path.

The image and the later XML values are **not atomic**. The proof explicitly says
`xml_values_atomic=false`; a consumer must read price/volume from the image,
not substitute the post-image XML's values. The host RPC interval bounds this
diagnostic capture; a receipt completion time is not a verified market quote
timestamp or trading date. These limitations remain relevant to a future Stock
integration.

## No physical-input authority

The diagnostic builder clears the prior native frame reference before a quote
read and calls the capture implementation with `inputObservation=false`.
Returning image provenance therefore does not mint an input observation. Its
proof records `input_authority=false` and contains no `based_on_frame_ref` that
could impersonate the strict original-frame contract. Default navigation still
uses the original exact-frame checks.

The final live negative check requests a tap with the returned quote-image
reference and **invalid negative coordinates**. These coordinates independently
prevent physical input even if the authority check regresses. Only rejection
at the earlier `observation_identity` check counts as success; coordinate errors,
timeouts or a successful response fail the test. The expected rejection ends
the diagnostic native session, which must then confirm cleanup.

## Build and audit

```sh
python scripts/build_observation_probe.py \
  --kengent-root /path/to/kengent --sdk-root /path/to/android-sdk \
  --output /private/new-quote-candidate \
  --single-pass --prefetch-siblings --retry-incomplete-checked \
  --hierarchy-retry-delay-ms 1000 --read-only-quote
```

The tested final bridge SHA-256 is
`95e1defc6fc2c2a5d5486d43d357183ea985bc9055960186bed81024dd0fa346`.
Private build receipts retain original/built source hashes. The probe checks
that the bridge matches its build receipt and the new mode was enabled.

Both public capture and public journey helpers require an explicit
`--read-only-quote`. The full route requires `--package com.guotai.dazhihui`
and `--junhong-page search-quote` (or an already verified quote/result page).
This cannot be combined with the old `--checked` mode. Source files and JARs
are copied into private build output; no live production source is patched.

`scripts/audit_read_only_quote.py` verifies three original request/response
pairs, the new proof, stock/period identity, original JPEG bytes, distinct frame
references, input denial and confirmed cleanup. It uses existing image and
hierarchy decoders offline; it calls no device or platform API. It explicitly
reports `production_stock_acceptance=false`. The old production-replay helper
refuses these new receipts, preventing a diagnostic from being mislabeled as
deployed Stock acceptance. Actual image identity still requires visual review.

## Observed result

The owned emulator used the previous symbol-bearing ARM32 build, two guest CPUs,
four host CPUs, nice 10, 768 MiB TCG cache and the verified volatile foreground
CPU allocation. No QEMU or official App binary changed in this experiment.

First Junhong startup **failed** in 62.283 seconds. Its new ANR event named
`AppwidgetUpdateService`, before the new bridge ran. The retained ANR trace did
not contain the exact Junhong main-process block, so it does not establish the
specific blocking call. Process inspection confirmed allowed CPUs 0-1.

One subsequent warm-host/App launch comparison passed display and peer-isolation
checks in 60.719 seconds. It does not erase the failed first launch or prove a
cold-start fix. The new bridge then completed public market selection, exact
symbol search, quote navigation, three images and the negative input check:

| Operation | Time |
| --- | ---: |
| Native transport / ready wait | 9.806 / 5.710 s |
| Quote entry read | 28.962 s |
| Quote image 1 / 2 / 3 | 22.987 / 17.856 / 20.973 s |
| Whole journey, including cleanup | 182.735 s |

All three original images passed the dedicated offline audit. Visual inspection
of the first and third showed 600999 / 招商证券, the selected 分时 page, graph and
five-level book. The displayed H-share comparison and clock changed across the
images. This does not by itself show which values changed *within* each capture;
that behavior is also exercised by the targeted fixtures. The screenshots were
taken after the mainland close and do not show an explicit trading date. Do not
describe them as verified current intraday execution prices or account data.

The expected `observation_identity` refusal was observed before any input
injection; native cleanup succeeded. The result is a passing prototype of the
new evidence contract, not a passing old strict-frame test and not a measured
speedup. Each image still costs roughly 18-23 seconds.

The complete suite covers 92 host tests, including 25 Java policy scenarios,
missing/incorrect proof, an unchanged default strict mode, one-shot quote
navigation and the negative input check. The real saved hierarchy also passed
an offline replay. No private image, quote receipt, userdata, APK, JAR or raw
ANR log belongs in Git.

## Final state and unfinished work

The final event log retained the one original startup ANR, with no later ANR
added; the crash buffer was empty. No native bridge process remained, ordinary
UID 2000 shell was verified, and the emulator stopped after 1180.43 seconds
within its original 1200-second bound. Its PID was absent and ports 5576/5577
were free. An automatic approval-service timeout delayed the offline audit;
the allowed single retry succeeded. TDX retesting was not started within the
remaining budget and must not be reported as done.

Remaining acceptance: repeatable Junhong cold startup, efficient TDX day-K
capture with verified image identity/date, dynamic market-hours validation,
the explicit production read-only evidence contract, and complete authenticated
funds/holdings/scroll coverage through the
[trusted managed ingress](managed-account-acceptance.md). Keep existing Stock
device bindings unchanged until those requirements pass. P30 was not operated.
