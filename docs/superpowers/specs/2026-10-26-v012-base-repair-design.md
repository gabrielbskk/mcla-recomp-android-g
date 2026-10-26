# v0.1.2 Android Base Repair Design

## Intent

Keep the known v0.1.2 Open Beta Android launcher/import flow as the release
baseline, while retaining only the later fixes that are independently
traceable. The manual Termux packaging path must not silently combine a stale
base APK with current native libraries and DEX.

## Scope

- Treat `0933c57` / `open-beta-v0.1.2-20261023` as the baseline source and
  release identity.
- Keep later source fixes already on `feature/android-vk-cache`, including the
  guest-memory work, present metrics, and pipeline-cache instrumentation.
- Fix the manual DEX path so Apache Commons Compress is included at runtime.
- Add a preflight verifier for a candidate APK: package identity, launcher
  DEX import class, and required native libraries.
- Align XAPK metadata with the Open Beta application ID.

## Non-goals

- No APK build, installation, release, or ADB test in this change.
- No import of RenanQueiroz/mcla-recomp code. Its GPL-3.0 patches are reviewed
  only as technical references until a specific patch has Android evidence.
- No claim of performance improvement without a controlled device measurement.

## Design choices

The release APK is a validated packaging input, not source of truth: generated
DEX and native libraries are replaced only after a preflight checks that the
base has the current Open Beta package ID. The verifier also checks for the
ZIP importer class in `classes.dex`; this catches the exact missing
`ZipArchiveInputStream` regression before installation.

The next performance work remains measurement-led. Renan's Vulkan threaded
submission, async pipeline skipping, and render-target patches are not copied
because their published measurements are Windows/NVIDIA-specific and the S23
has shown rendering artifacts.
