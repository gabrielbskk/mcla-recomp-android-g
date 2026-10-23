PRIVATE REPOSITORY CONTENTS AND SAFETY SCOPE
============================================

Destination: a new private GitHub repository owned by the project maintainer.
Purpose: continue the MCLA C++ recomp Android ARM64 work from the latest
organized netbook source branch.

Included:
- Current source snapshot from netbook branch s23-native-build-2026-10-22
  (tip 15e81b0). The new repository starts with a clean baseline commit rather
  than copying historical objects that could contain removed private files.
- Android app scaffold, data bootstrap/import UI, touch controls, graphics
  settings, diagnostics, performance instrumentation and build/package scripts.
- Existing project documentation and the Android/S23 build findings that are
  already tracked in the source tree.
- This file, which records what was selected for GitHub.

Not included:
- Signing keystores, passwords, API tokens, SSH keys or other credentials.
- Original game files or extracted game data (XEX, RPF, ISO, OBB, ZIP, videos).
- APK, XAPK, OBB, build outputs, GPU driver archives or raw device logs.
- Original game screenshots/artwork in docs/images (kept on the netbook; README
  references to those files were removed).
- Local absolute paths and network/ADB credentials.

The signing keystore was moved to an owner-only local folder on the netbook,
outside the source tree. Original game files, build artifacts and raw diagnostic
logs remain in their existing netbook archive folders and are not staged here.

Status at selection:
- This is experimental Android ARM64 recomp source, not a stable release.
- The netbook records a signed v8 APK build, but the ZIP import and full runtime
  path through car selection were still pending confirmation.
- There is no verified 30 FPS result; do not claim a measured performance gain.
- A private repository protects the source from public visibility, but does
  not make game files or signing credentials appropriate to commit.

Before every future push, verify the destination remains private and review the
staged file list. Never force-push or add local build/data folders.
