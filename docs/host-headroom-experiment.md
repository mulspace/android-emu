# Host CPU headroom and native startup experiment

Date: 2026-10-29, Asia/Shanghai. Follow-up to the
[four-CPU experiment](cpu-allocation-followup.md).

Only the owned emulator-5576 was operated. The same official Apps, existing
isolated userdata, ARM32 symbol-bearing emulator, 768 MiB TCG buffer, two guest
CPUs, disabled JNI diagnostics and sibling-prefetch JAR were used. Tongdaxin's
previous standard `speed` compilation remains part of this baseline. No account,
P30, production service, Scheduler or Stock binding operation was performed.

## Hypothesis and actual allocation

The earlier two-vCPU runs also confined ordinary emulator threads to two host
logical CPUs. This test allowed four host CPUs (12-15), keeping two guest CPUs
and nice 10, to check whether renderer/transport thread contention explains the
delays. These host CPUs belong to distinct physical cores; the original 14/15
pair was not a pair of SMT siblings. Host load/pressure was low at setup.

The first guest allocation helper invocation was explicitly a dry run: App CPU
sets remained CPU 0. A public Junhong startup completed display and peer-isolation
checks in 70.553 seconds. This is retained as an uncorrected observation, not
silently mixed with the corrected comparison. The subsequent explicit apply
verified foreground/top-app 0-1 and ordinary UID 2000 shell restoration in
20.294 seconds. No persistent image or APK modification was involved.

With corrected App CPU allocation, Junhong display was observed at 53.015 seconds
and startup plus peer-isolation completed at 57.330 seconds. These are helper
elapsed times, not exact ActivityManager launch durations. Neither startup
reported a new ANR. The tiny sequential sample and warmed caches do not establish
a causal speedup.

## CPU evidence

The new `scripts/sample_emulator_threads.py` reads only the verified direct
emulator's `/proc/PID/task` metadata for 1-60 seconds. It checks original process
identity on every interval, separates reused thread IDs, excludes intervals with
missing endpoints and fails on backwards counters. It does not issue device
commands. Raw reports remain private. Requested CPU affinity/nice are now also
recorded by future `run_debug.py` launches.

In a 30-second corrected-start sample, the two heaviest threads ran for
25.463/24.597 seconds and waited runnable for only 0.020/0.029 seconds. During
public navigation, they ran for 23.448/23.435 seconds and waited for
0.111/0.114 seconds. This argues against host scheduling wait as the dominant
cost for these two threads in these intervals. Other threads had different wait
times; it does not prove all latency is CPU execution.

The GPU driver independently expanded several renderer-thread affinities to
4-7,12-15. Requested launcher affinity is therefore not a guarantee for every
driver-created thread; the sampler records actual per-thread masks. No driver or
system scheduling setting was changed.

A separate 15-second `perf stat` sample measured 1.775 host CPUs used, 3.724 GHz
and 373863 context switches. A bounded 49 Hz cycle profile during the later TDX
native-start attempt attributed 12.44% to `cpu_get_tb_cpu_state`, 5.53% to
`helper_lookup_tb_ptr`, 3.12% to `get_phys_addr` and 2.12% to
`tlb_set_page_with_attrs`. It lost no samples. These are sample attributions,
not proof that removing any function produces an equal speedup. The actual
build is RelWithDebInfo, `-O2 -g -DNDEBUG`; unoptimized Debug compilation is not
the explanation. No ARM state, memory-permission or translation check was
removed based on this profile.

## Actual App checks

- Junhong reached the public 600999 quote. Its XML observation took 8.301 seconds;
  the following image request rejected changed content before capture after
  11.136 seconds. Whole journey: 140.579 seconds, native cleanup confirmed.
  This is a failed original-frame-bound capture, not account acceptance.
- TDX startup/display/peer-isolation checks completed in 42.234 seconds. Android
  had restored two Junhong processes; the existing bounded helper stopped them
  once and verified absence. The TDX native transport took 15.236 seconds, then
  missed the unchanged 10-second native-ready deadline (10.010 seconds).
  The journey stopped before page input. Whole probe including confirmed cleanup:
  67.249 seconds. No day-K capture passed in this attempt.

Increasing host CPU headroom did not establish repeatable collection. Neither
the previous-frame check nor startup/input deadlines were relaxed. These results
do not justify changing production defaults or switching Stock tasks.

## Self-owned bridge compilation diagnostic

The two content-addressed diagnostic JARs had no adjacent ARM odex files. Android
7's [ART OatFileAssistant](https://android.googlesource.com/platform/art/+/android-7.0.0_r1/runtime/oat_file_assistant.cc)
supports finding and validating precompiled files; merely finding no adjacent
file does not establish that no other cache exists or prove interpretation is
the startup bottleneck. A bounded, reversible test uses the guest's own dex2oat
on these self-owned JARs only, after exact SHA-256 readback, with their original
classpath and normal shell permissions. Official Apps and their signatures,
authentication, SELinux, frame checks and broker data remain unchanged.

The first JAR compilation hit its preset 100-second guest timeout (100.548
seconds including transport, exit 142). The second was not attempted. No
post-compilation capture was claimed. The guest process inventory then confirmed
no dex2oat process remained. Only this test's new sidecar and two empty cache
directories were removed; exact readback verified both original JAR hashes were
unchanged. This did not establish an AOT startup improvement and is not enabled
as a runtime default.

## Final state

All native sessions confirmed cleanup. The full App ANR/event and crash buffers
were empty at the final check, and ordinary UID 2000 shell was restored. The owned
emulator stopped deliberately after 1123.31 seconds within its original 1200-second
bound. Its PID was absent and both 5576/5577 ports were free. No diagnostic process
or temporary compiled sidecar was intentionally left running or enabled.

82 host tooling tests passed in 5.529 seconds, including four new scheduler-sample
tests for disappeared/reused threads, identity parsing and counter regression.
Only sanitized source, tests and findings belong in Git; raw perf data, screenshots,
JARs and logs remain private. No Kengent source was changed during this experiment.

The next technical investigation should target ARM execution-state/translated-block
lookup costs and the native JVM/service startup path using these bounded profiles,
not assume a larger host CPU allocation fixes either. Public collection still
needs repeatable passing journeys. Complete authenticated funds/holdings remains
unverified and still requires the [trusted managed acceptance ingress](managed-account-acceptance.md).
Do not switch Stock tasks on these results.
