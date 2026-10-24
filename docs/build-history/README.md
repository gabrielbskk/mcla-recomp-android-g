# Android Build History

This index separates the earlier Rust experiment from the current C++/ReXGlue recompilation. Each result belongs to the version and date named in its source record. Older measurements do not establish the current Open Beta's performance.

## Timeline

| Stage | What it was | Evidence and outcome |
|---|---|---|
| Rust prototype, 0.9.5–0.9.8 (Oct. 21, 2026) | A separate Rust-based Android port using wgpu with Android Vulkan/GLES backends. It is not the current C++ recomp. | ARM64 artifacts were compiled and installed. A gameplay trace reported about 0.5–0.6 FPS after loading, and an earlier session recorded an input-dispatch ANR. Experimental and not playable at those measured rates. See [Rust prototype report](rust-prototype.md). |
| First C++ recompilation (Oct. 22, 2026) | Xbox 360 PowerPC code was processed ahead of time by ReXGlue into C++, then built for Android ARM64. ReXGlue runtime and the Xenos GPU plugin remained part of the app. | Native libraries compiled in Termux. This proved compilation/linking only, not gameplay. See [C++ recompilation report](cpp-recomp.md) and [native-build record](../performance/s23-native-build-2026-10-22.md). |
| Source snapshots `build_v1`–`build_v7` | Successive source snapshots from the early C++ effort. | Trustworthy per-snapshot APKs and runtime reports were not available, so these are not presented as seven verified releases. |
| Android Open Beta / 0.1.2-experimental (Oct. 23, 2026) | Android launcher, private ZIP/folder import, graphics settings, draw-callback telemetry, and log export. | A user test reached car selection. Severe stutter, gamepad input failure, and no clear visible effect from preset/resolution settings remain reported. The draw metric is not presented FPS. See [current project status](../CONTINUITY_SUMMARY.md). |

## Reading the Records

- [Rust prototype](rust-prototype.md) is a separate archived predecessor; its Rust source and APKs are not this C++ recompilation.
- [C++ recompilation](cpp-recomp.md) explains the initial conversion/build pipeline and the limits of the first native library build.
- [Runtime analysis](../performance/s23-runtime-analysis-2026-10-22.md) contains measurements from an older runtime session and explains what those counters mean.
- [V8 status](../performance/s23-build-v8-status-2026-10-22.md) is a dated historical snapshot; it does not describe the current Open Beta.

All reports remain experimental. None claims a stable release, verified 30 FPS, or universal GPU compatibility.
