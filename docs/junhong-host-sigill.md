# Junhong host SIGILL investigation — 2026-10-28

## Status

Reproduced under GDB in a new, isolated ARM32 AVD on the same Linux x86-64
host. The 16-bit reset-offset overflow is now confirmed with source symbols.
Both the TCG fix and a subsequent deleted-vertex-buffer fix now compile. The
broker ordinary-account landing page renders after the fixes; full account
collection and repeatability validation remain incomplete. The pinned Clang 12.0.5 C/C++ compile-and-link checks and CMake configuration
now pass. The first Debug build completed all 5755 steps in 761.53 seconds;
its ARM32 headless ELF has .debug_info and .debug_line sections. Large official downloads were
completed through directory/file fallbacks and a per-request verified Google IP,
without changing global DNS/proxy settings.
A compiled candidate patch is available, but full application/account acceptance
is not complete. Stock jobs have **not** been switched.

## Baselines

- Failing SDK emulator: 30.5.3, build 7196367, ARM32 headless engine, host GL,
  one guest vCPU, software translation.
- Source baseline: official `emu-30-release` manifest; QEMU commit
  `e106d9eeab3c96db145bc5b59188283acdba3df8`, reporting version 30.7.5.
  This is not proven byte-for-byte equivalent to build 7196367.
- Guest: isolated copy of Android 7 / API 24 ARM32 with the previously tested
  signed WebView 119 installation. Official broker compatibility APK unchanged.
- The modern ARM64 broker APK is a different compatibility target; results here
  must not be reported as its acceptance.

## Observed failure

Open the broker's public home page and then the observed bottom broker navigation.
No account/password input or order action is involved. The host emulator vCPU
thread receives SIGILL with ILL_ILLOPN (`si_code=2`) in anonymous RWX memory.
The surrounding instructions have the translated software-MMU load/store shape.
Both runs stopped on the same byte pattern despite different host addresses.

The second capture includes the bytes before the fault. Relative to the fault PC:

```text
PC-9:   48 03 77 0c       add 0xc(%rdi), %rsi
PC-5:   44 88 16          mov %r10b, (%rsi)
PC-2:   41 83 c5 04       add $0x4, %r13d
PC+2:   45 8b d7          mov %r15d, %r10d
```

The fault PC points at `c5`, **two bytes into a normal four-byte ADD instruction**.
Disassembling from the fault PC instead of the correct boundary produces an
invalid instruction. This is concrete evidence of an instruction-boundary problem;
it is not evidence that the AMD CPU needs an unsupported AVX opcode.

A corrupt/wrong continuation address, generated-code patching, or another control-
flow defect remains a hypothesis. `GETPC_ADJ=2` in QEMU is normally a lookup
adjustment; its matching numeric value alone does not justify changing it.
No instruction was skipped, signal ignored, APK patched, or broker check bypassed.

## Validation status and remaining checks

1. Completed: pinned Debug and RelWithDebInfo builds, with DWARF and compiler/
   source provenance. The initial Debug engine SHA-256 is
   `dfc9ec4554dc3d3616d91932390803bc8031014d9438ea876d2789e373f29403`.
2. Completed: unpatched optimized build reproduced the TCG crash with concrete
   reset-offset overflow; the patched build crossed that failure point.
3. Completed: the next rendering crash was reproduced on both host GL and
   SwiftShader, diagnosed, and fixed with a failing-before/passing-after GL test.
4. Completed public-page checks: broker navigation through the first-login page;
   Tongdaxin market, index daily candles and individual-stock daily candles after
   a cold restart. This is limited UI evidence, not an unattended soak test.
5. Still required: approved managed login and complete current funds/holdings,
   followed by repeated account/market collection. No production switch until
   both applications pass that acceptance check.

## Evidence handling

Raw logs, screenshots, APKs, guest disks, credentials and cores stay in private
local storage. This file contains only sanitized diagnostic facts. GDB exiting
with status zero after printing a signal is not application success.

## Sources

- [Pinned Android Emulator source](https://android.googlesource.com/platform/external/qemu/+/e106d9eeab3c96db145bc5b59188283acdba3df8/)
- [Official build manifest](https://android.googlesource.com/platform/manifest/+/emu-30-release/default.xml)
- [QEMU translator internals](https://www.qemu.org/docs/master/devel/tcg.html)

## Early hypothesis (confirmed below)

The pinned baseline stores generated instruction-end and reset-jump offsets in
16-bit fields but does not reject a generated block exceeding 65535 bytes. The
captured slow-path branch lies about 90 KiB beyond the fault. This makes offset
truncation a concrete candidate, not a proven explanation for this crash. The
diagnostic script now reads code at fault PC + 65536 and, when symbols exist,
prints the last TCG generation offsets without executing inferior functions.

Upstream discussed a related offset overflow in
[QEMU bug 1824853](https://www.mail-archive.com/qemu-devel%40nongnu.org/msg611070.html).
A matching upstream report alone is not sufficient to declare this case fixed.

The initial sequential and interleaved NEON-store candidate programs both passed
on SDK 30.5.3. They do **not** yet reproduce the broker crash and cannot be used
as proof that the proposed overflow fix addresses it. The full broker path
remains the required reproduction. The guest regression is a native executable,
not an APK; it does not access Android accounts or any network service.

## Confirmed root cause and candidate patch

An unpatched `RelWithDebInfo` build reproduced SIGILL on the same broker navigation.
Its SHA-256 is `480dc1ab280c40a58f9943ac15f8258bf2ee94a0e2b772fd2876fa271e099139`.
GDB exposed the generated block and reset metadata:

| Measurement | Bytes |
| --- | ---: |
| Generated block including slow paths | 157696 |
| Correct reset continuation from code-buffer start | 113992 |
| Stored uint16 reset offset | 48456 |
| Lost offset | 65536 |

The reset jump carried a relative displacement of -65536 and landed inside an
unrelated instruction. A further SDK baseline instead raised SIGSEGV from the
same wrong-boundary mechanism. The guest APK is unchanged in both cases.

`patches/0001-tcg-bound-translation-blocks.patch` backports/adapts the upstream
4000-IR-operation soft limit and an actual generated-byte guard. Oversized blocks
are regenerated with half as many guest instructions; the TB cache/hash flags
are preserved. The older fork's target-specific instruction bounds are retained.
The invalid 0xffff reset-offset sentinel is also reserved. A single instruction
that cannot fit fails explicitly even in builds defining NDEBUG.

The patch is based on QEMU commits:
- [IR operation accounting](https://github.com/qemu/qemu/commit/abebf92597186be2bc48d487235da28b1127860f)
- [4000-operation limit](https://github.com/qemu/qemu/commit/9f754620651d3432114f4bb89c7f12cbea814b3e)
- [Explicit translation instruction bound](https://github.com/qemu/qemu/commit/8b86d6d25807e13a63ab6ea879f976b9f18cc45a)
- [Retry oversized translation blocks](https://github.com/qemu/qemu/commit/6e6c4efed995d9eca6ae0cfdb2252df830262f50)

The exact-source patch check passed for all 27 files. The patched symbolized ARM32
binary compiled in 56.38 seconds (incremental), SHA-256
`0268c9d08af1362341afe43881ba64f57a498c31f34088204e2c0be205578df9`.
Ten tooling tests passed. These checks do not yet establish application acceptance.

The unoptimized Debug build reached Android and the broker splash screen but
suffered system ANRs; it is retained as evidence. The optimized symbol build is
used for interactive application regression, with DWARF verified in both builds.

## Post-patch graphics failure

The patched host-GL run passed the prior translation failure point, then stopped
with SIGSEGV on a **rendering** thread in the host `libgallium` (Mesa 25.0.7),
called by `GLESv2Context::drawWithEmulations` / `glDrawArrays`. This is separate
from the vCPU TCG code-buffer failure. The fault address was 0x35c; the rendering
thread has no TCG context. No host driver package was changed.

The same navigation also crashes with bundled `swiftshader_indirect`: the render
thread reaches `memcpy` in its GLES library at address 0x2c8 through the same
translator draw call. This rules out an AMD/Mesa-only explanation. A private,
reversible diagnostic overlay records vertex-buffer state without suppressing
draws, changing the guest APK, or ignoring signals. The source and focused regression were subsequently corrected as described below.
Until the broker page and repeated collection work, production cutover is blocked. App startup
also produced an ANR while the main thread parsed its WebView-domain JSON
configuration; it resumed after one explicit Wait action. This performance issue
is recorded separately from the emulator crash.


## Confirmed deleted-vertex-buffer defect and fix

A bounded diagnostic capture linked the failing draw to a prior deletion in the
same GLES 2 context:

- `glDeleteBuffers` detached local buffer 5 from indexed bindings.
- Attribute 1 still reported legacy buffer 5 and offset 712; its indexed binding
  and global buffer mapping were both zero.
- The host driver therefore received a client pointer `0x2c8` instead of a valid
  VBO offset. The previous run showed the identical mismatch at `0x388`.

The translator maintained two inconsistent views of the same vertex attribute.
The second patch detaches the deleted buffer from the current VAO's legacy
pointer records as well as indexed bindings. It preserves enabled/format state
and the original offset for queries. The existing missing-client-data path can
then temporarily disable an unavailable array rather than dereferencing a guest
buffer offset as host memory. Other VAOs are not cleared; valid client arrays and
live VBOs retain their existing paths. No drawing command is globally suppressed.

A focused upstream GL test failed before the fix (deleted binding incorrectly
reported as 1). After the fix it passes, checking binding=0, enabled=1, retained
offset=8 and an actual green pixel after drawing. It passes using both bundled
SwiftShader and host AMD/Mesa. The standalone fixture uses a GLES 2 context and
initializes EGL before setting its maximum version; earlier fixture setup errors
are retained privately and are not counted as reproduction evidence.

The source patch contains the regression. A 32-file exact-hash validation passed,
as did fresh dry-run, upgrade of an existing TCG-only checkout, and idempotent
reapplication. Eleven Python tooling tests passed. The corrected render library
SHA-256 is `2fda01a1d0d2e1db9670b726d9ee7cec9b40f6a947eaa1751849439b1eacb011`;
the ARM engine SHA remains the TCG-fixed value above. Temporary logging probes
have been removed from the tested candidate.

With both fixes, the real, unchanged broker APK displayed the complete ordinary-
account landing page, including holdings and query navigation, without either
prior host crash. This is a logged-out UI check, **not** verified funds/holdings
capture. ARM software translation is still slow: one navigation command exceeded
25 seconds even though the requested tab appeared later; it was inspected instead
of blindly resubmitted. Production Stock binding, P30, Scheduler and services
remain unchanged.

The holdings entry also opened the broker's first-login flow. It presents a
phone-number/SMS-code registration/login form in this isolated guest, not an
already authenticated trading account. No phone number, SMS request, account ID
or password was submitted. Managed full-account testing additionally needs a
current tenant-app request Context and approved broker binding; neither is
provided to this terminal session. Do not replace that missing managed context
with operator credentials or a guessed account/device binding.

## Bounded application regression and performance

The corrected SwiftShader candidate completed a 1500-second run without either
previous host signal. It displayed broker home, the ordinary-account page,
holdings login choices, and the phone/SMS first-login page. Tongdaxin subsequently
rendered its actual market dashboard. The runner, GDB and emulator inferior were
all verified absent after the deadline; a zero GDB exit alone was not the check.

A second cold start with the host AMD/Mesa backend rendered the Tongdaxin market,
Shanghai index daily candles and China Merchants Securities (600999) daily candles.
The visible chart range ended on 2026-10-28 and included price, volume and MACD.
No credentials, private account values or order actions were used for these public
quote checks. Evidence is retained privately; only these observations are in Git.

Performance remains unsuitable to call production-ready: ARM software translation
saturated the single guest vCPU during startup, with main-thread skipped-frame
messages. A host-GL tap command took 24.25 seconds; other navigation commands ranged
from 9.26 to 21.45 seconds, and UI transitions could complete substantially later
than command return. A screenshot ranged from 1.67 to 8.78 seconds in this sample.
These are observations, not a controlled backend benchmark. The collector must
confirm the actual destination page before its next action; immediate screenshots
can still show the previous screen. Backend switching alone has not removed the
CPU/main-thread bottleneck. The host-GL sample used two low-priority host CPUs and
about 1.9 GiB emulator RSS, with no swap observed at that checkpoint.

The Android clock is already configured for Asia/Shanghai. Its status bar uses a
12-hour display; retained logcat timestamps confirm the corresponding 22:xx hour.
An unnecessary attempt to set the same timezone was rejected by guest SELinux;
no policy change or privilege escalation was made.

The 900-second host-GL cold-start run also ended at its limit without either host
signal, and its GDB/inferior PIDs were verified absent. Junhong cold startup showed
an Android application-not-responding dialog. One visible Wait action recovered
the public home page. The broker tab became selected, but this second run reached
its deadline before a complete ordinary-account page was captured again. That
second broker-page path is therefore **incomplete**, not a repeated pass. The
retained system ANR dump did not include the broker main-thread section, so it
cannot establish a more specific cause than the observed startup/main-thread
performance problem. No ANR threshold, APK, signature or security check was altered.

Acceptance remains partial: public market/daily-chart capture succeeded, emulator
crash regressions passed, but unattended startup and full authenticated account
collection did not. Production Stock bindings, Scheduler and P30 remain untouched.
