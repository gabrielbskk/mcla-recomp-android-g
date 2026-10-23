# Android ARM64 — V8-based test build

This guide describes the V8-based Android implementation (`0.1.2-experimental`, `versionCode 3`) and later test instrumentation. The build and UI history is recorded in `docs/performance/` and `docs/ui/`.

## Current status

- The V8-derived test build targets ARM64 (`arm64-v8a`) and was exercised on a Galaxy S23 SM-S911B running Android 16. The signed APK and signing key are stored outside this repository.
- The V8 screen offers **Import ZIP**, **Import extracted folder**, an optional `.bik` video checkbox, **Export logs**, and an ISO picker. Xbox 360 XGD ISO images are not extracted by the app.
- The user confirmed reaching the car-selection screen with the I/O-trace test build. The trace shows `default.xex`, `xarchive_cache.rpf`, and `xarchive_audlo.rpf` activity; it records no attempt to open `nxeart` or `root_directory_padding.pad`. It records one failed open of `intro720.bik`, after which the game continued. This does not prove that every `.bik` file can be omitted.
- The trace did not record `xarchive_audio.rpf` or `xarchive_music.rpf` before car selection. The import validator still requires all five configured files.
- Frame-timer samples ranged from 1.8 to 29.9 guest ticks/s and included long stalls. These are not measured presented FPS. No 30 FPS result or performance improvement is verified.
- Earlier Android measurements belong to older builds and must not be attributed to this build. See [the earlier runtime analysis](../docs/performance/s23-runtime-analysis-2026-10-22.md).

## Import and storage

The user selects a ZIP through Android's Storage Access Framework (`ACTION_OPEN_DOCUMENT`) or an extracted folder through `ACTION_OPEN_DOCUMENT_TREE`. The app copies the files into its private `filesDir/game`; the native runtime reads that private copy. This flow does not require `MANAGE_EXTERNAL_STORAGE` or the shared `/storage/emulated/0/MLR` directory.

`DataImportService` performs the copy in a foreground service with progress reporting, the `dataSync` service type, and a `WAKE_LOCK`. Files are prepared under `filesDir/game.part`, validated, then promoted to `game`. An existing previous copy is preserved as `game.previous` when applicable; it is not silently deleted. The import checks available space before writing.

Required files recognized by V8:

- `default.xex`
- `xarchive_cache.rpf`
- `xarchive_audio.rpf`
- `xarchive_audlo.rpf`
- `xarchive_music.rpf`

The app checks copied/source sizes, calculates SHA-256 for `default.xex`, and records metadata in `.mcla_ready`. `.bik` videos are optional and excluded by default. The later I/O-trace run continued after failing to open `intro720.bik`, and the user reported reaching car selection; other scenes and videos remain unverified. The ISO picker explains that XGD images must be extracted on a computer before importing the resulting folder or ZIP.

**Free space:** allow room for the imported data and temporary `game.part`. If `game` already exists, it remains during import, so the required free space can exceed the final size of the game files. The check also reserves a safety margin. If an import is interrupted, read the app's status before manually removing any directory.

Uninstalling the app removes imported files in `filesDir` and private saves. Back them up separately before uninstalling.

## Logs and diagnostics

Runtime logs stay in the app-private directory and rotate. **Export logs** asks the user to choose a destination through SAF once; a destination such as `Documents/MCLA/logs` can be selected. The exporter includes `.log` and `.csv` files, gives each file a content-derived name so repeat exports reuse identical documents, and writes a report about the previous process exit when Android provides one. This avoids broad storage permission.

## Launcher settings and intent overrides

The launcher settings include guest resolution (540p/720p/1080p), FPS limit, V-Sync, graphics preset, FPS counter, and optional performance logging. They use the private `filesDir/mcla-recomp/userdata/mcla.toml` consumed by ReXGlue; the in-game menu uses the same cvars. The FPS counter defaults to enabled, including on fresh installs. The graphics preset defaults to **Medium** and offers **Super Low**, **Low**, **Medium**, **High**, and **Ultra**. Legacy `performance`, `balanced`, and `original` values map to Super Low, Medium, and Ultra.

The overlay reports draw-callbacks per second and mean frame time. It does not measure completed Vulkan presents because this build does not hook the renderer's present path. The optional worker-thread log writes one-second `draw_fps`, average/p50/p95/p99/max frame time, and frames over 50 ms to `filesDir/mcla-recomp/logs/performance-v2.csv`. Submit/readback/acquire fence-wait columns remain unavailable until the renderer exports those counters. Guest game-timer ticks are reported separately in the runtime log.

The Android app's own labels, import messages, driver status, and diagnostics are in English. Android's system file picker may follow the device language. Game dialogue and other game-authored assets retain the language in the imported files; no runtime language-switch option was found in this project.

For a test run without changing the launcher controls, start the gameplay activity directly (game data must already be imported):

```sh
adb shell am start -n org.mcla.recomp.test/org.mcla.recomp.DataSetupActivity \
  --es resolution 540p --es effects low --ei fps_limit 0 \
  --ez vsync false --ez fps_counter true --ez performance_logging true
```

The launcher validates `filesDir/game` and forwards the extras to gameplay when it is ready. Supported `effects` values are `super_low`, `low`, `medium`, `high`, and `ultra` (plus the legacy aliases above). Valid FPS limits are `-1`, `0`, `30`, `60`, `120`, and `240`; invalid extras fall back to app defaults. Intent overrides apply only to that launch and do not rewrite the TOML file.

The I/O-trace test build logs file opens and reads. Its user-confirmed run reached car selection. Treat missing-file evidence as scoped to that run; do not remove game files solely from this short trace.

## Build

The V8 test APK was built in Termux. The complete Gradle build is not supported there because the SDK's CMake and AAPT2 tools are x86-64. Use the manual ARM64 process: build `libmain.so`, `librexruntime.so`, and `librexgpu-xenos.so` with the Termux ARM64 Clang/CMake toolchain, replace those libraries in the compatible base APK, then align and sign it. Keep the Android SDK, build outputs, APKs, and signing key outside Git. Do not version APK/XAPK/OBB files, game data, GPU driver archives, or signing material.

For the existing Termux cache, use `scripts/resume_android_termux_build.sh` with `MCLA_BUILD_DIR` and `REXGLUE_CODEGEN` set to the verified cache and host wrapper. It checks which checkout owns the cache and builds all three native libraries. The generic `scripts/build_android.sh` uses the NDK-host toolchain and must not be mistaken for the Termux procedure. See [manual build recovery](../docs/performance/termux-build-recovery-2026-10-23.md) for the commands and remaining reproducibility limits. Setting `MCLA_ANDROID_IO_TRACE=ON` enables temporary file-open/read tracing. Java changes must also be compiled to DEX before packaging; replacing only the native libraries does not include launcher changes.

## Launcher screenshots

These captures show only the app launcher, with no gameplay or game assets:

- [Before data validation](../docs/ui/import-before-data-validation-2026-10-22.png)
- [After the readiness validator enabled Play](../docs/ui/import-private-data-ready-2026-10-23.png)

See [the two-observation note](../docs/testing/android-ui-last-two-observations-2026-10-23.md) for their meaning and limits.

## Compatibility and performance

This build has no verified presented-FPS measurement or 30 FPS result. The S23 session showed low guest tick rates and severe stalls, but those figures are not render FPS. Mali G52/G57, Xclipse, and other GPUs have not been validated with this version.
