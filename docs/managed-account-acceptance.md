# Managed emulator acceptance handoff

Status on 2026-10-29: blocked before authenticated account validation. Public
navigation and cold startup remain intermittent; this handoff does not certify
compatibility, grant access or change any production binding.

## Correct ingress prerequisite

The host CLI currently has no configured authentication profile, the unauthenticated
console /v1/auth/me request returns 401, and this desktop session has no tenant-app
adapter. These are observations of missing ingress, not reasons to read stored
credentials directly.

A previous suggestion that supplying a CLI approval chat name would be sufficient
was too broad. The source distinguishes three interfaces:

- app/cli/lang.py login is a Lark-approved chat CLI flow under
  /v1/chat-agent/auth/login-requests and /v1/chat-agent/auth/me.
- The HTTP Gateway /v1/auth/me uses its own authenticated console session.
- tenant-app application_describe/application_call requires the current opaque
  request_context_id supplied by a trusted active tenant turn. Its server resolves
  and checks the canonical Context, tenant/workgroup/principal, roles and original
  response IO. A standalone CLI token is not that Context ID.

Use an already authenticated Kengent console to initiate a task in the previously
approved user/workgroup, or attach its properly scoped managed App transport.
Do not ask for passwords, token strings, cookies or a manually composed Context.
The existing same-account broker-login consent remains valid; the missing item is
the trusted invocation path. This follows the repository's authoritative
external/lang-knowledge/skills/android-stock-screen/SKILL.md.

## Before any device operation

Use authenticated inventory and binding reads to verify the exact approved test
emulator is online, has the two required packages and has no conflicting lease.
The diagnostic emulator-5576 and an earlier separately registered emulator must
not be assumed to be the same resource merely because their App names match.
Resolve the exact current fingerprint/resource revision using the managed path.

Both broker and phone-chart jobs select devices through labels, not through an
ADB serial in a job body. Verify that every eligible resource matching the
chosen labels is the intended test emulator. Generic package-installed labels
can also match P30 and are insufficient. Missing, ambiguous, offline or
non-test bindings stop this handoff before job submission. Do not queue an
unresolved selection: current device acquisition can otherwise wait up to an
hour for a resource. Do not create or alter production bindings to make a test
request pass. Any required test registration/binding is an explicit scoped
administrator configuration step, not guessed input to a model tool.

The complete immutable broker binding must already authorize the account,
credential, account action, test-device labels and login policy. Resolve its
exact binding_ref and expected_version from the approved scoped document. Keep
all credential values, account suffixes and device internals out of the request.

## Read-only account job

First discover startStockBroker through application_describe using the trusted
request_context_id. With the confirmed binding reference/version, its action is:

```json
{
  "kind": "account",
  "coverage": "holdings_pages",
  "max_pages": 8,
  "login_policy": "once_if_required"
}
```

This is only the action member of StockBrokerInput, not a complete executable
submission. Its other required fields are binding_ref and expected_version.
Submit once with a stable idempotency key for that exact approved intent. The
native App reuses the existing login consent and permits at most one login when
positive evidence says it is required. Challenges, missing account selection or
uncertain input stop; do not enter account data through shell or generic input.
Do not precede this with a second login job.

Return the accepted run ID/status once and let native terminal delivery handle
completion. On an explicit later status request, use getStockBroker and retained
getStockBrokerReport/getStockBrokerEvidence/getStockBrokerImage. These GETs do
not reoperate the device. Task cancellation is not a broker order cancellation.
No prepare/submit/order intent is part of this test.

Verify actual private evidence for total assets, securities value, available cash,
all holdings including the final scrolled row, costs, quantities, sellable shares,
quote/capture timestamps and complete page coverage. A queued run, logged-in page,
partial list, empty numeric defaults or public chart cannot prove this acceptance.
Never send account screenshots or report links to a guessed group/channel.

## Actual phone chart job

Discover startStockPhoneChart in the deployed contract. It accepts symbol, explicit
periods, device_labels and timeout_seconds. For the diagnostic public symbol
600999, periods=["daily"] requests the phone's 日K page; the labels must be the
verified emulator-only selection above. The documented timeout range is 30..600
seconds. Do not silently use ordinary Stock production defaults or run a general
AI analysis as a substitute for a chart capture.

Completion evidence is the original retained phone image and evidence manifest,
with the actual symbol, period and market date checked, native observation/frame
binding intact, and lease cleanup verified. getStockPhoneChartEvidence and
getStockPhoneChartImage are the retained read paths. Formula-rendered charts and
fresh unbound diagnostic screenshots are not interchangeable with this contract.

## Contract provenance and cutover

These operation/schema names were read from the local source contract
external/apps/stock/api/bundled/stock.json, SHA-256:
`a1d7defb65558752974456aa7621dac30f9d32187cc28afc3ea92030575442eb`.
This is source evidence only; discover the deployed schemas before execution.

Neither read-only job mutates the daily schedule or production selection. Keep
P30 and scheduled Stock work unchanged while validating repeated cold starts,
page navigation, current chart collection, complete real account collection,
lease release and explicit failure handling. Only confirmed stable success of
both Apps allows the separately verified Stock-device cutover. Until then the
full replacement goal remains unachieved.
