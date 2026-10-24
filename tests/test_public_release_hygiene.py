import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicReleaseHygieneTest(unittest.TestCase):
    def test_package_id_matches_open_beta_release(self):
        gradle = (ROOT / "android/app/build.gradle").read_text()
        self.assertIn("applicationId 'org.mcla.recomp.openbeta'", gradle)

    def test_android_guide_uses_open_beta_package(self):
        guide = (ROOT / "android/README.md").read_text()
        self.assertIn("org.mcla.recomp.openbeta", guide)
        self.assertNotIn("org.mcla.recomp.test", guide)

    def test_public_agent_guide_has_no_private_repository_instructions(self):
        guide = (ROOT / "AGENTS.md").read_text()
        self.assertIn("# Repository Guidelines", guide)
        self.assertNotIn("mcla-recomp-android-g", guide)
        self.assertNotIn("Cloud/", guide)
        self.assertFalse((ROOT / "READ_ME_FOR_GITHUB.txt").exists())

    def test_local_agent_memory_and_audit_history_are_ignored(self):
        ignore = (ROOT / ".gitignore").read_text().splitlines()
        self.assertIn("/agent.md", ignore)
        self.assertIn("/memory.md", ignore)
        self.assertIn("/.brooks-lint-history.json", ignore)

    def test_third_party_notices_cover_bundled_and_build_dependencies(self):
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text().lower()
        for name in ("sdl3", "commons compress", "commons io", "commons codec",
                     "commons lang", "rexglue", "libadrenotools", "dear imgui",
                     "libucontext"):
            self.assertIn(name, notices)
        self.assertTrue((ROOT / "licenses/third_party/Dear-ImGui-MIT.txt").is_file())
        self.assertTrue((ROOT / "licenses/third_party/libucontext-permissive.txt").is_file())


if __name__ == "__main__":
    unittest.main()
