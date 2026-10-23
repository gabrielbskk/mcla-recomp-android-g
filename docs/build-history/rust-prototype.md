# Historical report: Rust Android prototype

**Status:** archived predecessor, separate codebase. This is not the current C++/ReXGlue recompilation.

## What was attempted

The earlier `Rusty MCLA` project attempted to build an Android ARM64 game runtime from Rust. Its Android target used `aarch64-linux-android`, wgpu with Vulkan and GLES enabled, `winit`/`android-activity`, and Oboe through `cpal`. This path aimed to use Android's system graphics drivers rather than bundle an x86 translation layer or require a custom driver.

That approach produced ARM64 Android packages, but it did not become the current project. The C++ recompilation was later started as a separate line using ReXGlue and the Xbox 360 executable. The old Rust implementation, its UI, its APKs, and its performance data must not be described as part of the current C++ build.

## Recorded results for the old Rust packages

The archived build report dates package `0.9.5` to 2026-10-21. It records a successful 15-minute ARM64 release build, APK signing verification, installation, and launcher start. The archived test status also records later package artifacts `0.9.6`, `0.9.7`, and `0.9.8`; it does not establish that they were cleanly rebuilt from one consistent source snapshot.

One gameplay trace for that Rust line measured roughly 1.7–1.9 seconds per frame after loading (about 0.5–0.6 FPS). Another capture showed about 2 FPS. An earlier session recorded an Android input-dispatch ANR. These are poor results from the Rust prototype only; they are not measurements of the C++ recomp or V8.

## What the records do not prove

- They do not establish stable gameplay, a completed race, or that the ANR was fixed.
- They do not establish compatibility with Mali, Xclipse, or all Android devices.
- They do not establish any performance result for the current C++/ReXGlue line.

The summary above is based on the archived `ANDROID-UNIVERSAL-ARM64-BUILD-REPORT.md`, `TESTING-STATUS.md`, and `KNOWN-ISSUES.md` from the private local Rust archive. Raw logs, screenshots, APKs, and the archive itself are not included in this Git repository.
