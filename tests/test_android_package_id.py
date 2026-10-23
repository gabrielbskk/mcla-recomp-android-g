import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AndroidPackageIdTest(unittest.TestCase):
    def test_side_by_side_package_changes_without_renaming_java_or_jni_namespace(self):
        gradle = (ROOT / "android/app/build.gradle").read_text()
        manifest = (ROOT / "android/app/src/main/AndroidManifest.xml").read_text()
        java_sources = list((ROOT / "android/app/src/main/java/org/mcla/recomp").rglob("*.java"))

        self.assertEqual(re.findall(r"applicationId\s+'([^']+)'", gradle),
                         ["org.mcla.recomp.test"])
        self.assertIn("namespace 'org.libsdl.app'", gradle)
        self.assertIn('android:name="org.mcla.recomp.MclaActivity"', manifest)
        self.assertIn('android:name="org.mcla.recomp.DataSetupActivity"', manifest)
        self.assertIn('android:name="org.mcla.recomp.DataImportService"', manifest)
        self.assertNotIn("android:authorities", manifest)
        self.assertFalse(re.search(r'android:name="\.[^\"]+"', manifest))
        self.assertTrue(java_sources)
        for source in java_sources:
            self.assertRegex(source.read_text(), r"(?m)^package org\.mcla\.recomp;")
        sdl_activity = ROOT / "android/app/src/main/java/org/libsdl/app/SDLActivity.java"
        self.assertRegex(sdl_activity.read_text(), r"(?m)^package org\.libsdl\.app;")


if __name__ == "__main__":
    unittest.main()
