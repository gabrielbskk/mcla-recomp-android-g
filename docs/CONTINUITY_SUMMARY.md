# MCLA Recomp Android — Project Status

Updated 2026-10-26. This document summarizes the Android ARM64 project state and distinguishes user reports from measurements. Changes on an unpublished development branch are not evidence about the APK currently installed or hosted.

## Current Open Beta

- Android package: `org.mcla.recomp.openbeta`; version `0.1.2-experimental`; ABI `arm64-v8a`.
- The app imports a user-provided ZIP or extracted folder into app-private `filesDir/game`. The APK does not include game data. Uninstalling removes imported data and private saves.
- A user test reached car selection. An I/O-trace capture records an unsuccessful open of `intro720.bik`, followed by continued execution. No `nxeart` or `root_directory_padding.pad` open was recorded in that capture. These observations cover only that run.
- The maintainer reports severe stutter and low performance. The development branch replaces draw-callback counting with timestamps for successful Vulkan queue presentations (`VK_SUCCESS`/`VK_SUBOPTIMAL_KHR`), but that source change has not yet been rebuilt or tested on-device. It measures API presentations, not independent display scanout. There is no verified 30 FPS result.
- The latest user test reports that gamepad input was not recognized and that graphics preset/resolution changes were not visibly confirmed. These are unresolved issues.
- Testing has centered on one Samsung Galaxy S23 running Android 16. Other devices and GPU vendors are unvalidated.

## Runtime and Data Import

The launcher uses Android's Storage Access Framework for ZIP or folder selection, then imports the five validated files into private app storage. ISO extraction is not implemented; extract an Xbox 360 ISO elsewhere and import the resulting folder or ZIP. Runtime logs remain private until the user explicitly exports them.

A later I/O-trace run passed guest-memory setup and reached car selection after the earlier V8 setup failure. The observed run used `ASharedMemory_create`; a successful `memfd_create` fallback and complete memory-failure matrix are not proven. No claim is made that every game scene or optional video file has been validated.

## Performance and Compatibility

Graphics presets and resolution settings are present in the launcher/runtime configuration, but the latest user report did not observe a clear visual difference. The development-branch performance log records presentation timing, while submit/readback/acquire fence-wait columns remain unavailable. No controlled resolution sweep or cold-versus-warm run has established a bottleneck or gain. Treat prior guest-tick and draw-callback values as distinct from presented-FPS measurements.

Vulkan support and gameplay have not been validated across Mali, Xclipse, or older Adreno devices. A system-driver fallback exists in the code, but universal compatibility is not established.

## Development branch: Vulkan driver pipeline cache

Commit `709f7d6` adds a patcher-driven `VkPipelineCache` for the pinned ReXGlue v0.10.0 tree. It stores the cache below the existing app-private shader-cache root, validates `headerSize`, `headerVersion`, `vendorID`, `deviceID`, and `pipelineCacheUUID`, uses the cache for graphics-pipeline creation, and writes through a temporary sibling followed by rename. Cache access is serialized because Vulkan pipeline-cache host access is externally synchronized. Invalid or truncated data falls back to an empty cache without deleting the prior valid file.

The storage-writer thread emits aggregate keys `android_vk_cache_loaded`, `android_vk_cache_rejected`, `android_vk_cache_saved`, `android_vk_pipelines_created`, and total pipeline-creation microseconds at approximately ten-second intervals when the cache is dirty and at shutdown. These are diagnostic counters, not FPS measurements. The Python suite passes 51 tests, including six cache-patcher tests. The native Android build and S23 cold/warm measurements have not yet been completed; no performance gain is claimed.

## Build and Contribution

The project uses C++ generated from Xbox 360 PowerPC code with ReXGlue, SDL3, and a Vulkan Xenos backend. The Android build depends on a separately supplied ReXGlue v0.10.0 tree and legally obtained user game files. See [`android/README.md`](../android/README.md) for the documented ARM64 workflow and constraints. Do not commit game data, APKs, signing material, private logs, or device-specific credentials.

The root README describes this fork's Android scope. Earlier Rust, Windows, Linux, and PS5 work is retained only as historical context in `docs/build-history/` and `docs/OTHER_PLATFORMS_HISTORICAL.md`. The dated related-project survey in `docs/research/` is reference material, not evidence of MCLA performance or permission to reuse third-party code.
