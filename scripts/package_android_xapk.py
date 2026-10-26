#!/usr/bin/env python3
"""Build a local XAPK containing the arm64 APK and a user's extracted game data."""

import argparse
import json
import os
import tempfile
import zipfile
from pathlib import Path


PACKAGE_NAME = "org.mcla.recomp.openbeta"
REQUIRED_GAME_FILES = (
    "default.xex",
    "xarchive_cache.rpf",
    "xarchive_audio.rpf",
    "xarchive_audlo.rpf",
    "xarchive_music.rpf",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package an arm64 MCLA Recomp APK and a private game-data OBB into one XAPK."
    )
    parser.add_argument("--apk", required=True, type=Path, help="Signed universal arm64 APK")
    parser.add_argument("--game-dir", required=True, type=Path, help="Extracted game data directory")
    parser.add_argument("--output", required=True, type=Path, help="Output .xapk path")
    parser.add_argument("--version-code", default=3, type=int)
    parser.add_argument("--version-name", default="0.1.2-experimental")
    parser.add_argument("--min-sdk", default=26, type=int)
    parser.add_argument("--target-sdk", default=35, type=int)
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output file")
    return parser.parse_args()


def validate_game_dir(game_dir: Path) -> list[Path]:
    root = game_dir.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    for name in REQUIRED_GAME_FILES:
        file_path = root / name
        if not file_path.is_file() or file_path.stat().st_size == 0:
            raise ValueError(f"Missing required game file: {file_path}")

    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symbolic links are not supported in game data: {path}")
        if path.is_file():
            files.append(path)
    if not files:
        raise ValueError("The game-data directory is empty")
    return files


def make_manifest(apk_name: str, obb_name: str, apk_size: int, obb_size: int,
                  version_code: int, version_name: str, min_sdk: int,
                  target_sdk: int) -> dict[str, object]:
    obb_path = f"Android/obb/{PACKAGE_NAME}/{obb_name}"
    return {
        "xapk_version": 1,
        "package_name": PACKAGE_NAME,
        "name": "MCLA Recomp",
        "version_code": str(version_code),
        "version_name": version_name,
        "min_sdk_version": str(min_sdk),
        "target_sdk_version": str(target_sdk),
        "total_size": apk_size + obb_size,
        "split_apks": [{"file": apk_name, "id": "base"}],
        "expansions": [{
            "file": obb_path,
            "install_location": "EXTERNAL_STORAGE",
            "install_path": obb_path,
        }],
    }


def main() -> None:
    args = parse_args()
    apk = args.apk.resolve(strict=True)
    game_dir = args.game_dir.resolve(strict=True)
    output = args.output.resolve()
    if not apk.is_file() or apk.suffix.lower() != ".apk":
        raise ValueError(f"Not an APK file: {apk}")
    if output.suffix.lower() != ".xapk":
        raise ValueError("Output filename must end in .xapk")
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"Output already exists (use --overwrite): {output}")

    files = validate_game_dir(game_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    apk_name = f"{PACKAGE_NAME}.apk"
    obb_name = f"main.{args.version_code}.{PACKAGE_NAME}.obb"
    obb_member = f"Android/obb/{PACKAGE_NAME}/{obb_name}"

    output_temporary_fd, output_temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(output_temporary_fd)
    output_temporary = Path(output_temporary_name)
    try:
        with tempfile.TemporaryDirectory(prefix="mcla-xapk-") as temporary_directory:
            obb = Path(temporary_directory) / obb_name
            with zipfile.ZipFile(obb, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                for path in files:
                    archive.write(path, path.relative_to(game_dir).as_posix(), compress_type=zipfile.ZIP_STORED)

            obb_size = obb.stat().st_size
            manifest = make_manifest(
                apk_name, obb_name, apk.stat().st_size, obb_size,
                args.version_code, args.version_name, args.min_sdk, args.target_sdk,
            )
            with zipfile.ZipFile(output_temporary, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as xapk:
                xapk.write(apk, apk_name, compress_type=zipfile.ZIP_STORED)
                xapk.write(obb, obb_member, compress_type=zipfile.ZIP_STORED)
                xapk.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    compress_type=zipfile.ZIP_DEFLATED,
                )
                xapk.writestr(
                    "INSTALL.txt",
                    "MCLA Recomp XAPK: install with an XAPK installer that copies the declared OBB.\n"
                    "On first launch, the app extracts the OBB into its app-owned game-data folder.\n"
                    "Keep several GB free for extraction. The archive contains the game data supplied to the packager.\n",
                    compress_type=zipfile.ZIP_DEFLATED,
                )
            os.replace(output_temporary, output)
    finally:
        output_temporary.unlink(missing_ok=True)

    print(f"Created: {output}")
    print(f"APK: {apk.stat().st_size:,} bytes; OBB: {obb_size:,} bytes")
    print(f"Game data files: {len(files)}")


if __name__ == "__main__":
    main()
