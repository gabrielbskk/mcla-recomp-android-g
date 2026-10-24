# MCLA contributor entry point

Read `AGENTS.md` first; it is the shared source of repository rules for human
contributors, Claude Code, and other agents. Then read `CONTRIBUTING.md` and
`docs/contributing/HANDOFF.md` before building or changing runtime behavior.

This is the C++/ReXGlue Android project, not the archived Rust prototype.
Game data is imported into private `filesDir/game`. Do not restore old public
storage paths based on historical reports.

Preserve signing identity and saves. Ask the device owner to connect ADB and
confirm before installation or device testing. Never uninstall or clear data
without explicit permission. Keep game files, keys and personal logs outside Git.

Distinguish source implementation, host tests, built APK and device observations.
The development branch has presentation telemetry; its presence in source does
not establish that the hosted APK contains it. Do not infer performance gains
or a root cause from the research survey. Record reproducible evidence.

Review `THIRD_PARTY_NOTICES.md`: LARecomp redistribution permission remains
unconfirmed. Do not interpret this repository's license as clearing that issue.
