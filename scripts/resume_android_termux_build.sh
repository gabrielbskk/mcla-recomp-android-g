#!/usr/bin/env bash
# Resume an existing, verified ARM64 Termux CMake tree; does not package an APK.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
: "${MCLA_BUILD_DIR:?Set MCLA_BUILD_DIR to the existing Termux CMake build directory}"
: "${REXGLUE_CODEGEN:?Set REXGLUE_CODEGEN to the verified host-native codegen wrapper}"

python3 - "$repo_root" "$MCLA_BUILD_DIR" <<'PY'
import pathlib, sys
repo, build = map(pathlib.Path, sys.argv[1:])
cache = build / 'CMakeCache.txt'
if not cache.is_file():
    raise SystemExit('No existing CMake cache; this script does not bootstrap a fresh build.')
values = {}
for line in cache.read_text().splitlines():
    if line and not line.startswith(('#', '//')) and '=' in line:
        key, value = line.split('=', 1)
        values[key.split(':', 1)[0]] = value
if pathlib.Path(values.get('CMAKE_HOME_DIRECTORY', '')).resolve() != repo.resolve():
    raise SystemExit('Refusing to reuse a CMake cache belonging to another checkout.')
for key in ('CMAKE_TOOLCHAIN_FILE', 'REXSDK_DIR'):
    if not values.get(key) or not pathlib.Path(values[key]).exists():
        raise SystemExit(f'Missing cached {key}; restore the verified build dependencies first.')
PY

"$REXGLUE_CODEGEN" --version
cmake -S "$repo_root" -B "$MCLA_BUILD_DIR" \
    -DREXGLUE_CODEGEN_EXECUTABLE="$REXGLUE_CODEGEN" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build "$MCLA_BUILD_DIR" --target mcla rexruntime rexgpu-xenos \
    --parallel "${JOBS:-2}"
