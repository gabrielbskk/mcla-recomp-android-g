#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
: "${ANDROID_JAR:?Set ANDROID_JAR to the Android platform android.jar}"
: "${D8_JAR:?Set D8_JAR to a modern R8/D8 jar (dx is not supported)}"
: "${COMMONS_COMPRESS_JAR:?Set COMMONS_COMPRESS_JAR to commons-compress.jar}"
: "${DEX_OUT:?Set DEX_OUT to the output directory for classes.dex}"

if [[ ! -f "$ANDROID_JAR" || ! -f "$D8_JAR" || ! -f "$COMMONS_COMPRESS_JAR" ]]; then
  echo "Android Java build inputs are missing." >&2
  exit 2
fi

mkdir -p "$DEX_OUT"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/mcla-java-dex.XXXXXX")"
classes_dir="$work_dir/classes"
mkdir -p "$classes_dir"

javac -source 8 -target 8 \
  -cp "$ANDROID_JAR:$COMMONS_COMPRESS_JAR" \
  -d "$classes_dir" \
  $(find "$repo_root/android/app/src/main/java" -name '*.java' -print)

jar cf "$work_dir/classes.jar" -C "$classes_dir" .
java -cp "$D8_JAR" com.android.tools.r8.D8 \
  --lib "$ANDROID_JAR" \
  --min-api 26 \
  --output "$DEX_OUT" \
  "$work_dir/classes.jar"

test -s "$DEX_OUT/classes.dex"
echo "DEX: $DEX_OUT/classes.dex"
