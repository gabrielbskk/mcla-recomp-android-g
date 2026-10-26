# Android Vulkan Pipeline Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist and safely reuse the Vulkan driver pipeline cache across Android launches, with diagnostics that permit cold-versus-warm measurement.

**Architecture:** The existing ReXGlue patcher remains the only writer of SDK files. It will insert self-contained cache-file handling into the SDK Vulkan pipeline cache: validate device metadata, initialise `VkPipelineCache` from valid bytes, save atomically on its storage writer, and publish counters through the project’s existing diagnostics path.

**Tech Stack:** Python patcher/tests, ReXGlue v0.10.0 C++, Vulkan, Android private app storage, Termux ARM64 manual build.

**Spec:** `docs/superpowers/specs/2026-10-26-renan-selective-android-design.md`

## Global Constraints

- Do not copy reference-fork code; independently implement against the pinned ReXGlue v0.10.0 API.
- Never commit game data, caches, APK/XAPK/OBB, keys, or personal logs.
- Keep cache files under the existing private shader-cache root; no broad-storage permission.
- Do not claim a performance gain without an ADB cold/warm measurement.

## Review Focus

- Corrupt, truncated, or foreign-device cache files must fall back to an empty cache.
- A failed cache write must not prevent rendering or destroy the prior valid cache.
- Cache I/O must not block the graphics submission/render thread.
- SDK patch anchors must fail closed if ReXGlue v0.10.0 source differs.
- Cache metrics must distinguish loaded, rejected, saved, and newly created pipelines.

---

### Task 1: Specify and test cache patch anchors

**Files:**
- Create: `tests/test_android_pipeline_cache_patch.py`
- Modify: `scripts/patch_android_rexglue.py`

**Interfaces:**
- Produces `patch_android_vulkan_pipeline_cache(source: str) -> str`.

- [ ] **Step 1: Write failing unit tests**

Test that a representative ReXGlue pipeline-cache source gains header validation, `pInitialData`, `vkGetPipelineCacheData`, temporary-file rename, and idempotence; test unknown source fails closed.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m unittest tests.test_android_pipeline_cache_patch -v`

Expected: FAIL because the patch function is absent.

- [ ] **Step 3: Implement the minimal patch function**

Add exact, single-occurrence source anchors and replacement text in `scripts/patch_android_rexglue.py`. The injected C++ validates `VkPipelineCacheHeaderVersionOne` before supplying initial data and uses an atomic temporary sibling plus rename for writes.

- [ ] **Step 4: Run focused and full Python tests**

Run: `python -m unittest tests.test_android_pipeline_cache_patch -v && python -m unittest discover -s tests -p 'test_*.py' -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/patch_android_rexglue.py tests/test_android_pipeline_cache_patch.py
git commit -m "feat(android): persist Vulkan pipeline cache"
```

### Task 2: Integrate cache instrumentation with existing diagnostics

**Files:**
- Modify: `scripts/patch_android_rexglue.py`
- Modify: `tests/test_android_pipeline_cache_patch.py`
- Modify: `docs/CONTINUITY_SUMMARY.md`

**Interfaces:**
- Consumes `patch_android_vulkan_pipeline_cache` from Task 1.
- Produces SDK log keys `android_vk_cache_loaded`, `android_vk_cache_rejected`, `android_vk_cache_saved`, and `android_vk_pipelines_created`.

- [ ] **Step 1: Write failing tests**

Assert the injected source increments/logs each cache state and emits pipeline creation count without changing normal rendering control flow.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m unittest tests.test_android_pipeline_cache_patch -v`

Expected: FAIL for missing metric markers.

- [ ] **Step 3: Implement minimal instrumentation**

Add aggregate counters in the SDK storage/pipeline-cache path and periodic log snapshots on the existing non-render writer path. Document the exact log keys and that they are evidence, not FPS.

- [ ] **Step 4: Run focused and full tests**

Run: `python -m unittest tests.test_android_pipeline_cache_patch -v && python -m unittest discover -s tests -p 'test_*.py' -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/patch_android_rexglue.py tests/test_android_pipeline_cache_patch.py docs/CONTINUITY_SUMMARY.md
git commit -m "feat(android): log Vulkan pipeline cache state"
```

### Task 3: Build and prove the patch on device

**Files:**
- Modify: `docs/CONTINUITY_SUMMARY.md`

**Interfaces:**
- Consumes the patcher and diagnostics from Tasks 1–2.
- Produces recorded build output and two labelled ADB captures.

- [ ] **Step 1: Apply the patch to a clean pinned ReXGlue v0.10.0 tree**

Run the documented manual ARM64 patch/build workflow. Verify patcher output identifies every expected anchor exactly once.

- [ ] **Step 2: Build and validate artifacts**

Compile the three ARM64 libraries, assemble the APK manually, align and sign with the existing test key, then run `apksigner verify --print-certs`. Do not use Gradle on Termux.

- [ ] **Step 3: Request and wait for ADB confirmation**

Install only after the owner supplies a connected ADB endpoint. Do not uninstall or clear data.

- [ ] **Step 4: Capture cold and warm evidence**

Run once with no cache file, then a second time without clearing app data. Save redacted logs showing cache state, pipeline counts, present FPS, p50/p95/p99 frame time, and fence waits. Report unavailable metrics explicitly.

- [ ] **Step 5: Document evidence and commit**

Record only aggregate results and commands, not raw personal logs or cache files.

```bash
git add docs/CONTINUITY_SUMMARY.md
git commit -m "docs(android): record pipeline cache validation"
```

## Self-Review

- The plan covers persistence, validation, atomic writes, metrics, build, and required device evidence.
- Corrupt input, write failure, non-blocking I/O, patch drift, and metric completeness each have an owning task/test.
- No desktop-specific reference component is imported.
