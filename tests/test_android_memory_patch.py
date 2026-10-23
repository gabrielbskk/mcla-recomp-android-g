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


if __name__ == "__main__":
    unittest.main()
