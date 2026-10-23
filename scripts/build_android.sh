#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
: "${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME to the Android NDK root}"
: "${REXSDK_DIR:?Set REXSDK_DIR to the Android-patched ReXGlue v0.10.0 tree}"
: "${REXGLUE_CODEGEN:?Set REXGLUE_CODEGEN to the host-native rexglue executable}"

cmake_bin="${CMAKE:-cmake}"
jobs="${JOBS:-4}"
host_lib_dir="${REXGLUE_HOST_LIB_DIR:-$(dirname -- "$(dirname -- "$REXGLUE_CODEGEN")")/lib}"

if [[ ! -f "$repo_root/game/default.xex" ]]; then
  echo "Missing game/default.xex. Extract your own supported MCLA Complete Edition (Xbox 360) dump first." >&2
  exit 2
fi
if [[ ! -x "$REXGLUE_CODEGEN" ]]; then
  echo "Host-native ReXGlue code generator is not executable: $REXGLUE_CODEGEN" >&2
  exit 2
fi
if [[ ! -f "$REXSDK_DIR/CMakeLists.txt" ]]; then
  echo "Android-patched ReXGlue SDK tree not found: $REXSDK_DIR" >&2
  exit 2
fi

python3 "$repo_root/scripts/patch_android_rexglue.py" --sdk "$REXSDK_DIR"
"$cmake_bin" --preset android-arm64-release -S "$repo_root" \
  -DMCLA_ANDROID_IO_TRACE="${MCLA_ANDROID_IO_TRACE:-OFF}"
export LD_LIBRARY_PATH="$host_lib_dir${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$REXGLUE_CODEGEN" codegen "$repo_root/mcla_manifest.toml"
"$cmake_bin" --build --preset android-arm64-release --target mcla --parallel "$jobs"
