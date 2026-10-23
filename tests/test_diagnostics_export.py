import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DiagnosticsExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("javac") or not shutil.which("java"):
            raise unittest.SkipTest("JDK is required for log export naming tests")

    def test_log_and_csv_exports_use_stable_content_names(self):
        with tempfile.TemporaryDirectory(prefix="mcla-log-export-", dir=ROOT / "tests") as classes:
            sources = [
                ROOT / "android/app/src/main/java/org/mcla/recomp/LogExportNaming.java",
                ROOT / "tests/LogExportNamingTest.java",
            ]
            subprocess.run(["javac", "-d", classes, *map(str, sources)], check=True)
            result = subprocess.run(
                ["java", "-cp", classes, "org.mcla.recomp.LogExportNamingTest"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("log export naming: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
