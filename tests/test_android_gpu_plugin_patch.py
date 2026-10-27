import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "patch_android_rexglue", ROOT / "scripts" / "patch_android_rexglue.py"
)
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)


LOADER_SOURCE = r'''#include <rex/system/gpu_plugin.h>
#include <filesystem>
#include <string>
#include <vector>

namespace rex::system {
namespace {
std::string PluginFileName(std::string_view name) { return "librexgpu-" + std::string(name) + ".so"; }
std::vector<platform::DynamicLibrary>& LoadedPlugins() {
  static std::vector<platform::DynamicLibrary> plugins;
  return plugins;
}
}
std::unique_ptr<IGraphicsSystem> LoadGpuPlugin(std::string_view name, std::string_view backend) {
  auto path = rex::filesystem::GetExecutableFolder() / PluginFileName(name);
  if (!std::filesystem::exists(path)) {
    REXSYS_ERROR(
        "GPU plugin '{}' not found at {}. Stage it next to the executable "
        "(GPU_PLUGINS {} in rexglue_configure_target).",
        name, path.string(), name);
    return nullptr;
  }

  platform::DynamicLibrary library;
  if (!library.Load(path, platform::SymbolResolution::kImmediate)) {
    REXSYS_ERROR("GPU plugin '{}' failed to load: {}", name, path.string());
    return nullptr;
  }
  return nullptr;
}
}
'''


class AndroidGpuPluginPatchTest(unittest.TestCase):
    def test_android_uses_bundled_soname_not_proc_exe_folder(self):
        patched = PATCHER.patch_android_gpu_plugin_loader(LOADER_SOURCE)
        self.assertIn("#if REX_PLATFORM_ANDROID", patched)
        self.assertIn("path = filename;", patched)
        self.assertIn("library.Load(path, platform::SymbolResolution::kImmediate)", patched)
        self.assertIn("MCLA_ANDROID_GPU_PLUGIN_LOADER_PATCH", patched)
        self.assertIn("GetExecutableFolder() / filename", patched)

    def test_patch_is_idempotent(self):
        patched = PATCHER.patch_android_gpu_plugin_loader(LOADER_SOURCE)
        self.assertEqual(patched, PATCHER.patch_android_gpu_plugin_loader(patched))


if __name__ == "__main__":
    unittest.main()
