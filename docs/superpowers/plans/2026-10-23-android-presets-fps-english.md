# Android Presets, FPS Telemetry, and English UI Implementation Plan

> **For agentic workers:** Execute this plan inline, task by task. Each task uses test-first changes and ends with a focused verification.

**Goal:** Provide five consistent graphics presets, an honest render-callback counter, more useful opt-in performance logs, and English text across the Android app.

**Architecture:** Keep preset-to-render-option mapping in native MCLA code and let Android validate/store only canonical preset names. Count native app draw callbacks with a monotonic clock; report them separately from guest game ticks and do not call them completed presents. Keep log I/O on the existing worker thread and let the SAF exporter include the performance CSV idempotently.

**Tech Stack:** Java/Android, C++17, SDL3/ImGui, Python unittest wrappers, Termux ARM64 toolchain.

**Spec:** `AGENTS.md` and the user's current feature requests in the conversation.

## Global Constraints

- Preserve app-private `filesDir/game` data, saves, signing material, and untracked local files.
- Do not change the renderer or install/run the game on the S23 in this task.
- Keep performance logging opt-in and off the draw thread.
- Keep the FPS counter enabled by default and use `Medium` as the graphics preset default.
- Translate app/port-controlled text; do not claim game-authored assets are translated.
- Do not add APKs, game assets, caches, device logs, or signing material to Git.

## Review Focus

- Legacy preset values (`performance`, `balanced`, `original`) must map to `Super Low`, `Medium`, and `Ultra` respectively; pin parser and runtime mapping tests.
- Invalid or missing settings must fall back to `Medium`; pin missing, alias, and invalid values in Android settings tests.
- The counter must count elapsed draw callbacks rather than invert a single ImGui delta; pin exact one-second and irregular-window rates with a deterministic C++ test.
- Percentile and hitch statistics must handle empty input and the 50 ms boundary; pin those cases in the metrics test.
- Export must include CSV and avoid creating a new duplicate for identical contents; verify deterministic output naming and report SAF limitations.

---

### Task 1: Canonical five-tier graphics presets

**Files:** `AppSettings.java`, `MclaActivity.java`, `DataSetupActivity.java`, `src/settings_menu.cpp`, new `src/graphics_presets.h`, `tests/AndroidSettingsTest.java`, new `tests/test_graphics_presets.cpp`.

**Mapping:** Super Low = LOD 0.25, density 0, traffic 100 m, shadows/blur/MSAA/motion blur/DOF off; Low = 0.5, density 0.25, 150 m, the same heavy effects off; Medium = 0.75, density 0.5, 250 m, basic shadows on and heavy effects off; High = 0.75, density 0.75, 325 m, foliage shadows/fullscreen blur/MSAA/motion blur/DOF on; Ultra = 1.0, density 1.0, 400 m, all available effects on. Distant foliage impostors remain enabled in all tiers.

- [ ] Add failing Java and native cases for default, aliases, invalid names, and each preset's option values.
- [ ] Run the focused tests and confirm the expected failures.
- [ ] Implement canonical parsing and one native mapping; remove duplicate Java preset-to-cvar mapping.
- [ ] Run focused tests and the Android settings suite.

### Task 2: English Android app text

**Files:** `DataSetupActivity.java`, `DataImportService.java`, `GpuDriverManager.java`, `DiagnosticsExporter.java`, `android/README.md`.

- [x] Translate app-owned labels, import progress/errors, driver status, and export results to English.
- [x] Document preset names and intent extras; correct the build instructions to the manual ARM64 Termux process.
- [x] Review Android-owned Java/resources for remaining user-visible Portuguese text.

### Task 3: Render callback counter and one-second telemetry

**Files:** `src/mcla_app.cpp`, new `src/render_metrics.h`, new `tests/test_render_metrics.cpp`, `tests/test_android_settings.py`.

- [x] Add deterministic failing tests for draw-rate windows, percentiles, empty samples, and frames over 50 ms.
- [x] Count draw callbacks over monotonic one-second windows and show `DRAW FPS` plus mean frame time; keep guest tick rate separately labeled.
- [x] Extend the opt-in worker CSV with p50/p95/p99/max, hitches over 50 ms, and schema-versioned filename.
- [x] Run focused C++ metrics tests and the Android settings suite.
- [ ] Compile native integration with the manual ARM64 build path; blocked because the installed NDK only contains an x86_64 host compiler, while this Termux is aarch64.

### Task 4: Exportable diagnostics and final review

**Files:** `android/app/src/main/java/org/mcla/recomp/DiagnosticsExporter.java`, `android/README.md`.

- [x] Include current and rotated `.csv` files in SAF exports and use content-derived stable names so repeat exports reuse identical documents.
- [x] Review diff, `.gitignore`, and generated artifacts; keep device logs and build outputs outside Git.
- [x] Record unavailable device measurements and do not claim FPS improvement without a fresh S23 capture.
- [ ] Verify the SAF export flow on Android; host tests cover filename selection only.
