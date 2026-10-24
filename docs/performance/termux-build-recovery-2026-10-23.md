# Termux native build recovery — 2026-10-23

## Finding and fix

The generic NDK preset was the wrong entry point for this Termux session. A
working cache already existed for this checkout, using Termux's ARM64 Clang
and the NDK sysroot. The directory name `linux-x86_64` in that sysroot does
not require executing the NDK's x86_64 compiler.

The next failure was codegen loading `libc++_shared.so`. The existing private
host wrapper successfully reports ReXGlue 0.10.0 and supplies the host-only
library environment. Its JNI stubs must never enter game runtime packaging.

`cmake/HostCodegen.cmake` now honors `REXGLUE_CODEGEN_EXECUTABLE`. CMake adapts
a build-directory copy of the generated boilerplate, because codegen rewrites
the source copy. Tests exercise the SDK default, an explicit wrapper with
spaces, regeneration, and invalid input. No SDK source was changed for this fix.

## Verified commands for the existing cache

From this repository in Termux:

```sh
export MCLA_BUILD_DIR="$HOME/mcla-builds/build_v2/android-arm64/mcla-stage3a"
export REXGLUE_CODEGEN="$HOME/mcla-builds/build_v2/toolchain/rexglue-codegen"
bash scripts/resume_android_termux_build.sh
```

The cache must identify this checkout as `CMAKE_HOME_DIRECTORY`. Its toolchain
is `build_v2/toolchain/termux-android-aarch64.cmake`, with API 26, ARM64 Clang,
NDK libc++ headers and sysroot. The patched SDK is the existing private
`$HOME/.cache/mcla-build-deps/rexglue-sdk-v0.10.0` tree. This resumes a known
cache; clean-machine dependency/bootstrap reproduction is still pending.

## Results and limits

- All three targets linked: `mcla`, `rexruntime`, `rexgpu-xenos`.
- ELF inspection identifies all three libraries as AArch64. Sizes: 80,168,672,
  12,297,624 and 5,920,976 bytes respectively.
- The exported compile database contains 914 commands. The three host-path
  I/O translation units contain `-DMCLA_ANDROID_IO_TRACE=1`; this is actual
  compilation configuration, not only the cache option.
- All 19 Android/SDL Java sources compiled against API 35 with Java 8 source
  and target flags. D8 produced a 2,256,584-byte DEX with minimum API 26.
  Inputs included Commons Compress 1.28.0, Commons IO 2.20.0 and Lang 3.18.0.
- Native warnings still include the inherited FPCR operand-width diagnostic.
  Javac reports obsolete Java 8 options and deprecated API usage.
- The native artifacts retain development RUNPATH entries. Loader behavior,
  packaging dependency closure, signing and device behavior remain gates.
- No APK was packaged or installed in this recovery. Native/DEX compilation
  does not prove import, presets, gamepad, overlay accuracy, or improved FPS.

Full commands, hashes, native libraries and DEX are kept in the private build
archive. No codegen JNI shim, game files, logs or binaries belong in Git.
