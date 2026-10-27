# Selective Android Performance Integration

## Intent

Reduce cold-start shader/pipeline stutter in the Android ARM64 port without importing the Windows launcher, PS5 support, Direct3D 12, FSR, or game data from `RenanQueiroz/mcla-recomp`.

## Scope

The first change is a persistent Vulkan driver pipeline cache in the ReXGlue v0.10.0 patch path. It will live below the existing app-private shader-cache root, validate its Vulkan header against the active device, feed valid bytes into `vkCreatePipelineCache`, save atomically after pipeline creation and at shutdown, and expose cache-load/save and pipeline-creation metrics in the existing diagnostics.

The second, separate change is measurement only: pipeline creation time/count, present cadence, and fence waits. Shader preparation, EDRAM upload hoisting, and direct texture loads are deferred until measurements identify their cost on Android.

## Approaches Considered

1. Merge the reference fork wholesale: rejected. It carries desktop and PS5 functionality with incompatible lifecycle and graphics assumptions.
2. Reimplement selected behavior against the pinned ReXGlue source: selected. It keeps Android storage, lifecycle, package, and build paths intact.
3. Read the reference only: rejected because it cannot address cold-cache behavior.

## Design

`scripts/patch_android_rexglue.py` remains the sole mechanism that changes the cached ReXGlue tree. The patch adds a small helper in Vulkan pipeline-cache code that:

- loads only a complete cache file whose `VkPipelineCacheHeaderVersionOne` vendor ID, device ID, and UUID match;
- creates the Vulkan cache with `pInitialData` only after validation;
- uses that cache for the Xenos game pipeline creation path;
- writes to a temporary sibling, flushes, and renames it; and
- never blocks the render thread for file I/O.

The current ReXGlue tree still creates several auxiliary pipelines with
`VK_NULL_HANDLE` (the gamma pass, render-target transfer pipelines, presenter output
effects, and the immediate UI drawer). Those call sites are outside the first cache
patch and must be measured before sharing the driver cache with them. The game cache
also serializes `vkCreateGraphicsPipelines` calls because Vulkan externally
synchronizes access to a `VkPipelineCache`; a per-thread cache/merge design is a
separate optimization and is not assumed to help without lock-wait measurements.

The Android app passes the private cache root already used for shader storage; no public-storage permission, game asset, cache, or log is committed. Tests cover patch anchors and cache-header validation behavior. Device evidence is mandatory before claiming an improvement.

## Acceptance and Risks

Success means the manual ARM64 build succeeds, cold and warm launches log cache state, and an ADB run reaches the game without a Vulkan error. FPS or hitch improvement requires before/after measurements.

The reference repository is GPL-3.0, but this work must not copy its code. Its public descriptions are used only to guide an independent implementation. ReXGlue API drift and driver-specific cache formats remain risks.
