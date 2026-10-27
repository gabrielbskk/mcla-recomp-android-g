#!/usr/bin/env bash
# Capture runtime evidence from an APK already present on the device; never changes package state.
set -euo pipefail

: "${ADB_SERIAL:?Set ADB_SERIAL to the confirmed device endpoint}"
: "${PACKAGE_NAME:=org.mcla.recomp.openbeta}"
: "${ACTIVITY_NAME:=org.mcla.recomp.DataSetupActivity}"
: "${DURATION_SECONDS:=20}"
: "${OUTPUT_DIR:?Set OUTPUT_DIR outside the repository for device logs}"

adb_bin="${ADB:-adb}"
mkdir -p "$OUTPUT_DIR"
"$adb_bin" -s "$ADB_SERIAL" wait-for-device
"$adb_bin" -s "$ADB_SERIAL" shell pm path "$PACKAGE_NAME" >/dev/null
"$adb_bin" -s "$ADB_SERIAL" logcat -c
"$adb_bin" -s "$ADB_SERIAL" shell am force-stop "$PACKAGE_NAME"
"$adb_bin" -s "$ADB_SERIAL" shell dumpsys SurfaceFlinger --latency-clear >/dev/null 2>&1 || true
"$adb_bin" -s "$ADB_SERIAL" shell am start -n "$PACKAGE_NAME/$ACTIVITY_NAME" \
  --es resolution "${RESOLUTION:-720p}" \
  --es effects "${EFFECTS:-super_low}" \
  --ei fps_limit "${FPS_LIMIT:-0}" \
  --ez vsync "${VSYNC:-false}" \
  --ez fps_counter true \
  --ez performance_logging true >/dev/null

started_at="$(date +%s)"
sample_file="$OUTPUT_DIR/sampled-top-${started_at}.txt"
gpu_file="$OUTPUT_DIR/gpu-busy-${started_at}.txt"
touch "$sample_file" "$gpu_file"

# Native Vulkan work is not represented by dumpsys gfxinfo.  Sample the game
# process and KGSL while it is alive so the report can distinguish CPU pressure
# from an idle/underutilized GPU.  Device shells differ, therefore failed
# samples are recorded as unavailable instead of aborting the capture.
(
  deadline=$(( $(date +%s) + DURATION_SECONDS ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    sample_ts="$(date -Is)"
    pid="$($adb_bin -s "$ADB_SERIAL" shell pidof "$PACKAGE_NAME" 2>/dev/null | tr -d '\r' | awk '{print $1}')"
    printf '\n[%s] pid=%s\n' "$sample_ts" "${pid:-unavailable}" >>"$sample_file"
    if [ -n "$pid" ]; then
      "$adb_bin" -s "$ADB_SERIAL" shell top -b -n 1 -H -p "$pid" 2>/dev/null \
        >>"$sample_file" || printf 'top=unavailable\n' >>"$sample_file"
    else
      printf 'top=unavailable\n' >>"$sample_file"
    fi
    gpu_busy="$($adb_bin -s "$ADB_SERIAL" shell cat /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage 2>/dev/null | tr -d '\r' || true)"
    printf '%s %s\n' "$sample_ts" "${gpu_busy:-unavailable}" >>"$gpu_file"
    sleep 1
  done
) &
sampler_pid=$!
sleep "$DURATION_SECONDS"
wait "$sampler_pid" || true
ended_at="$(date +%s)"

"$adb_bin" -s "$ADB_SERIAL" logcat -d -v threadtime >"$OUTPUT_DIR/logcat-${started_at}-${ended_at}.txt"
"$adb_bin" -s "$ADB_SERIAL" shell dumpsys gfxinfo "$PACKAGE_NAME" >"$OUTPUT_DIR/gfxinfo-${started_at}-${ended_at}.txt" || true
"$adb_bin" -s "$ADB_SERIAL" shell dumpsys meminfo "$PACKAGE_NAME" >"$OUTPUT_DIR/meminfo-${started_at}-${ended_at}.txt" || true
"$adb_bin" -s "$ADB_SERIAL" shell top -b -n 1 -H >"$OUTPUT_DIR/top-${started_at}-${ended_at}.txt" || true
"$adb_bin" -s "$ADB_SERIAL" shell dumpsys SurfaceFlinger --latency "$PACKAGE_NAME/$ACTIVITY_NAME" \
  >"$OUTPUT_DIR/surface-latency-${started_at}-${ended_at}.txt" || true
"$adb_bin" -s "$ADB_SERIAL" shell run-as "$PACKAGE_NAME" \
  cat files/mcla-recomp/logs/performance-v3.csv \
  >"$OUTPUT_DIR/performance-v3-${started_at}-${ended_at}.csv" || true
# Release APKs are not debuggable, so run-as cannot read their private CSV.
# Prefer the app's exported public log as evidence when available.
public_log="$($adb_bin -s "$ADB_SERIAL" shell 'ls -t /sdcard/Documents/MCLA/logs/log-mcla-*.txt 2>/dev/null | head -1' | tr -d '\r' || true)"
if [ -n "$public_log" ]; then
  "$adb_bin" -s "$ADB_SERIAL" pull -q "$public_log" \
    "$OUTPUT_DIR/public-log-${started_at}-${ended_at}.txt" >/dev/null || true
fi
printf 'package=%s\nactivity=%s\nresolution=%s\neffects=%s\nduration_s=%s\n' \
  "$PACKAGE_NAME" "$ACTIVITY_NAME" "${RESOLUTION:-720p}" "${EFFECTS:-super_low}" \
  "$DURATION_SECONDS" >"$OUTPUT_DIR/run-${started_at}-${ended_at}.txt"
printf 'Capture written to %s\n' "$OUTPUT_DIR"
