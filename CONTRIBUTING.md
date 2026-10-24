# Contributing to MCLA Android

Start with [AGENTS.md](AGENTS.md), [the handoff](docs/contributing/HANDOFF.md),
and [the Android guide](android/README.md). Claude Code can use `CLAUDE.md` as
its entry point. The historical Rust prototype is not the current codebase.

## Get the current source

Fork the repository on GitHub and clone your fork recursively. The current
unmerged handoff and presentation-counter work is on `feat/present-fps-license`
in [PR #3](https://github.com/gabrielbskk/mcla-recomp-android-g/pull/3).
Until that PR merges, cloning only `main` does not include those changes.

For a read-only checkout of that development branch:

```sh
git clone --recurse-submodules --branch feat/present-fps-license \
  https://github.com/gabrielbskk/mcla-recomp-android-g.git
cd mcla-recomp-android-g
git switch -c contribution/describe-your-change
git remote -v
```

Contributors should push to their own fork and open a PR against the owner's
repository. Verify the destination explicitly; never reuse the maintainer's
credentials, signing key, device address, or private build cache.

## What is included and what is missing

The repository contains application sources, Android Java/resources, hook
configuration, SDK patches, tests, license notices and public historical reports.
ReXGlue v0.10.0 and its dependencies are external. `libadrenotools` is a pinned
Git submodule. Generated game code must be regenerated locally from your own
supported game files; neither it nor commercial assets are distributed here.

**A fresh-machine APK build is not yet reproducible from this checkout alone.**
The Termux resume script requires an existing compatible cache, patched SDK and
host code generator. The private packaging workflow has not been converted into
a complete public bootstrap. The handoff lists the gaps instead of inventing
commands that were never validated.

## Local checks

Python 3 runs the suite. Native header checks also need a C++ compiler; Java
checks need a JDK, and CMake fixture checks need CMake. Inspect skipped tests.

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

The 28-test result recorded for `0b3954b` covers host checks, not Android loading,
gameplay, GPU compatibility or an APK built from that commit.

## Changes and evidence

Use small commits and a focused PR. Explain the symptom, changed behavior,
source revision, checks run, and remaining risks. Performance submissions must
include scene, device/GPU/driver, settings, sample duration and cold/warm state,
with measured FPS and frame-time distributions. Never substitute guest ticks
or draw callbacks for presentation measurements.

Share sanitized summaries rather than raw device dumps. No game data, generated
game code, saves, APKs, keystores, tokens or pipeline caches belong in a PR.
Preserve third-party notices and resolve provenance before copying code.
