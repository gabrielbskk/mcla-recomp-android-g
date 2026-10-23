import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RenderMetricsTest(unittest.TestCase):
    def test_draw_rate_and_frame_time_statistics(self):
        compiler = shutil.which("c++") or shutil.which("clang++")
        if not compiler:
            self.skipTest("a C++ compiler is required for render metrics tests")
        with tempfile.TemporaryDirectory(prefix="mcla-render-metrics-", dir=ROOT / "tests") as output:
            executable = Path(output) / "render-metrics-test"
            subprocess.run([
                compiler, "-std=c++17", f"-I{ROOT / 'src'}",
                str(ROOT / "tests/test_render_metrics.cpp"), "-o", str(executable),
            ], check=True, capture_output=True, text=True)
            result = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
            self.assertIn("render metrics: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
