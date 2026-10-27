import unittest
from pathlib import Path


SCRIPT = (Path(__file__).resolve().parents[1] / "scripts" / "capture_android_perf.sh").read_text()


class CaptureAndroidPerfScriptTest(unittest.TestCase):
    def test_capture_is_read_only_and_collects_runtime_csv(self):
        self.assertIn("wait-for-device", SCRIPT)
        self.assertIn("run-as", SCRIPT)
        self.assertIn("performance-v3.csv", SCRIPT)
        self.assertNotIn("pm clear", SCRIPT)
        self.assertNotIn("uninstall", SCRIPT)
        self.assertNotIn("install ", SCRIPT)

    def test_capture_samples_native_threads_and_gpu_busy(self):
        self.assertIn("sampled-top-", SCRIPT)
        self.assertIn("kgsl-3d0/gpu_busy_percentage", SCRIPT)
        self.assertIn("pidof", SCRIPT)

    def test_capture_falls_back_to_public_exported_logs_for_release_builds(self):
        self.assertIn("Documents/MCLA/logs", SCRIPT)
        self.assertIn("public-log", SCRIPT)


if __name__ == "__main__":
    unittest.main()
