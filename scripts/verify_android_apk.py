#!/usr/bin/env python3
"""Fail closed when a manually assembled Android APK is stale or incomplete."""

import argparse
import dataclasses
import pathlib
import re
import struct
import subprocess
import sys
import zipfile


REQUIRED_NATIVE_LIBRARIES = (
    "libmain.so",
    "librexruntime.so",
    "librexgpu-xenos.so",
)
ZIP_IMPORT_CLASS = b"Lorg/apache/commons/compress/archivers/zip/ZipArchiveInputStream;"


@dataclasses.dataclass(frozen=True)
class ApkBadging:
    package_name: str
    application_label: str | None


def parse_badging(text: str) -> ApkBadging:
    package = re.search(r"(?m)^package: name='([^']+)'", text)
    if package is None:
        raise ValueError("aapt2 output has no package name")
    label = re.search(r"(?m)^application-label:'([^']*)'", text)
    return ApkBadging(package.group(1), label.group(1) if label else None)


def _u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError("truncated DEX table")
    return struct.unpack_from("<I", data, offset)[0]


def _uleb128_end(data: bytes, offset: int) -> int:
    for _ in range(5):
        if offset >= len(data):
            raise ValueError("truncated DEX string length")
        value = data[offset]
        offset += 1
        if not value & 0x80:
            return offset
    raise ValueError("invalid DEX string length")


def dex_defines_class(data: bytes, descriptor: bytes) -> bool:
    """Return whether a DEX contains a class definition, not merely a reference."""
    if len(data) < 0x70 or not data.startswith(b"dex\n"):
        return False
    try:
        string_count, string_offset = _u32(data, 0x38), _u32(data, 0x3C)
        type_count, type_offset = _u32(data, 0x40), _u32(data, 0x44)
        class_count, class_offset = _u32(data, 0x60), _u32(data, 0x64)
        if string_offset + string_count * 4 > len(data):
            return False
        if type_offset + type_count * 4 > len(data):
            return False
        if class_offset + class_count * 32 > len(data):
            return False
        target_type = None
        for type_index in range(type_count):
            descriptor_index = _u32(data, type_offset + type_index * 4)
            if descriptor_index >= string_count:
                return False
            value_offset = _u32(data, string_offset + descriptor_index * 4)
            value_offset = _uleb128_end(data, value_offset)
            value_end = data.find(b"\0", value_offset)
            if value_end < 0:
                return False
            if data[value_offset:value_end] == descriptor:
                target_type = type_index
                break
        if target_type is None:
            return False
        return any(_u32(data, class_offset + class_index * 32) == target_type
                   for class_index in range(class_count))
    except ValueError:
        return False


def verify_archive(apk: pathlib.Path, badging: str, expected_package: str) -> list[str]:
    errors: list[str] = []
    try:
        parsed = parse_badging(badging)
    except ValueError as error:
        return [str(error)]
    if parsed.package_name != expected_package:
        errors.append(
            f"APK package is {parsed.package_name!r}, expected {expected_package!r}; "
            "do not assemble from this stale base APK."
        )

    try:
        with zipfile.ZipFile(apk) as archive:
            names = set(archive.namelist())
            dex_names = sorted(name for name in names if re.fullmatch(r"classes\d*\.dex", name))
            if not dex_names:
                errors.append("APK contains no classes.dex")
            elif not any(dex_defines_class(archive.read(name), ZIP_IMPORT_CLASS)
                         for name in dex_names):
                errors.append("APK DEX lacks ZipArchiveInputStream; ZIP import will crash.")
            for library in REQUIRED_NATIVE_LIBRARIES:
                if f"lib/arm64-v8a/{library}" not in names:
                    errors.append(f"APK lacks lib/arm64-v8a/{library}")
    except (OSError, zipfile.BadZipFile) as error:
        errors.append(f"cannot read APK ZIP: {error}")
    return errors


def expected_package_from_gradle(repo_root: pathlib.Path) -> str:
    gradle = (repo_root / "android/app/build.gradle").read_text(encoding="utf-8")
    match = re.search(r"applicationId\s+'([^']+)'", gradle)
    if match is None:
        raise ValueError("android/app/build.gradle has no applicationId")
    return match.group(1)


def dump_badging(aapt2: str, apk: pathlib.Path) -> str:
    completed = subprocess.run(
        [aapt2, "dump", "badging", str(apk)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "aapt2 dump badging failed")
    return completed.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", required=True, type=pathlib.Path)
    parser.add_argument("--aapt2", default="aapt2")
    args = parser.parse_args()
    apk = args.apk.resolve()
    if not apk.is_file():
        parser.error(f"not an APK file: {apk}")
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    try:
        errors = verify_archive(apk, dump_badging(args.aapt2, apk),
                                expected_package_from_gradle(repo_root))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"APK preflight failed: {error}", file=sys.stderr)
        return 2
    if errors:
        print("APK preflight failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"APK preflight passed: {apk}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
