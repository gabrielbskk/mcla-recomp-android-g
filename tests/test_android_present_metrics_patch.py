import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "patch_android_present_metrics", ROOT / "scripts/patch_android_present_metrics.py"
)
patcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patcher)


HEADER_FIXTURE = ""
SOURCE_FIXTURE = """#include <rex/ui/vulkan/presenter.h>
namespace rex { namespace ui { namespace vulkan {
#endif  // defined(REX_HAS_FIDELITYFX_RUNTIME) && REX_HAS_FIDELITYFX_RUNTIME

// Generated with `xb buildshaders`.
void PresentResult(VkResult result) {
  switch (result) {
    case VK_SUCCESS:
      return PaintResult::kPresented;
    case VK_SUBOPTIMAL_KHR:
      return PaintResult::kPresentedSuboptimal;
    case VK_ERROR_DEVICE_LOST:
      return PaintResult::kGpuLostResponsible;
  }
}
}}}
"""


class AndroidPresentPatchTest(unittest.TestCase):
    def test_observer_runs_only_for_successful_present_results(self):
        header, source = patcher.patch_sources(HEADER_FIXTURE, SOURCE_FIXTURE)
        self.assertIn("SetSuccessfulPresentObserver", header)
        self.assertIn("#include <rex/ui/vulkan/present_observer.h>", source)
        self.assertIn("case VK_SUCCESS:\n      NotifySuccessfulPresent();", source)
        self.assertIn("case VK_SUBOPTIMAL_KHR:\n      NotifySuccessfulPresent();", source)
        self.assertIn("case VK_ERROR_DEVICE_LOST:\n      return", source)

    def test_patch_is_idempotent(self):
        first = patcher.patch_sources(HEADER_FIXTURE, SOURCE_FIXTURE)
        second = patcher.patch_sources(*first)
        self.assertEqual(first, second)

    def test_refuses_unrecognized_or_partially_patched_source(self):
        with self.assertRaises(ValueError):
            patcher.patch_sources("no presenter", SOURCE_FIXTURE)
        with self.assertRaises(ValueError):
            patcher.patch_sources(HEADER_FIXTURE, SOURCE_FIXTURE.replace(
                "case VK_SUCCESS:", "case VK_SUCCESS: NotifySuccessfulPresent();"
            ))


if __name__ == "__main__":
    unittest.main()
