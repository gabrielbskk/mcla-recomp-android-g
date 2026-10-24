# Android handoff and remaining evidence gaps

Snapshot: 2026-10-23, based on source commit `0b3954b`. This is a continuation
guide, not a stable-release claim. Read the source at the revision being tested.

## Current state

- C++ static recompilation through ReXGlue v0.10.0, SDL3 and the Xenos Vulkan
  backend. Package in this source: `org.mcla.recomp.openbeta`; Java/JNI namespaces
  remain unchanged. Data is imported through SAF into private `filesDir/game`.
- A historical S23 run passed guest-memory setup and reached car selection.
  That run used `ASharedMemory_create`; successful memfd fallback is not proven.
- Severe stutter, gamepad failure and no obvious preset/resolution effect were
  reported. No controlled capture establishes the cause or a 30 FPS result.
- PR #3 adds accepted-present telemetry; the hosted APK has not been shown to
  contain it. Fence-wait CSV columns still say `unavailable`.
- A partial asset trace continued after a failed `intro720.bik` open. It does
  not establish dispensability of all videos/audio or coverage of all scenes.

Evidence map: [status](../CONTINUITY_SUMMARY.md),
[build history](../build-history/README.md),
[Termux recovery](../performance/termux-build-recovery-2026-10-23.md), and
[Android settings/import](../../android/README.md).

## Build handoff gaps

| Item | Available | Still needed for a fresh checkout |
|---|---|---|
| Native runtime and game integration | `src/`, `config/`, `patches/`, `scripts/` | A pinned SDK/dependency bootstrap and verified patch order |
| Termux toolchain | `cmake/termux-android-aarch64.cmake`, recovered from the local build with paths parameterized | A clean configure/build using it; parsing alone is not a build |
| Host ReXGlue generator | Selection logic in `cmake/HostCodegen.cmake` | Reproducible host-only generator build; the historical wrapper depended on a local JNI stub library |
| Resume workflow | `scripts/resume_android_termux_build.sh:8-23` checks an existing cache | It explicitly cannot bootstrap a fresh cache |
| Present observer | `scripts/patch_android_present_metrics.py` pins SDK commit `f5337cdc947ff6d4c4196737e2c807a48f2a1fc2` | Audit all build entry points: the generic script currently invokes the memory patcher, not this observer patcher |
| Java/resources/APK | Android source and historical dependency versions | Reproducible DEX/resources/manifest packaging, base-APK provenance, dependency closure and signing procedure |

Do not use full Gradle on ARM64 Termux: the documented SDK host tools are
x86-64. Do not solve a host-codegen JNI failure by packaging dummy JNI symbols
into the game. Do not publish the maintainer's keys or binaries to fill a gap.
An independent fork uses its own signing identity and must respect the installed
app's certificate and saves when testing updates.

Historical Java build used API 35, Java 8 source/target, minimum API 26, Commons
Compress 1.28.0, Commons IO 2.20.0 and Commons Lang 3.18.0. These records do not
prove that the next APK packages the same dependency closure.

## What the performance diagnosis does and does not establish

| Hypothesis or statement | Assessment | Evidence needed |
|---|---|---|
| Pipeline compilation is the most likely cause | Plausible, not ranked by measurements | Timestamp/count pipeline creations, compiler work and frame stalls; compare cold and warm runs |
| No explicit VkPipelineCache means everything recompiles every launch | Unsupported inference: implementations can have internal caches | Inspect the resolved SDK/runtime and driver behavior; measure actual compilation |
| CPU work or too few threads limits performance | Unproven; thread count alone is not a diagnosis | Per-thread CPU samples and frame critical path |
| EDRAM resolves/readbacks stall the GPU queue | Plausible, not measured here | Durations and call stacks for submit, readback and acquire separately |
| Audio/VFS locks cause stalls | Unproven | Lock contention and I/O traces correlated with long frames |
| A 4.5 GiB guest backing region consumes 4.5 GiB resident RAM | Not implied by address/backing-file size | RSS/PSS, resident mapping data, faults and memory-pressure events |
| A successful present counter is fake because it is not scanout | It measures accepted API presentations, a useful but narrower metric | Cross-check against display/frame timeline; distinguish repeats, drops and new game frames |
| Resolution appeared unchanged, therefore CPU-bound | Not established: the setting might not reach the actual render target | Verify render-target dimensions and compare controlled scenes |

The observer matches `VK_SUCCESS`/`VK_SUBOPTIMAL_KHR` in
`scripts/patch_android_present_metrics.py:49-55`; timestamps enter
`src/mcla_app.cpp:132-136`. `src/render_metrics.h:83-113` summarizes a rolling
window. `src/mcla_app.cpp:83-102` writes CSV with unavailable fence columns.
Do not average per-window p95 values to obtain a whole-run p95; retain intervals
for that calculation. No specific amount of observer overhead has been measured.

Technical references: [Khronos on internal driver caches](https://www.khronos.org/blog/bringing-explicit-pipeline-caching-control-to-vulkan),
[Vulkan pipeline cache guide](https://docs.vulkan.org/guide/latest/pipeline_cache.html),
and [mmap semantics](https://www.man7.org/linux/man-pages/man2/mmap.2.html).

## Suggested next work, with proof gates

1. Reproduce the native/DEX/package chain and record source, SDK and artifact
   hashes. Match the tested APK to that source. Resolve the licensing question
   in `THIRD_PARTY_NOTICES.md` before treating adapted material as cleared.
2. With the device owner's confirmation, verify effective resolution/preset
   values and presentation telemetry. Capture 20 seconds per identical scene
   at 1080p, 720p and 540p, minimum effects, first and second pass. Record
   temperature/thermal state, governor/device context, GPU driver and V-Sync.
3. Collect per-thread CPU, GPU activity if readable, Perfetto/simpleperf where
   supported, pipeline creation counts and separate fence origins. Record
   permission failures; unavailable counters are not zeros.
4. Use those results to choose a change. Persistent VkPipelineCache in private
   storage is a candidate; validate compatibility, atomic saving, synchronization
   and cold/warm hitch counts before claiming improvement.
5. Investigate gamepad device discovery, SDL events and mapping separately.
   Preserve device-owner approval before testing and demonstrate the fix.

The related-project survey is a dated research lead, not a substitute for these
measurements or a license grant. Raw histories may contain private data; this
public handoff intentionally preserves engineering facts and evidence limits.
