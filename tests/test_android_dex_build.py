import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AndroidDexBuildScriptTest(unittest.TestCase):
    def test_uses_modern_d8_and_current_java_sources(self):
        script = (ROOT / "scripts" / "build_android_dex.sh").read_text()
        self.assertIn("com.android.tools.r8.D8", script)
        self.assertIn("android/app/src/main/java", script)
        self.assertIn('"$COMMONS_COMPRESS_JAR"', script)
        self.assertNotIn("dx --dex", script)


if __name__ == "__main__":
    unittest.main()
