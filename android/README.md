# Android ARM64 — Open Beta

This guide describes the Android ARM64 Open Beta (`0.1.2-experimental`, `versionCode 3`, package `org.mcla.recomp.openbeta`). The build and test history is recorded in `docs/performance/` and `docs/ui/`.

## Current status

- The APK targets ARM64 (`arm64-v8a`) and has been exercised on a Samsung Galaxy S23 running Android 16. Other devices and GPUs have not been validated.
- The launcher offers **Import ZIP**, **Import extracted folder**, an optional `.bik` video checkbox, **Export logs**, and an ISO picker. Xbox 360 XGD ISO images are not extracted by the app.
- A user test reached car selection. An I/O-trace capture recorded a failed open of `intro720.bik`, followed by continued execution; it recorded no attempt to open `nxeart` or `root_directory_padding.pad`. This does not prove that every `.bik` file can be omitted.
- That trace did not record `xarchive_audio.rpf` or `xarchive_music.rpf` before car selection. The import validator still requires all five configured files.
- The maintainer reports severe stutter and low performance. This source revision records successful Vulkan queue presentations (`VK_SUCCESS` and `VK_SUBOPTIMAL_KHR`) for the overlay and optional performance log. No 30 FPS result or performance improvement is verified until measured on-device.
- The latest user test reports that gamepad input was not recognized and that preset/resolution changes were not visibly confirmed. These remain open issues.

## Import and storage

Select a ZIP through Android's Storage Access Framework (`ACTION_OPEN_DOCUMENT`) or an extracted folder through `ACTION_OPEN_DOCUMENT_TREE`. The app copies the files into its private `filesDir/game`; the native runtime reads that private copy. This flow does not require `MANAGE_EXTERNAL_STORAGE` or broad shared-storage access.

`DataImportService` performs the copy in a foreground service with progress reporting, the `dataSync` service type, and a `WAKE_LOCK`. Files are prepared under `filesDir/game.part`, validated, then promoted to `game`. An existing previous copy is preserved as `game.previous` when applicable; it is not silently deleted. The import checks available space before writing.

Required files recognized by the importer:

- `default.xex`
- `xarchive_cache.rpf`
- `xarchive_audio.rpf`
- `xarchive_audlo.rpf`
- `xarchive_music.rpf`

The app checks copied/source sizes, calculates SHA-256 for `default.xex`, and records metadata in `.mcla_ready`. `.bik` videos are optional and excluded by default. The I/O-trace run continued after failing to open `intro720.bik`; other scenes and videos remain unverified. The ISO picker explains that XGD images must be extracted on a computer before importing the resulting folder or ZIP.

**Free space:** allow room for the imported data and temporary `game.part`. If `game` already exists, it remains during import, so the required free space can exceed the final size of the game files. The check also reserves a safety margin. If an import is interrupted, read the app's status before manually removing any directory.

Uninstalling the app removes imported files in `filesDir` and private saves. Back them up separately before uninstalling.

## Logs and diagnostics

Runtime logs stay in the app-private directory and rotate. **Export logs** asks the user to choose a destination through SAF once; a destination such as `Documents/MCLA/logs` can be selected. The exporter includes `.log` and `.csv` files, gives each file a content-derived name so repeat exports reuse identical documents, and writes a report about the previous process exit when Android provides one. This avoids broad storage permission.

## Launcher settings and intent overrides

The launcher settings include guest resolution (540p/720p/1080p), FPS limit, V-Sync, graphics preset, FPS counter, and optional performance logging. They use the private `filesDir/mcla-recomp/userdata/mcla.toml` consumed by ReXGlue; the in-game menu uses the same cvars. The FPS counter defaults to enabled, including on fresh installs. The graphics preset defaults to **Medium** and offers **Super Low**, **Low**, **Medium**, **High**, and **Ultra**. Legacy `performance`, `balanced`, and `original` values map to Super Low, Medium, and Ultra.

The overlay reports successful Vulkan presentations per second and presented frame-time p50/p95/p99. The optional worker-thread log writes rolling one-second `presented_fps`, presentation count, average/p50/p95/p99/max frame time, and frames over 50 ms to `filesDir/mcla-recomp/logs/performance-v3.csv`. Submit/readback/acquire fence-wait columns remain unavailable until the renderer exports those counters. Guest game-timer ticks are reported separately in the runtime log.

The Android app's own labels, import messages, driver status, and diagnostics are in English. Android's system file picker may follow the device language. Game dialogue and other game-authored assets retain the language in the imported files; no runtime language-switch option was found in this project.

For a test run without changing the launcher controls, start the gameplay activity directly (game data must already be imported):

```sh
adb shell am start -n org.mcla.recomp.openbeta/org.mcla.recomp.DataSetupActivity \
  --es resolution 540p --es effects low --ei fps_limit 0 \
  --ez vsync false --ez fps_counter true --ez performance_logging true
```

The launcher validates `filesDir/game` and forwards the extras to gameplay when it is ready. Supported `effects` values are `super_low`, `low`, `medium`, `high`, and `ultra` (plus the legacy aliases above). Valid FPS limits are `-1`, `0`, `30`, `60`, `120`, and `240`; invalid extras fall back to app defaults. Intent overrides apply only to that launch and do not rewrite the TOML file.

The I/O-trace test build logs file opens and reads. Its user-confirmed run reached car selection. Treat missing-file evidence as scoped to that run; do not remove game files solely from this short trace.

## Build

The Open Beta APK was built with the manual Termux ARM64 process. The complete Gradle build is not supported there because the SDK's CMake and AAPT2 tools are x86-64. Build `libmain.so`, `librexruntime.so`, and `librexgpu-xenos.so` with the Termux ARM64 Clang/CMake toolchain, replace those libraries in the compatible base APK, then align and sign it. Keep the Android SDK, build outputs, APKs, and signing key outside Git. Do not version APK/XAPK/OBB files, game data, GPU driver archives, or signing material.

For the existing Termux cache, use `scripts/resume_android_termux_build.sh` with `MCLA_BUILD_DIR` and `REXGLUE_CODEGEN` set to the verified cache and host wrapper. It checks which checkout owns the cache and builds all three native libraries. The generic `scripts/build_android.sh` uses the NDK-host toolchain and must not be mistaken for the Termux procedure. See [manual build recovery](../docs/performance/termux-build-recovery-2026-10-23.md) for the commands and remaining reproducibility limits. Setting `MCLA_ANDROID_IO_TRACE=ON` enables temporary file-open/read tracing. Java changes must also be compiled to DEX before packaging; replacing only the native libraries does not include launcher changes. Use `scripts/build_android_dex.sh` with a current Android platform `android.jar`, a modern R8/D8 jar, and `commons-compress.jar`. The legacy Termux `dx` tool is unsupported because it leaves Java lambda call sites that crash at launcher startup with `BootstrapMethodError`.

To assemble a test APK without Gradle, use `scripts/assemble_android_apk.sh`.
It accepts the working base APK, the three freshly built libraries, and a
keystore through environment variables, then strips old signatures, aligns,
signs, and runs both `apksigner` and the repository APK preflight verifier.
Keep `APK_KEYSTORE`, `APK_STORE_PASSWORD`, and `APK_KEY_PASSWORD` outside the
repository; never put them in a command recorded in project documentation.

## Launcher screenshots

These captures show only the app launcher, with no gameplay or game assets:

- [Before data validation](../docs/ui/import-before-data-validation-2026-10-22.png)
- [After the readiness validator enabled Play](../docs/ui/import-private-data-ready-2026-10-23.png)

See [the two-observation note](../docs/testing/android-ui-last-two-observations-2026-10-23.md) for their meaning and limits.

## Compatibility and performance

The revised present counter and per-resolution measurements require device validation; this change alone does not establish a FPS gain or 30 FPS. Low guest tick rates and severe stalls were reported in earlier tests, but those figures are not presented FPS. Mali G52/G57, Xclipse, and other GPUs have not been validated with this version.
