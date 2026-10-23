# Android ARM64 build (experimental)

This repository contains an experimental Android target for the C++ MCLA Recomp project. It uses SDL3 and the ReXGlue runtime and targets `arm64-v8a`.

## Current status

- The APK builds and has been installed on a Samsung Galaxy S23 running Android 16.
- The game found its data, initialized Vulkan on that device, and rendered the city scene.
- Performance is still poor. This is a development build, not a stable release; no 30 FPS claim is made.
- A tester reported that the app did not open on a Mali-G52 device; no device log was supplied, so the cause is unknown. Mali-G57 and other GPUs remain unverified.
- The current Android build enables Vulkan only. The Android build script enables ReXGlue's fallback paths when a GPU lacks optional geometry-shader or non-solid-fill features. The SDK version used here does not provide an OpenGL ES fallback, so ARM64 installation compatibility is not the same as GPU compatibility.
- Optional bundled drivers are selected automatically only for their matching GPU: Turnip for Adreno 740 and PanVK for Mali-G52. Other GPUs use Android's system Vulkan driver. PanVK remains experimental and has not yet been validated with MCLA.

## Game files

The APK does **not** include the game. Provide your own legally obtained and extracted Xbox 360 game data, including `default.xex` and the required RPF archives.

Preferred location:

```text
/storage/emulated/0/MLR/
```

Place the extracted game files directly in `MLR`, or put the game tree in `MLR/game`. The app checks these locations first. It also checks its app-specific storage as a fallback.

On Android 11 and newer, shared-storage scanning requires granting **Allow access to manage all files** in the Android settings page opened by the app. Return to the app after granting access; if it started before access was granted, close and reopen it. Keep the game files out of Git and do not distribute them with the APK.

## Full-data XAPK

The Android launcher can read a full-data OBB named `main.<versionCode>.org.mcla.recomp.obb`. On first launch it extracts the OBB into the app-owned `Android/data/org.mcla.recomp/files/game` directory before starting the native runtime. This avoids requiring broad storage access for an XAPK install. Existing data in `/MLR` remains supported and still requires **Allow access to manage all files** on Android 11 and newer.

To create a private XAPK from a signed APK and your own extracted game files, run:

```bash
python3 scripts/package_android_xapk.py \
  --apk android/app/build/outputs/apk/release/app-release.apk \
  --game-dir game \
  --output MCLA-Recomp-Android.xapk
```

XAPK is a third-party ZIP container, not an Android install format. Use an XAPK installer that installs the APK and places the declared OBB in `Android/obb/org.mcla.recomp/`. The first launch then prepares the game files. The output contains the supplied game data; keep it private and do not upload it to this source repository.

## In-game options

Open the game's pause menu, then **Settings**:

- **Display** includes the FPS counter toggle, frame-rate target, motion blur and depth of field. On Android, the overlay separates UI render-loop FPS from guest game ticks per second; the latter is not a Vulkan-present count.
- Android starts with a 960×540 guest video mode; **Display → Resolution** can select 540p, 720p or 1080p (restart required). The Android surface still fills the phone screen.
- **Performance** includes Performance, Balanced and Original graphics presets, plus individual detail controls.
- Changes are saved to the app's settings file.

## Touch controls

The Android game view includes an on-screen virtual gamepad: left stick for steering, RT/ LT for throttle and brake, A/B/X/Y, and START. The overlay hides after five seconds without touch. Touch the screen to reveal it again, or use the persistent PAD/HIDE button in the upper-right corner. Touch input is forwarded through SDL as a virtual gamepad, so the game uses the same input path as a physical controller.

The Android native C++ targets use `-O3` for the `RelWithDebInfo` release configuration; Android Gradle selects that configuration for the current release variant. This may reduce CPU time, but FPS still needs to be measured on a device.

On the next launch, the launcher exports the previous runtime's rotating log files and an Android process-exit report (including the system trace when available) to `Documents/MCLA Recomp`. The report includes device model, Android version, app version, and the prior process exit reason. Export failures do not block startup.
On Android, runtime logs also record a sample every 10 seconds: estimated UI render-loop FPS, p95 and maximum frame interval, and process VmRSS from `/proc/self/status`. This is an approximate render-loop metric, not a Vulkan-presented FPS measurement or Android PSS.
The Android frame-timer hook also logs guest frame-tick rate, p95 and maximum tick interval every 10 seconds. It measures game-loop cadence, not successful Vulkan presents. ReXGlue's draw-call counter is not instrumented by its Vulkan backend, so it is not used as an Android measurement.

The Android ReXGlue patch logs estimated Vulkan texture-cache allocation size, entry count, and soft/hard cache limits every 10 seconds. Compare it with VmRSS for context; VMA allocation size, process resident memory, and total GPU memory are different measurements.

Android Vulkan shader warm-up defaults to two background pipeline workers. When incomplete-frame skipping is enabled (the ReXGlue default), the Android build leaves queued pipeline compilation on those workers instead of draining and waiting for it at every GPU submission. Frames that use a placeholder are still skipped; this can trade temporary skipped frames during warm-up for less blocking of the emulation thread. Runtime gains still need to be measured on the S23.

Android logs record individual Vulkan pipeline creations at debug level rather than info level. This avoids writing a high-volume line for every pipeline during shader warm-up; pipeline failures and aggregate performance samples remain visible at their existing levels.

The Android guest video mode defaults to 540p to reduce pixel work, with the presenter scaling it to the phone display. This only helps if the game follows the Xbox video mode; it does not reduce CPU-side simulation or draw-call work. The current Android build uses bilinear scaling, so 540p may look softer than 720p. We still need an on-device frame-time comparison before claiming an FPS gain. ReXGlue's separate render-target scale remains 1x or higher.

## Optional Vulkan drivers

The app can bundle the supplied ARM64 Turnip and PanVK driver archives in one APK. It detects the renderer through a temporary EGL context, stages only the matching driver under app-private internal storage, and probes it with Vulkan before passing it to ReXGlue. If loading or the device probe fails, startup uses the Android system Vulkan driver. A marker left by an abnormal process exit makes the next launch use the system driver once.

The two driver ZIPs are intentionally not stored in this repository. To build with them in the Codespace, copy the archives to its private filesystem and set both variables:

```bash
export MCLA_TURNIP_DRIVER_ZIP=/path/to/Turnip-v26.3.0-20261005-8G2-OneUI.zip
export MCLA_PANVK_G52_DRIVER_ZIP=/path/to/PanVk-V7-0.0.2-alpha.zip
./scripts/build_android_codespace.sh
```

The packaging script checks the pinned SHA-256 hashes, archive paths, metadata, ELF format, and ARM64 machine type before adding either archive to APK assets. Builds without both variables use the system Vulkan driver. Bundling either driver increases APK/install storage; PanVK's library expands to about 128 MB. `libadrenotools` and its linker hooks are included under their BSD-2-Clause license. The supplied Mesa driver archives do not contain license notices, so add the corresponding upstream notices before redistributing a build that bundles them.

## Build requirements

Use a Linux x86-64 build host with Java 21, Android SDK/NDK, CMake 3.31.6, Ninja, Python 3.12, and an Android-patched ReXGlue v0.10.0 SDK. The host-native `rexglue` code generator and its host libraries are also required.

For the configured GitHub Codespace, run this from the repository root:

```bash
./scripts/build_android_codespace.sh
```

The script uses the Codespace Android SDK and local ReXGlue host code generator, and writes the APK under `android/app/build/outputs/apk/release/`. It does not install the APK on a connected phone. Release lint analysis is skipped by default because the current Codespaces Android lint metadata makes that task fail; set `MCLA_RUN_ANDROID_LINT=1` to include it.

Set these environment variables to local tool paths:

```bash
export JAVA_HOME=/path/to/jdk-21
export ANDROID_HOME=/path/to/android-sdk
export REXSDK_DIR=/path/to/android-patched-rexglue-sdk
export REXGLUE_CODEGEN=/path/to/linux-amd64/bin/rexglue
export REXGLUE_HOST_LIB_DIR=/path/to/linux-amd64/lib
export PYTHON_EXECUTABLE=/usr/bin/python3.12
export CMAKE=/path/to/android-sdk/cmake/3.31.6/bin/cmake
```

Then build from the repository root:

```bash
./android/gradlew -p android :app:assembleRelease
```

The result is written to `android/app/build/outputs/apk/release/app-release.apk`. A local build may use the Android debug signing key when no custom signing variables are set; that key is for testing only. Never commit signing keys or passwords.

## Repository hygiene

Game dumps, generated game code, SDK contents, build outputs, logs, and signing keys are ignored by Git. Do not remove those ignore rules or commit those files.
