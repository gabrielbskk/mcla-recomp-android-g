PRIVATE REPOSITORY CONTENTS AND SAFETY SCOPE
============================================

Destination: a new private GitHub repository owned by the project maintainer.
Purpose: continue the MCLA C++ recomp Android ARM64 work from the latest
organized netbook source branch.

Included:
- C++ ARM64 recomp source snapshot from the organized netbook Android branch.
- Android V8 launcher and data-import source: SAF ZIP/folder selection,
  app-private `filesDir/game` preparation, progress service, validation and
  user-triggered diagnostics export.
- Graphics settings, touch controls, runtime diagnostics and build/package
  scripts from the source snapshot.
- V8 build notes, the two latest launcher-only screenshots, and a continuity
  summary that distinguishes current V8 evidence from earlier builds.
- This file, which records the intended private-repository contents.

Not included:
- Signing keystores, passwords, API tokens, SSH keys or other credentials.
- Original game files or extracted game data (XEX, RPF, ISO, OBB, ZIP, videos).
- APK, XAPK, OBB, build outputs, GPU driver archives or raw device logs.
- Gameplay screenshots/artwork and personal device screenshots. The only images
  included are two recent app-launcher UI captures with no game content.
- Local absolute paths and network/ADB credentials.

The signing keystore was moved to an owner-only local folder on the netbook,
outside the source tree. Original game files, build artifacts and raw diagnostic
logs remain in their existing netbook archive folders and are not staged here.

Status at selection:
- The V8 UI screenshot reports that its private-data readiness validator
  passed; the screenshot does not prove which import action populated the data.
- The user requested that the game not be opened during the latest review. The
  v8 runtime path through car selection and per-file runtime evidence remain
  unverified.
- There is no verified 30 FPS result; do not claim a measured performance gain.
- Older `/MLR`, broad-storage and OBB/XAPK behavior is historical and must not
  be presented as the V8 import flow. The V8 guide is `android/README.md`.
- A private repository protects the source from public visibility, but does
  not make game files or signing credentials appropriate to commit.

Before every future push, verify the destination remains private and review the
staged file list. Never force-push or add local build/data folders.
