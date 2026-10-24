import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HostCodegenTest(unittest.TestCase):
    def setUp(self):
        if not shutil.which("cmake") or not shutil.which("ninja"):
            self.skipTest("CMake and Ninja are required")
        self.temp = tempfile.TemporaryDirectory(prefix="host-codegen-", dir=ROOT / "tests")
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)
        self.build = self.source / "build"
        self.default = self.make_generator("default", "default")
        self.generated = self.source / "generated.cmake"
        self.generated.write_text('''
add_custom_command(OUTPUT "${CMAKE_BINARY_DIR}/result.txt"
    COMMAND $<TARGET_FILE:rex::rexglue> codegen "${CMAKE_BINARY_DIR}/result.txt"
    VERBATIM)
add_custom_target(generate ALL DEPENDS "${CMAKE_BINARY_DIR}/result.txt")
''')
        self.original = self.generated.read_bytes()
        (self.source / "CMakeLists.txt").write_text(f'''
cmake_minimum_required(VERSION 3.25)
project(HostCodegenTest NONE)
add_executable(default_codegen IMPORTED GLOBAL)
set_target_properties(default_codegen PROPERTIES IMPORTED_LOCATION "{self.default}")
add_executable(rex::rexglue ALIAS default_codegen)
include("{ROOT / 'cmake/HostCodegen.cmake'}")
mcla_prepare_codegen_cmake("{self.generated}" "${{CMAKE_BINARY_DIR}}/adapted.cmake")
include("${{CMAKE_BINARY_DIR}}/adapted.cmake")
''')

    def make_generator(self, name, output):
        path = self.source / name
        path.write_text(f"#!{sys.executable}\nimport pathlib, sys\n"
                        f"pathlib.Path(sys.argv[2]).write_text({output!r})\n")
        path.chmod(0o700)
        return path

    def configure(self, *args):
        return subprocess.run(["cmake", "-S", str(self.source), "-B", str(self.build),
                               "-G", "Ninja", *args], capture_output=True, text=True)

    def build_and_read(self):
        subprocess.run(["cmake", "--build", str(self.build)], check=True,
                       capture_output=True, text=True)
        return (self.build / "result.txt").read_text()

    def test_default_uses_sdk_target(self):
        result = self.configure()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.build_and_read(), "default")

    def test_explicit_host_wrapper_with_spaces_replaces_sdk_target(self):
        wrapper = self.make_generator("host wrapper", "host override")
        result = self.configure(f"-DREXGLUE_CODEGEN_EXECUTABLE={wrapper}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.build_and_read(), "host override")
        self.assertEqual(self.generated.read_bytes(), self.original,
                         "adapting codegen must not rewrite the generated source")
        # A later codegen run restores the same original rule; it must still
        # select the host wrapper after CMake regenerates its build files.
        self.generated.write_bytes(self.original + b"\n# regenerated\n")
        (self.build / "result.txt").unlink()
        self.assertEqual(self.build_and_read(), "host override")

    def test_missing_wrapper_fails_during_configuration(self):
        result = self.configure(f"-DREXGLUE_CODEGEN_EXECUTABLE={self.source / 'missing'}")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Host codegen executable not found", result.stderr)

    def test_unknown_generated_rule_requires_review(self):
        self.generated.write_text("# changed upstream template\n")
        result = self.configure()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unrecognized ReXGlue codegen rule", result.stderr)


if __name__ == "__main__":
    unittest.main()
