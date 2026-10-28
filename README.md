# android-emu

Reproducible Android Emulator source builds and focused compatibility fixes for
Linux x86-64 hosts. Upstream sources are fetched at immutable revisions; local
patches, build tools and sanitized findings are maintained in this repository.

## Current objective

Diagnose the host SIGILL observed with Android Emulator 30.5.3 (build 7196367)
while an unmodified Junhong ARM32 compatibility APK opens its broker page.
Tongdaxin public quotes and daily candles already worked in the isolated test.
This does **not** establish complete broker-account collection or readiness for
production cutover.

The public `emu-30-release` manifest is the initial build baseline. Its pinned
source is **not claimed to be the exact source of build 7196367**. Each binary's
source revision, compiler, options, and symbols must be recorded for comparison.

## Build

Requires Linux, Python 3.12 or newer, Git, curl, standard C/C++ build utilities, and ample disk
space. Compiler/CMake/Ninja dependencies come from the pinned upstream manifest.
Use a separate local working directory, preferably outside the application repo.

```sh
python3 scripts/sync_archives.py --workspace /path/to/local/work
python3 scripts/build_debug.py --workspace /path/to/local/work --jobs 2 --host-cpus 0,1
```

For the reviewed TCG and deleted-vertex-buffer fixes, with debug symbols:

```sh
python3 scripts/apply_patches.py --workspace /path/to/local/work --check
python3 scripts/apply_patches.py --workspace /path/to/local/work
python3 scripts/build_debug.py --workspace /path/to/local/work --build-type RelWithDebInfo --jobs 2 --host-cpus 0,1
```

The patch helper checks every changed source file before writing, rejects mixed
or unrelated changes within a patch set, and shares a lock with the build. An
existing TCG-only checkout can safely receive the later GLES patch without
reapplying the first patch. Debug and
RelWithDebInfo use separate output directories. Receipts record patch state and
binary and renderer-library hashes; raw build trees and app evidence are never committed.

Compilation and diagnostic execution are bounded processes. Builds use limited
parallelism and reduced scheduling priority. No script starts an App, accesses a
physical phone, invokes a scheduler, or changes a production binding implicitly.

## Isolation and evidence

- Use one explicitly named disposable/isolated AVD and a dedicated loopback port.
- Preserve original system images and official APK signatures. Do not modify
  broker checks or substitute account credentials.
- Live account operations require the existing managed identity, binding and
  authorization. App startup and an empty unlogged-in holdings view are not
  account evidence.
- Keep userdata, APKs, credentials, raw logs, screenshots, cores and build output
  local. Do not commit or push them. Findings in `docs/` must be sanitized.
- Production cutover requires repeatable market capture **and** complete broker
  funds/holdings capture. Do not affect an existing physical-device workload.

## Upstream licensing

The fetched QEMU/Android sources retain their original licenses and notices.
This repository's glue scripts are Apache-2.0; patches to upstream files follow
the corresponding upstream file license. Distribution of a compiled emulator
requires preserving the applicable upstream source and license obligations.


## Validation and progress

```sh
python3 -m unittest discover -s tests -v
```

The focused graphics regression builds a host test and checks deleted-buffer
bindings, preserved attribute state, and actual output pixels. It accesses no
Android device or account and terminates its owned process on timeout:

```sh
python3 scripts/run_graphics_tests.py --workspace /path/to/local/work --host-cpus 0,1
# Optional cross-check using the explicitly supplied DISPLAY/XAUTHORITY:
python3 scripts/run_graphics_tests.py --workspace /path/to/local/work --gpu host --host-cpus 0,1
```

Read [the current crash investigation](docs/junhong-host-sigill.md) before using
this repository. Symbolized source builds are complete and the TCG offset-overflow cause is
confirmed. Application/account acceptance remains unfinished; a successful
tooling test alone does not establish it. Archive receipts record the official
commit URL and local SHA-256, not an independently signed artifact. Existing
source directories are preserved and must not be silently replaced on resync.
For a large archive that repeatedly fails, use the verified-file fallback:

```sh
python3 scripts/sync_gitiles_tree.py --workspace /path/to/local/work \
  --project prebuilts/clang/host/linux-x86 --subtree clang-r416183b --files
```

It resumes verified files, checks each direct blob against the official Git object
ID, and reports incomplete paths without marking the project successful.

For a broken fake-IP DNS/proxy route, `sync_archives.py --resolve-ip <verified-public-IP>`
changes only curl's destination for the original HTTPS hostname. Obtain the current
IP from a trusted DNS source. Certificate verification remains enabled; this does
not change system DNS or proxy services. Do not hard-code an old address in the lockfile.
