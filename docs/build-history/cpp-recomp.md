# First Android C++ recompilation

**Date of recorded native build:** 2026-10-22

**Status:** compile/link milestone; not by itself proof of a playable game.

## Why the project changed direction

The Rust Android prototype had been built and exercised, but its archived gameplay measurements were around 0.5–0.6 FPS and an earlier run had an input-dispatch ANR. The project then moved to a distinct C++ recompilation path. The old Rust prototype was preserved as historical material; it was not simply renamed or converted into this C++ codebase.

## How the recompilation works

1. The user supplies the Xbox 360 *Midnight Club: Los Angeles Complete Edition* executable (`default.xex`) and its game data. No game files are part of this repository.
2. ReXGlue analyzes/recompiles the Xbox 360 PowerPC executable ahead of time into C++ translation units.
3. Those C++ units and the ReXGlue runtime are built for Android `arm64-v8a` with the Android NDK/Termux toolchain.
4. The Android package loads the native libraries. ReXGlue still supplies Xbox 360 runtime services, including Xenos GPU emulation; the host code is ARM64-native, but this does not mean every Xbox subsystem was rewritten as a native Android game engine.

This is static recompilation plus a compatibility runtime, not x86 emulation and not a pure Android rewrite of the original game's engine.

## First native build record

The 2026-10-22 Termux record reports successful compilation/linking of:

- `libmain.so`: 80,024,784 bytes (about 77 MiB), ELF64 AArch64 for Android.
- `librexgpu-xenos.so`: 5,885,056 bytes (about 5.7 MiB), a separate ARM64 GPU plugin.

The build used Android SDL/input/audio configuration and Vulkan. The CMake/PIC fixes allowed static dependencies and generated game code to be linked into Android shared libraries. The detailed [native build report](../performance/s23-native-build-2026-10-22.md) lists dependencies, hashes, and limitations.

That first library milestone did not include an APK installation or a fresh gameplay run. It cannot be used to claim stable startup, successful import, car selection, or a frame rate.

## Progress toward V8

The netbook contains local source snapshots named `build_v1` through `build_v7`, followed by the V8 Android packaging/import snapshot. The reviewed v1–v7 directories did not provide per-build APKs or individual runtime reports, so the timeline groups them as source snapshots instead of inventing release-by-release results.

V8 (`0.1.2-experimental`, `versionCode 3`) packages the native ARM64 code and adds an Android launcher/import flow. Users choose a ZIP or extracted folder; the importer copies required files into the app-private `filesDir/game` directory, validates them, and only then enables **Jogar**. V8 also carries file-open/read tracing for a later authorized gameplay test.

The signed V8 APK exists and has been installed on the S23. The actual import and gameplay trace are tracked separately in the [V8 status record](../performance/s23-build-v8-status-2026-10-22.md) and the current netbook validation report. Do not infer that the game reached car selection from a successful compile or an enabled launcher button.
