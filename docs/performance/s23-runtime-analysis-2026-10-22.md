# Historical Runtime Performance Analysis — 2026-10-22

This analysis describes one exported runtime log from an older build tested on a Samsung Galaxy S23 running Android 16. It does not measure the current Open Beta.

## Observations

- Vulkan initialized on the system Adreno 740 driver. The captured log contained no fatal exception and recorded a user-requested process exit.
- Guest game-loop samples started near 30 ticks/s, then fell to 12 and later 2–4 ticks/s; p95 tick intervals reached about 1.55 seconds. This indicates severe stalls in that run.
- Process resident memory rose from roughly 0.9 GiB to 1.6 GiB. These are process RSS values, not total Android PSS or total GPU memory.
- Hundreds of graphics-pipeline creation messages appeared. Their early burst coincided with slowdown, but the game remained slow after pipeline creation subsided. Pipeline compilation alone did not explain the sustained slowdown.
- The old `android perf` estimate measured the ImGui/UI loop, not successful Vulkan presentation. Guest timer ticks and UI draw callbacks are not presented FPS.

## Changes Recorded After That Capture

The Android ReXGlue patch lowered per-pipeline creation details to DEBUG while retaining INFO on desktop. The overlay separated UI/draw-callback rate from guest timer ticks, and the guest timer stopped reading a draw-call counter that did not advance on the Vulkan backend. These changes were intended to reduce logging overhead and make diagnostics less misleading; no FPS gain was measured.

A separate texture-cache diagnostic was added to report VMA allocation estimates, cache entry count, and soft/hard limits periodically. VMA allocation size differs from process RAM and total GPU memory. This is instrumentation, not a measured optimization.

Static analysis of the earlier C++ snapshot found no project-source null dereference, bounds, or performance diagnostics. That static check does not replace runtime testing or validate later code.

## Current Status

The current Open Beta still has user-reported severe stutter. Its overlay counts draw callbacks rather than Vulkan presents, and no verified 30 FPS result exists. See the [current project status](../CONTINUITY_SUMMARY.md).
