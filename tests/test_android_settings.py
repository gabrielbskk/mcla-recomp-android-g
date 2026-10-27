import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AndroidSettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("javac") or not shutil.which("java"):
            raise unittest.SkipTest("JDK is required for Android settings tests")

    def test_parse_validation_persistence_and_fps_counter_default(self):
        with tempfile.TemporaryDirectory(prefix="mcla-settings-test-") as classes:
            sources = [
                ROOT / "android/app/src/main/java/org/mcla/recomp/AppSettings.java",
                ROOT / "tests/AndroidSettingsTest.java",
            ]
            subprocess.run(["javac", "-d", classes, *map(str, sources)], check=True)
            result = subprocess.run(
                ["java", "-cp", classes, "AndroidSettingsTest"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("AndroidSettingsTest: PASS", result.stdout)

    def test_runtime_fps_counter_cvar_defaults_to_enabled(self):
        settings_menu = (ROOT / "src/settings_menu.cpp").read_text()
        app = (ROOT / "src/mcla_app.cpp").read_text()
        self.assertRegex(
            settings_menu,
            r'REXCVAR_DEFINE_BOOL\(mcla_fps_counter,\s*true,',
        )
        self.assertIn(
            'SetFpsCounterVisible(rex::cvar::GetFlagByName("mcla_fps_counter") == "true")',
            app,
        )

    def test_android_startup_forces_thirty_fps_cap(self):
        settings_menu = (ROOT / "src/settings_menu.cpp").read_text()
        self.assertIn(
            'SetFlagByName("mcla_fps", "30")',
            settings_menu,
            "Android startup must override persisted or intent FPS values with the fixed cap",
        )

    def test_native_graphics_preset_mapping(self):
        compiler = shutil.which("c++") or shutil.which("clang++")
        if not compiler:
            self.skipTest("a C++ compiler is required for graphics preset tests")
        with tempfile.TemporaryDirectory(prefix="mcla-graphics-presets-", dir=ROOT / "tests") as output:
            executable = Path(output) / "graphics-presets-test"
            subprocess.run([
                compiler, "-std=c++17", f"-I{ROOT / 'src'}",
                str(ROOT / "tests/test_graphics_presets.cpp"), "-o", str(executable),
            ], check=True, capture_output=True, text=True)
            result = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
            self.assertIn("graphics presets: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
