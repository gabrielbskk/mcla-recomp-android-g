import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "patch_android_rexglue.py"
SPEC = importlib.util.spec_from_file_location("patch_android_rexglue", SCRIPT)
PATCHER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PATCHER)


COMMAND_HEADER = """#pragma once
#include <array>
#include <cstdint>
#include <vector>
  bool CanEndSubmissionImmediately() const;
  std::vector<draw_util::MemExportRange> memexport_ranges_;
"""

COMMAND_SOURCE = """#include <cstdint>
void VulkanCommandProcessor::CheckSubmissionFenceAndDeviceLoss(uint64_t await_submission) {
    VkResult wait_result =
        dfn.vkWaitForFences(device, uint32_t(await_submission - submission_completed_),
                            submissions_in_flight_fences_.data(), VK_TRUE, UINT64_MAX);
    VkResult fence_status =
        dfn.vkWaitForFences(device, 1, &submissions_in_flight_fences_[fences_awaited], VK_TRUE, 0);
}
void VulkanCommandProcessor::Readback() {
  if (!AwaitAllQueueOperationsCompletion()) {
    REXGPU_ERROR("Failed to await completion of Vulkan memexport readback");
  }
}
"""


TRACKER_SOURCE = """#include <cstdint>
#include <rex/assert.h>
void VulkanSubmissionTracker::Await() {
        if (dfn.vkWaitForFences(device, 1, &pending_pair.second, VK_TRUE, UINT64_MAX) ==
            VK_SUCCESS) {
          break;
        }
}
"""


class AndroidFenceMetricsPatchTest(unittest.TestCase):
    def test_header_adds_origin_counters_and_is_idempotent(self):
        patched = PATCHER.patch_android_fence_metrics_header(COMMAND_HEADER)
        self.assertIn("AndroidFenceWaitOrigin", patched)
        self.assertIn("android_fence_readback_wait_count_", patched)
        self.assertEqual(PATCHER.patch_android_fence_metrics_header(patched), patched)

    def test_command_processor_adds_wait_timing_and_is_idempotent(self):
        patched = PATCHER.patch_android_fence_metrics_command_processor(COMMAND_SOURCE)
        self.assertIn("MCLA_ANDROID_FENCE_METRICS_SOURCE", patched)
        self.assertEqual(patched.count("RecordAndroidFenceWait("), 3)
        self.assertEqual(PATCHER.patch_android_fence_metrics_command_processor(patched), patched)

    def test_tracker_adds_acquire_wait_timing(self):
        patched = PATCHER.patch_android_fence_metrics_submission_tracker(TRACKER_SOURCE)
        self.assertIn("MCLA_ANDROID_FENCE_METRICS_TRACKER", patched)
        self.assertIn("origin=acquire", patched)
        self.assertEqual(PATCHER.patch_android_fence_metrics_submission_tracker(patched), patched)


if __name__ == "__main__":
    unittest.main()
