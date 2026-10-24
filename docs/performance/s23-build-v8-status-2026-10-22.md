# Android V8 Build — Historical Snapshot

This dated note records the V8 build state at the time of its original validation. It is retained as history and is superseded by [`CONTINUITY_SUMMARY.md`](../CONTINUITY_SUMMARY.md) for the current Open Beta status.

## Build Record

- A signed Android Release APK was produced for ARM64 (`arm64-v8a`).
- The package added a private ZIP/folder import flow and foreground data-sync service.
- The import validator requires `default.xex`, `xarchive_cache.rpf`, `xarchive_audio.rpf`, `xarchive_audlo.rpf`, and `xarchive_music.rpf`.
- The APK does not include game data. All game files and private saves remain under app-private storage.

## Evidence Limits at That Checkpoint

At the original checkpoint, the import flow and runtime file access had not been proven. No gameplay, performance, or 30 FPS claim should be inferred from a successful build or launcher readiness screen.

A later I/O-trace capture continued after an unsuccessful request for `intro720.bik` and reached car selection according to the user. That capture did not record attempts to open `nxeart` or `root_directory_padding.pad`; this is evidence from one run only and does not prove every scene works without video files.

The current status, including reported performance and input limitations, is in the [project continuity summary](../CONTINUITY_SUMMARY.md).
