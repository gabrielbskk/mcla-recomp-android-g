# MCLA Recomp Android — continuity summary

Updated 2026-10-23. **V8 is the primary Android reference** in this repository. Earlier builds are historical and must be labeled as such; do not mix their storage behavior with the V8 flow.

## Project objective

Continue the C++ recompilation of *Midnight Club: Los Angeles Complete Edition* for Android ARM64, focusing on private data import, a simple launcher/configuration screen, diagnostics, and performance work. This remains an experimental recomp, not a release-ready Android game.

The project uses ReXGlue for static recompilation of PowerPC game code, with SDL/ReXGlue for graphics/runtime/input. Android ARM64 is the target for this line. Vulkan is the graphics backend recorded in the Android build. Universal GPU compatibility has not been demonstrated.

## Primary source and privacy

- Continuity repository: [`gabrielbskk/mcla-recomp-android-g`](https://github.com/gabrielbskk/mcla-recomp-android-g), private, branch `main`.
- Initial clean source import: commit `c23bd9a`.
- V8 Android launcher/import Java sources were synchronized from the V8 build source snapshot for this update. The C++ Android game-data and log paths were aligned to that private-storage flow while retaining the newer performance-related C++ changes from the source snapshot.
- Netbook working clone: `Cloud/01_MCLA_PROJETO/Codigo/mcla-recomp-android-g/`; local bare mirror: `Cloud/01_MCLA_PROJETO/Repositorios/mcla-recomp-android-g.git`; portable bundle backup: `Cloud/01_MCLA_PROJETO/Backups/Git/2026-10-23/`.
- Push source/documentation changes only to this private repository. Do not push to the older public repository without new authorization.
- Never commit original/extracted game data, XEX/RPF/ISO/BIK files, ZIP/XAPK/OBB, APKs, raw device logs, signing keys, passwords, tokens, SSH keys, saves, GPU-driver packages, or gameplay screenshots.
- The two retained images show only the launcher UI and contain no gameplay or user files.

## V8 Android behavior

Recorded app identity: `org.mcla.recomp`, `0.1.2-experimental`, `versionCode 3`, `arm64-v8a`, minimum Android API 26, target API 35.

1. `DataSetupActivity` lets the user choose a ZIP through Android SAF or an extracted directory through `ACTION_OPEN_DOCUMENT_TREE`. The `.bik` checkbox starts unchecked.
2. ZIP64 input is streamed with Apache Commons Compress. Directory import walks the SAF tree.
3. `DataImportService` runs as a foreground `dataSync` service with a `WAKE_LOCK`, reports progress, and implements Android 15's `onTimeout` callback.
4. Data is prepared in `filesDir/game.part`, validated, then promoted to `filesDir/game`. The previous game is preserved as `game.previous` when applicable; an existing previous copy stops a later import with an explicit message instead of being silently deleted.
5. Required files: `default.xex`, `xarchive_cache.rpf`, `xarchive_audio.rpf`, `xarchive_audlo.rpf`, and `xarchive_music.rpf`. V8 validates copied sizes and SHA-256 of `default.xex`, recording metadata in `.mcla_ready`.
6. `MANAGE_EXTERNAL_STORAGE` is not required for the V8 private flow. SAF grants access to the selected source only.
7. The ISO picker is present, but Xbox 360 XGD ISO extraction is not implemented. Extract it on a computer and import the resulting folder or ZIP.
8. Runtime logs stay private and are exported with **Export logs** using a user-selected SAF folder, such as `Documents/MCLA/logs`.

The V8 launcher/import sources have been synchronized into this repository. This replaces earlier Java code and docs that searched shared `/storage/emulated/0/MLR` and requested broad file access. The newer performance-related C++ source from the main snapshot was retained; its Android `OnConfigurePaths` now selects SDL's internal app storage `game` directory and configures private rotating logs.

## V8 build and artifacts

- Full build report on the netbook: `Cloud/01_MCLA_PROJETO/Builds/mcla-import-ux/build_v8/docs/BUILD_REPORT.txt`.
- Signed V8 Release APK: 38,971,639 bytes. Its SHA-256 is recorded only in the private netbook report. Do not copy the APK or its signature material into GitHub.
- The Android ARM64 build was compiled manually with Termux/Gradle, and the V8 APK was installed over the then-installed app on 2026-10-22.
- V8 manifest declares `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_DATA_SYNC`, and `WAKE_LOCK`; `DataImportService` uses `foregroundServiceType="dataSync"`.
- No APK was rebuilt during this review. The current changes align the source repository and docs with the V8 sources already present locally; they are not a new binary.

## Latest two UI captures

- 2026-10-22 23:25: launcher asked for data import and **Play** was disabled.
- 2026-10-23 04:39: launcher said `Dados privados validados. Pronto para jogar.` and enabled **Play**.

Images are under `docs/ui/`; interpretation and limits are in `docs/testing/android-ui-last-two-observations-2026-10-23.md`. The second capture supports that the readiness validator passed at that time. It does not show which import action populated the files, replace a service completion log, or prove the game was launched.

## Exact stop state

- The user explicitly asked **not to open the game**. That was followed: do not tap **Play**, install an APK, or build an APK as part of this documentation pass.
- ADB answered from the Samsung SM-S911B / Android 16. At the latest package query, `org.mcla.recomp` was not listed for the queried Android user and Termux was foregrounded. Do not confuse that current query with the earlier ready-screen capture.
- The import ZIP was not found among the paths checked on the phone/netbook. The netbook retains original data and prior packages; do not overwrite or move originals.
- A ready-screen capture exists, but no exported V8 I/O log was found proving that the user imported that ZIP through `DataImportService`.
- No game-specific `FATAL EXCEPTION`, Vulkan error, or ANR can be assessed from this review because the package was not installed at the check and the game was not started. The captured logcat was system activity without a gameplay session and must not be used as V8 runtime proof.

## Next steps when the user resumes testing

1. When asked, verify the correct V8 APK and signing state before any install. Do not uninstall another app or replace the current app without an explicit request.
2. The user selects their ZIP/folder in the V8 launcher and confirms import completion. Do not open the game without a separate explicit instruction.
3. Once gameplay testing is explicitly authorized, export app logs and test up to car selection. Review `android io trace open path=...` and `read ... bytes=...` lines to determine whether `.bik`, `nxeart`, or `root_directory_padding.pad` is opened.
4. If authorized, record direct evidence for the game proceeding without `.bik`.
5. Measure FPS/frame times, RAM/PSS, thermals, and load time in an authorized session. No V8 FPS gain or stable 30+ FPS claim is currently proven.
6. Test Mali G52/G57 and other GPUs separately. An ARM64 APK installing is not proof of graphics compatibility.
7. Keep build artifacts and originals in the netbook archive; push source only to the private GitHub repository after confirming privacy and reviewing the staged diff.

## Earlier builds (historical; not V8 behavior)

Older iterations used shared paths such as `/storage/emulated/0/MLR`, OBB/XAPK, or broad storage access. Those are not the V8 import flow. Earlier Android runs reached the city scene in at least one build but had very poor FPS; they do not establish V8 behavior. Existing old logs include estimates of guest tick/render rate and process RSS, not a reliable Vulkan-present FPS measure. See `docs/performance/s23-runtime-analysis-2026-10-22.md` as historical context only.

## Repository map

- `src/`, `config/`, `mcla_manifest.toml`: C++ application and recomp metadata.
- `android/app/src/main/java/org/mcla/recomp/`: Android launcher, private import, log export, and GPU setup.
- `patches/`: project-maintained ReXGlue patches.
- `scripts/`: native build and packaging; requires local tools and user-owned game input.
- `docs/performance/`: build/performance notes, labeled by build/date.
- `docs/ui/`: the two latest launcher captures only.
- `docs/testing/`: evidence and test limits.
- APKs, ZIPs, raw logs, game data, and signing material: local netbook/device archives only; never Git.
