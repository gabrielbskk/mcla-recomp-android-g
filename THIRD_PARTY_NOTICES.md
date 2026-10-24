# Third-Party Notices

This file records third-party code used by the source tree or Android build. Preserve the corresponding license notice when redistributing source or binaries. Full license texts are in `licenses/third_party/` unless noted otherwise.

| Component | Version / location | License | Use |
|---|---|---|---|
| SDL3 Android Java glue | 3.5.0; modified upstream Java sources in `android/app/src/main/java/org/libsdl/app/` | zlib | Android activity, input, and platform integration |
| SDL3 native library | Pinned by the external ReXGlue v0.10.0 dependency | zlib | Native Android platform, input, and audio integration |
| ReXGlue SDK | v0.10.0; external build dependency, with project patches under `patches/` | BSD 3-Clause | Xbox 360 static recompilation runtime/tooling; its license also attributes portions derived from Xenia |
| Dear ImGui | Pinned by the external ReXGlue v0.10.0 dependency | MIT | Runtime UI and touch controls |
| libucontext | Android ARM64 support added by `patches/rexglue-v0.10.0-android-arm64.patch` | Permissive license; copyright and permission notice required | ReXGlue context switching on Android ARM64 |
| Apache Commons Compress | 1.28.0; Gradle dependency | Apache-2.0 | ZIP/ZIP64 import |
| Apache Commons Codec | 1.19.0; required Commons Compress runtime dependency | Apache-2.0 | Transitive dependency |
| Apache Commons IO | 2.20.0; required Commons Compress runtime dependency | Apache-2.0 | Transitive dependency |
| Apache Commons Lang | 3.18.0; required Commons Compress runtime dependency | Apache-2.0 | Transitive dependency |
| libadrenotools | Git submodule `third_party/libadrenotools`, pinned by this repository | BSD 2-Clause | Optional Android Vulkan driver integration |
| Gradle Wrapper | Wrapper JAR under `android/gradle/wrapper/` | Apache-2.0 | Build tooling only; not part of the game runtime |

Commons Compress versions and licenses above follow its published 1.28.0 dependency metadata. Optional codecs are not listed as shipped dependencies. Confirm the resolved dependency graph and APK contents for each release before publishing an updated binary.

SDL's Java sources are modified project copies of upstream SDL Android glue. They remain identifiable as SDL code; project changes must not be presented as original SDL work. `docs/OTHER_PLATFORMS_HISTORICAL.md` is historical documentation, not a claim that this Android fork supports those platforms.

## LARecomp license check

Checked the `main` tree of [`mzzvxm/LARecomp` at commit `aa43aa991e204e2d4e10d046cecf652e4cea417a`](https://github.com/mzzvxm/LARecomp/tree/aa43aa991e204e2d4e10d046cecf652e4cea417a) on 2026-10-23. No `LICENSE`, `LICENSE.md`, or `COPYING` file is present in that commit's tree: **licença não declarada**. Therefore no license type, notice requirement, or copyleft obligation can be attributed to LARecomp from a repository license file. **LARecomp (commit aa43aa9): nenhum LICENSE encontrado; permissão de redistribuição não confirmada.** Source comments in this project say the author granted permission, but this checkout does not establish its scope for public source or binary redistribution. Do not treat the root GPL license as covering LARecomp-derived material.

Files explicitly marked as a port or adaptation from LARecomp:

- `src/settings_menu.cpp` and `config/settings_menu.toml` — pause-menu implementation and hook layout.
- `src/warp_fix.cpp` — warper hook adaptation.
- `src/button_prompts.cpp` and `config/ui.toml` — controller-prompt mechanism and hook configuration.

Other files attribute technical analysis or hook addresses, without claiming a copied code passage: `src/frame_timing.cpp`, `config/frame_timing.toml`, `src/perf_options.cpp`, `config/perf_options.toml`, and `config/render_perf.toml`. `src/mcla_app.cpp` only notes a similar symbolic-link behavior. These attributions identify provenance; they do not resolve redistribution rights. Game data, artwork, music, and other copyrighted game assets are not included here.

## Remaining redistribution question

Written confirmation covering the public source and adapted binaries is still needed, or the project must remove/replace the LARecomp-derived portions before claiming those materials are cleared for redistribution. The source repository and prior beta are already public; this check does not retroactively establish permission for them. Do not infer a permissive license or a copyleft license where the upstream `LICENSE` file is absent.

This inventory is based on the checked-in source and the configured ReXGlue v0.10.0 dependency. Verify the exact resolved SDK submodules, native link map, and APK contents when producing a distributable binary; this document is not a substitute for that artifact-specific check.

## License Texts

- SDL3 zlib license: [`licenses/third_party/SDL-3.5.0-zlib.txt`](licenses/third_party/SDL-3.5.0-zlib.txt)
- ReXGlue v0.10.0 BSD 3-Clause license and Xenia attribution: [`licenses/third_party/ReXGlue-v0.10.0-BSD-3-Clause.txt`](licenses/third_party/ReXGlue-v0.10.0-BSD-3-Clause.txt)
- Dear ImGui MIT license: [`licenses/third_party/Dear-ImGui-MIT.txt`](licenses/third_party/Dear-ImGui-MIT.txt)
- libucontext permission notice: [`licenses/third_party/libucontext-permissive.txt`](licenses/third_party/libucontext-permissive.txt)
- Apache License 2.0: [`licenses/third_party/Apache-2.0.txt`](licenses/third_party/Apache-2.0.txt)
- libadrenotools BSD 2-Clause license: [`licenses/third_party/libadrenotools-BSD-2-Clause.txt`](licenses/third_party/libadrenotools-BSD-2-Clause.txt)
