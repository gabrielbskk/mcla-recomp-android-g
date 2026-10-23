# Android ARM64 — V8 (primary reference)

This guide describes the V8 Android implementation (`0.1.2-experimental`, `versionCode 3`). The source reference is the snapshot recorded in `docs/performance/s23-build-v8-status-2026-10-22.md`, together with the launcher captures in `docs/ui/`.

## Current status

- V8 was built as an ARM64 (`arm64-v8a`) Release APK and installed on the Galaxy S23 SM-S911B running Android 16 on 2026-10-22. The signed APK and signing key are archived on the netbook and are not in this repository.
- The V8 screen offers **Import ZIP**, **Import extracted folder**, an optional `.bik` video checkbox, **Export logs**, and an ISO picker. Xbox 360 XGD ISO images are not extracted by the app.
- The latest launcher capture shows `Dados privados validados. Pronto para jogar.` with **Play** enabled. This confirms that the app's local readiness validator accepted the private files at capture time; it does not prove which import action supplied them.
- At the user's request, the game was not opened during the latest review. Reaching car selection with V8, runtime file-open evidence, and V8 FPS remain unverified.
- ADB responded during the review, but the queried Android user did not list `org.mcla.recomp` as installed at the end. No APK was installed or launched in this review.
- Behavior from earlier Android builds is historical and must not be attributed to V8 without a direct comparison. See [the earlier runtime analysis](../docs/performance/s23-runtime-analysis-2026-10-22.md).

## V8 import and storage

The user selects a ZIP through Android's Storage Access Framework (`ACTION_OPEN_DOCUMENT`) or an extracted folder through `ACTION_OPEN_DOCUMENT_TREE`. The app copies the files into its private `filesDir/game`; the native runtime reads that private copy. This flow does not require `MANAGE_EXTERNAL_STORAGE` or the shared `/storage/emulated/0/MLR` directory.

`DataImportService` performs the copy in a foreground service with progress reporting, the `dataSync` service type, and a `WAKE_LOCK`. Files are prepared under `filesDir/game.part`, validated, then promoted to `game`. An existing previous copy is preserved as `game.previous` when applicable; it is not silently deleted. The import checks available space before writing.

Required files recognized by V8:

- `default.xex`
- `xarchive_cache.rpf`
- `xarchive_audio.rpf`
- `xarchive_audlo.rpf`
- `xarchive_music.rpf`

The app checks copied/source sizes, calculates SHA-256 for `default.xex`, and records metadata in `.mcla_ready`. `.bik` videos are optional and excluded by default. There is no V8 gameplay evidence yet proving whether the game proceeds without them. The ISO picker explains that XGD images must be extracted on a computer before importing the resulting folder or ZIP.

**Free space:** allow room for the imported data and temporary `game.part`. If `game` already exists, it remains during import, so the required free space can exceed the final size of the game files. The check also reserves a safety margin. If an import is interrupted, read the app's status before manually removing any directory.

Uninstalling the app removes imported files in `filesDir` and private saves. Back them up separately before uninstalling.

## Logs and diagnostics

Runtime logs stay in the app-private directory and rotate. **Export logs** asks the user to choose a destination through SAF once; a destination such as `Documents/MCLA/logs` can be selected. This avoids broad storage permission. When available, the app also exports a report about the previous process exit.

## Launcher settings and intent overrides

The import screen has a **Configurações** section for guest resolution (540p/720p/1080p), FPS limit, V-Sync, effects preset, FPS counter, and optional performance logging. These are stored in the same private `filesDir/mcla-recomp/userdata/mcla.toml` read by ReXGlue at startup; the in-game settings menu uses the same cvars. The FPS counter defaults to enabled, including when no settings file exists. Performance logging defaults to off and, when enabled, writes one-second render-loop FPS, average frame time, and p95 to `filesDir/mcla-recomp/logs/performance.csv`. Fence-wait time split by submit/readback/acquire is marked unavailable until the renderer exports those counters; this build does not change the renderer.

For a test run without changing the launcher controls, start the gameplay activity directly (game data must already be imported):

```sh
adb shell am start -n org.mcla.recomp.test/org.mcla.recomp.DataSetupActivity \
  --es resolution 540p --es effects low --ei fps_limit 0 \
  --ez vsync false --ez fps_counter true --ez performance_logging true
```

The launcher validates `filesDir/game` and automatically forwards the extras to gameplay when it is ready. Supported `effects` values are `low`/`performance`, `medium`/`balanced`, and `high`/`original`. Valid FPS limits are `-1`, `0`, `30`, `60`, `120`, and `240`; invalid extras fall back to the app defaults. Intent overrides apply only to that launch and do not rewrite the TOML file.

The current Android test build includes temporary file-open/read tracing. Export and review the app log before deciding whether `.bik`, `nxeart`, or `root_directory_padding.pad` are needed. No gameplay trace from this build has been reviewed yet, so those files remain unclassified by runtime evidence.

## Build

The V8 APK was built manually in Termux with the ARM64 toolchain and Gradle. The build record is in `docs/performance/s23-build-v8-status-2026-10-22.md` and the detailed private build report is archived on the netbook. Do not put game data in Git or version APK/XAPK/OBB files, XEX/RPF files, GPU driver archives, or signing keys.

To reproduce a build, provide the compatible Android-patched ReXGlue SDK, host `rexglue` code generator, Android SDK/NDK, and Python locally. The native build uses `scripts/build_android.sh`; Gradle packaging uses `android/gradlew`. Setting `MCLA_ANDROID_IO_TRACE=ON` enables temporary file open/read tracing. Tool paths and signing material must remain outside the repository.

## Launcher screenshots

These captures show only the app launcher, with no gameplay or game assets:

- [Before data validation](../docs/ui/import-before-data-validation-2026-10-22.png)
- [After the readiness validator enabled Play](../docs/ui/import-private-data-ready-2026-10-23.png)

See [the two-observation note](../docs/testing/android-ui-last-two-observations-2026-10-23.md) for their meaning and limits.

## Compatibility and performance

V8 was packaged for ARM64 and installed on the S23 during the build round. There is no V8 FPS measurement or verified 30 FPS result. Earlier builds showed very poor performance; those measurements belong to older versions and must not be extrapolated to V8. Mali G52/G57, Xclipse, and other GPUs have not been validated with this version.
