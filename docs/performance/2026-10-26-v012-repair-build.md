# Open Beta v0.1.2 repair build

## Scope

This build keeps the working Open Beta Android manifest and Java/Dex payload and
replaces only the three ARM64 native libraries. It includes the current
Vulkan pipeline-cache instrumentation and successful-present metrics patches.
No game data, cache files, keystore, or device logs are included.

## Reproducible checks

- Native targets `mcla`, `rexruntime`, and `rexgpu-xenos` built successfully
  with the Termux ARM64 toolchain and Android API 26 sysroot.
- `build_android_dex.sh` completed with D8 8.6.17 and Commons Compress 1.28.0.
- The Open Beta base APK passed package/dependency preflight, including
  `ZipArchiveInputStream` and all required ARM64 libraries.
- The assembled APK passed `zipalign`, `apksigner verify`, and the repository
  preflight verifier.
- Repository tests: 52 passed.

## Artifact status

The signed APK is a local test artifact only. It has not been installed or
measured on an Android device in this cycle, so stability and FPS improvements
remain unproven. Device testing must capture logcat and presented-frame metrics
before any performance claim.

