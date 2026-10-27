#!/usr/bin/env bash
# Assemble an arm64 APK from a known-good base without running Gradle.
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
: "${BASE_APK:?Set BASE_APK to the working Open Beta/base APK}"
: "${LIBMAIN:?Set LIBMAIN to the freshly built libmain.so}"
: "${REXRUNTIME:?Set REXRUNTIME to the freshly built librexruntime.so}"
: "${REXGPU_XENOS:?Set REXGPU_XENOS to the freshly built librexgpu-xenos.so}"
: "${APK_KEYSTORE:?Set APK_KEYSTORE outside the repository}"
: "${APK_KEY_ALIAS:?Set APK_KEY_ALIAS}"
: "${APK_STORE_PASSWORD:?Set APK_STORE_PASSWORD without putting it in the repository}"
: "${APK_KEY_PASSWORD:?Set APK_KEY_PASSWORD without putting it in the repository}"
: "${OUTPUT_APK:?Set OUTPUT_APK to the desired APK path}"

for input in "$BASE_APK" "$LIBMAIN" "$REXRUNTIME" "$REXGPU_XENOS" "$APK_KEYSTORE"; do
  test -f "$input" || { echo "Missing input: $input" >&2; exit 2; }
done

zipalign_bin="${ZIPALIGN:-zipalign}"
apksigner_bin="${APKSIGNER:-apksigner}"
aapt2_bin="${AAPT2:-aapt2}"
apktool_bin="${APKTOOL:-apktool}"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/mcla-apk.XXXXXX")"
unsigned="$work_dir/unsigned.apk"
aligned="$work_dir/aligned.apk"
mkdir -p "$(dirname -- "$OUTPUT_APK")"

if [[ "${APK_DEBUGGABLE:-0}" == "1" ]]; then
  "$apktool_bin" d -f -s -o "$work_dir/tree" "$BASE_APK" >/dev/null
  python3 - "$work_dir/tree/AndroidManifest.xml" <<'PY'
from pathlib import Path
import sys

manifest = Path(sys.argv[1])
text = manifest.read_text(encoding="utf-8")
needle = '<application '
if 'android:debuggable="true"' not in text:
    if needle not in text:
        raise SystemExit("application element not found in decoded AndroidManifest.xml")
    text = text.replace(needle, '<application android:debuggable="true" ', 1)
    manifest.write_text(text, encoding="utf-8")
PY
  cp "$LIBMAIN" "$work_dir/tree/lib/arm64-v8a/libmain.so"
  cp "$REXRUNTIME" "$work_dir/tree/lib/arm64-v8a/librexruntime.so"
  cp "$REXGPU_XENOS" "$work_dir/tree/lib/arm64-v8a/librexgpu-xenos.so"
  "$apktool_bin" b "$work_dir/tree" -o "$unsigned" >/dev/null
else
  unzip -q "$BASE_APK" -d "$work_dir/tree"
  find "$work_dir/tree/META-INF" -type f -delete 2>/dev/null || true
  cp "$LIBMAIN" "$work_dir/tree/lib/arm64-v8a/libmain.so"
  cp "$REXRUNTIME" "$work_dir/tree/lib/arm64-v8a/librexruntime.so"
  cp "$REXGPU_XENOS" "$work_dir/tree/lib/arm64-v8a/librexgpu-xenos.so"
  (cd "$work_dir/tree" && zip -qr -0 "$unsigned" .)
fi
"$zipalign_bin" -f -p 4 "$unsigned" "$aligned"
"$apksigner_bin" sign \
  --ks "$APK_KEYSTORE" \
  --ks-key-alias "$APK_KEY_ALIAS" \
  --ks-pass "env:APK_STORE_PASSWORD" \
  --key-pass "env:APK_KEY_PASSWORD" \
  --out "$OUTPUT_APK" "$aligned"
"$apksigner_bin" verify --verbose --print-certs "$OUTPUT_APK"
python3 "$repo_root/scripts/verify_android_apk.py" --apk "$OUTPUT_APK" --aapt2 "$aapt2_bin"
sha256sum "$OUTPUT_APK"
