import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TRACE_CMAKE = REPO / "cmake" / "AndroidIoTrace.cmake"


class AndroidIoTraceCMakeTest(unittest.TestCase):
    def test_trace_is_enabled_for_runtime_and_host_filesystem_targets(self):
        with tempfile.TemporaryDirectory(prefix="mcla-cmake-trace-") as temp:
            project = Path(temp)
            (project / "CMakeLists.txt").write_text(
                "\n".join(
                    [
                        "cmake_minimum_required(VERSION 3.25)",
                        "project(AndroidIoTraceContract LANGUAGES C)",
                        'file(WRITE "${CMAKE_BINARY_DIR}/dummy.c" "int dummy(void) { return 0; }\\n")',
                        'add_library(rexruntime STATIC "${CMAKE_BINARY_DIR}/dummy.c")',
                        'add_library(rexfilesystem STATIC "${CMAKE_BINARY_DIR}/dummy.c")',
                        f'include("{TRACE_CMAKE.as_posix()}")',
                        "mcla_enable_android_io_trace()",
                        "foreach(target rexruntime rexfilesystem)",
                        "  get_target_property(definitions ${target} COMPILE_DEFINITIONS)",
                        '  if(NOT "MCLA_ANDROID_IO_TRACE=1" IN_LIST definitions)',
                        '    message(FATAL_ERROR "I/O trace missing from ${target}")',
                        "  endif()",
                        "endforeach()",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["cmake", "-S", str(project), "-B", str(project / "build")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
