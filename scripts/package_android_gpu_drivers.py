#!/usr/bin/env python3
"""Validate and stage the pinned user-supplied Android Vulkan driver archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import zipfile
from pathlib import Path, PurePosixPath


DRIVERS = {
    "turnip": {
        "asset": "turnip-adreno740.zip",
        "library": "libvulkan_freedreno.so",
        "sha256": "66c5719bc3bc59ed8a94608eb12f4d6bac47133cd0ba1983409bea3d2a01e06c",
        "max_total": 32 * 1024 * 1024,
    },
    "panvk": {
        "asset": "panvk-mali-g52.zip",
        "library": "libvulkan_panfrost.so",
        "sha256": "a5da75ae597b23337825c5a35d480c7a7cc0c8655d35850ca5fd25b37ac78289",
        "max_total": 200 * 1024 * 1024,
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_archive(path: Path, driver_id: str) -> None:
    expected = DRIVERS[driver_id]
    if not path.is_file():
        raise SystemExit(f"Missing {driver_id} driver archive: {path}")
    actual_hash = sha256(path)
    if actual_hash != expected["sha256"]:
        raise SystemExit(f"Unexpected {driver_id} archive SHA-256: {actual_hash}")

    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = set()
            total_size = 0
            for entry in entries:
                name = entry.filename
                parsed = PurePosixPath(name)
                if (entry.is_dir() or parsed.is_absolute() or len(parsed.parts) != 1 or "\\" in name
                        or name in {".", ".."}):
                    raise SystemExit(f"Unsafe path in {driver_id} archive: {name}")
                if name in names:
                    raise SystemExit(f"Duplicate file in {driver_id} archive: {name}")
                names.add(name)
                total_size += entry.file_size
                if total_size > expected["max_total"]:
                    raise SystemExit(f"Expanded {driver_id} archive exceeds its size limit")
            if expected["library"] not in names or "meta.json" not in names:
                raise SystemExit(f"{driver_id} archive is missing its driver or metadata")
            if archive.testzip() is not None:
                raise SystemExit(f"CRC failure in {driver_id} archive")
            metadata = json.loads(archive.read("meta.json"))
            if metadata.get("libraryName") != expected["library"]:
                raise SystemExit(f"Unexpected library name in {driver_id} metadata")
            with archive.open(expected["library"]) as binary:
                header = binary.read(64)
            if len(header) < 20 or header[:4] != b"\x7fELF" or header[4:6] != b"\x02\x01":
                raise SystemExit(f"{driver_id} library is not little-endian ELF64")
            if struct.unpack_from("<H", header, 18)[0] != 183:
                raise SystemExit(f"{driver_id} library is not AArch64")
    except zipfile.BadZipFile as error:
        raise SystemExit(f"Invalid {driver_id} ZIP archive: {error}") from error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turnip", required=True, type=Path)
    parser.add_argument("--panvk", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    validate_archive(args.turnip, "turnip")
    validate_archive(args.panvk, "panvk")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for driver_id, source in (("turnip", args.turnip), ("panvk", args.panvk)):
        destination = args.output_dir / DRIVERS[driver_id]["asset"]
        shutil.copyfile(source, destination)
        print(f"Staged {driver_id}: {destination} ({destination.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
