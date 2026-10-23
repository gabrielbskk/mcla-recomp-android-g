# First Android C++ Recompilation

**Recorded build date:** 2026-10-22
**Status:** compile/link milestone, not a stable or complete game release.

## Why the project changed direction

An earlier Rust Android prototype compiled and ran but had extremely low reported rates and an input-dispatch ANR. The project then moved to a separate C++ static-recompilation path. The Rust prototype remains historical material; it was not converted into the current source tree.

## How recompilation works

1. The user supplies a legally obtained Xbox 360 *Midnight Club: Los Angeles Complete Edition* executable (`default.xex`) and game data. No game files are included here.
2. ReXGlue analyzes the Xbox 360 PowerPC executable and generates C++ translation units ahead of time.
3. The generated units and ReXGlue runtime are built for Android `arm64-v8a`.
4. ReXGlue provides Xbox 360 runtime services, including Xenos GPU emulation. ARM64-native host code does not mean the Xbox 360 subsystems have been rewritten as a native Android game engine.

This is static recompilation plus a compatibility runtime, not x86 emulation or a full Android rewrite of the original engine.

## First native build record

The initial Termux build report recorded successful compilation and linking of `libmain.so` and the separate `librexgpu-xenos.so` plugin as Android ARM64 ELF files. That milestone did not include an APK installation or gameplay run, so it does not establish successful startup, import, car selection, or frame rate. See the [native build report](../performance/s23-native-build-2026-10-22.md) for the dated measurements and limitations.

## Android Open Beta

Archived source snapshots named `build_v1` through `build_v7` did not have trustworthy per-build APKs or individual runtime reports. They are grouped as source snapshots instead of being presented as seven verified releases.

The Open Beta (`0.1.2-experimental`, `versionCode 3`, package `org.mcla.recomp.openbeta`) packages native ARM64 code and provides an Android launcher/import flow. Users choose a ZIP or extracted folder; the importer copies required files into app-private `filesDir/game`, validates them, and then enables **Play**.

A user test reached car selection. The maintainer reports severe stutter, gamepad input failure, and no clear visible change from preset/resolution settings. The draw-callback metric is not presented FPS. See the [current project status](../CONTINUITY_SUMMARY.md); do not infer stability or a frame-rate result from successful compilation or import validation.
