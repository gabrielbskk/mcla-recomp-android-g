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
- The root README now presents only the Android ARM64 scope, Termux/S23 build limits, verified V8 state, credits evidenced by the repository, copyright/game-file notice, and AI-assistance apology. The previous Windows/Linux/PS5 instructions are preserved in `docs/OTHER_PLATFORMS_HISTORICAL.md` as unverified historical material. `.recomp.json` now marks this fork experimental and lists Android ARM64 as its target; shared platform code/scripts remain in the source tree but are not claims of support.
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

The V8 launcher/import sources and ReXGlue patch script have been synchronized into this repository. The patch script supplies the I/O open/read trace, asynchronous logging, and Android pipeline behavior used by the V8 diagnostic build. This replaces earlier Java code and docs that searched a shared external game-data folder and requested broad file access. The newer performance-related C++ source from the main snapshot was retained; its Android `OnConfigurePaths` now selects SDL's internal app storage `game` directory and configures private rotating logs.

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

## Latest runtime stop state — 2026-10-23

- The user launched the V8 test app. The S23 log confirms the system Vulkan driver initialized and a 1080x2340 swapchain was created.
- The app then failed before `Runtime::LoadXexImage`: guest-memory backing-store creation failed and `Runtime::Setup` returned `C0000001`. No game files were opened in this run.
- Android's exported process diagnostics record a `SIGABRT` during teardown with `FORTIFY: pthread_mutex_lock called on a destroyed mutex`. Frames include `Presenter::RemoveUIDrawerFromUIThread` and `ReXApp::OnDestroy`. The teardown failure is distinct from the earlier memory error until a new trace proves otherwise.
- The raw log export is stored outside this repository. Its paths and device-specific process data are not copied into GitHub.
- ADB is currently disconnected. The last remembered wireless debugging endpoint refused a connection; no new APK has been installed in this resumed session.
- The Android ARM64 objects for the patched memory backend and guest-memory setup compile in the existing Termux CMake build tree. The patch logs backing-store errors and each failed `mmap` view (address, size, offset, flags, errno), and reports nine views on success. Six patcher unit checks pass. No APK was generated, and there is no app-process runtime evidence for this patch yet.
- The ReXGlue patch script now reruns successfully against both a clean v0.10.0 worktree and the existing Termux cache with its earlier Android trace variants.
- See [`s23-memory-init-investigation-2026-10-23.md`](performance/s23-memory-init-investigation-2026-10-23.md) for the source analysis and limits of the shell probes.

## Next steps when the user resumes testing

1. Build and run a test package containing the guest-memory initialization/errno instrumentation when device installation is authorized and ADB is available.
2. Verify backing-object creation, all nine guest mappings, and successful return from `Runtime::Setup` in the new log before proceeding.
3. Investigate the presenter/mutex teardown crash independently if it still occurs.
4. After Phase 1 passes, capture an FPS baseline and profile threads/fence waits; measure pipeline cache, thread affinity, swapchain image count, and native resolution one change at a time.
5. Review I/O traces after gameplay reaches car selection to determine whether `.bik`, `nxeart`, or padding files are requested. No such runtime evidence exists yet.
6. Keep build artifacts and originals in the netbook archive; push source only to the private GitHub repository after confirming privacy and reviewing the staged diff.

## Earlier builds (historical; not V8 behavior)

Older iterations used shared external game-data folders, OBB/XAPK, or broad storage access. Those are not the V8 import flow. Earlier Android runs reached the city scene in at least one build but had very poor FPS; they do not establish V8 behavior. Existing old logs include estimates of guest tick/render rate and process RSS, not a reliable Vulkan-present FPS measure. See `docs/performance/s23-runtime-analysis-2026-10-22.md` as historical context only.

## Repository map

- `src/`, `config/`, `mcla_manifest.toml`: C++ application and recomp metadata.
- `android/app/src/main/java/org/mcla/recomp/`: Android launcher, private import, log export, and GPU setup.
- `patches/`: project-maintained ReXGlue patches.
- `scripts/`: native build and packaging; requires local tools and user-owned game input.
- `docs/performance/`: build/performance notes, labeled by build/date.
- `docs/ui/`: the two latest launcher captures only.
- `docs/testing/`: evidence and test limits.
- APKs, ZIPs, raw logs, game data, and signing material: local netbook/device archives only; never Git.
