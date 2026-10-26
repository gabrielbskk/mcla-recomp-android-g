# Vulkan/shader review — 2026-10-26

## What is already enabled

The pinned ReXGlue Vulkan backend enables dynamic rendering by default when the
device exposes it (`src/graphics/vulkan/command_processor.cpp`, lines 67–70 in
the external SDK). Android pipeline creation defaults to two worker threads
(`src/graphics/vulkan/pipeline_cache.cpp`, lines 50–62), instead of saturating
all S23 cores. Asynchronous shader compilation is enabled, and Android skips a
presentation that used an incomplete placeholder pipeline
(`src/graphics/vulkan/command_processor.cpp`, lines 58–61 and 2292–2304).

## Evidence and current change

The historical S23 capture recorded a burst of pipeline creation, but the game
remained slow after that burst subsided. It is therefore not proven that shader
compilation is the sole sustained bottleneck.

The Android patch now keeps the driver `VkPipelineCache` dirty bit, saves only
when new pipelines were created, and schedules saves approximately every ten
seconds instead of every second. It also aggregates total microseconds spent in
`vkCreateGraphicsPipelines`. These counters are diagnostic; no FPS gain is
claimed until a device run measures them.

## RenanQueiroz reference review

The Renan repository documents useful Vulkan ideas: asynchronous pipeline work,
parallel shader-storage translation, threaded submission, and render-target
upload/resolve changes. Its published measurements are Windows/NVIDIA or PS5
results, not Galaxy S23/Adreno results. The threaded submission and upload
patches are high-risk while the current Android run has green rendering
artifacts, so they are not copied yet. The next safe experiment is an A/B run
with the same scene and the new pipeline-create totals before changing renderer
semantics.

## Next measurement gate

For each cold and warm run, record presented FPS, frame-time p50/p95/p99,
pipeline count and total pipeline-create microseconds, plus CPU/GPU/fence wait
data where available. Only a measured dominance of pipeline creation justifies
importing the async-pipeline or shader-preparation patch; otherwise investigate
submission, EDRAM resolve/readback, and CPU guest work first.
