# S23 runtime performance analysis — 2026-10-22

Source: exported diagnostics and runtime log `Documents/MCLA Recomp/log-mcla_010.log.txt` from the Samsung SM-S911B, Android 16. No ADB session was used for this review.

## Observations

- Vulkan initialized on the system Qualcomm Adreno 740 driver. The log contains no fatal exception; the exported previous-process reason is `USER_REQUESTED` with status 0.
- The game-frame sample starts at 30.1 ticks/s, then falls to 12.0 and 2.0–4.2 ticks/s; p95 tick intervals rise as high as 1,553 ms. This confirms severe stalls in the guest game loop.
- Process VmRSS rises from about 909 MiB to about 1,680 MiB during the same run. These values are process resident memory, not total Android PSS.
- The log contains 497 `Creating graphics pipeline state` INFO messages during the run, including after the initial warm-up period. A time-bucket comparison shows the pipeline burst aligns with the first slowdown, but later intervals remain at 2.0–4.2 game ticks/s even when only 2–18 pipelines are created per 10-second interval. Pipeline compilation is therefore not enough to explain the sustained slowdown. The draw-call counter reports zero, but ReXGlue's `PROFILE_DRAW_CALL()` calls exist only in its D3D12 command processor; Vulkan never increments that counter, so zero is expected and the metric cannot diagnose Android rendering.
- The exported run was produced by an older binary: it still emits per-pipeline INFO lines and contains no `android thread CPU` samples, although the current source contains the logging-level reduction and thread sampler. The existing log therefore cannot validate those changes.
- The `android perf` render-loop estimate is an ImGui/UI-loop estimate. It is not the number of frames successfully presented by Vulkan and does not contradict the much slower game-frame samples.

## Change made

The Android ReXGlue patch now logs per-pipeline creation details at DEBUG level while retaining INFO on desktop. This reduces high-volume formatting and log writes during pipeline warm-up. Pipeline creation itself is still expensive, so this change is a small overhead reduction and is not claimed to fix the 1–4 tick/s stall.

The Android FPS overlay now distinguishes UI render-loop FPS from guest game-loop ticks per second. The guest rate is smoothed from the timer hook and shown as unavailable if no game tick arrives for two seconds. This prevents the fast ImGui loop from being presented as the game's frame rate.

The guest timer hook no longer reads the ReXGlue draw-call snapshot counter on every game tick. That counter stayed at zero throughout the exported session, so it added hot-path work without providing usable data. The periodic game-frame sample now reports only measured tick rate and interval percentiles.

The runtime's VmRSS rises from about 888 MiB to 1.6 GiB as the guest loop drops from 30.1 to 2–4 ticks/s. ReXGlue tracks texture-cache allocation sizes through VMA, but that estimate was not emitted in the exported log. The Android SDK patch logs the estimate, cache entry count, and soft/hard limits every 10 seconds. The separate `rexgpu-xenos` plugin target is now compiled with that diagnostic, confirmed in the plugin ELF. Comparing it with VmRSS will help distinguish texture-cache growth from other allocations; the values measure different things and VMA allocation size is not process RAM or total GPU memory. This is diagnostic instrumentation, not a claimed FPS optimization.

Cppcheck 2.22 analyzed all 14 project C++ source files with Android enabled. It found only `uninitMemberVarNoCtor` warnings for structs populated with aggregate initialization; source inspection confirmed those fields are supplied at each construction site. No null-pointer, bounds, or performance warnings were reported. This is static analysis only, not a native Android build.

## Build-station audit

The Void Linux notebook has CMake 4.2.2, Ninja 1.13.2, Clang/LLD 21.1.8,
OpenJDK 21, pkg-config, and Cppcheck 2.22. Its hardware is 1.9 GiB RAM, 4 CPU
cores, and 4 GiB swap, with 400 GiB disk space free at the latest check. It is
useful as a repository and Drive staging host, but remains a poor place for the
full native compile. Termux on the S23 now has the Android sysroot, CMake,
Ninja, Clang, and the initialized ReXGlue SDK. The Android ARM64 `libmain.so`
and the separate `librexgpu-xenos.so` plugin both compiled there on
2026-10-22. Their ELF metadata and hashes are recorded in
`s23-native-build-2026-10-22.md`. This is compile/link validation only. No APK
was generated or installed, and the installed runtime logs are from an older
binary, so the latest source changes have no runtime FPS validation yet.

## Next investigation

The Vulkan backend passes `VK_NULL_HANDLE` as the `VkPipelineCache` argument to
`vkCreateGraphicsPipelines`. ReXGlue's persistent Xenos shader and pipeline
description storage therefore does not provide a persisted Vulkan driver
pipeline cache. The run's 497 pipeline creations align with the initial
slowdown, but later intervals remain severely slow after pipeline creation
subsides. A pipeline cache could reduce repeat-start shader/pipeline work; it
cannot explain or be claimed to fix the sustained 2–4 ticks/s. Before changing
shared Vulkan synchronization or cache lifetime, the next diagnostic should be
a run of the current native libraries with the per-thread CPU and texture-cache
memory sampling enabled. The current plugin contains the cache sampler, but
the old exported logs predate it. The ADB endpoint last supplied by the user
refused connections, so no fresh process log was available. Do not package or
install an APK for this step.

## Current static audit — 2026-10-22

Cppcheck 2.22 analyzed all 14 app C++ source files with Android and AArch64
predefined. It reported no project-source null dereference, bounds, or
performance diagnostics. The sole remaining project-source diagnostic is
`duplInheritedMember` for the `FallbackAudioSystem::Create` static factory,
which intentionally provides the Android fallback factory with the same name
as the inherited SDL factory. Other warnings came from SDK headers (aggregate
initialization, compatibility casts, and similar upstream declarations), not
from the app source. This is static analysis; it does not replace a fresh
runtime capture from the current binary.

## Performance preset adjustment — 2026-10-22

The Android Performance preset now sets pedestrian and parked-car density to
zero instead of 25%; the Android defaults match, and the development density
A/B switch tests the same reduced setting. This removes ambient pedestrian and
parked-car populations that add guest simulation and draw work. The existing
settings menu still lets players restore either population. The change was
compiled into `libmain.so` with the S23 Termux Android build; the 77 MiB ELF
has SHA-256
`a872e33f66707b905dfcbee94a14a4db72d7475c0f4059856727541b30d40171`.
This is a targeted optimization hypothesis, not a measured FPS gain. The
current ADB endpoint refused connections, so the installed older runtime
cannot validate this source change yet. No APK was produced or installed.

No APK was generated or installed as part of this analysis.
