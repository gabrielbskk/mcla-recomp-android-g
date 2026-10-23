import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "patch_android_rexglue.py"
SPEC = importlib.util.spec_from_file_location("patch_android_rexglue", SCRIPT)
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)


MEMORY_BACKEND = """#if REX_PLATFORM_ANDROID
  // TODO(Triang3l): Check if memfd can be used instead on API 30+.
  if (android_ASharedMemory_create_) {
    int sharedmem_fd = android_ASharedMemory_create_(path.c_str(), length);
    return sharedmem_fd >= 0 ? static_cast<FileMappingHandle>(sharedmem_fd)
                             : kFileMappingHandleInvalid;
  }

  // Use /dev/ashmem on API versions below 26, which added ASharedMemory.
  // /dev/ashmem was disabled on API 29 for apps targeting it.
  // https://chromium.googlesource.com/chromium/src/+/master/third_party/ashmem/ashmem-dev.c
  int ashmem_fd = open("/" ASHMEM_NAME_DEF, O_RDWR);
  if (ashmem_fd < 0) {
    return kFileMappingHandleInvalid;
  }
  char ashmem_name[ASHMEM_NAME_LEN];
  strlcpy(ashmem_name, path.c_str(), rex::countof(ashmem_name));
  if (ioctl(ashmem_fd, ASHMEM_SET_NAME, ashmem_name) < 0 ||
      ioctl(ashmem_fd, ASHMEM_SET_SIZE, length) < 0) {
    close(ashmem_fd);
    return kFileMappingHandleInvalid;
  }
  return static_cast<FileMappingHandle>(ashmem_fd);
#else
"""

GUEST_MAPS = """    if (!views_.all_views[n]) {
      // Failed, so bail and try again.
      UnmapViews();
      return 1;
    }
  REXSYS_INFO("Guest memory arena mapped: virtual base 0x{:016X}, physical base 0x{:016X}",
              reinterpret_cast<uintptr_t>(virtual_membase_),
              reinterpret_cast<uintptr_t>(physical_membase_));
"""


class AndroidMemoryPatchTest(unittest.TestCase):
    def test_initializes_android_shared_memory_before_creating_mapping(self):
        patched = PATCHER.patch_android_memory_backend(MEMORY_BACKEND)
        self.assertLess(patched.index("std::call_once"), patched.index("android_ASharedMemory_create_"))
        self.assertIn("ASharedMemory_create failed", patched)
        self.assertIn("ashmem ASHMEM_SET_SIZE failed", patched)
        self.assertIn("errno", patched)

    def test_memory_backend_patch_is_idempotent(self):
        once = PATCHER.patch_android_memory_backend(MEMORY_BACKEND)
        twice = PATCHER.patch_android_memory_backend(once)
        self.assertEqual(once, twice)

    def test_rejects_unknown_sdk_memory_backend(self):
        with self.assertRaises(SystemExit):
            PATCHER.patch_android_memory_backend("#if REX_PLATFORM_ANDROID\n// changed SDK\n")

    def test_android_chrono_patch_accepts_existing_extended_libcpp_variant(self):
        source = (
            "#if defined(__APPLE__) || defined(__ANDROID__) || "
            "(defined(__linux__) && defined(_LIBCPP_VERSION))\n"
            "// Apple, Android, and Linux libc++ do not expose clock_time_conversion.\n"
        )
        self.assertEqual(PATCHER.patch_android_chrono_header(source), source)

    def test_android_host_trace_patch_recognizes_result_logging_variant(self):
        source = (
            'REXFS_INFO("android io trace open path=\'{}\' result={}");\n'
            'REXFS_INFO("android io trace open_mapped path=\'{}\' offset={} bytes={} result={}");\n'
        )
        self.assertEqual(PATCHER.patch_android_host_entry(source), source)

    def test_guest_map_patch_reports_failed_view_and_success_count(self):
        patched = PATCHER.patch_android_guest_maps(GUEST_MAPS)
        self.assertIn("Guest memory map attempt failed", patched)
        self.assertIn("errno={}", patched)
        self.assertIn("views={}", patched)
        self.assertIn("rex::countof(views_.all_views)", patched)
        self.assertEqual(PATCHER.patch_android_guest_maps(patched), patched)


if __name__ == "__main__":
    unittest.main()
