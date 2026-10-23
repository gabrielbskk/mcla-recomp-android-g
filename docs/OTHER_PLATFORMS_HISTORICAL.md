# Archived platform material from the former shared README

> Historical reference only. This text was carried over from the former shared README and is not an active guide for this Android-focused fork. Its build claims, requirements, and commands may be stale and refer to the previous shared/upstream project. This fork does not claim to support, build, or test Windows, Linux, or PS5. Use the [Android README](../README.md) and [Android build guide](../android/README.md) for this fork.

The platform-specific text below is preserved so the old material remains available without crowding or confusing the Android project page.

## Windows

You need Windows 10 or 11 (x86-64) with a Direct3D 12 graphics card, and about 20 GB of disk. In PowerShell:

```powershell
git clone https://github.com/holdmysocks/mcla-recomp.git
cd mcla-recomp
.\scripts\make_pc.ps1 -Iso C:\path\to\your.iso
```

The script checks for Git, CMake, Ninja, Python 3, Visual Studio Build Tools 2022 (C++ workload) and the project's own Clang 20, and offers to install what is missing (answer `y`, or add `-InstallTools`); the Build Tools ask for administrator rights. It then clones and patches the ReXGlue SDK v0.10.0, builds it (the long step, once), extracts your game into `game\`, recompiles it and builds `out\build\win-amd64-release\mcla.exe`. Each step is skipped when its result is already there, so after a failure or an update you run the same command again. Logs are in `out\logs`.

**Play:** double-click the **Midnight Club Los Angeles** shortcut the build leaves in the repository folder, or `mcla.exe` itself. Keep the folder where it was built; the game data is read from `game\`. An Xbox or PlayStation controller works.

Options go after the program name, for example `mcla.exe --fullscreen=true --mcla_fps=60` (30, 60, 120, or 0 for uncapped). The pause menu has three extra entries: DISPLAY (frame-rate target, vsync, fullscreen, motion blur, depth of field), PERFORMANCE (detail options) and CONTROLS (button prompts, intro speed); changes are saved to `mcla.toml` next to `mcla.exe`.

**Update:** `git pull`, then `.\scripts\make_pc.ps1` again.

| If | Then |
|---|---|
| The SDK build fails with `'crtversion.h' file not found` | Another Clang on your path was used. Update and run `make_pc.ps1` again: it now uses only its own. |
| Step 1 fails after downloading Clang, with `unable to run program "xz -d -qq"` | Windows 10's `tar.exe` cannot unpack `.tar.xz`. Update and run `make_pc.ps1` again: it now unpacks the archive with Python when `tar.exe` cannot. |
| `codegen failed` | `game\default.xex` is missing or not the supported release; see the end of `out\codegen.log`. |
| The game closes by itself | Start it with `--log_file=run.log --log_level=info` and open an issue with the end of that file. |

## Linux

Tested on Ubuntu 26.04. You need Clang 20 and LLD (`clang-20`, `clang++-20`, `lld-20`), CMake 3.25+, Ninja, Python 3, Git, a Vulkan 1.3 driver, and these packages (Debian/Ubuntu names): `libgtk-3-dev libx11-xcb-dev libxss-dev libvulkan-dev libwayland-dev libwayland-bin wayland-protocols libxkbcommon-dev libdecor-0-dev libasound2-dev libpulse-dev libpipewire-0.3-dev`. Linux 6.11 or newer is recommended.

```bash
git clone https://github.com/holdmysocks/mcla-recomp.git
cd mcla-recomp
git clone --recursive --branch v0.10.0 https://github.com/rexglue/rexglue-sdk.git third_party/rexglue-sdk
cd third_party/rexglue-sdk
git apply ../../patches/rexglue-v0.10.0-mcla.patch
git apply ../../patches/rexglue-minmax-blend-factor.patch
git -C thirdparty/FFmpeg apply ../../../../patches/rexglue-ffmpeg-ps5-config.patch
git apply ../../patches/rexglue-linux-procmap-query.patch
git apply ../../patches/rexglue-linux-wait-sleep.patch
CC=clang-20 CXX=clang++-20 cmake --preset linux-amd64 -DREXGLUE_USE_VULKAN=ON -DREXGLUE_ENABLE_TRACY=OFF
cmake --build out/build/linux-amd64 --config Release
cmake --install out/build/linux-amd64 --config Release
cd ../..
python3 scripts/extract_game.py /path/to/your.iso
SDK=$PWD/third_party/rexglue-sdk/out/install/linux-amd64
"$SDK/bin/rexglue" codegen mcla_manifest.toml
CC=clang-20 CXX=clang++-20 cmake --preset linux-amd64-release -DCMAKE_PREFIX_PATH="$SDK"
cmake --build --preset linux-amd64-release
./scripts/play_linux.sh
```

On Wayland, put `vulkan_allow_present_mode_immediate = false` and `vulkan_allow_present_mode_mailbox = false` in `out/build/linux-amd64-release/mcla.toml`; without them the game presents about 1,000 times a second and keeps the GPU busy.

## PS5

You need a jailbroken PS5 that runs homebrew, with an FTP server payload (port 2121 by default) and a homebrew mounter that shows folders under `/data/homebrew` on the home screen (ShadowMountPlus was used). The build runs on **Arch Linux as root**: on Windows, an Arch distribution under WSL2. Allow about 30 GB of disk, 16 GB of memory, and about 45 minutes the first time.

On Windows, in PowerShell as administrator:

```powershell
wsl --install --no-distribution
wsl --update
wsl --install -d archlinux
wsl -d archlinux -u root
```

Then, in that Linux shell (your Windows drives are under `/mnt`, so `C:\Games\mcla.iso` is `/mnt/c/Games/mcla.iso`):

```bash
pacman -Sy --noconfirm git
cd /root
git clone https://github.com/holdmysocks/mcla-recomp.git
cd mcla-recomp
bash ps5/make_ps5.sh --iso /mnt/c/path/to/your.iso --console 192.168.1.50
```

Use your console's address, and start the FTP payload first. Without `--console` it only builds and prints what to copy where. Keep the repository under `/root`, not `/mnt/c`. The script installs its packages, builds the PS5 toolchain and Vulkan driver ([mihawk-99/PS5_Vulkan](https://github.com/mihawk-99/PS5_Vulkan)), patches and builds the SDK, extracts and recompiles your game, packages the title and uploads it. Each step is skipped when its result exists, so you run the same command again after a failure or an update (`git pull` first). Logs are in `/root/mcla/logs`.

After the upload, let the mounter pick up `/data/homebrew/PPSA99779`; "Midnight Club: Los Angeles" appears on the home screen. On the console, `/data/mcla/game` holds the game data, `/data/mcla/mcla.toml` the settings and `/data/mcla/mcla-play.log` the log of the last start.

**Your own tile and theme (optional).** No artwork or music ships here. `--tile IMAGE` takes any common image (for example the [official cover art](https://assets-prd.ignimgs.com/2022/04/17/midnightcomplete-1650239367276.jpg)); `--theme FILE.at9` takes an ATRAC9 file. For a theme, turn the audio down first (`ffmpeg -i in.m4a -af loudnorm=I=-28:TP=-2 -ar 48000 -ac 2 quiet.wav`), then convert it with [AT9-AT3 Converter](https://github.com/BMK-Studio/AT9-AT3_Converter/releases) (AT9, PS4, bitrate 72). The console keeps a title's tile and sound from when it was first registered.

| If | Then |
|---|---|
| `this script needs Arch Linux` | Install Arch under WSL2 as above. |
| `SDK patch does not apply` | Remove `/root/mcla/rexglue-sdk` and run again. |
| `no FTP server at ...` | Start the FTP payload; check the address and `--ftp-port`. |
| A bar with frame rate and temperatures over the game | That is your homebrew enabler's overlay (with OnionHEN, `[overlay] enabled=false` in `/data/OnionHEN/config.ini`). |
| The game stops or closes | Fetch `/data/mcla/mcla-play.log` over FTP before starting it again and open an issue with it, your console model and firmware. |

If you hand this to an AI agent: it needs your disc image's path and the console's address from you, must not look for or download a disc image, and writes to the console only with `--console`.
