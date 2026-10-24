# Repository Guidelines

## Project Structure

- `src/` contains the C++ application and Android integration; `config/` contains recompilation and gameplay configuration.
- `android/app/` contains the SDL-based Android launcher, data importer, diagnostics exporter, manifest, and resources.
- `patches/` and `scripts/` maintain the ReXGlue patches and build/package workflows.
- `tests/` contains Python and C++ checks. `docs/` records public build history, test evidence, and known limitations.
- `third_party/libadrenotools` is a Git submodule. Initialize it with `git submodule update --init --recursive` when building.

## Build and Test

The Android build requires a local ReXGlue v0.10.0 tree, Android SDK/NDK, and user-supplied game files; none belong in Git. See `android/README.md` for the supported Termux ARM64 workflow and environment variables. Do not use the full Gradle build on Termux: its CMake/AAPT2 host binaries are x86-64.

Run the Python checks with:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

Some native checks require the CMake toolchain and generated ReXGlue code. Do not report an Android build or device test as successful without its actual command output and device evidence.

## Style and Changes

Follow nearby conventions: two-space indentation and `snake_case` for C++; four-space indentation and Java camelCase for Android classes. Keep Android package `org.mcla.recomp.openbeta` aligned across Gradle, documentation, and intent examples; Java/JNI namespaces remain `org.mcla.recomp` and `org.libsdl.app`.

Use small, descriptive commits (for example, `fix(android): validate imported archive paths`). Explain user-visible changes and test evidence in pull requests. Do not claim performance or hardware compatibility without measurements.

## Security and Licensing

The repository `gabrielbskk/mcla-recomp-android-g` is public by the owner's decision. Never change its visibility, publish a release, or delete a release without explicit authorization.

Never commit signing keys or keystores, tokens, `.env` files, game data (`.xex`, `.rpf`, `.bik`, `nxeart`), OBB/XAPK files, shader or pipeline caches, or logs containing personal data. Before each push, inspect `.gitignore` and list the files that will be sent. Preserve third-party notices. Before redistributing code or binaries adapted from a third-party project (including LARecomp), inspect that project's original `LICENSE` and record the result in `THIRD_PARTY_NOTICES.md`. The game and its assets are not included or licensed by this project.
