# Android build v8 status (2026-10-22)

This note records the last known state before the next on-device validation.

## Confirmed in the build record

- A signed Android Release APK was produced for ARM64 (`arm64-v8a`) and installed
  as an update on the S23.
- The game-data ZIP was transferred to the device and its copy was verified
  against the netbook copy.
- The ZIP contains the expected executable and four RPF archives. It omits BIK
  videos, `nxeart`, and `root_directory_padding.pad`.
- The APK manifest includes notification and data-sync foreground-service
  declarations; broad all-files access is not required.

## Still unverified

- The import flow had not yet been run with this ZIP.
- There is no runtime evidence showing whether the game opens BIK videos,
  `nxeart`, or `root_directory_padding.pad`.
- Reaching car selection with this build was not confirmed.
- No FPS measurement was captured. The project has no verified 30 FPS result.

Do not treat this build as a stable release. Continue by importing the local
game-data ZIP on-device, capturing the app's exported diagnostics, and recording
the exact point reached. Keep the ZIP, APK, signing material, and raw logs on the
netbook or device only; do not attach them to this repository.

## Follow-up observation (2026-10-23)

The later launcher capture at `docs/ui/import-private-data-ready-2026-10-23.png`
shows `Dados privados validados. Pronto para jogar.` and an enabled **Jogar**
button. The V8 launcher checks `filesDir/game` and enables the button only after
`DataImportService.validateInstalledGame()` succeeds. This shows that the
private files passed the launcher's readiness validator at capture time, but
does not identify how they arrived or prove the import service's completion
message. It does not prove that the native game opened any particular asset.

The user then explicitly asked not to open the game. The latest ADB check found
no installed `org.mcla.recomp` package in the queried Android user, with
Termux in the foreground. No APK was installed and no gameplay test was run in
the 2026-10-23 review. See `docs/testing/android-ui-last-two-observations-2026-10-23.md`
and `docs/CONTINUITY_SUMMARY.md` for the current handoff.
