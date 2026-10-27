# Vulkan Pipeline Cache: static audit (2026-10-27)

## Scope

Reviewed the Android patcher (`scripts/patch_android_rexglue.py`), its Python/C++
tests, and the patched ReXGlue v0.10.0 tree at
`mcla-build-deps/rexglue-sdk-full/rexglue-sdk-v0.10.0`. No APK build or device
run was performed for this audit.

## Verified paths

- `src/graphics/vulkan/pipeline_cache.cpp:296-363` creates the Android driver
  cache, validates `headerSize`, `headerVersion`, vendor ID, device ID, and
  `pipelineCacheUUID`, then passes valid bytes as `pInitialData`.
- `pipeline_cache.cpp:365-423` snapshots cache data under
  `driver_pipeline_cache_lock_`, releases that lock before temporary-file I/O,
  and serializes saves with `driver_pipeline_cache_save_lock_`.
- `pipeline_cache.cpp:3691-3703` passes `driver_pipeline_cache_` to the Xenos
  game `vkCreateGraphicsPipelines` call and accumulates wait time for the shared
  cache mutex in `android_vk_pipeline_cache_lock_wait_us_total`.
- `pipeline_cache.cpp:958-1000` stops creation/storage workers before destroying
  the driver cache.
- The harness in `tests/pipeline_cache_save_harness.cpp` proves that a pipeline
  can acquire the cache mutex while a save is doing file I/O, and that a new
  pipeline leaves the dirty bit set for a later save.

## Remaining blockers before a build

The shared cache does **not** cover every graphics-pipeline call in ReXGlue:

| File and lines | Path | Current cache |
|---|---|---|
| `command_processor.cpp:1724-1726,1744-1746` | swap/gamma pipelines | `VK_NULL_HANDLE` |
| `render_target_cache.cpp:4509-4510,4531-4532` | transfer/resolve pipelines | `VK_NULL_HANDLE` |
| `vulkan_presenter.cpp:2673-2674` | guest-output effects | `VK_NULL_HANDLE` |
| `vulkan_immediate_drawer.cpp:675-676,690-692` | UI triangle/line pipelines | `VK_NULL_HANDLE` |

These are likely one-time or per-key auxiliary pipelines, but that is not proven.
The Xenos path also serializes driver-cache access with one mutex, so the two
Android creation workers may still serialize inside `vkCreateGraphicsPipelines`.
Both questions require counters for call-site identity and cache-lock wait time;
changing to per-thread caches before those measurements would be speculative.

## Validation status

- Focused pipeline-cache tests: **14 passed**.
- Full Python suite: **65 passed**.
- `git diff --check`: clean after the last commit.
- No new APK, ADB installation, FPS measurement, or performance claim.

The next justified build is a measurement build that reports Xenos-cache lock
wait time and counts/times the four auxiliary call-site groups. Only those numbers
can establish whether sharing more caches or using per-thread caches is worthwhile.
