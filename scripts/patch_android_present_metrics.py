#!/usr/bin/env python3
"""Add the Android successful-Vulkan-present observer to the pinned ReXGlue SDK."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


SDK_COMMIT = "f5337cdc947ff6d4c4196737e2c807a48f2a1fc2"
HEADER = Path("include/rex/ui/vulkan/present_observer.h")
SOURCE = Path("src/ui/vulkan/vulkan_presenter.cpp")
HEADER_CONTENT = """#pragma once

namespace rex {
namespace ui {
namespace vulkan {

using SuccessfulPresentObserver = void (*)();
void SetSuccessfulPresentObserver(SuccessfulPresentObserver observer);

}  // namespace vulkan
}  // namespace ui
}  // namespace rex
"""
SOURCE_INCLUDE_ANCHOR = "#include <rex/ui/vulkan/presenter.h>"
SOURCE_ANCHOR = "#endif  // defined(REX_HAS_FIDELITYFX_RUNTIME) && REX_HAS_FIDELITYFX_RUNTIME\n\n// Generated with `xb buildshaders`."
SOURCE_ADDITION = """#endif  // defined(REX_HAS_FIDELITYFX_RUNTIME) && REX_HAS_FIDELITYFX_RUNTIME

namespace {
std::atomic<SuccessfulPresentObserver> g_successful_present_observer{nullptr};

void NotifySuccessfulPresent() {
#if REX_PLATFORM_ANDROID
  if (const SuccessfulPresentObserver observer =
          g_successful_present_observer.load(std::memory_order_acquire)) {
    observer();
  }
#endif
}
}  // namespace

void SetSuccessfulPresentObserver(SuccessfulPresentObserver observer) {
  g_successful_present_observer.store(observer, std::memory_order_release);
}

// Generated with `xb buildshaders`."""
SUCCESS_CASE = "    case VK_SUCCESS:\n      return PaintResult::kPresented;"
SUCCESS_REPLACEMENT = "    case VK_SUCCESS:\n      NotifySuccessfulPresent();\n      return PaintResult::kPresented;"
SUBOPTIMAL_CASE = "    case VK_SUBOPTIMAL_KHR:\n      return PaintResult::kPresentedSuboptimal;"
SUBOPTIMAL_REPLACEMENT = (
    "    case VK_SUBOPTIMAL_KHR:\n      NotifySuccessfulPresent();\n"
    "      return PaintResult::kPresentedSuboptimal;"
)


def patch_sources(header_text: str, source_text: str) -> tuple[str, str]:
    if not header_text:
        header_text = HEADER_CONTENT
    elif header_text != HEADER_CONTENT:
        raise ValueError("unexpected present observer header; refusing to overwrite it")

    if "NotifySuccessfulPresent" not in source_text:
        if source_text.count(SOURCE_INCLUDE_ANCHOR) != 1:
            raise ValueError("unexpected Vulkan presenter source; expected one presenter include")
        if source_text.count(SOURCE_ANCHOR) != 1:
            raise ValueError("unexpected Vulkan presenter source; expected one FidelityFX anchor")
        if source_text.count(SUCCESS_CASE) != 1 or source_text.count(SUBOPTIMAL_CASE) != 1:
            raise ValueError("unexpected present result switch; refusing partial instrumentation")
        source_text = source_text.replace(
            SOURCE_INCLUDE_ANCHOR,
            SOURCE_INCLUDE_ANCHOR + "\n#include <rex/ui/vulkan/present_observer.h>", 1,
        )
        source_text = source_text.replace(SOURCE_ANCHOR, SOURCE_ADDITION, 1)
        source_text = source_text.replace(SUCCESS_CASE, SUCCESS_REPLACEMENT, 1)
        source_text = source_text.replace(SUBOPTIMAL_CASE, SUBOPTIMAL_REPLACEMENT, 1)
    elif "SetSuccessfulPresentObserver" not in source_text:
        raise ValueError("partial present instrumentation detected")

    return header_text, source_text


def apply_patch(sdk_root: Path, *, check_revision: bool = True) -> None:
    if check_revision:
        revision = subprocess.run(
            ["git", "-C", str(sdk_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if revision != SDK_COMMIT:
            raise ValueError(f"expected ReXGlue {SDK_COMMIT}, found {revision}")

    header_path = sdk_root / HEADER
    source_path = sdk_root / SOURCE
    existing_header = header_path.read_text(encoding="utf-8") if header_path.exists() else ""
    header_text, source_text = patch_sources(
        existing_header, source_path.read_text(encoding="utf-8")
    )
    header_path.write_text(header_text, encoding="utf-8")
    source_path.write_text(source_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk", required=True, type=Path, help="ReXGlue SDK source directory")
    args = parser.parse_args()
    apply_patch(args.sdk.resolve())
    print(f"Applied Android successful-present observer to ReXGlue {SDK_COMMIT}")


if __name__ == "__main__":
    main()
