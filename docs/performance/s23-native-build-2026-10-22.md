# S23 native Android build — 2026-10-22

## Result

The C++ recompilation and Android shared-library link completed successfully
on the S23 using Termux. After the Performance preset density adjustment, the
latest artifact is `$PREFIX/tmp/mcla-s23-native-android-build/libmain.so`
(77 MiB; 80,024,784 bytes).

The GPU emulation is a separate ReXGlue plugin and must be built separately.
The completed plugin is
`$HOME/rexglue-sdk-v0.10.0-s23/out/android-arm64/librexgpu-xenos.so`
(5.7 MiB; 5,885,056 bytes).

- ELF: 64-bit little-endian AArch64 shared object, Android API 24.
- SHA-256: `a872e33f66707b905dfcbee94a14a4db72d7475c0f4059856727541b30d40171`
- GPU plugin SHA-256:
  `7e491f6c48e2a3219d7b38cd34583cbd6a09ccfaad3a218f697a7b0e94e2f7e4`
- Direct dynamic dependencies: `librexruntime.so`, `libc.so`, `libm.so`,
  `libiconv.so`, `libOpenSLES.so`, `libdl.so`, `liblog.so`, `libandroid.so`,
  and `libc++_shared.so`.
- The build used the Android Vulkan backend and Android SDL platform/input/audio
  configuration. The Android API floor is 24.
- The plugin is also ELF64 AArch64 for Android API 24, depends on
  `librexruntime.so` and Android system libraries, and exports the expected
  `rex_gpu_abi_version` and `rex_gpu_create` entry points. It contains the
  Android texture-cache memory diagnostic string.

## Build fixes

The first shared-library link exposed two missing position-independent-code
settings in the Termux-hosted Android build:

1. Static `adrenotools` and `linkernsbypass` archives are embedded in
   `librexruntime.so`. Their targets now explicitly enable PIC for Android.
2. Generated PPC translation units form the `mcla_recomp` object library linked
   into `libmain.so`. That target now explicitly enables PIC for Android.

The Android Vulkan loader callback is optional. Its declaration is weak and
the SDK checks it before calling, allowing the system Vulkan loader when no
custom loader callback is linked. The patch script also handles an already
patched checkout idempotently.

## Validation limits

This confirms compilation and ELF metadata only. No APK/XAPK was packaged or
installed, the S23 game process was not launched, and no FPS or stability
measurement was made. This build must not be described as a tested playable
release. It is not validated on Mali or other Android GPUs. The app build still
emits a compiler warning about the AArch64 FPCR inline assembly operand width.

The XEX and generated game assets remain local and are not included in this
repository record.
