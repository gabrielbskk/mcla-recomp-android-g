# Android build history

This index separates the earlier Rust experiment from the current C++/ReXGlue recompilation. Each result belongs to the version and date named in its source record. None of the old performance results establish the current V8 runtime's performance.

## Timeline

| Stage | What it was | Evidence and outcome |
|---|---|---|
| Rust prototype, 0.9.5–0.9.8 (Oct. 21, 2026) | A separate Rust-based Android port, using wgpu with Android Vulkan/GLES backends. It was not the current C++ recomp. | 0.9.5 compiled and packaged for ARM64 and was installed. Later test artifacts through 0.9.8 were recorded. A gameplay trace showed about 0.5–0.6 FPS after loading, and an earlier session recorded an input-dispatch ANR. Experimental and not playable at those measured rates. See [Rust prototype report](rust-prototype.md). |
| First C++ recompilation (Oct. 22, 2026) | Xbox 360 PowerPC code from the supported `default.xex` was processed ahead of time by ReXGlue into C++, then built for Android ARM64. ReXGlue runtime and the Xenos GPU plugin remained part of the app; this was not a full reimplementation of the Xbox 360 hardware. | `libmain.so` and the separate `librexgpu-xenos.so` compiled on the S23 in Termux. This proved compilation/linking only, not gameplay. See [C++ recompilation report](cpp-recomp.md) and the [native-build record](../performance/s23-native-build-2026-10-22.md). |
| Source snapshots build_v1–build_v7 | Successive local source snapshots in the netbook archive. | Individual, trustworthy APK/build/runtime reports for each snapshot were not found in the reviewed build folders. They are not presented as seven verified releases. |
| Android V8 / 0.1.2-experimental (Oct. 22, 2026) | The C++ Android launcher and ZIP/folder import flow were aligned around app-private `filesDir/game`; a diagnostic build includes file-open/read tracing. | A signed ARM64 APK was built and installed. At the time of the original build report, the game-data ZIP had been copied to the phone but the import flow had not yet run. The present follow-up is tracking the new import attempt; do not claim car selection or a file-open trace until the game is explicitly run and the exported log is inspected. See [V8 build status](../performance/s23-build-v8-status-2026-10-22.md). |

## Reading the records

- [Rust prototype](rust-prototype.md) is a separate, archived predecessor; its Rust source and APKs are not this C++ recomp project.
- [C++ recompilation](cpp-recomp.md) explains the initial conversion/build pipeline and the limits of the first native library build.
- [Runtime analysis](../performance/s23-runtime-analysis-2026-10-22.md) contains measurements from an older runtime session and explains what those counters mean.
- [V8 status](../performance/s23-build-v8-status-2026-10-22.md) records the V8 APK and the earlier unverified import state. A newer on-device follow-up will supersede that state when completed.

All reports are historical or experimental unless explicitly marked otherwise. No report in this folder claims a stable release, a verified 30 FPS result, or universal GPU compatibility.
