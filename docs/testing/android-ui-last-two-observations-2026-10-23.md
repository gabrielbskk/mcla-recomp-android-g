# V8 Android UI — latest two captures

These are the two most recent captures already available. No new capture was made by opening the game during this review.

| Local capture time | Screen state | What it supports |
|---|---|---|
| 2026-10-22 23:25 | V8 launcher asks for a ZIP or extracted folder; **Play** is disabled. | The launcher was displayed and did not report ready game data at that moment. |
| 2026-10-23 04:39 | V8 launcher says `Dados privados validados. Pronto para jogar.`; **Play** is enabled. | The app's private-data readiness check passed at the time of capture. |

Files:

- [`import-before-data-validation-2026-10-22.png`](../ui/import-before-data-validation-2026-10-22.png)
- [`import-private-data-ready-2026-10-23.png`](../ui/import-private-data-ready-2026-10-23.png)

## What these images do not prove

- The ready screen does not identify which action populated `filesDir/game`; by itself, it does not prove that the ZIP import flow completed.
- The game was not opened during this review, as requested by the user.
- No exported V8 log proves which files the runtime opened before car selection.
- There is no V8 FPS result, gameplay stability result, or V8 test without `.bik` videos.

At the end of the review, ADB was connected, but the package query did not find `org.mcla.recomp`; Termux was the foreground activity. No APK was installed or launched during this review. These images record past launcher states and do not describe the current installed-app state.
